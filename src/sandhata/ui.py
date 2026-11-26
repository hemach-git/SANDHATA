import html,json,time,uuid,os
from datetime import datetime,timedelta,timezone,date
from io import StringIO
from zoneinfo import ZoneInfo
import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components
from sqlalchemy.exc import SQLAlchemyError
from .config import ROOT,DATA,ISSUER,MODEL,AppError
from .db import resolve_identity,transaction,rows,one,scoped
from . import repository as repo
from . import identity as auth
from . import connectors
from .worker import enqueue,enqueue_batch
from .targeting import TARGET_FILTERS,SUGGESTED_BOARDS,priority
from .agenda import build_agenda,follow_up_calendar
from .presentation import configure_visuals,landing,workspace_brand,display_name,compact_chart

def safe_csv(records):
    frame=pd.DataFrame(records)
    for col in frame.select_dtypes(include='object'):
        frame[col]=frame[col].map(lambda v:"'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v)
    return frame.to_csv(index=False).encode('utf-8-sig')

def compact_dataframe(data,**kwargs):
    return st.dataframe(data,height=min(320,max(100,38+32*len(data))),**kwargs)

def toast(message): st.toast(message)

def private_download(p,label,kind,identifier='',params=''):
    cache=st.session_state.get('download_capability')
    if not cache or time.time()-cache['created']>840:
        cache=dict(token=auth.issue_capability(p),created=time.time());st.session_state['download_capability']=cache
    url=os.getenv('SANDHATA_API_BASE_URL','http://localhost:8851')+'/download/'+kind+('/'+str(identifier) if identifier else '')+params
    # Bearer token is in a private authenticated component, never in a URL, HTML attribute, or access log.
    script='''<button id="download" style="font:700 13px sans-serif;padding:7px 12px;border:2px solid #D8B65A;border-radius:8px;background:white;color:#164B99;cursor:pointer">LABEL</button><span id="message" style="font:12px sans-serif;margin-left:8px"></span>
    <style>button:hover{background:#F4C430!important;color:#123263!important}button:focus-visible{outline:3px solid #164B99;outline-offset:2px}</style><script>document.getElementById('download').onclick=async()=>{const m=document.getElementById('message');m.textContent='Authorizing…';try{const r=await fetch(URL,{headers:{Authorization:'Bearer '+TOKEN}});if(!r.ok)throw new Error('Access expired or file unavailable. Refresh this page.');const blob=await r.blob();const a=document.createElement('a');const u=URL_OBJECT.createObjectURL(blob);a.href=u;a.download=(r.headers.get('content-disposition')||'').split('filename="')[1]?.split('"')[0]||'SANDHATA-download';a.click();setTimeout(()=>URL_OBJECT.revokeObjectURL(u),1000);m.textContent='Downloaded';}catch(e){m.textContent=e.message;}};</script>'''
    script=script.replace('LABEL',html.escape(label)).replace('URL_OBJECT','window.URL').replace('URL,',json.dumps(url)+',').replace('TOKEN',json.dumps(cache['token']))
    if st.session_state.get('sn_dark'):
        script='<style>body{background:#152238;color:#EEF3FC}#download{background:#152238!important;color:#9BC2FF!important}#download:hover{background:#F8E8B4!important;color:#123263!important}</style>'+script
    components.html(script,height=48)

def result_view(result):
    st.caption('Experimental AI comparison · Review the quoted evidence before using this result.')
    a,b,c=st.columns(3)
    a.metric('Resume alignment',f"{result['score']:.0f}%" if result['score'] is not None else 'Withheld')
    b.metric('Evidence coverage',f"{result['coverage']:.0f}%")
    c.metric('Assessment','Provisional' if result['provisional'] else 'Evidence validated')
    st.caption(result['meaning']+' Literal quotes are verified; review whether they substantively support each judgment.')
    for flag in result.get('eligibility_flags',[]): st.warning(flag)
    for i,r in enumerate(result['requirements']):
        with st.expander(f"{r['status'].replace('_',' ').title()} · {r['requirement_quote'][:110]}"):
            st.write('**Job requirement**');st.text(r['requirement_quote'])
            st.write('**Selected resume evidence**');st.text(r['resume_quote'] or 'Not evidenced in this resume.')
            st.write(r['rationale']);st.caption(f"Category: {r['category']} · Job offset {r['job_offset']} · Resume offset {r['resume_offset']}")

def today_page(p,selected_resume):
    st.header('Today')
    st.caption('Follow-ups, quiet applications and new matches from your saved records.')
    now=datetime.now(ZoneInfo(p.timezone)).date()
    applications=repo.list_applications(p)
    plan=build_agenda(applications,now)
    jobs=repo.list_jobs(p)
    new=[j for j in jobs if j['is_new']]
    a,b,c,d=st.columns(4)
    a.metric('Overdue follow-ups',len(plan['overdue']));b.metric('Due in 7 days',len(plan['upcoming']))
    c.metric('Quiet 14+ days',len(plan['stale']));d.metric('New matches',len(new))
    columns=['title','company','status','follow_up','recruiter','notes']
    for key,label in [('overdue','Overdue'),('upcoming','Coming up'),('stale','No recent update and no follow-up date')]:
        if plan[key]:
            st.subheader(label)
            compact_dataframe(pd.DataFrame(plan[key])[columns],hide_index=True,use_container_width=True)
    if not any(plan.values()): st.info('Nothing is due. Add follow-up dates in Tracker to see them here.')
    dated=[x for x in plan['overdue']+plan['upcoming']]
    if dated: st.download_button('Add these follow-ups to my calendar (.ics)',follow_up_calendar(dated,datetime.now(timezone.utc)),'SANDHATA_FOLLOW_UPS.ics','text/calendar')
    if selected_resume:
        fit=repo.fit_by_version(p,selected_resume)
        tracked={str(x['job_id']) for x in applications}
        ranked=[(fit[str(j['version_id'])],j) for j in jobs if str(j['id']) not in tracked and fit.get(str(j['version_id']),{}).get('score') is not None]
        if ranked:
            st.subheader('Strongest compared roles not yet tracked')
            ranked.sort(key=lambda pair:(not pair[0]['provisional'],pair[0]['score'],pair[0]['coverage']),reverse=True)
            compact_dataframe(pd.DataFrame([dict(alignment=r['score'],coverage=r['coverage'],provisional=r['provisional'],title=j['title'],company=j['company'],location=j['location'],posting=j['original_url']) for r,j in ranked[:10]]),
                hide_index=True,use_container_width=True,column_config={'posting':st.column_config.LinkColumn('posting')})
    if new:
        st.subheader('Newest matches')
        top=sorted(new,key=priority,reverse=True)[:10]
        compact_dataframe(pd.DataFrame([dict(title=j['title'],company=j['company'],location=j['location'],posting=j['original_url']) for j in top]),
            hide_index=True,use_container_width=True,column_config={'posting':st.column_config.LinkColumn('posting')})
        st.caption('Open Discover to compare these roles and mark them reviewed.')

def target_choice(profiles,key):
    labels=['Senior AI and Forward Deployed roles (default)']+[x['label']+' · '+str(x['id'])[:6] for x in profiles]
    choice=st.selectbox('Match using',labels,key=key)
    return TARGET_FILTERS if choice==labels[0] else profiles[labels.index(choice)-1]['filters']

def watchlist(p,profiles):
    with st.expander('Target companies · scan employer boards',expanded=True):
        watched=repo.list_watchlist(p)
        if st.button('Add suggested AI employers'):
            for provider,board,company in SUGGESTED_BOARDS: repo.add_watch(p,provider,board,company)
            st.rerun()
        with st.form('add_watch',clear_on_submit=True):
            a,b,c=st.columns(3)
            provider=a.selectbox('Board provider',connectors.PROVIDERS)
            board=b.text_input('Board token')
            company=c.text_input('Company display name')
            if st.form_submit_button('Add to my companies'):
                connectors.check_board(provider,board);repo.add_watch(p,provider,board,company);st.rerun()
        if not watched:
            st.info('Add employers once, then scan them all for matching roles.');return
        compact_dataframe(pd.DataFrame(watched)[['company','provider','board','last_checked','last_note']],hide_index=True,use_container_width=True)
        a,b=st.columns([3,1])
        remove=a.selectbox('Company to remove',watched,format_func=lambda w:w['company']+' · '+w['provider'])
        if b.button('Remove company'): repo.remove_watch(p,remove['id']);st.rerun()
        filters=target_choice(profiles,'scan_filters')
        per_board=st.slider('Maximum roles saved per company',5,50,25)
        if st.button('Scan all companies',type='primary'):
            with st.spinner('Reading each employer board. This can take a minute or two…'):
                st.session_state['scan_results']=connectors.scan_watchlist(p,filters,per_board)
            st.rerun()
        for r in st.session_state.get('scan_results',[]):
            (st.success if r['ok'] else st.warning)(r['company']+': '+r['note'])
        st.caption('Scans run when you click. Roles are filtered across the whole board before the per-company limit applies.')

def discover(p,resumes,selected_resume,query):
    st.header('Discover your next opportunity')
    st.caption('Automatic public feeds. Assisted premium searches. Every job and comparison stays in your workspace.')
    profiles=repo.list_profiles(p)
    with st.expander('Search preferences',expanded=True):
        loaded=TARGET_FILTERS
        if profiles:
            choice=st.selectbox('Saved search', ['New search']+[x['label']+' · '+str(x['id'])[:6] for x in profiles])
            if choice!='New search': loaded=profiles[[x['label']+' · '+str(x['id'])[:6] for x in profiles].index(choice)]['filters']
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
            run=st.form_submit_button('Search Remotive',type='primary')
            save=st.form_submit_button('Save preferences')
        filters=dict(title=title,company=company,required_skills=skills,location=location,minimum_salary=salary,exclude=exclude,include_unknown_salary=unknown)
        if save:
            repo.save_profile(p,label,filters);toast('Search saved')
        if run:
            with st.spinner('Checking the shared source cache and saving matches to your workspace…'):
                outcome=connectors.search_remotive(p,filters)
            st.success(f"Saved {outcome['count']} matches. Source checked {outcome['checked']:%b %d %H:%M UTC}.")
            if outcome['stale']: st.warning('Source unavailable; used a labeled cached snapshot.')
        st.caption('Remotive public feed is delayed 24 hours. One deployment-wide refresh every six hours. Location/skill filters use posted text; validate restrictions in the original description.')
        cols=st.columns(3)
        for col,(label_,url) in zip(cols,connectors.premium_search_links(title.split(',')[0].strip(),location.split(';')[0].strip()).items()): col.link_button('Search '+label_,url,use_container_width=True)
        st.caption('Premium portals open in your own browser session. Import the posting below; no account cookies or passwords are collected.')
    watchlist(p,profiles)
    with st.expander('Import a premium posting or a job you found'):
        with st.form('manual_import',clear_on_submit=True):
            a,b=st.columns(2)
            jt=a.text_input('Job title');co=b.text_input('Company name')
            source=st.selectbox('Source',['LinkedIn','Ladders','Indeed','Remotive','Employer career page','Manual import'])
            url=st.text_input('Original HTTPS posting link')
            a,b=st.columns(2)
            loc=a.text_input('Posted location');pay=b.text_input('Posted salary with currency and interval')
            body=st.text_area('Full original job description',height=200)
            complete=st.checkbox('This is the complete description',value=True)
            if st.form_submit_button('Import job',type='primary'):
                repo.import_job(p,jt,co,body,source,url,loc,pay,complete=complete);toast('Job imported');st.rerun()
    with st.expander('Connect an employer board'):
        with st.form('employer'):
            provider=st.selectbox('Public employer feed',['Greenhouse','Lever','Ashby'])
            board=st.text_input('Employer board token',placeholder='Use the token from the employer’s hosted careers page')
            only=st.checkbox('Only roles matching the senior AI target filters',value=True)
            if st.form_submit_button('Import up to 50 employer postings'):
                with st.spinner('Loading the public employer feed…'): outcome=connectors.employer_feed(p,provider,board,TARGET_FILTERS if only else None)
                st.success(f"{outcome['matched']} of {outcome['total']} postings matched; {outcome['count']} saved.")
    jobs=repo.list_jobs(p,query)
    st.subheader(str(len(jobs))+' saved '+('opportunity' if len(jobs)==1 else 'opportunities'))
    if not jobs:
        st.info('Run a public search or import your first posting. Your saved jobs will appear here.');return
    private_download(p,'Export your jobs as CSV','jobs')
    fit=repo.fit_by_version(p,selected_resume) if selected_resume else {}
    a,b,c=st.columns(3)
    order=a.selectbox('Sort by',['Role priority','Resume alignment','Newest saved'])
    new_only=b.checkbox(f"New only ({sum(j['is_new'] for j in jobs)})")
    if new_only: jobs=[j for j in jobs if j['is_new']]
    # jobs arrive newest first; sorting is stable, so ties keep that order.
    if order=='Role priority': jobs=sorted(jobs,key=priority,reverse=True)
    if order=='Resume alignment':
        jobs=sorted(jobs,key=lambda j:(fit.get(str(j['version_id']),{}).get('score') is not None,fit.get(str(j['version_id']),{}).get('score') or 0),reverse=True)
        if not selected_resume: st.info('Choose a resume in the sidebar to sort by alignment.')
    pages=max(1,(len(jobs)+24)//25)
    number=c.number_input(f'Page of {pages}',1,pages,1)
    shown=jobs[(number-1)*25:number*25]
    a,b,c=st.columns(3)
    batch=a.number_input('Roles to compare',1,25,5)
    if b.button('Compare next unscored roles',disabled=not selected_resume,use_container_width=True):
        outcome=enqueue_batch(p,jobs,selected_resume,batch)
        st.success(f"{outcome['queued']} comparisons queued in the order shown. Each runs on your local model; follow progress in Diagnostics.")
        if outcome['stopped']: st.warning(outcome['stopped'])
    if c.button('Mark this page reviewed',disabled=not any(j['is_new'] for j in shown),use_container_width=True):
        repo.mark_reviewed(p,[j['id'] for j in shown]);st.rerun()
    if not shown: st.info('No roles match this view.')
    for j in shown:
        with st.container(border=True):
            st.markdown(f"### {html.escape(j['title'])}")
            score=fit.get(str(j['version_id']))
            badges=(['New'] if j['is_new'] else [])+([f"Resume alignment {score['score']:.0f}%"+(' (provisional)' if score['provisional'] else '')] if score and score['score'] is not None else [])
            if badges: st.markdown('**'+' · '.join(badges)+'**')
            st.write(f"**{j['company']}** · {j['location'] or 'Location not disclosed'} · {j['salary'] or 'Salary not disclosed'}")
            st.caption(f"Source: {j['source']} · Description: {j['completeness']} · Last checked: {j['last_checked']:%b %d %Y}")
            a,b,c=st.columns(3)
            if j['original_url']: a.link_button('Original posting ↗',j['original_url'],use_container_width=True)
            if b.button('Save to tracker',key='save_'+str(j['id']),use_container_width=True): repo.save_to_tracker(p,j['id']);toast('Saved to your tracker')
            if c.button('Compare selected resume',key='compare_'+str(j['id']),disabled=not selected_resume,use_container_width=True):
                task=enqueue(p,j['version_id'],selected_resume);st.success('Comparison queued. Open Diagnostics for progress and evidence.');st.caption('Run '+task)
            with st.expander('Full description and evidence'):
                st.text(j['body'])
                st.caption('Stored description version '+str(j['version_id']))
                with transaction(p) as conn:
                    assessments=rows(conn,'SELECT id,result,created_at FROM assessments WHERE job_version_id=%(job)s::uuid AND (%(resume)s::uuid IS NULL OR resume_id=%(resume)s::uuid) ORDER BY created_at DESC LIMIT 1',dict(job=str(j['version_id']),resume=str(selected_resume) if selected_resume else None))
                if assessments: result_view(assessments[0]['result'])

def resume_library(p,query):
    st.header('Your resume library')
    st.caption('Only you can access your original files and parsed evidence. Uploading creates an immutable version.')
    with st.form('resume_upload',clear_on_submit=True):
        file=st.file_uploader('PDF or DOCX · text documents up to 10 MB',type=['pdf','docx'])
        label=st.text_input('Version label',placeholder='AI Engineering · October 2026')
        if st.form_submit_button('Upload and parse',type='primary'):
            if file is None: raise AppError('Choose a document first.')
            repo.upload_resume(p,file.getvalue(),file.name,label);toast('Resume version saved');st.rerun()
    for r in repo.list_resumes(p):
        if query and query.lower() not in r['label'].lower(): continue
        with st.expander(r['label']+' · '+r['created_at'].strftime('%b %d %H:%M UTC')):
            detail=repo.resume_detail(p,r['id'])
            st.text(detail['body'])
            st.caption('Parser: '+detail['parser_version']+' · Content fingerprint '+r['file_hash'][:12])
            private_download(p,'Download your original','resume',r['id'])
            confirm=st.checkbox('Delete this version and its comparison evidence',key='deleteconfirm_'+str(r['id']))
            if st.button('Delete resume',key='delete_'+str(r['id']),disabled=not confirm): repo.delete_resume(p,r['id']);st.rerun()

def reset_tracker_draft(prefix):
    """Discard browser draft widget values only; never call storage APIs."""
    for key in list(st.session_state):
        if key.startswith(prefix): del st.session_state[key]

def reset_application_form(prefix,app_id):
    reset_tracker_draft(prefix)
    version_key='tracker_form_version_'+app_id
    st.session_state[version_key]=st.session_state.get(version_key,0)+1
    st.session_state['tracker_feedback_'+app_id]='Unsaved changes discarded. The form now shows the stored application. Saved history was not changed.'

def new_application(p):
    from .tracker_import import WORK_ARRANGEMENTS,JOB_TYPES
    prefix='tracker_new_'
    if st.session_state.pop('tracker_clear_new',False): reset_tracker_draft(prefix)
    message=st.session_state.pop('tracker_new_success',None)
    if message: st.success(message)
    with st.expander('New application · enter manually',expanded=False):
        st.caption('Paste the LinkedIn posting link and enter the role and employer. Start with Saved for a new lead; choose Applied only after submitting. Reset draft clears these fields without changing saved trackers or history.')
        with st.form('new_application'):
            a,b=st.columns(2)
            title=a.text_input('Job title *',max_chars=300,key=prefix+'title')
            company=b.text_input('Employer *',max_chars=200,key=prefix+'company')
            url=st.text_input('Posting URL (optional)',placeholder='https://www.linkedin.com/jobs/view/...',key=prefix+'url')
            a,b=st.columns(2)
            location=a.text_input('Location',max_chars=400,key=prefix+'location',placeholder='Charlotte, NC or Remote')
            arrangement=b.selectbox('Work arrangement',WORK_ARRANGEMENTS,format_func=lambda value:value or 'Not specified',key=prefix+'arrangement')
            a,b=st.columns(2)
            salary_description=a.text_input('Salary Description',max_chars=400,key=prefix+'salary',placeholder='$150k-$180k base + bonus, or $95/hour W2')
            job_type=b.selectbox('Job Type',JOB_TYPES,format_func=lambda value:value or 'Not specified',key=prefix+'job_type')
            a,b,c=st.columns(3)
            recruiter=c.text_input('Recruiter',key=prefix+'recruiter',max_chars=400,placeholder='Name or agency')
            source=a.selectbox('Source',['LinkedIn','Recruiter','Employer career page','Referral','Other'],key=prefix+'source')
            status=b.selectbox('Initial status',repo.STATUSES,key=prefix+'status')
            a,b=st.columns(2)
            applied=a.date_input('Application submitted on (optional)',value=None,max_value=datetime.now(ZoneInfo(p.timezone)).date(),key=prefix+'applied',help='Leave blank if not submitted or the date is unknown.')
            follow=b.date_input('Next follow-up (optional)',value=None,key=prefix+'follow')
            a,b=st.columns(2)
            description=a.text_area('Posting description (optional)',height=110,max_chars=150000,key=prefix+'description')
            notes=b.text_area('Notes / recruiter message',height=110,max_chars=10000,key=prefix+'notes')
            a,b=st.columns(2)
            save=a.form_submit_button('Save new application',type='primary')
            b.form_submit_button('Reset draft',on_click=reset_tracker_draft,args=(prefix,))
        if save:
            try:
                when=datetime.combine(applied,datetime.min.time(),tzinfo=ZoneInfo(p.timezone)) if applied else None
                result=repo.create_manual_application(p,title,company,status,url,location,arrangement,notes,description,when,follow,source,salary_description=salary_description,job_type=job_type,recruiter=recruiter)
                if result['added']:
                    st.session_state['tracker_clear_new']=True
                    st.session_state['tracker_new_success']='Application saved. The new-entry form is ready for another role. Clear search or status filters if the new item is hidden.'
                    st.rerun()
                else: st.warning('This application is already tracked. Existing data and history were preserved. Find it below to update it, or reset this draft.')
            except AppError as exc: st.error(str(exc))

def tracker(p,resumes,query):
    st.header('Application tracker')
    st.caption('Opening a posting never marks it applied. Record submissions and event dates explicitly.')
    search_col,clear_col=st.columns([4,1])
    tracker_query=search_col.text_input('Search applications',key='tracker_search',placeholder='Recruiter, company, city, or role',help='Case-insensitive partial matches. Combine words, such as Anthony Charlotte. Also searches notes. Sidebar search and status filters still apply.')
    def clear_tracker_filters():
        st.session_state['tracker_search']=''
        st.session_state['tracker_status_filter']=[]
    clear_col.button('Clear search / filters',on_click=clear_tracker_filters)
    new_application(p)
    from .tracker_import import TEMPLATE,parse_tracker
    with st.expander('Upload Tracker · one row or bulk CSV'):
        st.caption('Required: title, company. Optional columns are in the template. Dates: YYYY-MM-DD; timestamps may include a timezone (otherwise UTC). Existing uploaded postings are skipped without overwriting edits. Records have no automatic expiry and persist until an administrator deletes them, including through account erasure. Keep database backups for recovery.')
        st.download_button('Download upload template',TEMPLATE,'SANDHATA_TRACKER_TEMPLATE.csv','text/csv')
        upload=st.file_uploader('Upload Tracker',type=['csv'],key='tracker_upload')
        if upload is not None:
            data=upload.getvalue()
            try:
                preview=parse_tracker(data,repo.STATUSES)
                st.write(f'{len(preview)} validated rows')
                compact_dataframe(pd.DataFrame(preview),hide_index=True,use_container_width=True)
                if st.button('Import validated trackers',type='primary'):
                    result=repo.import_tracker(p,data)
                    st.success(f"Imported {result['added']} trackers; skipped {result['skipped']} duplicates.")
            except AppError as exc: st.error(str(exc))
    private_download(p,'Export your tracker','tracker')
    items=repo.list_applications(p,' '.join(filter(None,[query,tracker_query])))
    statuses=st.multiselect('Filter by status',repo.STATUSES,key='tracker_status_filter')
    if statuses: items=[item for item in items if item['status'] in statuses]
    st.caption(f'{len(items)} trackers match your search and filters.')
    if not items: st.info('No matching applications. Clear tracker search / filters or the sidebar search to see more, or add a new application.');return
    compact_dataframe(pd.DataFrame(items)[['title','company','location','work_arrangement','salary_description','job_type','recruiter','status','applied_at','follow_up','notes']],use_container_width=True,hide_index=True)
    chosen=st.selectbox('Update an application',items,format_func=lambda a:f"{a['title']} · {a['company']}")
    rid=str(chosen['id'])
    detail=repo.job_detail(p,chosen['job_id'])
    with st.expander('Posting details'):
        st.write(detail['title']+' · '+detail['company'])
        if detail['original_url']: st.link_button('Open original posting',detail['original_url'])
        st.write('Salary Description: '+(detail.get('salary') or 'Not specified'))
        st.write('Job Type: '+(detail.get('job_type') or 'Not specified'))
        st.write('Recruiter: '+(chosen.get('recruiter') or 'Not specified'))
        st.text(detail['body'])
    edit_prefix='tracker_edit_'+rid+'_'
    feedback=st.session_state.pop('tracker_feedback_'+rid,None)
    if feedback: st.info(feedback)
    st.caption('Save update edits this application. Status history gets a new row only when Status changes. Reset unsaved changes reloads stored values without deleting anything.')
    with st.form('tracker_'+rid+'_'+str(st.session_state.get('tracker_form_version_'+rid,0))):
        a,b=st.columns(2)
        status=a.selectbox('Status',repo.STATUSES,index=repo.STATUSES.index(chosen['status']),key=edit_prefix+'status')
        event_date=b.date_input('Event date',key=edit_prefix+'event',value=datetime.now(ZoneInfo(p.timezone)).date(),max_value=datetime.now(ZoneInfo(p.timezone)).date())
        a,b=st.columns(2)
        resume=a.selectbox('Resume used for this application',[None]+resumes,key=edit_prefix+'resume',format_func=lambda r:'Keep existing / not recorded' if r is None else r['label'])
        recruiter=b.text_input('Recruiter',value=chosen.get('recruiter',''),key=edit_prefix+'recruiter',max_chars=400)
        a,b=st.columns(2)
        location=a.text_input('Location',value=chosen['location'],key=edit_prefix+'location',max_chars=400,placeholder='Charlotte, NC or Remote')
        from .tracker_import import WORK_ARRANGEMENTS,work_arrangement as normalize_arrangement
        try: current_arrangement=normalize_arrangement(chosen['work_arrangement'])
        except ValueError: current_arrangement=''
        arrangement=b.selectbox('Work arrangement',WORK_ARRANGEMENTS,index=WORK_ARRANGEMENTS.index(current_arrangement),key=edit_prefix+'arrangement',format_func=lambda value:value or 'Not specified')
        from .tracker_import import JOB_TYPES
        a,b=st.columns(2)
        salary_description=a.text_input('Salary Description',value=chosen.get('salary_description',''),key=edit_prefix+'salary',max_chars=400)
        stored_type=chosen.get('job_type','')
        job_type=b.selectbox('Job Type',JOB_TYPES,index=JOB_TYPES.index(stored_type) if stored_type in JOB_TYPES else 0,key=edit_prefix+'job_type',format_func=lambda value:value or 'Not specified')
        a,b=st.columns([2,1])
        notes=a.text_area('Your notes',height=110,value=chosen['notes'],key=edit_prefix+'notes')
        follow=b.date_input('Next follow-up',value=chosen['follow_up'],key=edit_prefix+'follow')
        a,b=st.columns(2)
        save_update=a.form_submit_button('Save update',type='primary')
        b.form_submit_button('Reset unsaved changes',on_click=reset_application_form,args=(edit_prefix,rid))
        if save_update:
            when=datetime.combine(event_date,datetime.min.time(),tzinfo=ZoneInfo(p.timezone)).astimezone(timezone.utc)
            result=repo.update_application(p,chosen['id'],status,notes,when,str(uuid.uuid4()),resume['id'] if resume else None,follow,location=location,work_arrangement=arrangement,salary_description=salary_description,job_type=job_type,recruiter=recruiter)
            st.session_state['tracker_feedback_'+rid]={'unchanged':'No changes to save. No records or history rows were added.','details_updated':'Application details saved. Status history was unchanged.','status_changed':'Application saved and status change recorded once.'}[result]
            st.rerun()
    st.subheader('Status history')
    st.caption('Each row is a recorded status event for this application, not a duplicate application. Earlier history is preserved.')
    compact_dataframe(repo.application_history(p,chosen['id']),use_container_width=True,hide_index=True)
    if p.role=='admin':
        with st.expander('Administrator · permanently delete this tracker'):
            reason=st.text_input('Deletion reason',key='tracker_delete_reason_'+rid)
            confirmed=st.checkbox('Permanently delete this tracker and its status history',key='tracker_delete_confirm_'+rid)
            if st.button('Delete tracker',disabled=not confirmed,key='tracker_delete_'+rid):
                repo.delete_tracker(p,rid,reason);toast('Tracker deleted');st.rerun()

def insights(p):
    st.header('Your search insights')
    a,b=st.columns(2)
    start=a.date_input('Applied cohort from',date.today()-timedelta(days=90));end=b.date_input('Through',date.today())
    if end<start: raise AppError('The end date must be on or after the start date.')
    metrics=repo.tracker_metrics(p,start,end);cohort=metrics['cohort'];n=len(cohort)
    interview=sum(bool(x['interview']) for x in cohort);offer=sum(bool(x['offer']) for x in cohort)
    a,b,c=st.columns(3);a.metric('Applications in cohort',n);b.metric('Reached interview',f'{interview}/{n}');c.metric('Recorded offer',f'{offer}/{n}')
    st.caption(f'Applied-date cohort in {p.timezone}. Later recorded events are observed through now. Small samples do not establish which resume or source causes better outcomes.')
    if n<10: st.info('Small sample: fewer than ten applications in this cohort.')
    a,b=st.columns(2)
    if metrics['current']:
        a.plotly_chart(compact_chart(px.pie(pd.DataFrame(metrics['current']),names='status',values='n',hole=.65,title='Current pipeline · all saved applications')),use_container_width=True,theme=None)
    if metrics['weekly']:
        b.plotly_chart(compact_chart(px.line(pd.DataFrame(metrics['weekly']).assign(week=lambda d:pd.to_datetime(d['week']).dt.strftime('%b %d, %Y')),x='week',y='applications',markers=True,title='Weekly applications')),use_container_width=True,theme=None)
    progression_col,gap_col=st.columns(2) if n and metrics['gaps'] else (st.container(),st.container())
    if n:
        with st.expander('Application report details'):
            compact_dataframe(pd.DataFrame(cohort)[['title','company','location','work_arrangement','salary_description','job_type','recruiter','applied_at']],hide_index=True,use_container_width=True)
        progression_col.plotly_chart(compact_chart(px.funnel(pd.DataFrame({'Stage':['Applied','Interview','Offer'],'Applications':[n,interview,offer]}),x='Applications',y='Stage',title='Observed cohort progression'),rows=3),use_container_width=True,theme=None)
        frame=pd.DataFrame(cohort)
        st.subheader('Source and resume outcomes')
        a,b=st.columns(2)
        a.table(frame.groupby('source').agg(applications=('id','count'),interviews=('interview','sum'),offers=('offer','sum')).reset_index())
        frame['resume_label']=frame['resume_label'].fillna('Not recorded')
        b.table(frame.groupby('resume_label').agg(applications=('id','count'),interviews=('interview','sum'),offers=('offer','sum')).reset_index())
        private_download(p,'Export applied cohort','cohort',params=f'?start={start.isoformat()}&end={end.isoformat()}')
    if metrics['gaps']:
        gaps=pd.DataFrame(metrics['gaps'],columns=['Requirement not evidenced','Count'])
        gap_col.plotly_chart(compact_chart(px.bar(gaps,x='Count',y='Requirement not evidenced',orientation='h',title='Frequently not evidenced requirements'),rows=len(gaps)),use_container_width=True,theme=None)
    if not n and not metrics['current']: st.info('Your charts will populate from saved jobs and recorded application events.')

def diagnostics(p):
    st.header('Your runs and evidence')
    if st.button('Refresh run status',type='primary'): st.rerun()
    heartbeat=DATA/'worker_heartbeat'
    if heartbeat.exists(): st.caption('Worker heartbeat: '+heartbeat.read_text(encoding='utf-8'))
    else: st.warning('No worker heartbeat. Start the comparison worker using the project startup script.')
    for task in repo.tasks(p):
        with st.expander(f"{task['state'].title()} · {str(task['id'])[:12]} · {task['created_at']:%b %d %H:%M}"):
            if task['error_code']: st.warning(task['error_code']+' · Retry from Discover after checking the model and selected files.')
            if task['state'] in ('queued','running') and st.button('Cancel comparison',key='cancel'+str(task['id'])):
                from .worker import cancel_task
                cancel_task(p,task['id']);st.rerun()
            with st.expander('Run execution details'):
                st.json(task['trace'])
            if task['result_id']: result_view(repo.assessment_detail(p,task['result_id'])['result'])
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

def admin_console(p):
    # Rechecks role in every service; the navigation check is only presentation.
    st.header('Administrator console')
    st.caption('Manage user access, usage, system health and housekeeping.')
    tabs=st.tabs(['Users','Invitations','Usage and health','Audit','Housekeeping'])
    with tabs[0]:
        accounts=auth.list_accounts(p)
        compact_dataframe([{k:str(v) if isinstance(v,uuid.UUID) else v for k,v in row.items()} for row in accounts],use_container_width=True,hide_index=True)
        chosen=st.selectbox('Manage account',accounts,format_func=lambda u:u['display_name']+' · '+u['email'])
        with st.form('account_edit'):
            a,b,c=st.columns(3)
            role=a.selectbox('Role',['member','admin'],index=['member','admin'].index(chosen['role']))
            state=b.selectbox('State',['active','suspended'],index=0 if chosen['state']=='active' else 1)
            quota=c.number_input('Comparisons per UTC day',1,1000,value=chosen['quota'])
            reason=st.text_input('Reason for account change')
            if st.form_submit_button('Update account',type='primary'):
                auth.change_account(p,chosen['user_id'],role,state,quota,reason);toast('Account updated; sessions and task authority revoked');st.rerun()
        st.caption('At least one active administrator must remain. Passwords and MFA are managed by the identity provider, not this application.')
    with tabs[1]:
        with st.form('invite'):
            a,b=st.columns(2)
            email=a.text_input('Exact verified identity-provider email')
            role=b.selectbox('Invited role',['member','admin'])
            if st.form_submit_button('Create 48-hour invitation',type='primary'):
                st.code(auth.invite(p,email,role));st.info('Copy this code securely to the intended user. No email has been sent.')
        invitations=auth.list_invitations(p)
        compact_dataframe([{k:str(v) if isinstance(v,uuid.UUID) else v for k,v in row.items()} for row in invitations],use_container_width=True,hide_index=True)
        pending=[i for i in invitations if not i['revoked'] and not i['redeemed_at']]
        if pending:
            revoke=st.selectbox('Invitation to revoke',pending,format_func=lambda i:i['email_hint']+' · '+str(i['id'])[:8])
            if st.button('Revoke selected invitation'):
                auth.revoke_invitation(p,revoke['id']);st.rerun()
        st.caption('For the local pilot, identity users are provisioned in Keycloak first. Only an intended verified identity can redeem an invitation.')
    with tabs[2]:
        metrics=auth.admin_metrics(p)
        a,b,c,d=st.columns(4)
        a.metric('Users',metrics['members']);b.metric('Active',metrics['active']);c.metric('Queued / running',metrics['queued']);d.metric('Failures · 24 h',metrics['failed'])
        compact_dataframe(metrics['usage'],use_container_width=True,hide_index=True)
        st.caption('Resource usage and system health. Model: '+MODEL)
        if metrics['public_cache_age_seconds'] is not None: st.caption(f"Public source cache age: {float(metrics['public_cache_age_seconds'])/3600:.1f} hours")
        heartbeat=DATA/'worker_heartbeat'
        if heartbeat.exists(): st.write('Worker heartbeat',heartbeat.read_text(encoding='utf-8'))
        report=ROOT/'runtime/last_backup.json'
        if report.exists():
            backup=json.loads(report.read_text(encoding='utf-8'))
            st.success('Backup and restore verification recorded')
            st.caption('Last verified: '+backup.get('created_at','Not recorded'))
            st.caption('Original files verified: '+str(backup.get('originals',0)))
        else: st.warning('No verified backup record. Use the operator backup script before shared deployment.')
    with tabs[3]:
        events=auth.audit_events(p)
        compact_dataframe(events,use_container_width=True,hide_index=True)
        private_download(p,'Export safe audit metadata','audit')
    with tabs[4]:
        kind=st.selectbox('Maintenance job',['expired_invitations','old_tasks','cancel_revoked_tasks','erase_account'])
        target=None
        if kind=='erase_account':
            target=st.selectbox('Account to erase',accounts,format_func=lambda u:u['display_name']+' · '+str(u['user_id']))['user_id']
            st.warning('Erasure removes this member’s active career records. Backup tombstones remain for restore protection.')
        if st.button('Preview affected records'):
            st.session_state['maintenance_preview']=auth.maintenance(p,kind,target,True)
        preview=st.session_state.get('maintenance_preview')
        if preview and preview['kind']==kind and str(preview.get('target'))==str(target):
            st.json(preview)
            reason=st.text_input('Maintenance reason')
            confirmation=st.checkbox('I reviewed the scope and want to execute this maintenance')
            second=True
            if kind=='erase_account': second=st.text_input('Type ERASE to confirm permanent removal')=='ERASE'
            if st.button('Execute confirmed maintenance',disabled=not(confirmation and second),type='primary'):
                result=auth.maintenance(p,kind,target,False,preview['count'],str(uuid.uuid4()),reason)
                st.session_state.pop('maintenance_preview',None);st.success('Maintenance completed');st.json(result)

def main():
    st.set_page_config(page_title='SANDHĀTĀ · Career Intelligence',page_icon='↗',layout='wide')
    configure_visuals()
    if not getattr(st.user,'is_logged_in',False):
        try: auth_ready='auth' in st.secrets and 'keycloak' in st.secrets['auth']
        except Exception: auth_ready=False
        # The local identity provider serves the complete landing with its real form.
        # Hosted providers retain their supported redirect flow.
        if auth_ready and ISSUER == 'http://localhost:18180/realms/sandhata':
            st.caption('Loading SANDHĀTĀ sign-in…')
            st.login('keycloak')
        else:
            landing(auth_ready)
        return
    st.html('<span class="sn-workspace-marker" aria-hidden="true"></span>')
    claims=dict(st.user)
    if claims.get('iss')!=ISSUER: st.error('Identity provider mismatch.');st.stop()
    current=claims.get('sub','')
    if st.session_state.get('identity_subject')!=current:
        st.session_state.clear();st.session_state['identity_subject']=current
    now=time.time()
    if now-st.session_state.get('last_activity',now)>1800 or now-st.session_state.get('session_started',now)>28800 or now-int(claims.get('iat',now))>28800:
        st.session_state.clear();st.logout();st.stop()
    st.session_state.setdefault('session_started',now);st.session_state['last_activity']=now
    try:
        p=resolve_identity(ISSUER,current)
        if p is None:
            st.title('Workspace access required')
            st.info('This identity is not an active member. Redeem an invitation intended for your verified email, or contact your administrator.')
            with st.form('accept_invitation'):
                token=st.text_input('Invitation code',type='password')
                if st.form_submit_button('Join my workspace',type='primary'): auth.accept_invitation(claims,token);st.rerun()
            st.button('Sign out',on_click=st.logout);return
        if st.session_state.get('membership_version',p.auth_version)!=p.auth_version:
            st.session_state.clear();st.logout();st.stop()
        st.session_state['membership_version']=p.auth_version
        with st.sidebar:
            st.markdown(workspace_brand(),unsafe_allow_html=True)
            st.write(display_name(p.display_name));st.caption('Administrator' if p.role=='admin' else 'Member workspace')
            pages=['Today','Discover','Resume Library','Tracker','Insights','Diagnostics']+(['Admin Console'] if p.role=='admin' else [])
            page=st.radio('Workspace',pages,label_visibility='collapsed')
            query=st.text_input('Search your workspace',placeholder='Role, company, skill or note')
            resumes=repo.list_resumes(p)
            resume=st.selectbox('Resume for comparisons',[None]+resumes,format_func=lambda r:'Choose a resume' if r is None else r['label'])
            st.caption('Search · Analyze · Navigate · Discover · Highlight · Apply · Track · Advance')
            st.button('Sign out',on_click=st.logout)
        selected=resume['id'] if resume else None
        if page=='Today': today_page(p,selected)
        elif page=='Discover': discover(p,resumes,selected,query)
        elif page=='Resume Library': resume_library(p,query)
        elif page=='Tracker': tracker(p,resumes,query)
        elif page=='Insights': insights(p)
        elif page=='Diagnostics': diagnostics(p)
        elif page=='Admin Console': admin_console(p)
    except AppError as exc: st.error(str(exc))
    except SQLAlchemyError: st.error('The database operation could not complete. Your data was not displayed. Check system health and retry.')

if __name__=='__main__': main()
