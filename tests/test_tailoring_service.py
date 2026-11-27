"""End to end with fake models and a real disposable database: run, decide one at a time, compose."""
from io import BytesIO
import os,uuid
import psycopg,pytest
from docx import Document
from sqlalchemy.exc import DBAPIError
from sandhata import repository as r
from sandhata import tailoring as t
from sandhata.config import AppError,DATA
from sandhata.db import transaction,one,rows
from sandhata.parsing import parse_resume
from sandhata.worker import run_once,enqueue_batch
from tailor_fixtures import RESUME,JOB
from tailor_fakes import Writer,Checker,analyzer,proposal,B2,B4,GOOD_B2,GOOD_B4,REQUIRED

def resume_docx():
    document=Document()
    for line in RESUME.strip().split('\n'): document.add_paragraph(line)
    out=BytesIO();document.save(out);return out.getvalue()

def setup(p,complete=True):
    r.import_job(p,'Lead AI Forward Deployed Engineer','Synthetic Co',JOB,complete=complete)
    resume=r.upload_resume(p,resume_docx(),'synthetic.docx','Base')
    return resume,str(r.list_jobs(p)[0]['version_id'])

def reviewed(p,writer=None,checker=None):
    resume,version=setup(p)
    run=t.start_run(p,resume,version)
    assert run_once(analyzer,writer or Writer(),checker or Checker())
    found=t.get_run(p,run)
    return resume,version,found,{s['unit_id']:str(s['id']) for s in found['suggestions']}

def admin_sql(statement,params):
    with psycopg.connect(os.environ['SANDHATA_MIGRATION_URL']) as c: c.execute(statement,params)

def files(p): return sorted((DATA/p.tenant_id/p.user_id).glob('*'))

def test_run_reaches_review_with_a_trace_and_a_shared_assessment(family):
    p=family[1];resume,version,found,suggestions=reviewed(p)
    assert found['state']=='ready_for_review' and (found['track'],found['level'])==('fde','lead')
    assert set(suggestions)=={'r1.b4','r1.b2','k2'}
    names=[x['component'] for x in found['trace']]
    assert 'fit_analyst' in names and 'verifier' in names and found['assessment_id']
    assert any(g['kind']=='skill' for g in found['gaps'])
    assert all(s['decision'] is None for s in found['suggestions'])
    assert str(r.assessment_detail(p,found['assessment_id'])['id'])==str(found['assessment_id'])

def test_same_inputs_reuse_the_run_without_another_model_call(family):
    p=family[1];resume,version,found,_=reviewed(p)
    assert t.start_run(p,resume,version)==str(found['id'])
    assert not run_once(analyzer,Writer(),Checker())
    assert t.start_run(p,resume,version,level='senior')!=str(found['id'])

def test_comparison_screens_ignore_tailoring_tasks(family):
    p=family[1];resume,version=setup(p)
    t.start_run(p,resume,version)
    assert r.tasks(p)==[]
    assert enqueue_batch(p,r.list_jobs(p),resume)['queued']==1

def test_partial_job_descriptions_are_refused(family):
    p=family[1];resume,version=setup(p,complete=False)
    with pytest.raises(AppError,match='full job description'): t.start_run(p,resume,version)

def test_unknown_track_and_foreign_documents_are_refused(family):
    resume,version=setup(family[1])
    with pytest.raises(AppError,match='track'): t.start_run(family[1],resume,version,track='sales')
    with pytest.raises(AppError,match='not available'): t.start_run(family[2],resume,version)

def test_quota_applies_to_tailoring(family):
    p=family[1];resume,version=setup(p)
    admin_sql('UPDATE memberships SET quota=1 WHERE user_id=%s',(p.user_id,))
    t.start_run(p,resume,version)
    with pytest.raises(AppError,match='quota'): t.start_run(p,resume,version,level='senior')

def test_model_failure_fails_the_run_and_a_retry_replaces_it(family):
    p=family[1];resume,version=setup(p)
    run=t.start_run(p,resume,version)
    run_once(analyzer,Writer(RuntimeError('outage')),Checker())
    found=t.get_run(p,run)
    assert found['state']=='failed' and found['error_code']=='tailoring_failed_validation_or_provider' and found['trace']
    again=t.start_run(p,resume,version)
    assert again!=run
    run_once(analyzer,Writer(),Checker())
    assert t.get_run(p,again)['state']=='ready_for_review'

def test_planning_continues_when_the_fit_analyst_fails(family):
    p=family[1];resume,version=setup(p)
    run=t.start_run(p,resume,version)
    run_once(lambda *a: ({},{}),Writer(),Checker())
    found=t.get_run(p,run)
    assert found['state']=='ready_for_review' and found['assessment_id'] is None and found['suggestions']

def test_cancel_before_and_during_a_run(family):
    p=family[1];resume,version=setup(p)
    run=t.start_run(p,resume,version);t.cancel_run(p,run)
    assert t.get_run(p,run)['state']=='failed' and not run_once(analyzer,Writer(),Checker())
    second=t.start_run(p,resume,version)
    def cancel_mid_draft():
        t.cancel_run(p,second);return [proposal('r1.b2',GOOD_B2)]
    checker=Checker();run_once(analyzer,Writer(cancel_mid_draft),checker)
    assert not checker.requests and t.get_run(p,second)['suggestions']==[] and t.get_run(p,second)['state']=='failed'

def test_suggestions_cannot_be_edited_by_the_application(family):
    p=family[1];reviewed(p)
    with pytest.raises(DBAPIError):
        with transaction(p) as c: c.exec_driver_sql("UPDATE tailor_suggestions SET after_text='changed'")

def test_decisions_are_one_at_a_time_and_latest_wins(family):
    p=family[1];_,_,found,s=reviewed(p);run=str(found['id'])
    with pytest.raises(AppError,match='one proposal at a time'): t.decide(p,run,list(s.values()),'approve')
    with pytest.raises(AppError): t.decide(p,run,s['r1.b2'],'approve_all')
    with pytest.raises(AppError): t.decide(p,run,s['r1.b2'],'approve',final_text='x')
    t.decide(p,run,s['r1.b2'],'approve');t.decide(p,run,s['r1.b2'],'reject')
    states={x['unit_id']:x['decision'] for x in t.get_run(p,run)['suggestions']}
    assert states=={'r1.b2':'reject','r1.b4':None,'k2':None}
    assert not [name for name in dir(t) if 'all' in name.lower() and 'decide' in name.lower()]

def test_repeated_request_is_recorded_once(family):
    p=family[1];_,_,found,s=reviewed(p);run=str(found['id']);key=str(uuid.uuid4())
    for _ in range(2): t.decide(p,run,s['r1.b2'],'approve',request_id=key)
    with transaction(p) as c: assert one(c,'SELECT count(*) n FROM suggestion_decisions')['n']==1
    with pytest.raises(AppError,match='already used'): t.decide(p,run,s['r1.b4'],'approve',request_id=key)

def test_own_edit_with_new_claims_needs_attestation(family):
    p=family[1];_,_,found,s=reviewed(p);run=str(found['id'])
    text=B2+' and trained 12 new staff'
    with pytest.raises(t.AttestationRequired) as refused: t.decide(p,run,s['r1.b2'],'edit_approve',final_text=text)
    assert '12' in refused.value.details
    assert t.decide(p,run,s['r1.b2'],'edit_approve',final_text=text,attest=True)['user_attested']
    harmless=t.decide(p,run,s['r1.b4'],'edit_approve',final_text=GOOD_B4,attest=True)
    assert harmless['user_attested'] is False

@pytest.mark.parametrize('text',['','**Bold** claim','Reach me at sam@example.com about this work item',B2,'x'*500,'Two\nlines of text'])
def test_unusable_edits_are_refused_even_with_attestation(family,text):
    p=family[1];_,_,found,s=reviewed(p)
    with pytest.raises(AppError) as refused: t.decide(p,str(found['id']),s['r1.b2'],'edit_approve',final_text=text,attest=True)
    assert not isinstance(refused.value,t.AttestationRequired)

def test_compose_needs_an_approval(family):
    p=family[1];_,_,found,s=reviewed(p);run=str(found['id'])
    with pytest.raises(AppError,match='Approve at least one'): t.compose(p,run)
    t.decide(p,run,s['r1.b2'],'reject')
    with pytest.raises(AppError,match='Approve at least one'): t.compose(p,run)

def test_compose_applies_only_approved_changes_to_a_new_version(family):
    p=family[1];resume,_,found,s=reviewed(p);run=str(found['id'])
    source=r.resume_detail(p,resume)
    t.decide(p,run,s['r1.b2'],'approve');t.decide(p,run,s['r1.b4'],'reject');t.decide(p,run,s['k2'],'approve')
    new=t.compose(p,run)
    made=r.resume_detail(p,new)
    expected=source['body'].replace(B2,GOOD_B2).replace('Tools: LangChain, pgvector, Spark, Kubernetes','Tools: LangChain, Kubernetes, pgvector, Spark')
    assert made['body']==expected
    assert str(made['parent_resume_id'])==resume and str(made['tailor_run_id'])==run
    assert 'Lead AI Forward Deployed Engineer' in made['label'] and len(made['label'])<=100
    data,suffix=r.resume_download(p,new)
    assert suffix=='.docx' and GOOD_B2 in parse_resume(data,'tailored.docx')['body']
    unchanged=r.resume_detail(p,resume)
    assert (unchanged['body'],unchanged['file_hash'])==(source['body'],source['file_hash'])
    assert t.compose(p,run)==new and t.get_run(p,run)['state']=='composed'
    with pytest.raises(AppError,match='not open'): t.decide(p,run,s['r1.b4'],'approve')
    assert r.retrieve(p,'claims users',parent_id=new)

def test_attested_edit_composes(family):
    p=family[1];_,_,found,s=reviewed(p);run=str(found['id']);text=B2+' and trained 12 new staff'
    t.decide(p,run,s['r1.b2'],'edit_approve',final_text=text,attest=True)
    assert text in r.resume_detail(p,t.compose(p,run))['body']

@pytest.mark.parametrize('statement',[
    "UPDATE tailor_suggestions SET after_text=after_text||' with Terraform' WHERE id=%s",
    "UPDATE tailor_suggestions SET start_offset=start_offset+1 WHERE id=%s",
    "UPDATE tailor_suggestions SET before_text='Something else entirely' WHERE id=%s",
    "UPDATE tailor_suggestions SET evidence='[{\"quote\":\"Invented evidence\"}]' WHERE id=%s",
])
def test_tampered_proposals_write_nothing(family,statement):
    p=family[1];_,_,found,s=reviewed(p);run=str(found['id'])
    t.decide(p,run,s['r1.b2'],'approve')
    admin_sql(statement,(s['r1.b2'],))
    before=files(p)
    with pytest.raises(AppError): t.compose(p,run)
    assert files(p)==before and len(r.list_documents(p))==1 and t.get_run(p,run)['state']=='ready_for_review'

def test_changed_source_is_refused(family):
    p=family[1];resume,_,found,s=reviewed(p);run=str(found['id'])
    t.decide(p,run,s['r1.b2'],'approve')
    admin_sql("UPDATE resumes SET file_hash='changed' WHERE id=%s",(resume,))
    with pytest.raises(AppError,match='changed after this run'): t.compose(p,run)

def test_database_failure_removes_the_new_file(family,monkeypatch):
    p=family[1];_,_,found,s=reviewed(p);run=str(found['id'])
    t.decide(p,run,s['r1.b2'],'approve')
    def broken(*args): raise RuntimeError('synthetic index failure')
    monkeypatch.setattr(r,'index_text',broken);before=files(p)
    with pytest.raises(RuntimeError): t.compose(p,run)
    assert files(p)==before and len(r.list_documents(p))==1

def test_expired_runs_cannot_be_decided_or_composed(family):
    p=family[1];_,_,found,s=reviewed(p);run=str(found['id'])
    admin_sql("UPDATE tailor_runs SET expires_at=now()-interval '1 day' WHERE id=%s",(run,))
    with pytest.raises(AppError,match='not open'): t.decide(p,run,s['r1.b2'],'approve')
    assert t.get_run(p,run)['state']=='expired'
    with pytest.raises(AppError,match='not ready'): t.compose(p,run)

def test_other_members_and_admin_cannot_use_the_run(family):
    admin,p,other=family;_,_,found,s=reviewed(p);run=str(found['id'])
    for stranger in (other,admin):
        assert t.list_runs(stranger)==[]
        for action in (lambda: t.get_run(stranger,run),lambda: t.decide(stranger,run,s['r1.b2'],'approve'),lambda: t.compose(stranger,run)):
            with pytest.raises(AppError): action()
    assert len(t.list_runs(p))==1

def test_summary_row_shows_in_the_run_list(family):
    p=family[1];reviewed(p)
    item=t.list_runs(p)[0]
    assert item['suggestions']==3 and item['company']=='Synthetic Co' and item['resume_label']=='Base'
