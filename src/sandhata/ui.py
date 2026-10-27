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
from .worker import enqueue
from .presentation import configure_visuals,landing,workspace_brand,display_name

def safe_csv(records):
    frame=pd.DataFrame(records)
    for col in frame.select_dtypes(include='object'):
        frame[col]=frame[col].map(lambda v:"'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v)
    return frame.to_csv(index=False).encode('utf-8-sig')

def toast(message): st.toast(message)

def private_download(p,label,kind,identifier='',params=''):
    cache=st.session_state.get('download_capability')
    if not cache or time.time()-cache['created']>840:
        cache=dict(token=auth.issue_capability(p),created=time.time());st.session_state['download_capability']=cache
    url=os.getenv('SANDHATA_API_BASE_URL','http://localhost:18502')+'/download/'+kind+('/'+str(identifier) if identifier else '')+params
    # Bearer token is in a private authenticated component, never in a URL, HTML attribute, or access log.
    script='''<button id="download" style="font:14px sans-serif;padding:9px 14px;border:2px solid #F4C430;border-radius:8px;background:white;color:#164B99;cursor:pointer">LABEL</button><span id="message" style="font:12px sans-serif;margin-left:8px"></span>
    <style>button:hover{background:#F4C430!important;color:#123263!important}button:focus-visible{outline:3px solid #164B99;outline-offset:2px}</style><script>document.getElementById('download').onclick=async()=>{const m=document.getElementById('message');m.textContent='Authorizing…';try{const r=await fetch(URL,{headers:{Authorization:'Bearer '+TOKEN}});if(!r.ok)throw new Error('Access expired or file unavailable. Refresh this page.');const blob=await r.blob();const a=document.createElement('a');const u=URL_OBJECT.createObjectURL(blob);a.href=u;a.download=(r.headers.get('content-disposition')||'').split('filename="')[1]?.split('"')[0]||'SANDHATA-download';a.click();setTimeout(()=>URL_OBJECT.revokeObjectURL(u),1000);m.textContent='Downloaded';}catch(e){m.textContent=e.message;}};</script>'''
    script=script.replace('LABEL',html.escape(label)).replace('URL_OBJECT','window.URL').replace('URL,',json.dumps(url)+',').replace('TOKEN',json.dumps(cache['token']))
    components.html(script,height=55)

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

def discover(p,resumes,selected_resume,query):
    st.header('Discover your next opportunity')
    st.caption('Automatic public feeds. Assisted premium searches. Every job and comparison stays in your workspace.')
    profiles=repo.list_profiles(p)
    with st.expander('Search preferences',expanded=True):
        loaded={}
        if profiles:
            choice=st.selectbox('Saved search', ['New search']+[x['label']+' · '+str(x['id'])[:6] for x in profiles])
            if choice!='New search': loaded=profiles[[x['label']+' · '+str(x['id'])[:6] for x in profiles].index(choice)]['filters']
        with st.form('search_preferences'):
            a,b=st.columns(2)
            title=a.text_input('Job titles separated by commas',value=loaded.get('title',''))
            company=b.text_input('Company',value=loaded.get('company',''))
            a,b=st.columns(2)
            skills=a.text_input('Required skills separated by commas',value=loaded.get('required_skills',''))
            location=b.text_input('Location or remote region',value=loaded.get('location',''))
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
        for col,(label_,url) in zip(cols,connectors.premium_search_links(title,location).items()): col.link_button('Search '+label_,url,use_container_width=True)
        st.caption('Premium portals open in your own browser session. Import the posting below; no account cookies or passwords are collected.')
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
            if st.form_submit_button('Import up to 50 employer postings'):
                with st.spinner('Loading the public employer feed…'): count=connectors.employer_feed(p,provider,board)
                st.success(f'{count} employer postings saved.');st.rerun()
    jobs=repo.list_jobs(p,query)
    st.subheader(str(len(jobs))+' saved '+('opportunity' if len(jobs)==1 else 'opportunities'))
    if not jobs:
        st.info('Run a public search or import your first posting. Your saved jobs will appear here.');return
    private_download(p,'Export your jobs as CSV','jobs')
    for j in jobs[:50]:
        with st.container(border=True):
            st.markdown(f"### {html.escape(j['title'])}")
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

def tracker(p,resumes,query):
    st.header('Application tracker')
    st.caption('Opening a posting never marks it applied. Record submissions and event dates explicitly.')
    items=repo.list_applications(p,query)
    if not items: st.info('Save a job from Discover to begin tracking.');return
    private_download(p,'Export your tracker','tracker')
    st.dataframe(pd.DataFrame(items)[['title','company','status','applied_at','follow_up','notes']],use_container_width=True,hide_index=True)
    chosen=st.selectbox('Update an application',items,format_func=lambda a:f"{a['title']} · {a['company']}")
    rid=str(chosen['id'])
    with st.form('tracker_'+rid):
        a,b=st.columns(2)
        status=a.selectbox('Status',repo.STATUSES,index=repo.STATUSES.index(chosen['status']))
        event_date=b.date_input('Event date',value=datetime.now(ZoneInfo(p.timezone)).date(),max_value=datetime.now(ZoneInfo(p.timezone)).date())
        resume=st.selectbox('Resume used for this application',[None]+resumes,format_func=lambda r:'Keep existing / not recorded' if r is None else r['label'])
        notes=st.text_area('Your notes',value=chosen['notes'])
        follow=st.date_input('Next follow-up',value=chosen['follow_up'])
        if st.form_submit_button('Save update',type='primary'):
            when=datetime.combine(event_date,datetime.min.time(),tzinfo=ZoneInfo(p.timezone)).astimezone(timezone.utc)
            repo.update_application(p,chosen['id'],status,notes,when,str(uuid.uuid4()),resume['id'] if resume else None,follow);toast('Tracker updated');st.rerun()
    st.subheader('Status history')
    st.dataframe(repo.application_history(p,chosen['id']),use_container_width=True,hide_index=True)

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
        a.plotly_chart(px.pie(pd.DataFrame(metrics['current']),names='status',values='n',hole=.65,title='Current pipeline · all saved applications'),use_container_width=True)
    if metrics['weekly']:
        b.plotly_chart(px.line(pd.DataFrame(metrics['weekly']),x='week',y='applications',markers=True,title='Weekly applications'),use_container_width=True)
    if n:
        st.plotly_chart(px.funnel(pd.DataFrame({'Stage':['Applied','Interview','Offer'],'Applications':[n,interview,offer]}),x='Applications',y='Stage',title='Observed cohort progression'),use_container_width=True)
        frame=pd.DataFrame(cohort)
        st.subheader('Source and resume outcomes')
        st.dataframe(frame.groupby('source').agg(applications=('id','count'),interviews=('interview','sum'),offers=('offer','sum')).reset_index(),hide_index=True)
        frame['resume_label']=frame['resume_label'].fillna('Not recorded')
        st.dataframe(frame.groupby('resume_label').agg(applications=('id','count'),interviews=('interview','sum'),offers=('offer','sum')).reset_index(),hide_index=True)
        private_download(p,'Export applied cohort','cohort',params=f'?start={start.isoformat()}&end={end.isoformat()}')
    if metrics['gaps']:
        gaps=pd.DataFrame(metrics['gaps'],columns=['Requirement not evidenced','Count'])
        st.plotly_chart(px.bar(gaps,x='Count',y='Requirement not evidenced',orientation='h',title='Frequently not evidenced requirements'),use_container_width=True)
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
        st.dataframe([{k:str(v) if isinstance(v,uuid.UUID) else v for k,v in row.items()} for row in accounts],use_container_width=True,hide_index=True)
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
            email=st.text_input('Exact verified identity-provider email')
            role=st.selectbox('Invited role',['member','admin'])
            if st.form_submit_button('Create 48-hour invitation',type='primary'):
                st.code(auth.invite(p,email,role));st.info('Copy this code securely to the intended user. No email has been sent.')
        invitations=auth.list_invitations(p)
        st.dataframe([{k:str(v) if isinstance(v,uuid.UUID) else v for k,v in row.items()} for row in invitations],use_container_width=True,hide_index=True)
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
        st.dataframe(metrics['usage'],use_container_width=True,hide_index=True)
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
        st.dataframe(events,use_container_width=True,hide_index=True)
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
            pages=['Discover','Resume Library','Tracker','Insights','Diagnostics']+(['Admin Console'] if p.role=='admin' else [])
            page=st.radio('Workspace',pages,label_visibility='collapsed')
            query=st.text_input('Search your workspace',placeholder='Role, company, skill or note')
            resumes=repo.list_resumes(p)
            resume=st.selectbox('Resume for comparisons',[None]+resumes,format_func=lambda r:'Choose a resume' if r is None else r['label'])
            st.caption('Search · Analyze · Navigate · Discover · Highlight · Apply · Track · Advance')
            st.button('Sign out',on_click=st.logout)
        selected=resume['id'] if resume else None
        if page=='Discover': discover(p,resumes,selected,query)
        elif page=='Resume Library': resume_library(p,query)
        elif page=='Tracker': tracker(p,resumes,query)
        elif page=='Insights': insights(p)
        elif page=='Diagnostics': diagnostics(p)
        elif page=='Admin Console': admin_console(p)
    except AppError as exc: st.error(str(exc))
    except SQLAlchemyError: st.error('The database operation could not complete. Your data was not displayed. Check system health and retry.')

if __name__=='__main__': main()
