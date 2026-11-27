"""Resume Tailor service: start a run, record one decision at a time, compose a new version. No model calls.

Every function runs under the caller's server-resolved Principal and row-level security.
"""
import hashlib,json,uuid
from datetime import date

from . import repository as repo
from .agents.tailor import PROMPT_VERSION,REWRITES
from .agents.verifier import PROMPT_VERSION as VERIFIER_PROMPT_VERSION
from .composer import Change,compose_text,verify,build_docx,keeps_shape
from .config import MODEL,VERIFIER_MODEL,AppError
from .db import transaction,one,rows,scoped
from .planner import LENS_VERSION,TRACKS,LEVELS,default_track_level,lens
from .providers import DEFAULT_PROVIDER
from .segmenter import segment,contains_contact
from .tailor_validation import POLICY,POLICY_VERSION,PLAIN,validate,check_text

EDITABLE_TYPES=('rephrase','summary','skills_reorder')
DECISIONS=('approve','reject','edit_approve')
PARSER_VERSION='tailor-compose-v1'

class AttestationRequired(AppError):
    """The member's own edit says something the resume does not. They must confirm it is true."""
    def __init__(self,reason,details):
        self.reason=reason; self.details=tuple(details)
        super().__init__('Your edit adds claims the resume does not show: '+', '.join(self.details)
                         +'. Confirm that this is true and that you are adding it yourself, or change the text.')

def _refresh(c):
    """Close runs whose task ended without a result, and expire old unreviewed runs."""
    c.exec_driver_sql("UPDATE tailor_runs r SET state='failed',error_code=coalesce(error_code,'task_ended') WHERE state IN ('queued','running') "
        "AND NOT EXISTS(SELECT 1 FROM tasks t WHERE t.kind='tailor' AND t.payload->>'run_id'=r.id::text AND t.state IN ('queued','running'))")
    c.exec_driver_sql("UPDATE tailor_runs SET state='expired' WHERE state='ready_for_review' AND expires_at<now()")

def cache_key(job_hash,resume_hash,track,level,provider=DEFAULT_PROVIDER,model=MODEL,verifier_model=VERIFIER_MODEL):
    parts=[resume_hash,job_hash,track,level,provider,model,verifier_model,PROMPT_VERSION,VERIFIER_PROMPT_VERSION,POLICY_VERSION,LENS_VERSION]
    return hashlib.sha256('|'.join(parts).encode()).hexdigest()

def start_run(p,resume_id,job_version_id,track=None,level=None,request_id=None):
    """Queue a tailoring run, or return the existing one for the same inputs."""
    with transaction(p) as c:
        c.exec_driver_sql('SELECT pg_advisory_xact_lock(hashtextextended(%(k)s,0))',dict(k=p.user_id+'quota'))
        job=one(c,'SELECT v.id,v.content_hash,v.completeness,j.title FROM job_versions v JOIN jobs j ON j.id=v.job_id WHERE v.id=%(id)s::uuid',dict(id=str(job_version_id)))
        resume=one(c,"SELECT id,body,file_hash FROM resumes WHERE id=%(id)s::uuid AND doc_type='resume' AND active",dict(id=str(resume_id)))
        if not job or not resume: raise AppError('Selected documents are not available in your workspace.')
        if job['completeness']!='full': raise AppError('Tailoring needs the full job description. Add it to this job first.')
        suggested=default_track_level(job['title'])
        track=track or suggested[0]; level=level or suggested[1]
        if track not in TRACKS or level not in LEVELS: raise AppError('Choose a valid target track and level.')
        segment(resume['body'])  # Fail now, with a clear message, if the resume has nothing that can be tailored.
        key=cache_key(job['content_hash'],resume['file_hash'],track,level)
        _refresh(c)
        found=one(c,'SELECT r.id,r.state,(SELECT count(*) FROM tailor_suggestions s WHERE s.run_id=r.id) shown,'
                    'EXISTS(SELECT 1 FROM resumes t WHERE t.tailor_run_id=r.id) composed_copy FROM tailor_runs r WHERE cache_key=%(k)s FOR UPDATE',dict(k=key))
        if found:
            keep=(found['state'] in ('queued','running') or (found['state']=='ready_for_review' and found['shown'])
                  or (found['state']=='composed' and found['composed_copy']))
            if keep: return str(found['id'])
        quota=one(c,'SELECT quota FROM memberships WHERE user_id=%(u)s::uuid',dict(u=p.user_id))['quota']
        if one(c,"SELECT count(*) n FROM tasks WHERE created_at>=date_trunc('day',now())")['n']>=quota:
            raise AppError('Your daily model run quota is reached.')
        # An earlier run that failed, expired or produced nothing is replaced.
        if found: c.exec_driver_sql('DELETE FROM tailor_runs WHERE id=%(id)s::uuid',dict(id=str(found['id'])))
        run=str(one(c,'INSERT INTO tailor_runs(tenant_id,owner_user_id,resume_id,job_version_id,track,level,provider,model,verifier_model,'
            'prompt_version,policy_version,lens_version,source_hash,cache_key) VALUES(%(t)s::uuid,%(u)s::uuid,%(r)s::uuid,%(j)s::uuid,'
            '%(track)s,%(level)s,%(provider)s,%(model)s,%(verifier)s,%(prompt)s,%(policy)s,%(lens)s,%(source)s,%(key)s) RETURNING id',
            scoped(p,r=str(resume['id']),j=str(job['id']),track=track,level=level,provider=DEFAULT_PROVIDER,model=MODEL,verifier=VERIFIER_MODEL,
                   prompt=PROMPT_VERSION+'+'+VERIFIER_PROMPT_VERSION,policy=POLICY_VERSION,lens=LENS_VERSION,source=resume['file_hash'],key=key))['id'])
        queued=one(c,"INSERT INTO tasks(tenant_id,owner_user_id,auth_version,kind,payload,request_id) VALUES(%(t)s::uuid,%(u)s::uuid,%(v)s,'tailor',%(payload)s::jsonb,%(rid)s) "
            'ON CONFLICT(tenant_id,owner_user_id,request_id) DO NOTHING RETURNING id',
            scoped(p,v=p.auth_version,payload=json.dumps(dict(run_id=run,resume_id=str(resume['id']),job_version_id=str(job['id']))),rid=request_id or str(uuid.uuid4())))
        if not queued: raise AppError('This request was already used. Start the run again.')
    return run

def cancel_run(p,run_id):
    with transaction(p) as c:
        c.exec_driver_sql("UPDATE tasks SET state='cancelled',finished_at=now(),lease_until=NULL WHERE kind='tailor' AND payload->>'run_id'=%(id)s AND state IN ('queued','running')",dict(id=str(run_id)))
        _refresh(c)

def list_runs(p):
    with transaction(p) as c:
        _refresh(c)
        return rows(c,'SELECT r.id,r.state,r.track,r.level,r.error_code,r.created_at,r.expires_at,r.resume_id,r.job_version_id,j.title,j.company,'
            'd.label resume_label,(SELECT count(*) FROM tailor_suggestions s WHERE s.run_id=r.id) suggestions FROM tailor_runs r '
            'JOIN job_versions v ON v.id=r.job_version_id JOIN jobs j ON j.id=v.job_id JOIN resumes d ON d.id=r.resume_id ORDER BY r.created_at DESC LIMIT 100')

def _suggestions(c,run_id):
    """Suggestions in rank order, each with its latest decision (or None)."""
    return rows(c,'SELECT s.*,d.decision,d.final_text,d.user_attested,d.decided_at FROM tailor_suggestions s LEFT JOIN LATERAL '
        '(SELECT decision,final_text,user_attested,decided_at FROM suggestion_decisions WHERE suggestion_id=s.id ORDER BY sequence DESC LIMIT 1) d ON true '
        'WHERE s.run_id=%(r)s::uuid ORDER BY s.rank',dict(r=str(run_id)))

def available(p):
    """False until the database has the tailoring tables, so other pages keep working before migration."""
    with transaction(p) as c:
        return one(c,"SELECT count(*) n FROM information_schema.columns WHERE table_name='tailor_suggestions' AND column_name='verdict'")['n']>0

def get_run(p,run_id):
    with transaction(p) as c:
        _refresh(c)
        run=one(c,'SELECT * FROM tailor_runs WHERE id=%(id)s::uuid',dict(id=str(run_id)))
        if not run: raise AppError('Tailoring run unavailable in your workspace.')
        composed=one(c,'SELECT id,label,body FROM resumes WHERE tailor_run_id=%(id)s::uuid ORDER BY created_at DESC LIMIT 1',dict(id=str(run_id)))
        source=one(c,'SELECT label resume_label,body resume_body FROM resumes WHERE id=%(id)s::uuid',dict(id=str(run['resume_id'])))
        job=one(c,'SELECT j.id job_id,j.title job_title,j.company FROM job_versions v JOIN jobs j ON j.id=v.job_id WHERE v.id=%(id)s::uuid',dict(id=str(run['job_version_id'])))
        return dict(run,**source,**job,suggestions=_suggestions(c,run_id),composed=composed,target=lens(run['track'],run['level'])['label'])

def link_application(p,run_id):
    """On the member's request, record the tailored version as the resume for this job, adding it to the tracker if needed."""
    run=get_run(p,run_id)
    if not run['composed']: raise AppError('Create the tailored version first.')
    app_id=repo.save_to_tracker(p,run['job_id'])
    with transaction(p) as c:
        c.exec_driver_sql('UPDATE applications SET resume_id=%(r)s::uuid,updated_at=now() WHERE id=%(a)s::uuid',dict(r=str(run['composed']['id']),a=app_id))
    return app_id

def linked_resume(p,job_id):
    """The resume currently recorded for this job in the tracker, if any."""
    with transaction(p) as c:
        found=one(c,'SELECT resume_id FROM applications WHERE job_id=%(j)s::uuid',dict(j=str(job_id)))
    return str(found['resume_id']) if found and found['resume_id'] else None

def alignment(p,job_version_id,resume_id):
    """The latest Fit Analyst result for this pair, or None."""
    with transaction(p) as c:
        found=one(c,'SELECT result FROM assessments WHERE job_version_id=%(j)s::uuid AND resume_id=%(r)s::uuid ORDER BY created_at DESC LIMIT 1',
                  dict(j=str(job_version_id),r=str(resume_id)))
    return found['result'] if found else None

def measures(p):
    """Counts from the member's own runs and latest decisions. Nothing is estimated."""
    with transaction(p) as c:
        _refresh(c)
        runs=rows(c,'SELECT state,error_code,trace,dropped FROM tailor_runs')
        latest=rows(c,'SELECT s.change_type,d.decision,d.user_attested FROM tailor_suggestions s LEFT JOIN LATERAL '
            '(SELECT decision,user_attested FROM suggestion_decisions WHERE suggestion_id=s.id ORDER BY sequence DESC LIMIT 1) d ON true')
    states={};failures={};dropped={};seconds=[];repaired=0
    for run in runs:
        states[run['state']]=states.get(run['state'],0)+1
        if run['error_code']: failures[run['error_code']]=failures.get(run['error_code'],0)+1
        for reason,count in run['dropped'].items(): dropped[reason]=dropped.get(reason,0)+count
        spent=sum(step.get('duration_ms',0) for step in run['trace'])/1000
        if run['state'] in ('ready_for_review','composed') and spent: seconds.append(spent)
        repaired+=any(step.get('component')=='tailor_repair' for step in run['trace'])
    by_type={}
    for row in latest:
        counts=by_type.setdefault(row['change_type'],dict(change=row['change_type'],shown=0,approved=0,edited=0,rejected=0,undecided=0,own_statements=0))
        counts['shown']+=1
        counts[{None:'undecided','approve':'approved','edit_approve':'edited','reject':'rejected'}[row['decision']]]+=1
        counts['own_statements']+=bool(row['user_attested'])
    ordered=sorted(seconds)
    return dict(runs=len(runs),states=states,failures=failures,dropped=dropped,repaired=repaired,
        median_seconds=ordered[len(ordered)//2] if ordered else None,slowest_seconds=ordered[-1] if ordered else None,
        decisions=sorted(by_type.values(),key=lambda x:x['change']))

def _locked_run(c,run_id):
    _refresh(c)
    run=one(c,'SELECT * FROM tailor_runs WHERE id=%(id)s::uuid FOR UPDATE',dict(id=str(run_id)))
    if not run: raise AppError('Tailoring run unavailable in your workspace.')
    return run

def _documents(c,run):
    resume=one(c,'SELECT * FROM resumes WHERE id=%(id)s::uuid FOR SHARE',dict(id=str(run['resume_id'])))
    job=one(c,'SELECT v.body,j.title,j.company FROM job_versions v JOIN jobs j ON j.id=v.job_id WHERE v.id=%(id)s::uuid',dict(id=str(run['job_version_id'])))
    if not resume or not job: raise AppError('The source documents are no longer available.')
    if resume['file_hash']!=run['source_hash']: raise AppError('The source resume changed after this run. Start a new run.')
    return resume,job

def _unit_for(units,source,s):
    unit=next((u for u in units if u.unit_id==s['unit_id']),None)
    if (unit is None or (unit.start,unit.end)!=(s['start_offset'],s['end_offset'])
            or source[unit.start:unit.end]!=s['before_text']):
        raise AppError('A proposal no longer matches the source resume. Start a new run.')
    return unit

def review_edit(source,units,job_text,suggestion,text):
    """Check a member's own wording. Returns (reason, details) needing attestation; raises for unusable text."""
    if suggestion['change_type'] not in EDITABLE_TYPES: raise AppError('A move can only be approved or rejected.')
    unit=_unit_for(units,source,suggestion)
    if not isinstance(text,str) or not text.strip(): raise AppError('Enter the replacement text, or reject this proposal.')
    text=text.strip()
    if text==unit.text.strip(): raise AppError('This is the original text. Reject the proposal to keep it.')
    limit=POLICY['limits']['summary_chars' if unit.kind=='summary' else 'bullet_chars']
    if len(text)>max(limit,len(unit.text)): raise AppError(f'Use at most {max(limit,len(unit.text))} characters.')
    if any(not PLAIN.fullmatch(ch) for ch in text) or '**' in text or '`' in text:
        raise AppError('Use plain single-line text without markup or unusual symbols.')
    if contains_contact(text) and not contains_contact(unit.text): raise AppError('Contact details cannot be added here.')
    if not keeps_shape(source,units,unit,text): raise AppError('This text would no longer read as the same resume line. Start with an action verb.')
    related=[u.text for u in units if (u.kind=='bullet' and u.role==unit.role and unit.kind=='bullet')
             or (unit.kind=='summary' and u.kind!='contact')]
    support='\n'.join([unit.text]+[e['quote'] for e in suggestion['evidence']]+related)
    return check_text(text,support,job_text,unit.text)

def decide(p,run_id,suggestion_id,decision,final_text=None,attest=False,request_id=None):
    """Record one decision on one proposal. There is deliberately no way to decide several at once."""
    if not isinstance(suggestion_id,(str,uuid.UUID)): raise AppError('Decide one proposal at a time.')
    if decision not in DECISIONS: raise AppError('Choose approve, reject, or edit then approve.')
    if (decision=='edit_approve')!=(final_text is not None): raise AppError('Replacement text belongs only to edit then approve.')
    request_id=request_id or str(uuid.uuid4())
    with transaction(p) as c:
        run=_locked_run(c,run_id)
        used=one(c,'SELECT suggestion_id,decision,final_text,user_attested FROM suggestion_decisions WHERE request_id=%(r)s',dict(r=request_id))
        if used:
            same=(str(used['suggestion_id'])==str(suggestion_id) and used['decision']==decision
                  and used['final_text']==(final_text.strip() if final_text is not None else None))
            if not same: raise AppError('This request was already used for another decision.')
            return dict(decision=decision,user_attested=used['user_attested'])
        if run['state']!='ready_for_review': raise AppError('This run is not open for review.')
        s=one(c,'SELECT * FROM tailor_suggestions WHERE id=%(id)s::uuid AND run_id=%(r)s::uuid',dict(id=str(suggestion_id),r=str(run_id)))
        if not s: raise AppError('Proposal unavailable in this run.')
        attested=False
        if decision=='edit_approve':
            resume,job=_documents(c,run)
            reason,details=review_edit(resume['body'],segment(resume['body']),job['body'],s,final_text)
            if reason:
                if attest is not True: raise AttestationRequired(reason,details)
                attested=True
            final_text=final_text.strip()
        c.exec_driver_sql('INSERT INTO suggestion_decisions(tenant_id,owner_user_id,suggestion_id,decision,final_text,user_attested,request_id) '
            'VALUES(%(t)s::uuid,%(u)s::uuid,%(s)s::uuid,%(d)s,%(f)s,%(a)s,%(rid)s)',scoped(p,s=str(suggestion_id),d=decision,f=final_text,a=attested,rid=request_id))
    return dict(decision=decision,user_attested=attested)

def _approved_change(source,units,job_text,s):
    """Re-check one approved proposal against the rules before it is applied."""
    unit=_unit_for(units,source,s)
    if s['decision']=='edit_approve':
        reason,details=review_edit(source,units,job_text,s,s['final_text'])
        if reason and not s['user_attested']: raise AppError('An edited proposal no longer passes the checks: '+', '.join(details))
        return Change(unit.unit_id,'text',s['final_text'])
    proposal=dict(unit_id=s['unit_id'],change_type=s['change_type'],after=s['after_text'],new_position=s['new_position'],
        evidence=[dict(quote=e['quote']) for e in s['evidence']],job_quote=s['job_quote'],rationale=s['rationale'])
    result=validate(proposal,units,source,job_text)
    if not result.ok: raise AppError('An approved proposal no longer passes the checks ('+result.reason+'). Nothing was saved.')
    if s['change_type']=='reorder': return Change(unit.unit_id,'move',position=s['new_position'])
    if s['change_type']=='deemphasize': return Change(unit.unit_id,'lower')
    if s['change_type'] in REWRITES and not keeps_shape(source,units,unit,s['after_text']):
        raise AppError('An approved proposal would change the resume structure. Nothing was saved.')
    return Change(unit.unit_id,'text',s['after_text'])

def compose(p,run_id):
    """Create a new resume version from the approved proposals only. The source is never modified."""
    new_id=str(uuid.uuid4()); path=None
    try:
        with transaction(p) as c:
            c.exec_driver_sql('SELECT pg_advisory_xact_lock(hashtextextended(%(key)s,0))',dict(key=p.tenant_id+p.user_id))
            run=_locked_run(c,run_id)
            if run['state']=='composed':
                found=one(c,'SELECT id FROM resumes WHERE tailor_run_id=%(id)s::uuid',dict(id=str(run_id)))
                if not found: raise AppError('The tailored version was deleted. Start a new run.')
                return str(found['id'])
            if run['state']!='ready_for_review': raise AppError('This run is not ready to compose.')
            resume,job=_documents(c,run)
            source=resume['body'];units=segment(source)
            approved=[s for s in _suggestions(c,run_id) if s['decision'] in ('approve','edit_approve')]
            if not approved: raise AppError('Approve at least one proposal first.')
            changes=[_approved_change(source,units,job['body'],s) for s in approved]
            output,spans,blocks=compose_text(source,units,changes)
            verify(source,output,units,changes,spans)
            if output==source: raise AppError('The approved changes leave the resume as it was.')
            data=build_docx(blocks)
            key=f'{p.tenant_id}/{p.user_id}/{new_id}.docx'
            path=repo.private_path(key)
            repo.check_document_quota(c,len(data))
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            label=f"{lens(run['track'],run['level'])['label']} · {job['company']} · {date.today().isoformat()}"[:100]
            c.exec_driver_sql('INSERT INTO resumes(id,tenant_id,owner_user_id,label,object_key,file_hash,body,parser_version,doc_type,parent_resume_id,tailor_run_id) '
                "VALUES(%(id)s::uuid,%(t)s::uuid,%(u)s::uuid,%(label)s,%(key)s,%(hash)s,%(body)s,%(parser)s,'resume',%(parent)s::uuid,%(run)s::uuid)",
                scoped(p,id=new_id,label=label,key=key,hash=hashlib.sha256(data).hexdigest(),body=output,parser=PARSER_VERSION,parent=str(resume['id']),run=str(run_id)))
            repo.index_text(c,p,new_id,'resume',output)
            c.exec_driver_sql("UPDATE tailor_runs SET state='composed' WHERE id=%(id)s::uuid",dict(id=str(run_id)))
    except Exception:
        if path: path.unlink(missing_ok=True)
        raise
    return new_id
