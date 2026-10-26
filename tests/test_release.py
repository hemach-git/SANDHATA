import os,uuid
import pytest,psycopg
from sandhata.config import AppError,ISSUER
from sandhata.db import transaction,one,engine
from sandhata import repository as r,identity as a
from sandhata.worker import enqueue,cancel_task,run_once

def test_cancelled_queue_never_calls_model(family,docx_bytes,job_text):
    p=family[1];rid=r.upload_resume(p,docx_bytes,'r.docx','Fixture');jid=r.import_job(p,'Engineer','Fixture',job_text)
    task=enqueue(p,r.job_detail(p,jid)['version_id'],rid)
    cancel_task(p,task)
    def forbidden(*args): pytest.fail('Cancelled inference must never run')
    run_once(forbidden)
    assert r.tasks(p)[0]['state']=='cancelled'

def test_pool_scope_cleared_after_rollback(family,job_text):
    p=family[1];r.import_job(p,'Engineer','Private',job_text)
    with pytest.raises(RuntimeError):
        with transaction(p): raise RuntimeError('Synthetic rollback')
    with engine().begin() as c: assert one(c,'SELECT count(*) n FROM jobs')['n']==0

def test_mcp_rechecks_capability_and_only_own_records(family,job_text,monkeypatch):
    from sandhata.mcp_server import search_my_jobs
    admin,p,other=family
    r.import_job(p,'Engineer','Private A',job_text)
    monkeypatch.setenv('SANDHATA_MCP_CAPABILITY',a.issue_capability(other))
    assert search_my_jobs()==[]
    monkeypatch.setenv('SANDHATA_MCP_CAPABILITY',a.issue_capability(p))
    assert len(search_my_jobs())==1
    a.change_account(admin,p.user_id,'member','suspended',100,'Synthetic revocation')
    with pytest.raises(AppError):search_my_jobs()

def test_invitation_wrong_verified_email_and_expiry(family):
    admin=family[0];token=a.invite(admin,'new@fixture.local')
    with pytest.raises(AppError):
        a.accept_invitation(dict(iss=ISSUER,sub=str(uuid.uuid4()),email='wrong@fixture.local',email_verified=True,name='Fixture'),token)
    with psycopg.connect(os.environ['SANDHATA_MIGRATION_URL']) as c:
        c.execute("UPDATE invitations SET expires_at=now()-interval '1 minute' WHERE tenant_id=%s",(admin.tenant_id,))
    with pytest.raises(AppError):
        a.accept_invitation(dict(iss=ISSUER,sub=str(uuid.uuid4()),email='new@fixture.local',email_verified=True,name='Fixture'),token)

def test_unverified_identity_cannot_redeem_invite(family):
    token=a.invite(family[0],'new@fixture.local')
    with pytest.raises(AppError):
        a.accept_invitation(dict(iss=ISSUER,sub=str(uuid.uuid4()),email='new@fixture.local',email_verified=False,name='Fixture'),token)

def test_hired_does_not_fabricate_offer_event(family,job_text):
    from datetime import datetime,timezone,timedelta,date
    p=family[1];jid=r.import_job(p,'Engineer','Fixture',job_text);aid=r.save_to_tracker(p,jid)
    now=datetime.now(timezone.utc)-timedelta(days=2)
    r.update_application(p,aid,'Applied','',now,'applied')
    r.update_application(p,aid,'Hired','',now,'hired')
    cohort=r.tracker_metrics(p,date(2000,1,1),date(2100,1,1))['cohort']
    assert len(cohort)==1 and not cohort[0]['offer']
