"""Database rules for Resume Tailor: isolation, append-only decisions, deletion and task kinds."""
import os,subprocess,sys,uuid
import pytest
from sqlalchemy.exc import DBAPIError
from sandhata import repository as r
from sandhata.config import ROOT
from sandhata.db import transaction,one,rows,scoped
from sandhata.worker import run_once

def make_run(p,docx_bytes,job_text):
    r.create_manual_application(p,'Lead AI Engineer','Synthetic Co',description=job_text)
    resume=r.upload_resume(p,docx_bytes,'synthetic.docx','Base')
    with transaction(p) as c:
        version=str(one(c,'SELECT id FROM job_versions')['id'])
        run=str(one(c,"INSERT INTO tailor_runs(tenant_id,owner_user_id,resume_id,job_version_id,track,level,provider,model,prompt_version,policy_version,lens_version,source_hash,cache_key) VALUES(%(t)s::uuid,%(u)s::uuid,%(r)s::uuid,%(j)s::uuid,'fde','lead','ollama','m','p','v','l','h','k') RETURNING id",scoped(p,r=resume,j=version))['id'])
        suggestion=str(one(c,"INSERT INTO tailor_suggestions(tenant_id,owner_user_id,run_id,unit_id,start_offset,end_offset,change_type,before_text,evidence,job_quote,job_offset) VALUES(%(t)s::uuid,%(u)s::uuid,%(run)s::uuid,'r1.b1',0,5,'deemphasize','Built','[{\"quote\":\"Built\"}]','Python',0) RETURNING id",scoped(p,run=run))['id'])
    return resume,version,run,suggestion

def decide(p,suggestion,decision='approve',final=None,attested=False):
    with transaction(p) as c:
        c.exec_driver_sql('INSERT INTO suggestion_decisions(tenant_id,owner_user_id,suggestion_id,decision,final_text,user_attested,request_id) VALUES(%(t)s::uuid,%(u)s::uuid,%(s)s::uuid,%(d)s,%(f)s,%(a)s,%(rid)s)',scoped(p,s=suggestion,d=decision,f=final,a=attested,rid=str(uuid.uuid4())))

def count(p,table):
    with transaction(p) as c: return one(c,f'SELECT count(*) n FROM {table}')['n']

def test_members_and_admin_cannot_see_each_others_tailoring(family,docx_bytes,job_text):
    admin,a,b=family
    *_,suggestion=make_run(a,docx_bytes,job_text);decide(a,suggestion)
    for other in (b,admin):
        for table in ('tailor_runs','tailor_suggestions','suggestion_decisions'): assert count(other,table)==0
        with pytest.raises(DBAPIError): decide(other,suggestion)
    assert count(a,'suggestion_decisions')==1

def test_forced_row_security_is_on(family):
    with transaction(family[1]) as c:
        found=rows(c,"SELECT relname FROM pg_class WHERE relname IN ('tailor_runs','tailor_suggestions','suggestion_decisions') AND relforcerowsecurity")
    assert len(found)==3

@pytest.mark.parametrize('statement',["UPDATE suggestion_decisions SET decision='approve'",'DELETE FROM suggestion_decisions'])
def test_decisions_are_append_only(family,docx_bytes,job_text,statement):
    p=family[1];*_,suggestion=make_run(p,docx_bytes,job_text);decide(p,suggestion,'reject')
    with pytest.raises(DBAPIError):
        with transaction(p) as c: c.exec_driver_sql(statement)

@pytest.mark.parametrize('decision,final,attested',[('edit_approve',None,False),('approve','changed text',False),('approve',None,True),('approve_all',None,False)])
def test_inconsistent_decisions_are_refused(family,docx_bytes,job_text,decision,final,attested):
    p=family[1];*_,suggestion=make_run(p,docx_bytes,job_text)
    with pytest.raises(DBAPIError): decide(p,suggestion,decision,final,attested)

def test_deleting_the_source_removes_runs_but_keeps_the_tailored_copy(family,docx_bytes,job_text):
    p=family[1];resume,_,run,suggestion=make_run(p,docx_bytes,job_text);decide(p,suggestion)
    tailored=r.upload_resume(p,docx_bytes,'synthetic.docx','Tailored')
    with transaction(p) as c:
        c.exec_driver_sql('UPDATE resumes SET parent_resume_id=%(s)s::uuid,tailor_run_id=%(run)s::uuid WHERE id=%(id)s::uuid',dict(s=resume,run=run,id=tailored))
    r.delete_resume(p,resume)
    for table in ('tailor_runs','tailor_suggestions','suggestion_decisions'): assert count(p,table)==0
    kept=r.resume_detail(p,tailored)
    assert kept['parent_resume_id'] is None and kept['tailor_run_id'] is None

def test_administrator_deletion_also_removes_runs(family,docx_bytes,job_text):
    admin,member,_=family;resume,*_=make_run(member,docx_bytes,job_text)
    r.admin_document(admin,resume,'delete','Synthetic cleanup reason')
    assert count(member,'tailor_runs')==0

def test_tailor_task_without_a_run_fails_without_calling_a_model(family,docx_bytes,job_text):
    p=family[1];resume,version,*_=make_run(p,docx_bytes,job_text)
    with transaction(p) as c:
        c.exec_driver_sql("INSERT INTO tasks(tenant_id,owner_user_id,auth_version,kind,payload,request_id) VALUES(%(t)s::uuid,%(u)s::uuid,%(v)s,'tailor','{}',%(rid)s)",scoped(p,v=p.auth_version,rid=str(uuid.uuid4())))
    def never(*args): raise AssertionError('the model must not run')
    assert run_once(never)
    with transaction(p) as c: task=one(c,'SELECT state FROM tasks')
    assert task['state']=='failed' and count(p,'assessments')==0

def test_migration_can_run_again():
    for _ in range(2):
        done=subprocess.run([sys.executable,str(ROOT/'scripts/migrate.py'),'--schema-only'],cwd=ROOT,env=os.environ.copy(),capture_output=True,text=True)
        assert done.returncode==0,done.stderr
