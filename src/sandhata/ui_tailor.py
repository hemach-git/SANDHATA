"""Resume Tailor screen: start a run, review one proposal at a time, create a new version. There is no approve-all."""
import difflib,html,re
import streamlit as st
from . import repository as repo
from . import tailoring
from .config import AppError
from .planner import TRACKS,LEVELS,default_track_level,lens
from .segmenter import segment
from .ui_common import md,flash,show_flash,navigate,private_download,alignment_text
from .ui_results import worker_status
from .worker import enqueue

TRACK_NAMES=dict(fde='AI Forward Deployed Engineer',ai_engineer='AI Engineer')
LEVEL_NAMES=dict(senior='Senior',lead='Lead',manager='Manager')
CHANGES=dict(rephrase='Reword a bullet',summary='Rewrite the summary',skills_reorder='Reorder skills',reorder='Move a bullet',deemphasize='Move a bullet to the end')
DECISIONS={None:'Not decided','approve':'Approved','edit_approve':'Approved with your edit','reject':'Rejected'}
STATES=dict(queued='Waiting',running='Working',ready_for_review='Ready for review',composed='Version created',failed='Did not finish',expired='Expired')
VERDICTS=dict(passed='Second AI check: found nothing beyond the evidence.',warning='Second AI check: unsure. Read this one carefully.',
    not_checked='Second AI check: did not run for this change. Read this one carefully.',not_needed='No new wording, so no second AI check was needed.')
FAILURES={'tailoring_failed_validation_or_provider':'The local model was unavailable, its draft could not be read twice, or the documents were too long. Check that Ollama is running, then start again.',
    'access_or_document_unavailable':'The resume or posting was removed, or your access changed, while this ran.',
    'worker_lease_exhausted':'The worker stopped twice before finishing. Restart the worker, then start again.',
    'task_ended':'The run was cancelled or its task ended before finishing.'}
LIMITS=('Code checks compare words, and a second AI reviews meaning. Both can miss things, and a passed check is not proof. '
        'Before approving, confirm that you could defend every word in an interview.')

def quoted(text,extra=''):
    st.html(f'<div class="sn-quote {extra}">{text}</div>')

def diff_html(before,after):
    """Escaped before and after text with changed words marked."""
    a=re.findall(r'\s+|[^\s]+',before); b=re.findall(r'\s+|[^\s]+',after)
    old=[];new=[]
    for kind,i,j,k,l in difflib.SequenceMatcher(a=a,b=b,autojunk=False).get_opcodes():
        left=html.escape(''.join(a[i:j]));right=html.escape(''.join(b[k:l]))
        if kind=='equal': old.append(left);new.append(right)
        else:
            if left: old.append(f'<del>{left}</del>')
            if right: new.append(f'<ins>{right}</ins>')
    return ''.join(old),''.join(new)

def highlighted(body,spans,target):
    """The source resume, escaped, with cited evidence marked and the edited line outlined."""
    points=sorted({0,len(body),*[x for s in spans for x in s],*target})
    parts=[]
    for start,end in zip(points,points[1:]):
        piece=html.escape(body[start:end])
        edited=target[0]<=start and end<=target[1]
        if any(s<=start and end<=e for s,e in spans) or edited:
            piece=f'<mark class="{"sn-target" if edited else "sn-cited"}">{piece}</mark>'
        parts.append(piece)
    return ''.join(parts)

def start_form(p,resumes,selected):
    jobs=[j for j in repo.list_jobs(p) if j['completeness']=='full']
    if not resumes: st.info('Upload a resume in Resume Library to start.');st.button('Open Resume Library',on_click=navigate,args=('Resume Library',));return
    if not jobs: st.info('Save a job with its full description to start. Short feed snippets cannot be tailored.');st.button('Open Discover',on_click=navigate,args=('Discover',));return
    by_job={str(j['version_id']):j for j in jobs};by_resume={str(r['id']):r for r in resumes}
    a,b=st.columns(2)
    version=a.selectbox('Job to tailor for',list(by_job),key='tailor_job',format_func=lambda v:f"{by_job[v]['title']} · {by_job[v]['company']}")
    chosen=b.selectbox('Resume to start from',list(by_resume),key='tailor_resume',
        index=list(by_resume).index(str(selected)) if str(selected) in by_resume else 0,format_func=lambda r:by_resume[r]['label'])
    track,level=default_track_level(by_job[version]['title'])
    a,b=st.columns(2)
    # Keys include the job so a new job brings its own suggested target.
    track=a.selectbox('Target track',TRACKS,index=TRACKS.index(track),format_func=TRACK_NAMES.get,key='tailor_track_'+version)
    level=b.selectbox('Target level',LEVELS,index=LEVELS.index(level),format_func=LEVEL_NAMES.get,key='tailor_level_'+version)
    st.caption(f"Target: {lens(track,level)['label']}. Suggested from the job title; change it if needed. Runs on your local model and can take several minutes. Your original resume is never changed.")
    if st.button('Start tailoring',type='primary'):
        try:
            st.session_state['tailor_open']=tailoring.start_run(p,chosen,version,track,level)
            flash('Tailoring run ready below. If it was run before with the same inputs, the earlier result is shown.')
            st.rerun()
        except AppError as exc: st.error(str(exc))

def gap_panel(run):
    gaps=run['gaps']
    if not gaps: return
    with st.expander(f'Gaps to consider ({len(gaps)}) · nothing is written for these'):
        st.caption('Add something only if it is true. Update your resume yourself, upload it as a new version, then tailor again.')
        for kind,title in (('level',f"Often expected for {run['target']}, not found in this resume"),('skill','Job requirements this resume does not show')):
            found=[g for g in gaps if g['kind']==kind]
            if found:
                st.markdown(f'**{md(title)}**')
                for gap in found: st.markdown('- '+md(gap['label']))

def move_text(run,s):
    units=segment(run['resume_body'])
    unit=next((u for u in units if u.unit_id==s['unit_id']),None)
    if unit is None: return 'This line is no longer found in the source resume.'
    siblings=[u for u in units if u.kind=='bullet' and u.role==unit.role]
    now=siblings.index(unit)+1
    headers=[u.text for u in units if u.kind=='role_header' and u.role==unit.role]
    role=(' under '+headers[0]) if headers else ''
    if s['change_type']=='deemphasize': return f'Move bullet {now} of {len(siblings)}{role} to the end of that role. The wording stays the same.'
    return f"Move bullet {now} of {len(siblings)}{role} to position {s['new_position']+1}. The wording stays the same."

def record(p,run,s,decision,**extra):
    """Save one decision, then move to the next proposal still waiting."""
    try: tailoring.decide(p,run['id'],str(s['id']),decision,**extra)
    except tailoring.AttestationRequired as exc:
        st.session_state['tailor_attest_'+str(s['id'])]=(extra['final_text'],list(exc.details));st.rerun()
    except AppError as exc: st.error(str(exc));return
    st.session_state.pop('tailor_attest_'+str(s['id']),None)
    ids=[str(x['id']) for x in run['suggestions']];here=ids.index(str(s['id']))
    waiting=[x for x in ids[here+1:]+ids[:here] if next(y for y in run['suggestions'] if str(y['id'])==x)['decision'] is None]
    if waiting: st.session_state['tailor_next_'+str(run['id'])]=waiting[0]
    flash(DECISIONS[decision]+'.');st.rerun()

def proposal_card(p,run,s):
    key=str(s['id'])
    with st.container(border=True,key='sn_card_proposal'):
        st.markdown(f"**{CHANGES[s['change_type']]}** · {DECISIONS[s['decision']]}"+(' · Includes your own statement' if s['user_attested'] else ''))
        verdict=s['verdict'].get('status','not_checked')
        (st.warning if verdict in ('warning','not_checked') else st.caption)(VERDICTS.get(verdict,VERDICTS['not_checked']))
        for note in s['warnings']: st.warning(md(note))
        if s['change_type'] in ('reorder','deemphasize'):
            st.text(move_text(run,s));quoted(html.escape(s['before_text']))
        else:
            old,new=diff_html(s['before_text'],s['final_text'] or s['after_text'])
            a,b=st.columns(2)
            with a: st.caption('Before (removed words struck through)');quoted(old)
            with b: st.caption('Your approved text' if s['final_text'] else 'Proposed (new words marked)');quoted(new)
        a,b=st.columns(2)
        with a:
            st.caption('Job requirement this targets');st.text(s['job_quote'])
            if s['rationale']: st.caption('Why the AI suggests it');st.text(s['rationale'])
        with b:
            st.caption('Evidence from your resume')
            for item in s['evidence']: quoted(html.escape(item['quote']))
        with st.expander('Show the evidence inside your resume'):
            spans=[(e['offset'],e['offset']+len(e['quote'])) for e in s['evidence']]
            quoted(highlighted(run['resume_body'],spans,(s['start_offset'],s['end_offset'])),'sn-resume')
        if run['state']!='ready_for_review': return
        row=st.container(horizontal=True)
        if row.button('Approve this change',key='approve_'+key,type='primary'): record(p,run,s,'approve')
        if row.button('Reject this change',key='reject_'+key): record(p,run,s,'reject')
        if s['change_type'] in tailoring.EDITABLE_TYPES: edit_controls(p,run,s,key)

def edit_controls(p,run,s,key):
    with st.expander('Edit, then approve',expanded='tailor_attest_'+key in st.session_state):
        text=st.text_area('Your wording',value=s['final_text'] or s['after_text'],key='edit_'+key,max_chars=1000)
        if st.button('Check and approve my wording',key='save_edit_'+key): record(p,run,s,'edit_approve',final_text=text)
        pending=st.session_state.get('tailor_attest_'+key)
        if not pending: return
        if pending[0]!=text: st.info('Your wording changed. Check it again.');return
        st.warning('Your wording says more than the cited resume evidence: '+md(', '.join(pending[1])))
        agreed=st.checkbox('This is true and I am adding it myself',key='attest_'+key)
        if st.button('Approve with my statement',key='save_attest_'+key,disabled=not agreed):
            record(p,run,s,'edit_approve',final_text=text,attest=True)

def review(p,run):
    found=run['suggestions']
    if not found:
        st.info('No proposal passed the checks, so there is nothing to change. This can be the right answer. Starting the same inputs again makes a new attempt.')
        if run['dropped']: st.caption('Removed by checks: '+', '.join(f'{k} ({v})' for k,v in run['dropped'].items()))
        return
    approved=sum(s['decision'] in ('approve','edit_approve') for s in found);waiting=sum(s['decision'] is None for s in found)
    for column,(label,value) in zip(st.columns(4),[('Proposals',len(found)),('Waiting for you' if run['state']=='ready_for_review' else 'Left undecided',waiting),('Approved',approved),('Removed by checks',sum(run['dropped'].values()))]):
        column.metric(label,value)
    st.caption(LIMITS)
    by_id={str(s['id']):s for s in found};ids=list(by_id);choice='tailor_proposal_'+str(run['id'])
    move=st.session_state.pop('tailor_next_'+str(run['id']),None)
    if move in by_id: st.session_state[choice]=move
    if st.session_state.get(choice) not in by_id: st.session_state[choice]=ids[0]
    def step(by): st.session_state[choice]=ids[(ids.index(st.session_state[choice])+by)%len(ids)]
    st.selectbox('Proposal',ids,key=choice,format_func=lambda i:f"{ids.index(i)+1} of {len(ids)} · {CHANGES[by_id[i]['change_type']]}")
    row=st.container(horizontal=True)
    row.button('Previous',on_click=step,args=(-1,),key='tailor_previous');row.button('Next',on_click=step,args=(1,),key='tailor_following')
    proposal_card(p,run,by_id[st.session_state[choice]])
    if run['state']=='ready_for_review':
        st.subheader('Create the tailored version')
        st.caption(f'{approved} approved change(s) will be applied. Rejected and undecided proposals are left out. The new file uses a plain single-column layout.')
        if st.button(f'Create version with {approved} approved change(s)',type='primary',disabled=not approved,key='tailor_compose'):
            try: tailoring.compose(p,run['id']);flash('Tailored version created.');st.rerun()
            except AppError as exc: st.error(str(exc))

def composed_view(p,run):
    new=run['composed']
    st.subheader('Your tailored version')
    if not new: st.info('The tailored version was deleted. Start the same inputs again to make a new run.');return
    st.markdown(md(new['label']))
    st.caption('Saved in Resume Library. Read the whole document before sending it.')
    private_download(p,'Download Word file','resume',new['id'])
    with st.expander('Preview the text'): quoted(html.escape(new['body']),'sn-resume')
    linked=tailoring.linked_resume(p,run['job_id'])==str(new['id'])
    row=st.container(horizontal=True)
    if linked: st.caption('Recorded as the resume for this job in your tracker.')
    elif row.button('Use for this job in Tracker',key='tailor_link'):
        tailoring.link_application(p,run['id']);flash('Recorded in your tracker. Nothing was sent to the employer.');st.rerun()
    before=tailoring.alignment(p,run['job_version_id'],run['resume_id']);after=tailoring.alignment(p,run['job_version_id'],new['id'])
    if not after and row.button('Compare the new version with this job',key='tailor_compare'):
        try: enqueue(p,run['job_version_id'],new['id']);flash('Comparison queued. See Diagnostics for progress.');st.rerun()
        except AppError as exc: st.error(str(exc))
    if before or after:
        a,b=st.columns(2)
        a.caption('Original resume');a.markdown(alignment_text(before))
        b.caption('Tailored version');b.markdown(alignment_text(after))
        st.caption('Alignment compares a resume with a description. It is not a chance of an interview, and small differences can come from the model.')

def run_view(p,run):
    state=run['state']
    st.markdown(f"**{STATES[state]}** · Target: {md(run['target'])} · From resume: {md(run['resume_label'])}")
    if state in ('queued','running'):
        st.info('Waiting for the worker.' if state=='queued' else 'Your local model is drafting and checking changes. This can take several minutes.')
        row=st.container(horizontal=True)
        if row.button('Refresh',type='primary',key='tailor_refresh'): st.rerun()
        if row.button('Cancel run',key='tailor_cancel'): tailoring.cancel_run(p,run['id']);st.rerun()
        worker_status();return
    if state in ('failed','expired'):
        st.warning(FAILURES.get(run['error_code'],'This run did not finish.') if state=='failed' else 'This run expired after 14 days without a new version.')
        if st.button('Start again with the same inputs',key='tailor_retry',type='primary'):
            try:
                st.session_state['tailor_open']=tailoring.start_run(p,run['resume_id'],run['job_version_id'],run['track'],run['level']);st.rerun()
            except AppError as exc: st.error(str(exc))
    else:
        gap_panel(run)
        if state=='composed': composed_view(p,run)
        review(p,run)
    if run['trace']:
        with st.expander('Run execution details'): st.json(run['trace'])

def tailor_page(p,resumes,selected):
    st.header('Tailor your resume')
    st.caption('AI suggests changes backed by your own resume. You approve each one; a new version is created and your original stays as it is.')
    show_flash()
    if not tailoring.available(p):
        st.warning('Tailoring needs a database update. Ask the operator to back up, then run scripts/migrate.py. Other pages are not affected.');return
    with st.expander('Start a new tailoring run',expanded=not tailoring.list_runs(p)): start_form(p,resumes,selected)
    runs=tailoring.list_runs(p)
    if not runs: st.info('No tailoring runs yet.');return
    by_id={str(r['id']):r for r in runs}
    wanted=st.session_state.pop('tailor_open',None)
    if wanted in by_id: st.session_state['tailor_run']=wanted
    if st.session_state.get('tailor_run') not in by_id: st.session_state['tailor_run']=next(iter(by_id))
    chosen=st.selectbox('Tailoring run',list(by_id),key='tailor_run',
        format_func=lambda i:f"{by_id[i]['title']} · {by_id[i]['company']} · {LEVEL_NAMES[by_id[i]['level']]} · {by_id[i]['created_at']:%b %d %H:%M} UTC")
    try: run_view(p,tailoring.get_run(p,chosen))
    except AppError as exc: st.error(str(exc))
