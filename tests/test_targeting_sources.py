from datetime import date,datetime,timedelta,timezone
import pytest
from sandhata import connectors
from sandhata.agenda import build_agenda,follow_up_calendar
from sandhata.config import AppError
from sandhata.parsing import plain_html
from sandhata.targeting import TARGET_FILTERS,location_matches,matches_filters,priority,title_matches

BODY='Build production AI agents with Python for enterprise customers across the platform.'
ESCAPED='&lt;div&gt;&lt;p&gt;'+BODY+' &lt;strong&gt;Python&lt;/strong&gt; &amp;amp; SQL&lt;/p&gt;&lt;/div&gt;'

def greenhouse(*postings):
    return dict(jobs=[dict(id=i,title=title,content=ESCAPED,absolute_url=f'https://example.com/{i}',location=dict(name=location))
                      for i,(title,location) in enumerate(postings)])

def test_greenhouse_escaped_html_is_cleaned():
    job=connectors.parse_board('Greenhouse','acme',greenhouse(('AI Engineer','Remote - US')))[0]
    text=plain_html(job['description'])
    assert '<' not in text and '&lt;' not in text and BODY in text and '& SQL' in text

def test_greenhouse_tolerates_missing_location_and_content():
    job=connectors.parse_board('Greenhouse','acme',dict(jobs=[dict(id=1,title='AI Engineer',content=None,location=None,absolute_url='https://example.com/1')]))[0]
    assert job['location']=='' and job['description']==''

def test_lever_keeps_requirement_lists_and_remote_flag():
    payload=[dict(id='a',text='AI Engineer',description='<p>Intro</p>',lists=[dict(text='Requirements',content='<li>Python</li>')],
                  hostedUrl='https://example.com/a',categories=dict(location='New York'),workplaceType='remote')]
    job=connectors.parse_board('Lever','acme',payload)[0]
    assert 'Python' in job['description'] and job['location']=='New York (Remote)'

def test_ashby_unlisted_hidden_and_compensation_kept():
    base=dict(title='AI Engineer',jobUrl='https://example.com/x',descriptionHtml='<p>x</p>',location='Charlotte, NC')
    payload=dict(jobs=[dict(base,id='1',compensation=dict(compensationTierSummary='$200K - $250K')),dict(base,id='2',isListed=False)])
    jobs=connectors.parse_board('Ashby','acme',payload)
    assert len(jobs)==1 and jobs[0]['salary']=='$200K - $250K'

@pytest.mark.parametrize('location',[
    'Charlotte, NC','Raleigh, North Carolina','Remote','Remote - US','US-Remote','Remote, United States',
    'Remote (USA)','New York, NY (Remote)','Remote-Friendly (Travel Required) | San Francisco, CA','Worldwide','London; Remote - US'])
def test_target_locations_accepted(location):
    assert location_matches(location,TARGET_FILTERS['location'])

@pytest.mark.parametrize('location',[
    'Vancouver, Canada','Paris, France','Sydney, Australia','Austin, TX','New York, NY','Remote - India',
    'Remote - Canada','London (Remote)','Remote EMEA','Cincinnati, OH',''])
def test_other_locations_rejected(location):
    assert not location_matches(location,TARGET_FILTERS['location'])

@pytest.mark.parametrize('title,expected',[
    ('Forward Deployed Software Engineer',True),('Senior AI Engineer',True),('Engineering Manager, Applied AI',True),
    ('Lead Engineer, AI Platform',True),('Thai Language Engineer',False),('Account Executive',False),('Maintenance Engineer',False)])
def test_default_titles(title,expected):
    assert any(title_matches(title.lower(),t.strip().lower()) for t in TARGET_FILTERS['title'].split(','))==expected

def test_exclusions_and_skills_use_whole_words():
    job=dict(title='AI Engineer',company='Acme',description='Internal tools in JavaScript and C++',location='Remote')
    assert matches_filters(job,dict(exclude='intern'))
    assert not matches_filters(job,dict(required_skills='java'))
    assert matches_filters(job,dict(required_skills='C++'))

def test_priority_prefers_senior_forward_deployed():
    ranked=sorted(['AI Engineer','Senior Forward Deployed Engineer','Account Executive'],key=lambda t:priority(dict(title=t,location='Remote')),reverse=True)
    assert ranked==['Senior Forward Deployed Engineer','AI Engineer','Account Executive']

def test_filters_apply_before_the_limit(monkeypatch):
    postings=[('Account Executive','Remote')]*60+[('AI Engineer','Remote - US'),('Senior Forward Deployed Engineer','Charlotte, NC')]
    saved=[]
    monkeypatch.setattr(connectors,'fetch_json',lambda *a,**k:greenhouse(*postings))
    monkeypatch.setattr(connectors,'job_count',lambda p:len(saved))
    monkeypatch.setattr(connectors,'import_job',lambda p,title,*a,**k:saved.append(title))
    outcome=connectors.employer_feed(None,'Greenhouse','acme',TARGET_FILTERS,limit=1)
    assert saved==['Senior Forward Deployed Engineer']
    assert outcome==dict(total=62,matched=2,count=1,new=1)

def test_unsupported_provider_rejected():
    with pytest.raises(AppError): connectors.fetch_board('Workday','acme')

def application(status,follow=None,age=0,**extra):
    today=date(2026,11,26)
    return dict(id=extra.get('id','1'),title=extra.get('title','AI Engineer'),company='Acme, Inc.',status=status,
                follow_up=None if follow is None else today+timedelta(days=follow),
                updated_at=datetime(2026,11,26,tzinfo=timezone.utc)-timedelta(days=age))

def test_agenda_groups_open_applications():
    items=[application('Applied',-1),application('Saved',3),application('Applied',30,age=40),application('Applied',age=20),
           application('Applied',age=2),application('Saved',age=90),application('Rejected',-5)]
    plan=build_agenda(items,date(2026,11,26))
    assert [len(plan[k]) for k in ('overdue','upcoming','stale')]==[1,1,1]

def test_calendar_is_escaped_folded_and_excludes_notes():
    item=dict(application('Applied',1,title='Lead Engineer; '+'Very long title '*8),notes='private note')
    text=follow_up_calendar([item,application('Applied')],datetime(2026,11,26,tzinfo=timezone.utc)).decode('utf-8')
    assert text.count('BEGIN:VEVENT')==1 and 'DTSTART;VALUE=DATE:20261127' in text and 'private note' not in text
    assert 'Lead Engineer\\;' in text.replace('\r\n ','') and 'Acme\\, Inc.' in text.replace('\r\n ','')
    assert all(len(line.encode('utf-8'))<=75 for line in text.split('\r\n'))

@pytest.mark.parametrize('flags,expected',[
    (dict(isRemote=True,workplaceType='Remote'),'New York (Remote)'),(dict(isRemote=True,workplaceType='Hybrid'),'New York'),
    (dict(isRemote=True),'New York (Remote)'),(dict(isRemote=False,workplaceType='OnSite'),'New York')])
def test_ashby_hybrid_is_not_remote(flags,expected):
    payload=dict(jobs=[dict(flags,id='1',title='AI Engineer',jobUrl='https://example.com/x',descriptionHtml='<p>x</p>',location='New York')])
    assert connectors.parse_board('Ashby','acme',payload)[0]['location']==expected
