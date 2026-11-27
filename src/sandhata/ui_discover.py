"""Discover: saved matches, watched employers, searches and manual import."""
import re
import pandas as pd
import streamlit as st
from .config import AppError
from . import repository as repo
from . import connectors
from .worker import enqueue,enqueue_batch
from .targeting import TARGET_FILTERS,SUGGESTED_BOARDS,priority,has_term
from .ui_common import (DISCOVER_FILTERS,md,compact_dataframe,private_download,toast,flash,show_flash,
    navigate,open_application,open_discover,confirm_button,alignment_text)
from .ui_results import result_view,remember_inputs

TABS=['Matches','Target companies','Search','Add a posting']
PAGE_SIZE=25
BATCH_LIMIT=25
LEVELS=(('Director or head',('director','head','vp')),('Manager',('manager',)),('Principal or staff',('principal','staff')),
    ('Lead',('lead',)),('Senior',('senior','sr')))
OTHER_LEVEL='Other or unstated'
PLACES=['Any location','Remote','Charlotte','Remote or Charlotte']
ORDERS=['Role priority','Resume alignment','Newest saved']

# ---- Client-side filtering and ordering -------------------------------------

def seniority(title):
    title=(title or '').lower()
    return next((level for level,words in LEVELS if any(has_term(title,w) for w in words)),OTHER_LEVEL)

def in_place(job,place):
    if place=='Any location': return True
    location=(job.get('location') or '').lower()
    remote=has_term(location,'remote') or job.get('workplace')=='Remote'
    charlotte=has_term(location,'charlotte')
    return {'Remote':remote,'Charlotte':charlotte,'Remote or Charlotte':remote or charlotte}[place]

def score_of(job,fit): return fit.get(str(job['version_id']),{}).get('score')

def filter_jobs(jobs,fit,new=False,company=(),level=(),source=(),place='Any location',minimum=0):
    def keep(j):
        if new and not j['is_new']: return False
        if company and j['company'] not in company: return False
        if level and seniority(j['title']) not in level: return False
        if source and j['source'] not in source: return False
        if minimum and (score_of(j,fit) is None or score_of(j,fit)<minimum): return False
        return in_place(j,place)
    return [j for j in jobs if keep(j)]

def sort_jobs(jobs,fit,order):
    # Jobs arrive newest first; sorting is stable, so ties keep that order.
    if order=='Role priority': return sorted(jobs,key=priority,reverse=True)
    if order=='Resume alignment': return sorted(jobs,key=lambda j:(score_of(j,fit) is not None,score_of(j,fit) or 0),reverse=True)
    return jobs

def scan_failed(watch):
    # A successful scan note starts with its counts; any other note is an error message.
    note=watch.get('last_note') or ''
    return bool(note) and not re.match(r'\d+ matched of \d+',note)

# ---- Matches ----------------------------------------------------------------

def first_page(): st.session_state['discover_page']=1

def clear_filters():
    st.session_state.update(DISCOVER_FILTERS);first_page()

def toggle_pick(job_id):
    picked=st.session_state.setdefault('discover_selected',set())
    if st.session_state['pick_'+job_id]: picked.add(job_id)
    else: picked.discard(job_id)

def set_picks(ids,value):
    picked=st.session_state.setdefault('discover_selected',set())
    if value: picked.update(ids)
    else: picked.difference_update(ids)

def toggle_details(job_id):
    st.session_state['discover_open']=None if st.session_state.get('discover_open')==job_id else job_id

def filter_bar(jobs):
    for key,value in DISCOVER_FILTERS.items(): st.session_state.setdefault(key,value)
    options=dict(discover_company=sorted({j['company'] for j in jobs},key=str.casefold),
        discover_seniority=[level for level,_ in LEVELS]+[OTHER_LEVEL],discover_source=sorted({j['source'] for j in jobs}))
    # Drop selections that no longer exist, for example after the sidebar search narrows the list.
    for key,available in options.items(): st.session_state[key]=[v for v in st.session_state[key] if v in available]
    with st.container(border=True,key='sn_card_filters'):
        a,b,c,d=st.columns(4)
        a.multiselect('Company',options['discover_company'],key='discover_company',on_change=first_page,placeholder='All companies')
        b.multiselect('Seniority',options['discover_seniority'],key='discover_seniority',on_change=first_page,placeholder='All levels',help='Read from words in the job title.')
        c.multiselect('Source',options['discover_source'],key='discover_source',on_change=first_page,placeholder='All sources')
        d.selectbox('Remote or Charlotte',PLACES,key='discover_place',on_change=first_page)
        a,b,c,d=st.columns(4)
        a.number_input('Minimum resume alignment %',0,100,step=5,key='discover_min',on_change=first_page,help='Above 0, roles without a score are hidden.')
        b.selectbox('Sort by',ORDERS,key='discover_order',on_change=first_page,help='Role priority orders by title, seniority and location. It is not a fit score.')
        c.checkbox(f"New only ({sum(j['is_new'] for j in jobs)})",key='discover_new',on_change=first_page)
        d.button('Clear filters',on_click=clear_filters,use_container_width=True)

def comparison_message(outcome,asked):
    flash(f"{outcome['queued']} comparisons queued. Each runs on your local model; follow progress in Diagnostics.")
    if outcome['queued']<asked and not outcome['stopped']:
        flash(f"{asked-outcome['queued']} were skipped: already scored, already queued, or the description is partial.",'info')
    if outcome['stopped']: flash(outcome['stopped'],'warning')

def action_bar(p,jobs,shown,tracked,fit,resume_id):
    picked=st.session_state.setdefault('discover_selected',set())
    chosen=[j for j in jobs if str(j['id']) in picked]
    hidden=len(picked)-len(chosen)
    unscored=sum(j['completeness']=='full' and str(j['version_id']) not in fit for j in jobs)
    with st.container(border=True,key='sn_card_actions'):
        st.markdown(f"**{len(chosen)} selected**"+(f' · {hidden} more hidden by filters and not included' if hidden>0 else ''))
        row=st.container(horizontal=True)
        row.button('Select this page',on_click=set_picks,args=([str(j['id']) for j in shown],True),disabled=not shown)
        row.button('Clear selection',on_click=set_picks,args=(list(picked),False),disabled=not picked)
        if row.button('Compare selected',type='primary',disabled=not(chosen and resume_id)):
            asked=chosen[:BATCH_LIMIT]
            comparison_message(enqueue_batch(p,asked,resume_id,BATCH_LIMIT),len(asked))
            if len(chosen)>BATCH_LIMIT: flash(f'Only the first {BATCH_LIMIT} selected roles were considered.','info')
            st.rerun()
        if row.button('Save selected to tracker',disabled=not chosen):
            added=[j for j in chosen if str(j['id']) not in tracked]
            for j in added: repo.save_to_tracker(p,j['id'])
            flash(f'{len(added)} saved to your tracker; {len(chosen)-len(added)} already tracked.');st.rerun()
        if row.button('Mark this page reviewed',disabled=not any(j['is_new'] for j in shown)):
            repo.mark_reviewed(p,[j['id'] for j in shown]);st.rerun()
        a,b,c=st.columns([1,1.3,1.3],vertical_alignment='bottom')
        batch=a.number_input('Roles to compare',1,BATCH_LIMIT,5)
        if b.button('Compare next unscored roles',disabled=not resume_id or not unscored,use_container_width=True):
            comparison_message(enqueue_batch(p,jobs,resume_id,batch),min(batch,unscored));st.rerun()
        c.button('Open Diagnostics',on_click=navigate,args=('Diagnostics',),use_container_width=True)
        if resume_id: st.caption(f'About {unscored} filtered roles are unscored, including any already queued. Up to {BATCH_LIMIT} per click, within your daily comparison quota.')
        else: st.caption('Choose a resume in the sidebar to compare roles.')

def job_row(p,j,result,app_id,resume_id):
    key=str(j['id']);picked=st.session_state.setdefault('discover_selected',set())
    with st.container(border=True,key='sn_card_job_'+key):
        pick,info,score,act=st.columns([.3,3.4,1.7,2.6])
        st.session_state['pick_'+key]=key in picked
        pick.checkbox('Select '+md(j['title']),key='pick_'+key,on_change=toggle_pick,args=(key,),label_visibility='collapsed')
        info.markdown((':primary-badge[New] ' if j['is_new'] else '')+f"**{md(j['title'])}**  \n{md(j['company'])} · {md(j['location'] or 'Location not disclosed')} · {md(j['salary'] or 'Salary not disclosed')}")
        info.caption(md(j['source'])+(' · Partial description' if j['completeness']!='full' else '')+f" · Checked {j['last_checked']:%b %d}"+(' · In tracker' if app_id else ''))
        score.markdown(alignment_text(result))
        row=act.container(horizontal=True,horizontal_alignment='right')
        if j['original_url']: row.link_button('Posting ↗',j['original_url'])
        if app_id: row.button('Open in Tracker',key='open_'+key,on_click=open_application,args=(app_id,))
        elif row.button('Save',key='save_'+key,help='Save to tracker. This does not mark it applied.'):
            repo.save_to_tracker(p,j['id']);flash('Saved to your tracker.');st.rerun()
        if row.button('Compare',key='compare_'+key,disabled=not resume_id or j['completeness']!='full',help='Compare with the selected resume.'):
            try:
                remember_inputs(enqueue(p,j['version_id'],resume_id),j['version_id'],resume_id)
                st.success('Comparison queued. Open Diagnostics for progress and evidence.')
            except AppError as exc: st.error(str(exc))
        opened=st.session_state.get('discover_open')==key
        row.button('Hide details' if opened else 'Details',key='details_'+key,on_click=toggle_details,args=(key,))
        if opened:
            if result: result_view(result,'job_'+key)
            st.markdown('**Original description**')
            with st.container(height=360,border=True,key='sn_card_body_'+key): st.text(j['body'])
            st.caption('Stored description version '+str(j['version_id']))

def matches(p,resume_id,query):
    jobs=repo.list_jobs(p,query)
    st.subheader(str(len(jobs))+' saved '+('opportunity' if len(jobs)==1 else 'opportunities'))
    if not jobs:
        if query: st.info('No saved roles match the sidebar search. Clear it to see all roles.');return
        st.info('Scan your target companies, run a search, or add a posting. Saved roles appear here.')
        row=st.container(horizontal=True)
        for tab in TABS[1:]: row.button(tab,key='empty_'+tab,on_click=open_discover,args=(tab,))
        return
    fit=repo.fit_by_version(p,resume_id) if resume_id else {}
    tracked={str(a['job_id']):str(a['id']) for a in repo.list_applications(p)}
    filter_bar(jobs)
    state=st.session_state
    if state['discover_order']=='Resume alignment' and not resume_id: st.info('Choose a resume in the sidebar to sort by alignment.')
    found=sort_jobs(filter_jobs(jobs,fit,state['discover_new'],state['discover_company'],state['discover_seniority'],
        state['discover_source'],state['discover_place'],state['discover_min']),fit,state['discover_order'])
    pages=max(1,(len(found)+PAGE_SIZE-1)//PAGE_SIZE)
    state['discover_page']=min(max(state.get('discover_page',1),1),pages)
    a,b=st.columns([3,1],vertical_alignment='bottom')
    start=(state['discover_page']-1)*PAGE_SIZE
    shown=found[start:start+PAGE_SIZE]
    a.caption(f'Showing {start+1 if shown else 0}–{start+len(shown)} of {len(found)} matching roles ({len(jobs)} saved).')
    b.number_input(f'Page of {pages}',1,pages,key='discover_page')
    action_bar(p,found,shown,tracked,fit,resume_id)
    if not shown: st.info('No roles match these filters.')
    for j in shown: job_row(p,j,fit.get(str(j['version_id'])),tracked.get(str(j['id'])),resume_id)
    private_download(p,'Export your jobs as CSV','jobs')

# ---- Target companies -------------------------------------------------------

def target_choice(profiles,key):
    labels=['Senior AI and Forward Deployed roles (default)']+[x['label']+' · '+str(x['id'])[:6] for x in profiles]
    choice=st.selectbox('Match using',labels,key=key)
    return TARGET_FILTERS if choice==labels[0] else profiles[labels.index(choice)-1]['filters']

def scan_summary(results):
    ok=[r for r in results if r['ok']]
    st.subheader('Last scan')
    a,b,c,d=st.columns(4)
    a.metric('Companies read',len(ok));b.metric('Failed',len(results)-len(ok))
    c.metric('Matching roles',sum(r.get('matched',0) for r in ok));d.metric('New roles',sum(r.get('new',0) for r in ok))
    for r in results:
        (st.success if r['ok'] else st.warning)(md(r['company'])+': '+md(r['note']))
    if sum(r.get('new',0) for r in ok): st.button('Show new roles',type='primary',on_click=open_discover,args=('Matches',True))

def target_companies(p,profiles):
    st.caption('Scans run only when you click Scan. Nothing runs on a schedule.')
    watched=repo.list_watchlist(p)
    have={(w['provider'],w['board']) for w in watched}
    missing=[s for s in SUGGESTED_BOARDS if (s[0],s[1]) not in have]
    if st.button(f'Add suggested AI employers ({len(missing)})',disabled=not missing):
        for provider,board,company in missing: repo.add_watch(p,provider,board,company)
        flash(f'Added {len(missing)} suggested employers.');st.rerun()
    with st.form('add_watch',clear_on_submit=True):
        a,b,c=st.columns(3)
        provider=a.selectbox('Board provider',connectors.PROVIDERS)
        board=b.text_input('Board token',help='The employer name in the address of its hosted careers page.')
        company=c.text_input('Company display name')
        if st.form_submit_button('Add to my companies'):
            try:
                connectors.check_board(provider,board);repo.add_watch(p,provider,board,company);flash('Company added.');st.rerun()
            except AppError as exc: st.error(str(exc))
    if not watched:
        st.info('Add employers once, then scan them all for matching roles.');return
    failed=[w for w in watched if scan_failed(w)]
    if failed:
        st.subheader(f'Boards that failed last time ({len(failed)})')
        for w in failed:
            with st.container(border=True,key='sn_card_board_'+str(w['id'])):
                st.warning(md(w['company'])+' · '+w['provider']+' · '+md(w['board'])+': '+md(w['last_note']))
                if confirm_button(st,'Remove this board','drop_'+str(w['id']),'Remove '+md(w['company'])+' from your companies? Saved roles are kept.'):
                    repo.remove_watch(p,w['id']);flash('Company removed.');st.rerun()
    st.subheader(f'Watched companies ({len(watched)})')
    table=pd.DataFrame([dict(company=w['company'],provider=w['provider'],board=w['board'],last_checked=w['last_checked'],
        last_result='Not scanned yet' if not w['last_note'] else ('Failed: ' if scan_failed(w) else '')+w['last_note']) for w in watched])
    compact_dataframe(table,hide_index=True,use_container_width=True)
    filters=target_choice(profiles,'scan_filters')
    per_board=st.slider('Maximum roles saved per company',5,50,25)
    if st.button('Scan all companies',type='primary'):
        with st.spinner('Reading each employer board. This can take a minute or two…'):
            st.session_state['scan_results']=connectors.scan_watchlist(p,filters,per_board)
        st.rerun()
    st.caption('Roles are filtered across the whole board before the per-company limit applies.')
    if st.session_state.get('scan_results'): scan_summary(st.session_state['scan_results'])
    with st.expander('Remove a company'):
        remove=st.selectbox('Company to remove',watched,format_func=lambda w:w['company']+' · '+w['provider'])
        if confirm_button(st,'Remove company','remove_'+str(remove['id']),'Remove '+md(remove['company'])+' from your companies? Saved roles are kept.'):
            repo.remove_watch(p,remove['id']);flash('Company removed.');st.rerun()

# ---- Search and manual import -----------------------------------------------

def search(p,profiles):
    loaded=TARGET_FILTERS
    if profiles:
        labels=[x['label']+' · '+str(x['id'])[:6] for x in profiles]
        choice=st.selectbox('Saved search',['New search']+labels)
        if choice!='New search': loaded=profiles[labels.index(choice)]['filters']
    with st.form('search_preferences'):
        a,b=st.columns(2)
        title=a.text_input('Job titles separated by commas',value=loaded.get('title',''),help='All words of one title must appear, in any order.')
        company=b.text_input('Company',value=loaded.get('company',''))
        a,b=st.columns(2)
        skills=a.text_input('Required skills separated by commas',value=loaded.get('required_skills',''))
        location=b.text_input('Locations separated by semicolons',value=loaded.get('location',''),help='Whole words only. US remote means remote roles open to the United States.')
        a,b=st.columns(2)
        salary=a.number_input('Minimum disclosed USD annual salary',min_value=0,value=int(loaded.get('minimum_salary',0)),step=10000)
        exclude=b.text_input('Exclude words',value=loaded.get('exclude',''))
        unknown=st.checkbox('Include jobs with undisclosed or non-comparable salary',value=loaded.get('include_unknown_salary',True))
        label=st.text_input('Save search as',value='My search')
        row=st.container(horizontal=True)
        run=row.form_submit_button('Search Remotive',type='primary')
        save=row.form_submit_button('Save preferences')
    filters=dict(title=title,company=company,required_skills=skills,location=location,minimum_salary=salary,exclude=exclude,include_unknown_salary=unknown)
    if save:
        repo.save_profile(p,label,filters);flash('Search saved.');st.rerun()
    if run:
        try:
            with st.spinner('Checking the shared source cache and saving matches to your workspace…'):
                outcome=connectors.search_remotive(p,filters)
            st.success(f"Saved {outcome['count']} matches. Source checked {outcome['checked']:%b %d %H:%M UTC}.")
            if outcome['stale']: st.warning('Source unavailable; used a labeled cached snapshot.')
            if outcome['count']: st.button('View saved matches',on_click=open_discover,args=('Matches',))
            else: st.info('No roles matched. Try fewer titles or skills.')
        except AppError as exc: st.error(str(exc))
    st.caption('Remotive public feed is delayed 24 hours. One deployment-wide refresh every six hours. Location/skill filters use posted text; validate restrictions in the original description.')
    for column,(name,url) in zip(st.columns(3),connectors.premium_search_links(title.split(',')[0].strip(),location.split(';')[0].strip()).items()):
        column.link_button('Search '+name,url,use_container_width=True)
    st.caption('Premium portals open in your own browser session. Add the posting under Add a posting; no account cookies or passwords are collected.')

def add_posting(p):
    st.markdown('**Import a premium posting or a job you found**')
    with st.form('manual_import',clear_on_submit=False):
        a,b=st.columns(2)
        jt=a.text_input('Job title');co=b.text_input('Company name')
        source=st.selectbox('Source',['LinkedIn','Ladders','Indeed','Remotive','Employer career page','Manual import'])
        url=st.text_input('Original HTTPS posting link')
        a,b=st.columns(2)
        loc=a.text_input('Posted location');pay=b.text_input('Posted salary with currency and interval')
        body=st.text_area('Full original job description',height=200)
        complete=st.checkbox('This is the complete description',value=True)
        if st.form_submit_button('Import job',type='primary'):
            try:
                repo.import_job(p,jt,co,body,source,url,loc,pay,complete=complete);toast('Job imported')
                st.success('Job imported. It is listed under Matches.')
            except AppError as exc: st.error(str(exc))
    with st.expander('Import once from an employer board'):
        with st.form('employer'):
            provider=st.selectbox('Public employer feed',connectors.PROVIDERS)
            board=st.text_input('Employer board token',placeholder='Use the token from the employer’s hosted careers page')
            only=st.checkbox('Only roles matching the senior AI target filters',value=True)
            if st.form_submit_button('Import up to 50 employer postings'):
                try:
                    with st.spinner('Loading the public employer feed…'): outcome=connectors.employer_feed(p,provider,board,TARGET_FILTERS if only else None)
                    st.success(f"{outcome['matched']} of {outcome['total']} postings matched; {outcome['count']} saved.")
                except AppError as exc: st.error(str(exc))

def discover(p,resumes,selected_resume,query):
    st.header('Discover your next opportunity')
    st.caption('Automatic public feeds. Assisted premium searches. Every job and comparison stays in your workspace.')
    show_flash()
    profiles=repo.list_profiles(p)
    found,target,searching,adding=st.tabs(TABS,key='discover_tab',on_change='rerun')
    # Matches is filled last so roles saved by the other tabs appear in the same run.
    with target: target_companies(p,profiles)
    with searching: search(p,profiles)
    with adding: add_posting(p)
    with found: matches(p,selected_resume,query)
