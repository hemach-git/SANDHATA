"""Database integration: watchlists, new-job flags, batch ranking and the new screens."""
from datetime import datetime,timezone
import pytest
from streamlit.testing.v1 import AppTest
from sandhata import repository as r,connectors,identity as a
from sandhata.config import AppError
from sandhata.targeting import TARGET_FILTERS
from sandhata.worker import enqueue_batch

BODY='<p>Build production AI agents with Python for enterprise customers across the platform.</p>'

def feed(*titles,location='Remote - US'):
    return dict(jobs=[dict(id=i,title=t,content=BODY.replace('<','&lt;').replace('>','&gt;'),absolute_url=f'https://example.com/{i}',location=dict(name=location)) for i,t in enumerate(titles)])

def test_watchlist_is_private_and_deduplicated(family):
    _,member,other=family
    r.add_watch(member,'Greenhouse','acme','Acme');r.add_watch(member,'Greenhouse','acme','Acme AI')
    assert [w['company'] for w in r.list_watchlist(member)]==['Acme AI']
    watch=r.list_watchlist(member)[0]
    assert r.list_watchlist(other)==[]
    r.remove_watch(other,watch['id']);assert len(r.list_watchlist(member))==1
    r.remove_watch(member,watch['id']);assert r.list_watchlist(member)==[]

def test_scan_flags_only_new_roles_and_isolates_failures(family,monkeypatch):
    p=family[1]
    r.add_watch(p,'Greenhouse','acme','Acme');r.add_watch(p,'Greenhouse','broken','Broken')
    titles=['AI Engineer']
    def fake(url,*args,**kwargs):
        if 'broken' in url: raise AppError('Source unavailable.')
        return feed(*titles)
    monkeypatch.setattr(connectors,'fetch_json',fake)
    first=connectors.scan_watchlist(p,TARGET_FILTERS)
    assert [x['ok'] for x in first]==[True,False] and first[0]['new']==1
    job=r.list_jobs(p)[0]
    assert job['is_new'] and job['company']=='Acme' and '<' not in job['body']
    r.mark_reviewed(p,[job['id']])
    titles.append('Forward Deployed Engineer')
    assert connectors.scan_watchlist(p,TARGET_FILTERS)[0]['new']==1
    assert {j['title']:j['is_new'] for j in r.list_jobs(p)}=={'AI Engineer':False,'Forward Deployed Engineer':True}
    assert all(w['last_checked'] and w['last_note'] for w in r.list_watchlist(p))

def test_refresh_preserves_tracked_details(family,job_text):
    p=family[1];url='https://example.com/role'
    jid=r.import_job(p,'AI Engineer','Acme',job_text,url=url,location='Remote',salary='USD 200k annually')
    app=r.save_to_tracker(p,jid)
    r.update_application(p,app,'Saved','',datetime.now(timezone.utc),'edit',location='Charlotte, NC',salary_description='$210k base')
    r.import_job(p,'AI Engineer','Acme',job_text,url=url,location='Remote - US',salary='')
    job=r.job_detail(p,jid)
    assert job['location']=='Charlotte, NC' and job['salary']=='$210k base'

def test_batch_comparison_skips_pending_partial_and_respects_limit(family,docx_bytes,job_text):
    p=family[1];resume=r.upload_resume(p,docx_bytes,'r.docx','Fixture')
    for i in range(3): r.import_job(p,f'AI Engineer {i}','Acme',job_text+str(i))
    r.import_job(p,'Partial role','Acme',job_text+' partial',complete=False)
    jobs=r.list_jobs(p)
    assert enqueue_batch(p,jobs,resume,2)==dict(queued=2,stopped='')
    assert enqueue_batch(p,jobs,resume,10)==dict(queued=1,stopped='')
    assert enqueue_batch(p,jobs,resume,10)==dict(queued=0,stopped='')

def test_batch_comparison_stops_at_daily_quota(family,docx_bytes,job_text):
    admin,p,_=family
    a.change_account(admin,p.user_id,'member','active',1,'Synthetic quota')
    from dataclasses import replace
    p=replace(p,auth_version=p.auth_version+1)
    resume=r.upload_resume(p,docx_bytes,'r.docx','Fixture')
    for i in range(3): r.import_job(p,f'AI Engineer {i}','Acme',job_text+str(i))
    outcome=enqueue_batch(p,r.list_jobs(p),resume,3)
    assert outcome['queued']==1 and 'quota' in outcome['stopped']

def test_account_erasure_removes_watchlist(family):
    admin,p,_=family;r.add_watch(p,'Lever','acme','Acme')
    preview=a.maintenance(admin,'erase_account',p.user_id,True)
    a.maintenance(admin,'erase_account',p.user_id,False,preview['count'],'erase-watch','Synthetic erasure')
    import os,psycopg
    with psycopg.connect(os.environ['SANDHATA_MIGRATION_URL']) as c:
        assert c.execute('SELECT count(*) FROM watchlists WHERE tenant_id=%s',(p.tenant_id,)).fetchone()[0]==0

def screen(user,tenant,page):
    from sandhata import ui,repository
    from sandhata.db import Principal
    p=Principal(user,tenant,'member',1,'Fixture')
    resumes=repository.list_resumes(p)
    selected=resumes[0]['id'] if resumes else None
    if page=='Today': ui.today_page(p,selected)
    else: ui.discover(p,resumes,selected,'')

@pytest.mark.parametrize('page',['Today','Discover'])
def test_screens_render_with_and_without_data(family,docx_bytes,job_text,page):
    p=family[1]
    def render():
        app=AppTest.from_function(screen,args=(p.user_id,p.tenant_id,page),default_timeout=30).run()
        assert not app.exception,[e.message for e in app.exception]
        return app
    render()
    r.upload_resume(p,docx_bytes,'r.docx','Fixture');r.add_watch(p,'Greenhouse','acme','Acme')
    jid=r.import_job(p,'AI Engineer','Acme',job_text,flag_new=True)
    app_id=r.save_to_tracker(p,jid)
    r.update_application(p,app_id,'Applied','',datetime.now(timezone.utc),'applied',follow_up=datetime.now().date())
    app=render()
    if page=='Today': assert {m.label:m.value for m in app.metric}['New matches']=='1'
    else: assert any('New' in m.value for m in app.markdown)
