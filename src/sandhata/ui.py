"""Application shell, navigation, resume library, tracker, insights and administration."""
import json,time,uuid
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError
from .config import ROOT,DATA,ISSUER,MODEL,AppError
from .db import resolve_identity
from . import repository as repo
from . import identity as auth
from .ui_documents import document_library,admin_documents
from .agenda import build_agenda,CLOSED
from .presentation import configure_visuals,landing,workspace_brand,display_name
from .ui_common import DISCOVER_FILTERS,safe_csv,compact_dataframe,toast,private_download,show_flash
from .ui_today import today_page
from .ui_discover import discover
from .ui_results import result_view,diagnostics
from .ui_insights import insights
from .ui_tailor import tailor_page

def resume_library(p,query):
    document_library(p,query,private_download)

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

def follow_up_state(item,today):
    follow=item.get('follow_up')
    if not follow or item['status'] in CLOSED: return ''
    if follow<today: return 'Overdue'
    return 'Due soon' if follow<=today+timedelta(days=7) else ''

def tracker_table(items,today):
    """Grouped by status, dated follow-ups first. Overdue rows are labelled and shaded."""
    ordered=sorted(items,key=lambda i:(repo.STATUSES.index(i['status']),i.get('follow_up') is None,i.get('follow_up') or today))
    columns=['status','due','title','company','follow_up','location','work_arrangement','salary_description','job_type','recruiter','applied_at','notes']
    frame=pd.DataFrame([dict(i,due=follow_up_state(i,today)) for i in ordered],columns=columns)
    shade=lambda row:['background-color: #FFE4CC; color: #7C2D12' if row['due']=='Overdue' else '']*len(row)
    return frame.style.apply(shade,axis=1)

def tracker(p,resumes,query):
    st.header('Application tracker')
    st.caption('Opening a posting never marks it applied. Record submissions and event dates explicitly.')
    show_flash()
    search_col,clear_col=st.columns([4,1])
    tracker_query=search_col.text_input('Search applications',key='tracker_search',placeholder='Recruiter, company, city, or role',help='Case-insensitive partial matches. Combine words, such as Anthony Charlotte. Also searches notes. Sidebar search and status filters still apply.')
    def clear_tracker_filters():
        st.session_state['tracker_search']=''
        st.session_state['tracker_status_filter']=[]
        st.session_state['tracker_overdue_only']=False
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
    today=datetime.now(ZoneInfo(p.timezone)).date()
    overdue=[item for item in items if follow_up_state(item,today)=='Overdue']
    if st.checkbox(f'Overdue follow-ups only ({len(overdue)})',key='tracker_overdue_only'): items=overdue
    st.caption(f'{len(items)} trackers match your search and filters.')
    if not items: st.info('No matching applications. Clear tracker search / filters or the sidebar search to see more, or add a new application.');return
    counts=[(s,sum(item['status']==s for item in items)) for s in repo.STATUSES]
    st.markdown(' · '.join(f'{name} **{n}**' for name,n in counts if n))
    compact_dataframe(tracker_table(items,today),use_container_width=True,hide_index=True)
    by_id={str(item['id']):item for item in items}
    if st.session_state.get('tracker_selected') not in by_id: st.session_state.pop('tracker_selected',None)
    if st.session_state.pop('tracker_opened',None) in by_id: st.info('Opened your selected application. Its details and update form are below.')
    rid=st.selectbox('Update an application',list(by_id),key='tracker_selected',format_func=lambda k:f"{by_id[k]['title']} · {by_id[k]['company']}")
    chosen=by_id[rid]
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

def admin_console(p):
    # Rechecks role in every service; the navigation check is only presentation.
    st.header('Administrator console')
    st.caption('Manage user access, usage, system health and housekeeping.')
    tabs=st.tabs(['Users','Invitations','Usage and health','Audit','Housekeeping','Documents'])
    with tabs[0]:
        accounts=auth.list_accounts(p)
        compact_dataframe([{k:str(v) if isinstance(v,uuid.UUID) else v for k,v in row.items()} for row in accounts],use_container_width=True,hide_index=True)
        chosen=st.selectbox('Manage account',accounts,format_func=lambda u:u['display_name']+' · '+u['email'])
        with st.form('account_edit'):
            a,b,c=st.columns(3)
            role=a.selectbox('Role',['member','admin'],index=['member','admin'].index(chosen['role']))
            state=b.selectbox('State',['active','suspended'],index=0 if chosen['state']=='active' else 1)
            quota=c.number_input('Model runs per UTC day',1,1000,value=chosen['quota'],help='Comparisons and tailoring runs share this limit.')
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

    with tabs[5]: admin_documents(p,private_download)

def attention_counts(p):
    """New matches and overdue follow-ups for the sidebar."""
    # Tolerates a database without the new column, so other pages keep working before migration.
    new=sum(bool(j.get('is_new')) for j in repo.list_jobs(p))
    today=datetime.now(ZoneInfo(p.timezone)).date()
    return new,len(build_agenda(repo.list_applications(p),today)['overdue'])

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
            name=display_name(p.display_name);role='Administrator' if p.role=='admin' else 'Member workspace'
            st.write(name)
            if name!=role: st.caption(role)
            pages=['Today','Discover','Resume Library','Tailor','Tracker','Insights','Diagnostics']+(['Admin Console'] if p.role=='admin' else [])
            # Discover filters keep their values while another page is open.
            for key in DISCOVER_FILTERS:
                if key in st.session_state: st.session_state[key]=st.session_state[key]
            page=st.radio('Workspace',pages,label_visibility='collapsed',key='sn_page')
            counts=st.empty()
            query=st.text_input('Search your workspace',placeholder='Role, company, skill or note',key='sn_query')
            resumes=repo.list_resumes(p)
            resume=st.selectbox('Resume for comparisons',[None]+resumes,format_func=lambda r:'Choose a resume' if r is None else r['label'])
            st.button('Sign out',on_click=st.logout)
        selected=resume['id'] if resume else None
        if page=='Today': today_page(p,selected)
        elif page=='Discover': discover(p,resumes,selected,query)
        elif page=='Resume Library': resume_library(p,query)
        elif page=='Tailor': tailor_page(p,resumes,selected)
        elif page=='Tracker': tracker(p,resumes,query)
        elif page=='Insights': insights(p)
        elif page=='Diagnostics': diagnostics(p)
        elif page=='Admin Console': admin_console(p)
        # Filled after the page so the counts include changes made on it.
        new,overdue=attention_counts(p)
        counts.caption(f'New matches: {new} · Overdue follow-ups: {overdue}')
    except AppError as exc: st.error(str(exc))
    except SQLAlchemyError: st.error('The database operation could not complete. Your data was not displayed. Check system health and retry.')

if __name__=='__main__': main()
