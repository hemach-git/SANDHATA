"""Comparison results and run diagnostics."""
from datetime import datetime,timezone
import streamlit as st
from .config import DATA,AppError
from . import repository as repo
from . import identity as auth
from .worker import enqueue,cancel_task
from .ui_common import md,flash,show_flash,navigate,open_discover

GROUPS=(('supported','Supported'),('partial','Partially supported'),('not_evidenced','Not evidenced'),('unknown','Unknown'))
FAILURES={
    'comparison_failed_validation_or_provider':'The local model was unavailable, the documents were too long for it, or it could not quote both documents accurately after one repair. Check that Ollama is running, then retry.',
    'access_or_document_unavailable':'The resume or posting was removed, or your access changed, while this ran. Choose available documents and compare again.',
    'worker_lease_exhausted':'The comparison worker stopped twice before finishing. Restart the worker, then retry.',
    'access_revoked':'Cancelled because the account access changed.',
}

def result_view(result,scope='result'):
    st.caption('Experimental AI comparison · Review the quoted evidence before using this result.')
    flags=result.get('eligibility_flags',[])
    if flags:
        st.markdown('**Check eligibility first**')
        for flag in flags: st.warning(md(flag))
    a,b,c=st.columns(3)
    a.metric('Resume alignment',f"{result['score']:.0f}%" if result['score'] is not None else 'Withheld')
    b.metric('Evidence coverage',f"{result['coverage']:.0f}%")
    c.metric('Assessment','Provisional' if result['provisional'] else 'Evidence validated')
    st.caption(result['meaning']+' Literal quotes are verified; review whether they substantively support each judgment.')
    for status,label in GROUPS:
        found=[r for r in result['requirements'] if r['status']==status]
        st.markdown(f'**{label} ({len(found)})**')
        for number,r in enumerate(found):
            with st.container(border=True,key=f'sn_card_{scope}_{status}_{number}'):
                job,resume=st.columns(2)
                job.caption('Job requirement');job.text(r['requirement_quote'])
                resume.caption('Selected resume evidence');resume.text(r['resume_quote'] or 'Not evidenced in this resume.')
                st.text(r['rationale'])
                st.caption(f"Category: {r['category'].replace('_',' ')} · Job offset {r['job_offset']} · Resume offset {r['resume_offset']}")

def remember_inputs(task_id,version_id,resume_id):
    """Lets Diagnostics retry a comparison queued in this browser session."""
    st.session_state.setdefault('task_inputs',{})[str(task_id)]=(str(version_id),str(resume_id))

def task_inputs(task):
    if task.get('job_version_id') and task.get('resume_id'): return str(task['job_version_id']),str(task['resume_id'])
    return st.session_state.get('task_inputs',{}).get(str(task['id']))

def worker_status():
    heartbeat=DATA/'worker_heartbeat'
    if not heartbeat.exists():
        st.warning('No worker heartbeat. Start the comparison worker using the project startup script.');return
    text=heartbeat.read_text(encoding='utf-8')
    try: age=(datetime.now(timezone.utc)-datetime.fromisoformat(text.strip())).total_seconds()
    except (ValueError,TypeError): age=None
    # The heartbeat pauses while one comparison runs, so only a long silence is a problem.
    if age is not None and age>600: st.warning(f'The worker has been silent for {age/60:.0f} minutes. Restart it if comparisons are not finishing.')
    st.caption('Worker heartbeat: '+text)

def task_view(p,task):
    state=task['state'];key=str(task['id'])
    with st.expander(f"{state.title()} · {key[:12]} · {task['created_at']:%b %d %H:%M} UTC",expanded=state=='failed'):
        if state=='queued': st.info('Waiting for the worker. Refresh to see progress.')
        if state=='running': st.info('Your local model is working on this comparison. This can take several minutes.')
        if state=='cancelled' and not task['error_code']: st.caption('Cancelled before finishing.')
        if task['error_code']:
            st.warning(FAILURES.get(task['error_code'],'The comparison did not finish. Check the worker and the local model, then retry.'))
            st.caption('Error code: '+task['error_code'])
        if state=='failed':
            inputs=task_inputs(task)
            if inputs:
                if st.button('Retry comparison',key='retry_'+key,type='primary'):
                    try:
                        remember_inputs(enqueue(p,*inputs),*inputs)
                        flash('Comparison queued again.');st.rerun()
                    except AppError as exc: st.error(str(exc))
            else:
                st.button('Retry from Discover',key='retry_'+key,on_click=open_discover)
                st.caption('Select the role and the resume, then choose Compare.')
        if state in ('queued','running') and st.button('Cancel comparison',key='cancel'+key):
            cancel_task(p,task['id']);st.rerun()
        if task['result_id'] and st.toggle('Show evidence',key='evidence_'+key):
            result_view(repo.assessment_detail(p,task['result_id'])['result'],'task_'+key)
        if task['trace']:
            with st.expander('Run execution details',expanded=False): st.json(task['trace'])

def tailoring_measures(p):
    from . import tailoring
    if not tailoring.available(p): return
    found=tailoring.measures(p)
    st.subheader('Resume tailoring')
    if not found['runs']: st.caption('No tailoring runs yet.');return
    a,b,c,d=st.columns(4)
    a.metric('Tailoring runs',found['runs']);b.metric('Failed',found['states'].get('failed',0))
    c.metric('Needed a repair',found['repaired'])
    d.metric('Median model time','Not measured' if found['median_seconds'] is None else f"{found['median_seconds']:.0f} s")
    if found['decisions']:
        st.caption('Latest decision for each proposal')
        st.dataframe(found['decisions'],hide_index=True,use_container_width=True)
    if found['dropped']:
        st.caption('Proposals removed by checks before you saw them')
        st.dataframe([dict(reason=k,count=v) for k,v in sorted(found['dropped'].items())],hide_index=True,use_container_width=True)
    if found['failures']: st.caption('Run error codes: '+', '.join(f'{k} ({v})' for k,v in sorted(found['failures'].items())))

def diagnostics(p):
    st.header('Your runs and evidence')
    show_flash()
    row=st.container(horizontal=True)
    if row.button('Refresh run status',type='primary'): st.rerun()
    row.button('Back to Discover',on_click=navigate,args=('Discover',))
    tasks=repo.tasks(p)
    for column,state in zip(st.columns(4),('queued','running','completed','failed')):
        column.metric(state.title(),sum(t['state']==state for t in tasks))
    st.caption('Counts cover your 50 most recent runs. The page updates when you refresh.')
    worker_status()
    if not tasks: st.info('No comparisons yet. Choose a resume, then compare roles in Discover.')
    for task in tasks: task_view(p,task)
    tailoring_measures(p)
    st.subheader('Search saved evidence')
    question=st.text_input('Find a skill, responsibility, or phrase in your saved evidence')
    if question:
        found=repo.retrieve(p,question)
        if not found: st.info('Your saved evidence does not establish an answer for this query.')
        for r in found:
            st.text(r['body']);st.caption(f"Citation: {r['parent_type']} {r['parent_id']} · passage {r['id']} · offset {r['start_offset']}")
    with st.expander('Local read-only MCP access'):
        st.caption('Create a capability valid for 15 minutes. Store it securely; suspension and role changes revoke it. It grants only your own read-only data access.')
        if st.button('Create my MCP capability'):
            st.code(auth.issue_capability(p));st.warning('Copy this securely. It will not be displayed again after leaving this page.')
