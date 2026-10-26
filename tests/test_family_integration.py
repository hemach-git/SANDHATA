import uuid,os
from datetime import datetime,timezone,timedelta,date
import pytest,psycopg
from starlette.testclient import TestClient
from sandhata import repository as r,identity as a
from sandhata.db import engine,transaction,rows,one,scoped,Principal
from sandhata.config import AppError
from sandhata.worker import enqueue,run_once
from sandhata.private_api import app

def test_missing_scope_denies_private_rows(family,job_text):
    _,member,_=family;r.import_job(member,'Engineer','Fixture',job_text)
    with engine().begin() as c: assert rows(c,'SELECT * FROM jobs')==[]

def test_two_members_have_private_jobs_and_admin_no_bypass(family,job_text):
    admin,member,other=family;jid=r.import_job(member,'Engineer','Private A',job_text)
    assert len(r.list_jobs(member))==1
    assert not r.list_jobs(other) and not r.list_jobs(admin)
    for p in [other,admin]:
        with pytest.raises(AppError): r.job_detail(p,jid)

def test_duplicate_import_and_immutable_versions(family,job_text):
    p=family[1]
    jid=r.import_job(p,'Engineer','Fixture',job_text)
    assert r.import_job(p,'Engineer','Fixture',job_text)==jid
    r.import_job(p,'Engineer','Fixture',job_text+' New requirement: Docker.')
    with transaction(p) as c: assert one(c,'SELECT count(*) n FROM job_versions')['n']==2

def test_resume_private_download_and_deletion(family,docx_bytes):
    _,member,other=family;rid=r.upload_resume(member,docx_bytes,'resume.docx','Engineer')
    assert r.resume_download(member,rid)[0]==docx_bytes
    with pytest.raises(AppError):r.resume_download(other,rid)
    r.delete_resume(member,rid)
    with pytest.raises(AppError):r.resume_detail(member,rid)
    assert not r.retrieve(member,'Python')

def test_tracker_idempotency_history_and_isolation(family,job_text):
    _,member,other=family;jid=r.import_job(member,'Engineer','Fixture',job_text);aid=r.save_to_tracker(member,jid)
    now=datetime.now(timezone.utc)-timedelta(days=2)
    for _ in range(2):r.update_application(member,aid,'Applied','private note',now,'same-request')
    assert len(r.application_history(member,aid))==1
    with pytest.raises(AppError):r.update_application(other,aid,'Hired','tamper',now,'cross-user')
    assert not r.list_applications(other)

def test_member_cannot_invoke_admin(family):
    with pytest.raises(AppError): a.list_accounts(family[1])
    with pytest.raises(AppError): a.invite(family[1],'someone@fixture.local')

def test_last_admin_protected(family):
    admin=family[0]
    with pytest.raises(AppError):a.change_account(admin,admin.user_id,'member','active',100,'Test last administrator')

def test_suspend_revokes_existing_principal_and_capability(family):
    admin,member,_=family;token=a.issue_capability(member)
    assert a.capability_principal(token).user_id==member.user_id
    a.change_account(admin,member.user_id,'member','suspended',50,'Fixture suspension')
    with pytest.raises(AppError):r.list_jobs(member)
    with pytest.raises(AppError):a.capability_principal(token)

def test_citations_and_retrieval_never_cross_owner(family,docx_bytes):
    admin,member,other=family;r.upload_resume(member,docx_bytes,'r.docx','Private A')
    assert r.retrieve(member,'Python')
    assert r.retrieve(other,'Python')==[] and r.retrieve(admin,'Python')==[]

def test_real_postgres_role_cannot_bypass_rls(family):
    with engine().begin() as c:
        role=one(c,'SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')
        assert not role['rolsuper'] and not role['rolbypassrls']
        tables=rows(c,"SELECT relname,relforcerowsecurity FROM pg_class WHERE relname IN ('jobs','resumes','assessments','passages')")
        assert len(tables)==4 and all(t['relforcerowsecurity'] for t in tables)

def test_cross_owner_foreign_keys_rejected(family,job_text):
    _,member,other=family;jid=r.import_job(member,'Engineer','Fixture',job_text)
    with pytest.raises(Exception):
        with transaction(other) as c:c.exec_driver_sql('INSERT INTO applications(tenant_id,owner_user_id,job_id) VALUES(%(t)s::uuid,%(u)s::uuid,%(job)s::uuid)',scoped(other,job=jid))

def test_private_api_requires_bearer_and_rechecks_owner(family,docx_bytes):
    _,member,other=family;rid=r.upload_resume(member,docx_bytes,'r.docx','A')
    client=TestClient(app)
    assert client.get('/download/resume/'+rid).status_code==401
    assert client.get('/download/resume/'+rid,headers={'Authorization':'Bearer '+a.issue_capability(other)}).status_code==403
    response=client.get('/download/resume/'+rid,headers={'Authorization':'Bearer '+a.issue_capability(member)})
    assert response.status_code==200 and response.content==docx_bytes and response.headers['cache-control']=='no-store'

def test_metrics_use_applied_cohort(family,job_text):
    member=family[1];now=datetime.now(timezone.utc)-timedelta(days=1)
    for i in range(10):
        jid=r.import_job(member,'Engineer '+str(i),'Fixture',job_text)
        aid=r.save_to_tracker(member,jid);r.update_application(member,aid,'Applied','',now,str(uuid.uuid4()))
        if i<3:r.update_application(member,aid,'Interviewing','',now,str(uuid.uuid4()))
        if i==0:r.update_application(member,aid,'Offer','',now,str(uuid.uuid4()))
    m=r.tracker_metrics(member,date.today()-timedelta(days=7),date.today())
    assert len(m['cohort'])==10 and sum(x['interview'] for x in m['cohort'])==3 and sum(x['offer'] for x in m['cohort'])==1

def test_admin_metrics_do_not_include_career_text(family,docx_bytes):
    admin,member,_=family;r.upload_resume(member,docx_bytes,'r.docx','Secret career details')
    metrics=a.admin_metrics(admin)
    assert metrics['members']==3 and 'Secret career details' not in str(metrics) and 'Python' not in str(metrics)

def test_housekeeping_allowlist_and_dry_run(family):
    admin=family[0]
    preview=a.maintenance(admin,'expired_invitations')
    assert preview['count']==0
    done=a.maintenance(admin,'expired_invitations',preview=False,count=0,request_id='same',reason='Fixture cleanup')
    assert a.maintenance(admin,'expired_invitations',preview=False,count=0,request_id='same',reason='Fixture retry')==done
    with pytest.raises(Exception):a.maintenance(admin,'arbitrary_sql')

def test_queue_and_bounded_graph_write_assessment(family,docx_bytes,job_text):
    member=family[1];jid=r.import_job(member,'Engineer','Fixture',job_text)
    job=r.job_detail(member,jid);rid=r.upload_resume(member,docx_bytes,'r.docx','Engineering')
    task=enqueue(member,job['version_id'],rid,'queued-once')
    assert enqueue(member,job['version_id'],rid,'queued-once')==task
    def fixture_model(job,resume,repair):return {'requirements':[dict(category='required_skills',requirement_quote='Python',resume_quote='Built Python data pipelines and SQL analytics on AWS.',status='supported',rationale='Direct evidence')],'eligibility_flags':[]},{}
    assert run_once(fixture_model)
    completed=next(t for t in r.tasks(member) if str(t['id'])==task)
    assert completed['state']=='completed' and r.assessment_detail(member,completed['result_id'])['result']['score']==100

def test_concurrent_sessions_keep_their_scope(family,job_text):
    from concurrent.futures import ThreadPoolExecutor
    _,member,other=family
    r.import_job(member,'Engineer A','Private A',job_text);r.import_job(other,'Engineer B','Private B',job_text)
    def read(p):return {j['company'] for j in r.list_jobs(p)}
    with ThreadPoolExecutor(max_workers=5) as pool: results=list(pool.map(read,[member,other,member,other,member]))
    assert results==[{'Private A'},{'Private B'},{'Private A'},{'Private B'},{'Private A'}]
