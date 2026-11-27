"""Durable private worker for comparisons and tailoring. Log metadata only, never document/model contents."""
import json,time,uuid
from datetime import datetime,timezone
from .db import engine,transaction,one,rows,scoped,Principal
from .matching import build_graph,assessment_key
from .providers import get_provider
from .agents.tailor import tailor
from .config import AppError,DATA

def enqueue(p,job_version_id,resume_id,request_id=None):
    with transaction(p) as c:
        c.exec_driver_sql('SELECT pg_advisory_xact_lock(hashtextextended(%(k)s,0))',dict(k=p.user_id+'quota'))
        job=one(c,'SELECT id FROM job_versions WHERE id=%(id)s::uuid',dict(id=str(job_version_id)))
        resume=one(c,"SELECT id FROM resumes WHERE id=%(id)s::uuid AND doc_type='resume' AND active",dict(id=str(resume_id)))
        if not job or not resume: raise AppError('Selected documents are not available in your workspace.')
        quota=one(c,'SELECT quota FROM memberships WHERE user_id=%(u)s::uuid',dict(u=p.user_id))['quota']
        count=one(c,"SELECT count(*) n FROM tasks WHERE created_at>=date_trunc('day',now())")['n']
        if count>=quota: raise AppError('Your daily comparison quota is reached.')
        result=one(c,"INSERT INTO tasks(tenant_id,owner_user_id,auth_version,kind,payload,request_id) VALUES(%(t)s::uuid,%(u)s::uuid,%(v)s,'compare',%(payload)s::jsonb,%(rid)s) ON CONFLICT(tenant_id,owner_user_id,request_id) DO UPDATE SET request_id=EXCLUDED.request_id RETURNING id",scoped(p,v=p.auth_version,payload=json.dumps(dict(job_version_id=str(job_version_id),resume_id=str(resume_id))),rid=request_id or str(uuid.uuid4())))
        return str(result['id'])

def enqueue_batch(p,jobs,resume_id,limit=10):
    """Queue unscored full descriptions in the given order, skipping work already done or pending."""
    with transaction(p) as c:
        found=rows(c,"SELECT job_version_id::text v FROM assessments WHERE resume_id=%(r)s::uuid UNION SELECT payload->>'job_version_id' FROM tasks WHERE kind='compare' AND state IN ('queued','running') AND payload->>'resume_id'=%(text)s",dict(r=str(resume_id),text=str(resume_id)))
    done={x['v'] for x in found}
    queued=0;stopped=''
    for job in jobs:
        if queued>=limit: break
        if str(job['version_id']) in done or job['completeness']!='full': continue
        try: enqueue(p,job['version_id'],resume_id)
        except AppError as exc:
            stopped=str(exc);break
        queued+=1
    return dict(queued=queued,stopped=stopped)

def log_event(event,**fields):
    DATA.mkdir(parents=True,exist_ok=True)
    with (DATA/'operations.jsonl').open('a',encoding='utf-8') as f:
        f.write(json.dumps(dict(timestamp=datetime.now(timezone.utc).isoformat(),event=event,**fields))+'\n')

def cancel_task(p,task_id):
    with transaction(p) as c:
        c.exec_driver_sql("UPDATE tasks SET state='cancelled',finished_at=now(),lease_until=NULL WHERE id=%(id)s::uuid AND state IN ('queued','running')",dict(id=str(task_id)))

TAILOR_TIMEOUT=420  # seconds per local model call; the lease is renewed before each call

def _tailor(p,task,trace,analyzer,writer,verifier):
    """Run one tailoring task and store its proposals. Returns the run ID."""
    run_id=task['payload'].get('run_id');task_id=str(task['id'])
    def authority_check():
        # Entering the transaction rechecks membership; the update renews the lease for the next step.
        with transaction(p,worker=True) as c:
            if not one(c,"UPDATE tasks SET lease_until=now()+interval '10 minutes' WHERE id=%(id)s::uuid AND state='running' RETURNING id",dict(id=task_id)):
                raise AppError('Task cancelled or unavailable.')
    with transaction(p,worker=True) as c:
        run=one(c,"UPDATE tailor_runs SET state='running' WHERE id=%(id)s::uuid AND state IN ('queued','running') RETURNING *",dict(id=run_id)) if run_id else None
        if not run: raise AppError('Tailoring run unavailable.')
        job=one(c,'SELECT * FROM job_versions WHERE id=%(id)s::uuid',dict(id=str(run['job_version_id'])))
        resume=one(c,'SELECT * FROM resumes WHERE id=%(id)s::uuid',dict(id=str(run['resume_id'])))
        if not job or not resume or resume['file_hash']!=run['source_hash']: raise AppError('selected_document_unavailable')
        found=one(c,'SELECT id,result FROM assessments WHERE resume_id=%(r)s::uuid AND job_version_id=%(j)s::uuid ORDER BY created_at DESC LIMIT 1',
                  dict(r=str(resume['id']),j=str(job['id'])))
    writer=writer or get_provider(run['provider'],run['model'],TAILOR_TIMEOUT)
    verifier=verifier or get_provider(run['provider'],run['verifier_model'] or run['model'],TAILOR_TIMEOUT)
    assessment=found['result'] if found else None;assessment_id=str(found['id']) if found else None;calls=0
    if not found:
        # Reuse the Fit Analyst so tailoring and fit share one evidence format. Planning continues if it fails.
        authority_check()
        try:
            state=build_graph(analyzer,authority_check,writer).invoke(dict(job=job['body'],resume=resume['body'],completeness=job['completeness'],trace=[]))
            assessment=state['result'];trace.extend(state['trace']);calls=state['attempts']
        except AppError:
            authority_check();calls=2
            trace.append(dict(component='fit_analyst',outcome='unavailable_planning_without_it'))
    else: trace.append(dict(component='fit_analyst',outcome='reused_assessment'))
    result=tailor(resume['body'],job['body'],run['track'],run['level'],writer,verifier,assessment,authority_check,trace,calls)
    with transaction(p,worker=True) as c:
        current=one(c,'SELECT state FROM tasks WHERE id=%(id)s::uuid FOR UPDATE',dict(id=task_id))
        if not current or current['state']!='running': raise AppError('Task cancelled or unavailable.')
        if assessment and not assessment_id:
            key=assessment_key(job['content_hash'],resume['file_hash'],writer.name,writer.model)
            assessment_id=str(one(c,'INSERT INTO assessments(tenant_id,owner_user_id,resume_id,job_version_id,cache_key,result) VALUES(%(t)s::uuid,%(u)s::uuid,%(r)s::uuid,%(j)s::uuid,%(key)s,%(result)s::jsonb) ON CONFLICT(tenant_id,owner_user_id,cache_key) DO UPDATE SET cache_key=EXCLUDED.cache_key RETURNING id',
                scoped(p,r=str(resume['id']),j=str(job['id']),key=key,result=json.dumps(assessment)))['id'])
        c.exec_driver_sql('DELETE FROM tailor_suggestions WHERE run_id=%(id)s::uuid',dict(id=run_id))
        for s in result['suggestions']:
            c.exec_driver_sql('INSERT INTO tailor_suggestions(tenant_id,owner_user_id,run_id,unit_id,start_offset,end_offset,change_type,before_text,after_text,new_position,evidence,job_quote,job_offset,rationale,warnings,verdict,rank) '
                'VALUES(%(t)s::uuid,%(u)s::uuid,%(run)s::uuid,%(unit_id)s,%(start)s,%(end)s,%(change_type)s,%(before)s,%(after)s,%(new_position)s,%(evidence)s::jsonb,%(job_quote)s,%(job_offset)s,%(rationale)s,%(warnings)s::jsonb,%(verdict)s::jsonb,%(rank)s)',
                scoped(p,run=run_id,**dict(s,evidence=json.dumps(s['evidence']),warnings=json.dumps(s['warnings']),verdict=json.dumps(s['verdict']))))
        c.exec_driver_sql("UPDATE tailor_runs SET state='ready_for_review',assessment_id=%(a)s::uuid,gaps=%(g)s::jsonb,dropped=%(d)s::jsonb,trace=%(trace)s::jsonb,error_code=NULL WHERE id=%(id)s::uuid",
            dict(a=assessment_id,g=json.dumps(result['gaps']),d=json.dumps(result['dropped']),trace=json.dumps(trace),id=run_id))
        c.exec_driver_sql("UPDATE tasks SET state='completed',result_id=%(result)s::uuid,trace=%(trace)s::jsonb,finished_at=now(),lease_until=NULL WHERE id=%(id)s::uuid",
            dict(result=run_id,trace=json.dumps(trace),id=task_id))
    return run_id

def run_once(analyzer=None,writer=None,verifier=None):
    with engine(True).begin() as c: task=one(c,'SELECT * FROM appsec.claim_task()')
    if not task: return False
    p=Principal(str(task['owner_user_id']),str(task['tenant_id']),'member',task['auth_version'])
    started=time.monotonic();trace=[]
    def authority_check():
        with transaction(p,worker=True) as c:
            row=one(c,'SELECT state FROM tasks WHERE id=%(id)s::uuid',dict(id=str(task['id'])))
            if not row or row['state']!='running': raise AppError('Task cancelled or unavailable.')
    tailoring=task['kind']=='tailor'
    try:
        if tailoring:
            _tailor(p,task,trace,analyzer,writer,verifier)
            log_event('tailoring_completed',task_id=str(task['id']),user_id=p.user_id,duration_ms=round((time.monotonic()-started)*1000))
            return True
        if task['kind']!='compare': raise AppError('Task kind unavailable.')
        provider=get_provider()
        with transaction(p,worker=True) as c:
            job=one(c,'SELECT * FROM job_versions WHERE id=%(id)s::uuid',dict(id=task['payload']['job_version_id']))
            resume=one(c,'SELECT * FROM resumes WHERE id=%(id)s::uuid',dict(id=task['payload']['resume_id']))
            if not job or not resume: raise AppError('selected_document_unavailable')
            key=assessment_key(job['content_hash'],resume['file_hash'],provider.name,provider.model)
            cached=one(c,'SELECT id FROM assessments WHERE cache_key=%(key)s',dict(key=key))
        if cached: result_id=str(cached['id']);trace=[dict(component='cache',outcome='hit')]
        else:
            # Recheck current authority immediately before expensive inference.
            with transaction(p,worker=True): pass
            graph=build_graph(analyzer,authority_check,provider)
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
        # A model outage is a provider failure, not a document one.
        denied=isinstance(exc,AppError) and 'local model' not in str(exc) and ('access' in str(exc) or 'unavailable' in str(exc))
        error='access_or_document_unavailable' if denied else ('tailoring' if tailoring else 'comparison')+'_failed_validation_or_provider'
        try:
            with transaction(p,worker=True) as c:
                c.exec_driver_sql("UPDATE tasks SET state='failed',error_code=%(e)s,trace=%(trace)s::jsonb,finished_at=now(),lease_until=NULL WHERE id=%(id)s::uuid AND state='running'",dict(e=error,trace=json.dumps(trace),id=str(task['id'])))
                if tailoring and task['payload'].get('run_id'):
                    c.exec_driver_sql("UPDATE tailor_runs SET state='failed',error_code=%(e)s,trace=%(trace)s::jsonb WHERE id=%(id)s::uuid AND state IN ('queued','running')",dict(e=error,trace=json.dumps(trace),id=task['payload']['run_id']))
        except Exception: pass # Revoked principals cannot mutate their task; audited admin cleanup handles it.
        log_event(('tailoring' if tailoring else 'comparison')+'_failed',task_id=str(task['id']),user_id=p.user_id,error_code=error)
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
