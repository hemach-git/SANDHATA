"""Durable private comparison worker. Log metadata only, never document/model contents."""
import json,time,uuid
from datetime import datetime,timezone
from .db import engine,transaction,one,rows,scoped,Principal
from .matching import build_graph,assessment_key
from .config import AppError,DATA

def enqueue(p,job_version_id,resume_id,request_id=None):
    with transaction(p) as c:
        c.exec_driver_sql('SELECT pg_advisory_xact_lock(hashtextextended(%(k)s,0))',dict(k=p.user_id+'quota'))
        job=one(c,'SELECT id FROM job_versions WHERE id=%(id)s::uuid',dict(id=str(job_version_id)))
        resume=one(c,'SELECT id FROM resumes WHERE id=%(id)s::uuid',dict(id=str(resume_id)))
        if not job or not resume: raise AppError('Selected documents are not available in your workspace.')
        quota=one(c,'SELECT quota FROM memberships WHERE user_id=%(u)s::uuid',dict(u=p.user_id))['quota']
        count=one(c,"SELECT count(*) n FROM tasks WHERE created_at>=date_trunc('day',now())")['n']
        if count>=quota: raise AppError('Your daily comparison quota is reached.')
        result=one(c,"INSERT INTO tasks(tenant_id,owner_user_id,auth_version,kind,payload,request_id) VALUES(%(t)s::uuid,%(u)s::uuid,%(v)s,'compare',%(payload)s::jsonb,%(rid)s) ON CONFLICT(tenant_id,owner_user_id,request_id) DO UPDATE SET request_id=EXCLUDED.request_id RETURNING id",scoped(p,v=p.auth_version,payload=json.dumps(dict(job_version_id=str(job_version_id),resume_id=str(resume_id))),rid=request_id or str(uuid.uuid4())))
        return str(result['id'])

def log_event(event,**fields):
    DATA.mkdir(parents=True,exist_ok=True)
    with (DATA/'operations.jsonl').open('a',encoding='utf-8') as f:
        f.write(json.dumps(dict(timestamp=datetime.now(timezone.utc).isoformat(),event=event,**fields))+'\n')

def cancel_task(p,task_id):
    with transaction(p) as c:
        c.exec_driver_sql("UPDATE tasks SET state='cancelled',finished_at=now(),lease_until=NULL WHERE id=%(id)s::uuid AND state IN ('queued','running')",dict(id=str(task_id)))

def run_once(analyzer=None):
    with engine(True).begin() as c: task=one(c,'SELECT * FROM appsec.claim_task()')
    if not task: return False
    p=Principal(str(task['owner_user_id']),str(task['tenant_id']),'member',task['auth_version'])
    started=time.monotonic();trace=[]
    def authority_check():
        with transaction(p,worker=True) as c:
            row=one(c,'SELECT state FROM tasks WHERE id=%(id)s::uuid',dict(id=str(task['id'])))
            if not row or row['state']!='running': raise AppError('Task cancelled or unavailable.')
    try:
        with transaction(p,worker=True) as c:
            job=one(c,'SELECT * FROM job_versions WHERE id=%(id)s::uuid',dict(id=task['payload']['job_version_id']))
            resume=one(c,'SELECT * FROM resumes WHERE id=%(id)s::uuid',dict(id=task['payload']['resume_id']))
            if not job or not resume: raise AppError('selected_document_unavailable')
            key=assessment_key(job['content_hash'],resume['file_hash'])
            cached=one(c,'SELECT id FROM assessments WHERE cache_key=%(key)s',dict(key=key))
        if cached: result_id=str(cached['id']);trace=[dict(component='cache',outcome='hit')]
        else:
            # Recheck current authority immediately before expensive inference.
            with transaction(p,worker=True): pass
            graph=build_graph(analyzer,authority_check) if analyzer else build_graph(authority_check=authority_check)
            state=graph.invoke(dict(job=job['body'],resume=resume['body'],completeness=job['completeness'],trace=[]))
            trace=state['trace']+[dict(component='evidence_validator',outcome='passed'),dict(component='deterministic_scoring',outcome='completed')]
            with transaction(p,worker=True) as c:
                current=one(c,"SELECT state FROM tasks WHERE id=%(id)s::uuid FOR UPDATE",dict(id=str(task['id'])))
                if not current or current['state']!='running': raise AppError('Task cancelled or unavailable.')
                r=one(c,'INSERT INTO assessments(tenant_id,owner_user_id,resume_id,job_version_id,cache_key,result) VALUES(%(t)s::uuid,%(u)s::uuid,%(resume)s::uuid,%(job)s::uuid,%(key)s,%(result)s::jsonb) ON CONFLICT(tenant_id,owner_user_id,cache_key) DO UPDATE SET cache_key=EXCLUDED.cache_key RETURNING id',scoped(p,resume=str(resume['id']),job=str(job['id']),key=key,result=json.dumps(state['result'])))
                result_id=str(r['id'])
        with transaction(p,worker=True) as c:
            c.exec_driver_sql("UPDATE tasks SET state='completed',result_id=%(result)s::uuid,trace=%(trace)s::jsonb,finished_at=now(),lease_until=NULL WHERE id=%(id)s::uuid AND state='running'",dict(result=result_id,trace=json.dumps(trace),id=str(task['id'])))
        log_event('comparison_completed',task_id=str(task['id']),user_id=p.user_id,duration_ms=round((time.monotonic()-started)*1000))
    except Exception as exc:
        error='access_or_document_unavailable' if isinstance(exc,AppError) and ('access' in str(exc) or 'unavailable' in str(exc)) else 'comparison_failed_validation_or_provider'
        try:
            with transaction(p,worker=True) as c:
                c.exec_driver_sql("UPDATE tasks SET state='failed',error_code=%(e)s,trace=%(trace)s::jsonb,finished_at=now(),lease_until=NULL WHERE id=%(id)s::uuid AND state='running'",dict(e=error,trace=json.dumps(trace),id=str(task['id'])))
        except Exception: pass # Revoked principals cannot mutate their task; audited admin cleanup handles it.
        log_event('comparison_failed',task_id=str(task['id']),user_id=p.user_id,error_code=error)
    return True

def main():
    DATA.mkdir(parents=True,exist_ok=True)
    while True:
        (DATA/'worker_heartbeat').write_text(datetime.now(timezone.utc).isoformat(),encoding='utf-8')
        try:
            if not run_once(): time.sleep(2)
        except Exception:
            log_event('worker_dependency_unavailable');time.sleep(5)

if __name__=='__main__': main()
