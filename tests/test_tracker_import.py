import pytest
from sandhata.config import AppError
from sandhata.tracker_import import parse_tracker
from sandhata import repository as repo
from datetime import datetime,timezone

def test_tracker_search_recruiter_company_city_role_and_literal_characters(family):
    _,member,other=family
    repo.create_manual_application(member,'Platform Engineer','Matlen Silver',location='Charlotte, NC',recruiter='Anthony Ferranti')
    repo.create_manual_application(member,'Solution Architect','Example',location='Raleigh, NC',recruiter='Jane Smith')
    for query in ['ANTHONY','ferr','matlen','charl','platform','Anthony Charlotte',' silver  ENGINEER ']:
        matches=repo.list_applications(member,query)
        assert len(matches)==1 and matches[0]['company']=='Matlen Silver'
    assert len(repo.list_applications(member,'nc'))==2
    for query in ['Anthony Raleigh','missing','%','_','\' OR 1=1 --']:
        assert repo.list_applications(member,query)==[]
    assert len(repo.list_applications(member,''))==2
    assert repo.list_applications(other,'Charlotte')==[]

def test_recruiter_and_update_does_not_duplicate_history(family):
    _,member,_=family
    repo.create_manual_application(member,'Engineer','Example',recruiter='Jane Smith - Recruiting',status='Applied',applied_at=datetime(2026,1,2,tzinfo=timezone.utc))
    app=repo.list_applications(member)[0]
    assert app['recruiter']=='Jane Smith - Recruiting'
    original=repo.application_history(member,app['id'])
    now=datetime.now(timezone.utc)
    assert repo.update_application(member,app['id'],'Applied','',now,'unchanged')=='unchanged'
    assert repo.update_application(member,app['id'],'Applied','New notes',now,'details',recruiter='Alex - Agency')=='details_updated'
    assert repo.application_history(member,app['id'])==original
    assert repo.update_application(member,app['id'],'Interviewing','New notes',now,'status')=='status_changed'
    assert repo.update_application(member,app['id'],'Interviewing','New notes',now,'repeat')=='unchanged'
    assert len(repo.application_history(member,app['id']))==len(original)+1
    assert len(repo.list_applications(member))==1
    assert repo.list_applications(member)[0]['recruiter']=='Alex - Agency'
    assert repo.tracker_metrics(member,datetime(2026,1,1).date(),now.date())['cohort'][0]['recruiter']=='Alex - Agency'
    repo.update_application(member,app['id'],'Interviewing','New notes',now,'clear',recruiter='')
    assert repo.list_applications(member)[0]['recruiter']==''

def test_recruiter_csv_compatibility():
    from sandhata.tracker_import import TEMPLATE
    assert parse_tracker(b'title,company\nEngineer,Example\n',repo.STATUSES)[0]['recruiter']==''
    assert parse_tracker(TEMPLATE,repo.STATUSES)[0]['recruiter']=='Jane Smith - Example Recruiting'

def test_salary_and_job_type_import_update_report(family):
    _,member,other=family
    repo.create_manual_application(member,'Engineer','Example',status='Applied',applied_at=datetime(2026,1,2,tzinfo=timezone.utc),salary_description='$150,000 base + 15% bonus',job_type='Full Time')
    app=repo.list_applications(member)[0]
    assert app['salary_description']=='$150,000 base + 15% bonus' and app['job_type']=='Full Time'
    repo.update_application(member,app['id'],'Applied','Updated',datetime.now(timezone.utc),'salary-update',salary_description='$95/hour W2',job_type='Contract to Hire')
    app=repo.list_applications(member)[0]
    assert app['salary_description']=='$95/hour W2' and app['job_type']=='Contract to Hire'
    detail=repo.job_detail(member,app['job_id'])
    assert detail['salary']=='$95/hour W2' and detail['job_type']=='Contract to Hire'
    report=repo.tracker_metrics(member,datetime(2026,1,1).date(),datetime.now().date())['cohort'][0]
    assert report['salary_description']=='$95/hour W2' and report['job_type']=='Contract to Hire'
    assert repo.list_applications(other)==[]
    repo.update_application(member,app['id'],'Applied','Cleared',datetime.now(timezone.utc),'salary-clear',salary_description='',job_type='')
    assert repo.list_applications(member)[0]['salary_description']==''

def test_salary_job_type_csv_validation():
    old=parse_tracker(b'title,company\nEngineer,Example\n',repo.STATUSES)[0]
    assert old['salary_description']==old['job_type']==''
    parsed=parse_tracker(b'title,company,salary_description,job_type\nEngineer,Example,"$150,000 base + bonus",full-time\n',repo.STATUSES)[0]
    assert parsed['job_type']=='Full Time' and parsed['salary_description']=='$150,000 base + bonus'
    with pytest.raises(AppError):
        parse_tracker(b'title,company,job_type\nEngineer,Example,Bogus\n',repo.STATUSES)

def test_location_and_arrangement_csv_backwards_compatible():
    old=parse_tracker(b'title,company\nEngineer,Example\n',repo.STATUSES)[0]
    assert old['location']==old['work_arrangement']==''
    new=parse_tracker(b'title,company,location,work_arrangement\nEngineer,Example,"Charlotte, NC",on-site\n',repo.STATUSES)[0]
    assert new['location']=='Charlotte, NC' and new['work_arrangement']=='OnSite'
    with pytest.raises(AppError):
        parse_tracker(b'title,company,work_arrangement\nEngineer,Example,Occasional\n',repo.STATUSES)

def test_tracker_location_persists_and_remains_private(family):
    _,member,other=family
    repo.import_tracker(member,b'title,company,location,work_arrangement\nEngineer,Example,"Charlotte, NC",Hybrid\n')
    app=repo.list_applications(member)[0]
    assert app['location']=='Charlotte, NC' and app['work_arrangement']=='Hybrid'
    now=datetime.now(timezone.utc)
    with pytest.raises(AppError):
        repo.update_application(other,app['id'],'Saved','',now,'other-update',location='Elsewhere',work_arrangement='Remote')
    repo.update_application(member,app['id'],'Saved','Updated',now,'location-update',location='Remote',work_arrangement='Remote')
    updated=repo.list_applications(member)[0]
    assert updated['location']=='Remote' and updated['work_arrangement']=='Remote'
    assert repo.job_detail(member,app['job_id'])['location']=='Remote'
    repo.update_application(member,app['id'],'Saved','Cleared',now,'location-clear',location='',work_arrangement='')
    assert repo.list_applications(member)[0]['location']==''

def test_csv_multiline_and_dates():
    rows=parse_tracker(b'title,company,status,notes,applied_at\nEngineer,Example,Offer,"first\nsecond",2026-01-01\n',repo.STATUSES)
    assert rows[0]['notes']=='first\nsecond'
    assert rows[0]['applied_at'].tzinfo is not None

@pytest.mark.parametrize('data',[
    b'title,company\n,Example\n',
    b'title,company,status\nEngineer,Example,Unknown\n',
    b'title,company,original_url\nEngineer,Example,http://example.com\n',
    b'title,company,applied_at\nEngineer,Example,2099-01-01\n',
    b'title,company\nEngineer,Example,Extra\n',
    b'title,company\n',
])
def test_invalid_csv(data):
    with pytest.raises(AppError): parse_tracker(data,repo.STATUSES)

def test_import_atomic_isolated_and_admin_delete(family):
    admin,member,other=family
    data=b'title,company,status,applied_at,notes\nEngineer,Example,Offer,2026-01-01,Imported\nDesigner,Other,Saved,,\n'
    assert repo.import_tracker(member,data)==dict(added=2,skipped=0)
    assert repo.import_tracker(member,data)==dict(added=0,skipped=2)
    apps=repo.list_applications(member)
    assert len(apps)==2
    assert repo.list_applications(other)==[]
    offer=next(a for a in apps if a['status']=='Offer')
    assert len(repo.application_history(member,offer['id']))==2
    assert repo.job_detail(member,offer['job_id'])['completeness']=='partial'
    with pytest.raises(AppError): repo.delete_tracker(member,offer['id'],'Test deletion')
    repo.delete_tracker(admin,offer['id'],'Test deletion')
    assert len(repo.list_applications(member))==1
