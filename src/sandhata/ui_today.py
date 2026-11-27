"""Today: the daily action list built from saved records."""
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from . import repository as repo
from .targeting import priority
from .agenda import build_agenda,follow_up_calendar
from .ui_common import md,compact_dataframe,flash,show_flash,navigate,open_application,open_discover,alignment_text

SECTION_LIMIT=10

def setup_steps(p,jobs,fit):
    """First-run checklist as (done, label, button, callback, arguments)."""
    watched=repo.list_watchlist(p)
    compared=bool(fit) or any(t['state']=='completed' for t in repo.tasks(p))
    return [
        (bool(repo.list_resumes(p)),'Upload a resume','Open Resume Library',navigate,('Resume Library',)),
        (bool(watched),'Add the companies you want to watch','Add companies',open_discover,('Target companies',)),
        (bool(jobs) or any(w['last_checked'] for w in watched),'Scan for matching roles, or add a posting','Scan companies',open_discover,('Target companies',)),
        (compared,'Compare a role with your resume','Choose roles to compare',open_discover,('Matches',)),
    ]

def checklist(steps):
    with st.container(border=True,key='sn_card_setup'):
        st.subheader('Get started')
        st.caption(f"{sum(s[0] for s in steps)} of {len(steps)} steps done.")
        for number,(done,label,button,action,args) in enumerate(steps,1):
            text,act=st.columns([3,1])
            text.markdown(('✓ Done · ' if done else f'{number}. ')+label)
            if not done: act.button(button,key=f'setup_{number}',on_click=action,args=args,use_container_width=True)

def follow_up_text(item,today):
    follow=item.get('follow_up')
    if not follow: return f"No update since {item['updated_at']:%b %d}"
    days=(today-follow).days
    when=f'{days} day'+('s' if days!=1 else '')+' overdue' if days>0 else ('due today' if days==0 else f'due in {-days} day'+('s' if days!=-1 else ''))
    return f'Follow up {follow:%b %d} · {when}'

def application_row(item,today):
    key=str(item['id'])
    with st.container(border=True,key='sn_card_due_'+key):
        info,act=st.columns([2,1])
        info.markdown(f"**{md(item['title'])}** · {md(item['company'])}")
        info.markdown(md(item['status'])+' · '+follow_up_text(item,today)+(' · '+md(item['recruiter']) if item.get('recruiter') else ''))
        if item.get('notes'): info.caption(md(item['notes'][:160]+('…' if len(item['notes'])>160 else '')))
        row=act.container(horizontal=True,horizontal_alignment='right')
        if item.get('original_url'): row.link_button('Posting ↗',item['original_url'])
        row.button('Open in Tracker',key='today_open_'+key,on_click=open_application,args=(key,),type='primary')

def action_list(plan,today):
    for key,label in [('overdue','Overdue'),('upcoming','Coming up'),('stale','No recent update and no follow-up date')]:
        items=plan[key]
        if not items: continue
        st.subheader(f'{label} ({len(items)})')
        show_all=len(items)>SECTION_LIMIT and st.toggle(f'Show all {len(items)}',key='today_all_'+key)
        for item in items if show_all else items[:SECTION_LIMIT]: application_row(item,today)

def strongest_roles(p,jobs,applications,fit):
    tracked={str(x['job_id']) for x in applications}
    ranked=[(fit[str(j['version_id'])],j) for j in jobs if str(j['id']) not in tracked and fit.get(str(j['version_id']),{}).get('score') is not None]
    if not ranked: return
    # Fully evidenced results come before provisional ones.
    ranked.sort(key=lambda pair:(not pair[0]['provisional'],pair[0]['score'],pair[0]['coverage']),reverse=True)
    st.subheader('Strongest compared roles not yet tracked')
    for result,job in ranked[:SECTION_LIMIT]:
        key=str(job['id'])
        with st.container(border=True,key='sn_card_top_'+key):
            info,score,act=st.columns([2,1.2,1.3])
            info.markdown(f"**{md(job['title'])}**  \n{md(job['company'])} · {md(job['location'] or 'Location not disclosed')}")
            score.markdown(alignment_text(result))
            row=act.container(horizontal=True,horizontal_alignment='right')
            if job['original_url']: row.link_button('Posting ↗',job['original_url'])
            if row.button('Save to tracker',key='today_save_'+key):
                repo.save_to_tracker(p,job['id']);flash('Saved to your tracker.');st.rerun()

def today_page(p,selected_resume):
    st.header('Today')
    st.caption('Follow-ups, quiet applications and new matches from your saved records.')
    show_flash()
    today=datetime.now(ZoneInfo(p.timezone)).date()
    applications=repo.list_applications(p)
    plan=build_agenda(applications,today)
    jobs=repo.list_jobs(p)
    new=[j for j in jobs if j['is_new']]
    fit=repo.fit_by_version(p,selected_resume) if selected_resume else {}
    a,b,c,d=st.columns(4)
    a.metric('Overdue follow-ups',len(plan['overdue']));b.metric('Due in 7 days',len(plan['upcoming']))
    c.metric('Quiet 14+ days',len(plan['stale']));d.metric('New matches',len(new))
    if not applications:
        steps=setup_steps(p,jobs,fit)
        if not all(s[0] for s in steps): checklist(steps)
    action_list(plan,today)
    if applications and not any(plan.values()): st.info('Nothing is due. Add follow-up dates in Tracker to see them here.')
    dated=plan['overdue']+plan['upcoming']
    if dated: st.download_button('Add these follow-ups to my calendar (.ics)',follow_up_calendar(dated,datetime.now(timezone.utc)),'SANDHATA_FOLLOW_UPS.ics','text/calendar')
    if selected_resume: strongest_roles(p,jobs,applications,fit)
    elif jobs: st.caption('Choose a resume in the sidebar to see your strongest compared roles.')
    if new:
        st.subheader('Newest matches')
        top=sorted(new,key=priority,reverse=True)[:SECTION_LIMIT]
        compact_dataframe(pd.DataFrame([dict(title=j['title'],company=j['company'],location=j['location'],posting=j['original_url']) for j in top]),
            hide_index=True,use_container_width=True,column_config={'posting':st.column_config.LinkColumn('posting')})
        st.button(f'Review all {len(new)} new matches',on_click=open_discover,args=('Matches',True))
