"""Workspace screens: empty and populated rendering, actions, navigation and safety."""
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from streamlit.testing.v1 import AppTest
from sandhata import repository as r,ui,ui_discover
from sandhata.ui_common import md
from sandhata.worker import enqueue,run_once

def shell(user,tenant):
    """The whole signed-in application, with only the identity provider replaced."""
    import time
    from unittest.mock import patch
    import streamlit as st
    from sandhata import ui
    from sandhata.config import ISSUER
    from sandhata.db import Principal
    class User(dict): is_logged_in=True
    claims=User(iss=ISSUER,sub='fixture',iat=time.time())
    principal=Principal(user,tenant,'member',1,'Fixture Member')
    with patch.object(st,'user',claims),patch.object(ui,'resolve_identity',return_value=principal):
        ui.main()

def start(p,page='Today'):
    app=AppTest.from_function(shell,args=(p.user_id,p.tenant_id),default_timeout=60)
    # An established session; a first sign-in would clear the state AppTest reads back.
    app.session_state['identity_subject']='fixture'
    app.run()
    if page!='Today': app.radio(key='sn_page').set_value(page).run()
    return check(app)

def check(app):
    assert not app.exception,[e.message for e in app.exception]
    assert not app.error,[e.value for e in app.error]
    return app

def click(app,label=None,key=None):
    button=app.button(key=key) if key else next(b for b in app.button if b.label==label)
    return check(button.click().run())

def text(app): return ' '.join(m.value for m in app.markdown)
def metrics(app): return {m.label:m.value for m in app.metric}
def today(p): return datetime.now(ZoneInfo(p.timezone)).date()

def tracked(p,title,job_text,follow_days,status='Applied'):
    job=r.import_job(p,title,'Acme',job_text+title)
    app_id=r.save_to_tracker(p,job)
    r.update_application(p,app_id,status,'',datetime.now(timezone.utc),'seed-'+title,follow_up=today(p)+timedelta(days=follow_days))
    return job,app_id

def analyzer(job,resume,repair=''):
    rows=[dict(category='required_skills',requirement_quote='Python and SQL',status='supported',resume_quote='Python data pipelines',rationale='Both are present.'),
          dict(category='preferred_skills',requirement_quote='Kubernetes',status='not_evidenced',resume_quote='',rationale='Not mentioned.')]
    return dict(requirements=rows,eligibility_flags=['Review: remote in the United States']),{}

def test_every_page_renders_empty(family):
    app=start(family[1])
    assert 'Resume Library' in app.radio(key='sn_page').options
    assert any(s.value=='Get started' for s in app.subheader)
    assert any('New matches: 0 · Overdue follow-ups: 0' in c.value for c in app.caption)
    for page in ['Discover','Resume Library','Tracker','Insights','Diagnostics','Today']:
        check(app.radio(key='sn_page').set_value(page).run())

def test_checklist_opens_the_matching_discover_tab(family):
    app=click(start(family[1]),key='setup_2')
    assert app.radio(key='sn_page').value=='Discover'
    assert app.session_state['discover_tab']=='Target companies'

def test_today_opens_the_chosen_application_in_tracker(family,job_text):
    p=family[1]
    tracked(p,'Overdue Engineer',job_text,-3)
    _,soon=tracked(p,'Upcoming Engineer',job_text,2)
    app=start(p)
    assert metrics(app)['Overdue follow-ups']=='1' and metrics(app)['Due in 7 days']=='1'
    assert any('Overdue follow-ups: 1' in c.value for c in app.caption)
    assert not any(s.value=='Get started' for s in app.subheader)
    app=click(app,key='today_open_'+soon)
    assert app.radio(key='sn_page').value=='Tracker'
    assert app.selectbox(key='tracker_selected').value==soon

def test_tracker_open_clears_filters_that_would_hide_the_application(family,job_text):
    p=family[1];_,late=tracked(p,'Late Engineer',job_text,-1)
    app=start(p,'Tracker')
    app.text_input(key='tracker_search').set_value('nothing matches this').run()
    check(app.radio(key='sn_page').set_value('Today').run())
    app=click(app,key='today_open_'+late)
    assert app.selectbox(key='tracker_selected').value==late

def test_tracker_highlights_and_filters_overdue(family,job_text):
    p=family[1];tracked(p,'Late Engineer',job_text,-2);tracked(p,'Future Engineer',job_text,20)
    app=start(p,'Tracker')
    box=app.checkbox(key='tracker_overdue_only')
    assert box.label=='Overdue follow-ups only (1)'
    check(box.check().run())
    assert len(app.selectbox(key='tracker_selected').options)==1
    items=r.list_applications(p)
    assert sorted(ui.follow_up_state(i,today(p)) for i in items)==['','Overdue']
    assert ui.follow_up_state(dict(status='Rejected',follow_up=today(p)-timedelta(days=9)),today(p))==''

def test_discover_filters_and_selected_comparison(family,docx_bytes,job_text):
    p=family[1];r.upload_resume(p,docx_bytes,'r.docx','Fixture')
    first=r.import_job(p,'Senior AI Engineer','Acme',job_text+'1',location='Remote - US',flag_new=True)
    r.import_job(p,'Engineering Manager','Beta',job_text+'2',location='Boston')
    app=start(p,'Discover')
    assert ':primary-badge[New]' in text(app)
    check(app.multiselect(key='discover_company').set_value(['Acme']).run())
    assert any('of 1 matching roles (2 saved)' in c.value for c in app.caption)
    click(app,'Clear filters')
    app.selectbox(key='discover_place').set_value('Remote').run()
    assert any('of 1 matching roles' in c.value for c in app.caption)
    resume=next(s for s in app.selectbox if s.label=='Resume for comparisons')
    check(resume.select_index(1).run())
    check(app.checkbox(key='pick_'+first).check().run())
    click(app,'Compare selected')
    assert len(r.tasks(p))==1
    assert any('1 comparisons queued' in s.value for s in app.success)

def test_discover_saves_selected_rows(family,job_text):
    p=family[1];job=r.import_job(p,'AI Engineer','Acme',job_text)
    app=start(p,'Discover')
    click(app,'Select this page');click(app,'Save selected to tracker')
    assert [str(a['job_id']) for a in r.list_applications(p)]==[job]
    assert r.list_applications(p)[0]['status']=='Saved'

def test_discover_filters_survive_a_visit_to_another_page(family,job_text):
    p=family[1];r.import_job(p,'AI Engineer','Acme',job_text,flag_new=True)
    app=start(p,'Discover')
    check(app.checkbox(key='discover_new').check().run())
    for page in ['Diagnostics','Discover']: check(app.radio(key='sn_page').set_value(page).run())
    assert app.checkbox(key='discover_new').value

def test_insights_charts_and_tables(family,docx_bytes,job_text):
    p=family[1];resume=r.upload_resume(p,docx_bytes,'r.docx','Fixture')
    hostile='<a href="https://evil.example">Engineer</a> **bold**'
    job=r.import_job(p,hostile,'Acme',job_text)
    enqueue(p,r.list_jobs(p)[0]['version_id'],resume);assert run_once(analyzer)
    r.update_application(p,r.save_to_tracker(p,job),'Applied','',datetime.now(timezone.utc),'applied')
    for dark in (False,True):
        app=start(p,'Insights')
        if dark: check(app.toggle(key='sn_dark').set_value(True).run())
        assert metrics(app)['Applications in cohort']=='1'
        assert len(app.get('plotly_chart'))==4 and len(app.table)==3
        assert any(md(hostile) in str(t.value.to_dict()) or md(hostile) in t.value.index for t in app.table)

def test_gap_labels_are_short_unique_and_escaped():
    from sandhata.ui_insights import gap_labels,PALETTES
    long='Experience with distributed systems '*4
    labels,full=gap_labels([long+'one',long+'two','<b>x</b>'])
    assert len(set(labels))==3 and max(map(len,labels))<60
    assert labels[2]=='&lt;b&gt;x&lt;/b&gt;' and full[2]==labels[2]
    assert all(set(r.STATUSES)==set(colors['status']) for colors in PALETTES.values())

def test_sidebar_tag_line_and_single_role_label(family):
    from sandhata.presentation import workspace_brand,EXPANSION
    brand=workspace_brand()
    assert all('<b>'+w[0]+'</b>'+w[1:] in brand for w in EXPANSION)
    assert brand.index('SANDHĀTĀ')<brand.index('sn-workspace-tagline')
    app=start(family[1])
    assert not any('Search · Analyze' in c.value for c in app.sidebar.caption)
    assert any(c.value=='Member workspace' for c in app.sidebar.caption)

def test_filter_helpers():
    jobs=[dict(version_id=str(i),title=t,company='A',source='S',location=l,is_new=False,workplace='') for i,(t,l) in
          enumerate([('Sr AI Engineer','Charlotte, NC'),('Director of AI','Remote'),('AI Engineer','Paris')])]
    fit={'0':dict(score=80),'1':dict(score=None)}
    assert [ui_discover.seniority(j['title']) for j in jobs]==['Senior','Director or head','Other or unstated']
    assert len(ui_discover.filter_jobs(jobs,fit,place='Remote or Charlotte'))==2
    assert [j['version_id'] for j in ui_discover.filter_jobs(jobs,fit,minimum=50)]==['0']
    assert ui_discover.scan_failed(dict(last_note='Source unavailable.'))
    assert not ui_discover.scan_failed(dict(last_note='2 matched of 9; saved 2; 0 new'))

def test_posting_text_is_escaped(family,job_text):
    p=family[1];hostile='[click](https://evil.example) <img src=x> $x$'
    r.import_job(p,hostile,'**Acme**',job_text,flag_new=True)
    app=start(p,'Discover')
    assert hostile not in text(app) and md(hostile) in text(app)
    assert md('a\n# b')=='a \\# b'

def test_failed_board_removal_needs_confirmation(family):
    p=family[1];r.add_watch(p,'Greenhouse','broken','Broken')
    watch=r.list_watchlist(p)[0];r.record_scan(p,watch['id'],'Source unavailable.')
    app=start(p,'Discover')
    assert any('Boards that failed last time (1)'==s.value for s in app.subheader)
    app=click(app,key='drop_'+str(watch['id']))
    assert r.list_watchlist(p)
    click(app,key='drop_'+str(watch['id'])+'_yes')
    assert r.list_watchlist(p)==[]

def test_results_and_diagnostics_explain_runs(family,docx_bytes,job_text):
    p=family[1];resume=r.upload_resume(p,docx_bytes,'r.docx','Fixture')
    r.import_job(p,'AI Engineer','Acme',job_text)
    version=r.list_jobs(p)[0]['version_id']
    done=enqueue(p,version,resume);assert run_once(analyzer)
    app=start(p,'Diagnostics')
    assert metrics(app)['Completed']=='1' and metrics(app)['Queued']=='0'
    check(app.toggle(key='evidence_'+done).set_value(True).run())
    shown=[m.value for m in app.markdown]
    groups=[v for v in shown if v.startswith('**') and v.endswith(')**')]
    assert groups==['**Supported (1)**','**Partially supported (0)**','**Not evidenced (1)**','**Unknown (0)**']
    assert shown.index('**Check eligibility first**')<shown.index('**Supported (1)**')
    assert any(t.value=='Python data pipelines' for t in app.text)
    # Today lists the compared role that is not tracked yet.
    resume_box=next(s for s in check(app.radio(key='sn_page').set_value('Today').run()).selectbox if s.label=='Resume for comparisons')
    check(resume_box.select_index(1).run())
    assert any(s.value=='Strongest compared roles not yet tracked' for s in app.subheader)
    job=r.list_jobs(p)[0]
    click(app,key='today_save_'+str(job['id']))
    assert len(r.list_applications(p))==1

def test_failed_run_has_plain_explanation_and_retry(family,docx_bytes,job_text):
    p=family[1];resume=r.upload_resume(p,docx_bytes,'r.docx','Fixture')
    r.import_job(p,'AI Engineer','Acme',job_text)
    task=enqueue(p,r.list_jobs(p)[0]['version_id'],resume)
    assert run_once(lambda *args:({},{}))
    app=start(p,'Diagnostics')
    assert any('Check that Ollama is running' in w.value for w in app.warning)
    # Inputs of an earlier session are unknown, so the user is sent to Discover.
    app=click(app,key='retry_'+task)
    assert app.radio(key='sn_page').value=='Discover'

def test_one_thousand_saved_jobs(family,job_text):
    p=family[1]
    for i in range(1000): r.import_job(p,f'AI Engineer {i}',f'Company {i%40}',job_text+str(i),flag_new=i%2==0)
    app=start(p)
    assert metrics(app)['New matches']=='500'
    check(app.radio(key='sn_page').set_value('Discover').run())
    assert any('of 1000 matching roles' in c.value for c in app.caption)
    assert len([c for c in app.checkbox if c.key and c.key.startswith('pick_')])==25
    check(app.number_input(key='discover_page').set_value(40).run())
    check(app.multiselect(key='discover_company').set_value(['Company 1']).run())
    assert app.number_input(key='discover_page').value==1
