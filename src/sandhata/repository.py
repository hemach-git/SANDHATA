import hashlib,json,uuid
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlsplit
from .config import DATA,AppError
from .db import transaction,rows,one,scoped
from .parsing import plain_html,parse_resume,passages

STATUSES=['Saved','Preparing','Applied','Screening','Interviewing','Offer','Hired','Rejected','Withdrawn','Cancelled']

def private_path(key):
    path=(DATA/key).resolve()
    if not path.is_relative_to(DATA.resolve()): raise AppError('Invalid private object reference.')
    return path

def index_text(c,p,parent_id,parent_type,body):
    for offset,chunk in passages(body):
        c.exec_driver_sql('INSERT INTO passages(tenant_id,owner_user_id,parent_id,parent_type,start_offset,body) VALUES(%(t)s::uuid,%(u)s::uuid,%(id)s::uuid,%(kind)s,%(o)s,%(body)s)',scoped(p,id=str(parent_id),kind=parent_type,o=offset,body=chunk))

def import_job(p,title,company,description,source='Manual import',url='',location='',salary='',source_key=None,complete=True,workplace=''):
    title,company=title.strip(),company.strip()
    if not title or not company or len(title)>300 or len(company)>200: raise AppError('Job title and company are required and must fit the field limits.')
    if len(description)>150000 or len(description.strip())<40: raise AppError('Paste a description between 40 and 150,000 characters.')
    if url and (urlsplit(url).scheme!='https' or not urlsplit(url).hostname): raise AppError('Use an HTTPS original posting URL.')
    body=plain_html(description)
    if len(body)<40: raise AppError('Not enough description text remains after removing markup.')
    body=body.replace('\x00','')
    content_hash=hashlib.sha256(body.encode()).hexdigest()
    key=str(source_key or url or hashlib.sha256((title+'|'+company+'|'+location).encode()).hexdigest())
    with transaction(p) as c:
        j=one(c,'INSERT INTO jobs(tenant_id,owner_user_id,title,company,location,salary,source,original_url,source_key,workplace) VALUES(%(t)s::uuid,%(u)s::uuid,%(title)s,%(company)s,%(location)s,%(salary)s,%(source)s,%(url)s,%(key)s,%(workplace)s) ON CONFLICT(tenant_id,owner_user_id,source,source_key) DO UPDATE SET last_checked=now(),title=EXCLUDED.title,company=EXCLUDED.company,location=EXCLUDED.location,salary=EXCLUDED.salary RETURNING id',scoped(p,title=title,company=company,location=location[:400],salary=salary[:400],source=source[:100],url=url,key=key,workplace=workplace))
        v=one(c,'INSERT INTO job_versions(tenant_id,owner_user_id,job_id,body,raw_html,content_hash,completeness) VALUES(%(t)s::uuid,%(u)s::uuid,%(job)s::uuid,%(body)s,%(raw)s,%(hash)s,%(comp)s) ON CONFLICT(tenant_id,owner_user_id,job_id,content_hash) DO NOTHING RETURNING id',scoped(p,job=str(j['id']),body=body,raw=description,hash=content_hash,comp='full' if complete else 'partial'))
        if v: index_text(c,p,v['id'],'job',body)
        return str(j['id'])

def list_jobs(p,query='',limit=100):
    with transaction(p) as c:
        return rows(c,"SELECT j.*,v.id version_id,v.body,v.completeness FROM jobs j JOIN LATERAL (SELECT id,body,completeness FROM job_versions WHERE job_id=j.id ORDER BY created_at DESC LIMIT 1) v ON true WHERE (%(q)s='' OR to_tsvector('simple',j.title||' '||j.company||' '||j.location||' '||v.body) @@ plainto_tsquery('simple',%(q)s)) ORDER BY j.created_at DESC LIMIT %(n)s",dict(q=query[:200],n=min(int(limit),200)))

def job_detail(p,job_id,version_id=None):
    with transaction(p) as c:
        r=one(c,'SELECT j.*,v.id version_id,v.body,v.raw_html,v.completeness FROM jobs j JOIN job_versions v ON v.job_id=j.id WHERE j.id=%(id)s::uuid AND (%(version)s::uuid IS NULL OR v.id=%(version)s::uuid) ORDER BY v.created_at DESC LIMIT 1',dict(id=str(job_id),version=str(version_id) if version_id else None))
        if not r: raise AppError('Job unavailable in your workspace.')
        return r

def upload_resume(p,data,filename,label):
    if not label.strip() or len(label)>100: raise AppError('Choose a label of at most 100 characters.')
    parsed=parse_resume(data,filename)
    rid=str(uuid.uuid4()); key=f'{p.tenant_id}/{p.user_id}/{rid}.{parsed["ext"]}'
    file=private_path(key)
    with transaction(p) as c:
        # Serialize quota checks for concurrent uploads in this member workspace.
        c.exec_driver_sql('SELECT pg_advisory_xact_lock(hashtextextended(%(key)s,0))',dict(key=p.tenant_id+p.user_id))
        existing=rows(c,'SELECT object_key FROM resumes')
        if len(existing)>=20 or sum(private_path(r['object_key']).stat().st_size for r in existing if private_path(r['object_key']).exists())+len(data)>100*1024*1024: raise AppError('Resume or storage quota reached. Delete an unused version first.')
        file.parent.mkdir(parents=True,exist_ok=True)
        file.write_bytes(data)
        try:
            c.exec_driver_sql('INSERT INTO resumes(id,tenant_id,owner_user_id,label,object_key,file_hash,body,parser_version) VALUES(%(id)s::uuid,%(t)s::uuid,%(u)s::uuid,%(label)s,%(key)s,%(hash)s,%(body)s,%(parser)s)',scoped(p,id=rid,label=label.strip(),key=key,hash=parsed['file_hash'],body=parsed['body'],parser=parsed['parser_version']))
            index_text(c,p,rid,'resume',parsed['body'])
        except Exception:
            file.unlink(missing_ok=True)
            raise
    return rid

def list_resumes(p):
    with transaction(p) as c: return rows(c,'SELECT id,label,file_hash,created_at,parser_version FROM resumes ORDER BY created_at DESC')

def resume_detail(p,resume_id):
    with transaction(p) as c:
        r=one(c,'SELECT * FROM resumes WHERE id=%(id)s::uuid',dict(id=str(resume_id)))
        if not r: raise AppError('Resume unavailable in your workspace.')
        return r

def resume_download(p,resume_id):
    r=resume_detail(p,resume_id)
    path=private_path(r['object_key'])
    if not path.exists(): raise AppError('Original file unavailable; contact the operator about recovery.')
    return path.read_bytes(),path.suffix

def delete_resume(p,resume_id):
    with transaction(p) as c:
        r=one(c,'SELECT object_key FROM resumes WHERE id=%(id)s::uuid FOR UPDATE',dict(id=str(resume_id)))
        if not r: raise AppError('Resume unavailable in your workspace.')
        c.exec_driver_sql('INSERT INTO deletion_tombstones(tenant_id,owner_user_id,object_id,object_type) VALUES(%(t)s::uuid,%(u)s::uuid,%(id)s::uuid,\'resume\') ON CONFLICT DO NOTHING',scoped(p,id=str(resume_id)))
        c.exec_driver_sql('UPDATE applications SET resume_id=NULL WHERE resume_id=%(id)s::uuid',dict(id=str(resume_id)))
        c.exec_driver_sql('DELETE FROM assessments WHERE resume_id=%(id)s::uuid',dict(id=str(resume_id)))
        c.exec_driver_sql("DELETE FROM tasks WHERE payload->>'resume_id'=%(id)s",dict(id=str(resume_id)))
        c.exec_driver_sql("DELETE FROM passages WHERE parent_type='resume' AND parent_id=%(id)s::uuid",dict(id=str(resume_id)))
        c.exec_driver_sql('DELETE FROM resumes WHERE id=%(id)s::uuid',dict(id=str(resume_id)))
    private_path(r['object_key']).unlink(missing_ok=True)

def save_profile(p,label,filters):
    with transaction(p) as c:
        return str(one(c,'INSERT INTO profiles(tenant_id,owner_user_id,label,filters) VALUES(%(t)s::uuid,%(u)s::uuid,%(label)s,%(f)s::jsonb) RETURNING id',scoped(p,label=label[:100],f=json.dumps(filters)))['id'])

def list_profiles(p):
    with transaction(p) as c: return rows(c,'SELECT id,label,filters FROM profiles ORDER BY created_at DESC')

def save_to_tracker(p,job_id):
    job_detail(p,job_id)
    with transaction(p) as c:
        r=one(c,'INSERT INTO applications(tenant_id,owner_user_id,job_id) VALUES(%(t)s::uuid,%(u)s::uuid,%(job)s::uuid) ON CONFLICT(tenant_id,owner_user_id,job_id) DO UPDATE SET job_id=EXCLUDED.job_id RETURNING id',scoped(p,job=str(job_id)))
        return str(r['id'])

def list_applications(p,query=''):
    with transaction(p) as c: return rows(c,"SELECT a.*,j.title,j.company,j.source,j.original_url FROM applications a JOIN jobs j ON j.id=a.job_id WHERE (%(q)s='' OR to_tsvector('simple',j.title||' '||j.company||' '||a.notes) @@ plainto_tsquery('simple',%(q)s)) ORDER BY a.updated_at DESC",dict(q=query[:200]))

def update_application(p,app_id,status,notes,occurred_at,request_id,resume_id=None,follow_up=None):
    if status not in STATUSES or len(notes)>10000: raise AppError('Choose a valid status and notes under 10,000 characters.')
    if occurred_at.tzinfo is None or occurred_at>datetime.now(timezone.utc): raise AppError('Use a timezone-aware event date that is not in the future.')
    with transaction(p) as c:
        app=one(c,'SELECT * FROM applications WHERE id=%(id)s::uuid FOR UPDATE',dict(id=str(app_id)))
        if not app: raise AppError('Tracker item unavailable in your workspace.')
        if resume_id and not one(c,'SELECT id FROM resumes WHERE id=%(id)s::uuid',dict(id=str(resume_id))): raise AppError('Selected resume unavailable.')
        event=one(c,'INSERT INTO status_events(tenant_id,owner_user_id,application_id,status,occurred_at,request_id) VALUES(%(t)s::uuid,%(u)s::uuid,%(a)s::uuid,%(s)s,%(date)s,%(rid)s) ON CONFLICT(tenant_id,owner_user_id,request_id) DO NOTHING RETURNING id',scoped(p,a=str(app_id),s=status,date=occurred_at,rid=request_id))
        if not event: return
        c.exec_driver_sql("UPDATE applications SET status=%(s)s,notes=%(notes)s,resume_id=coalesce(%(r)s::uuid,resume_id),follow_up=%(follow)s,applied_at=CASE WHEN %(s)s='Applied' THEN coalesce(applied_at,%(date)s) ELSE applied_at END,updated_at=now() WHERE id=%(id)s::uuid",dict(s=status,notes=notes,r=str(resume_id) if resume_id else None,follow=follow_up,date=occurred_at,id=str(app_id)))

def application_history(p,app_id):
    with transaction(p) as c: return rows(c,'SELECT status,occurred_at,recorded_at FROM status_events WHERE application_id=%(id)s::uuid ORDER BY recorded_at',dict(id=str(app_id)))

def retrieve(p,query,limit=5,parent_id=None):
    with transaction(p) as c:
        return rows(c,"SELECT id,parent_id,parent_type,start_offset,body,ts_rank(search_doc,plainto_tsquery('simple',%(q)s)) rank FROM passages WHERE search_doc @@ plainto_tsquery('simple',%(q)s) AND (%(parent)s::uuid IS NULL OR parent_id=%(parent)s::uuid) ORDER BY rank DESC LIMIT %(n)s",dict(q=query[:200],parent=str(parent_id) if parent_id else None,n=max(1,min(int(limit),20))))

def tracker_metrics(p,start,end):
    with transaction(p) as c:
        current=rows(c,'SELECT status,count(*) n FROM applications GROUP BY status')
        cohort=rows(c,"SELECT a.id,a.applied_at,j.source,r.label resume_label,EXISTS(SELECT 1 FROM status_events e WHERE e.application_id=a.id AND e.status='Interviewing') interview,EXISTS(SELECT 1 FROM status_events e WHERE e.application_id=a.id AND e.status='Offer') offer FROM applications a JOIN jobs j ON j.id=a.job_id LEFT JOIN resumes r ON r.id=a.resume_id WHERE (a.applied_at AT TIME ZONE %(tz)s)::date BETWEEN %(start)s AND %(end)s",dict(tz=p.timezone,start=start,end=end))
        weekly=rows(c,"SELECT date_trunc('week',applied_at AT TIME ZONE %(tz)s)::date week,count(*) applications FROM applications WHERE (applied_at AT TIME ZONE %(tz)s)::date BETWEEN %(start)s AND %(end)s GROUP BY 1 ORDER BY 1",dict(tz=p.timezone,start=start,end=end))
        latest=rows(c,'SELECT DISTINCT ON (v.job_id) a.result FROM assessments a JOIN job_versions v ON v.id=a.job_version_id ORDER BY v.job_id,a.created_at DESC')
    gaps={}
    for a in latest:
        for requirement in a['result'].get('requirements',[]):
            if requirement['status']=='not_evidenced': gaps[requirement['requirement_quote']]=gaps.get(requirement['requirement_quote'],0)+1
    return dict(current=current,cohort=cohort,weekly=weekly,gaps=sorted(gaps.items(),key=lambda x:x[1],reverse=True)[:15],timezone=p.timezone)

def assessment_detail(p,assessment_id):
    with transaction(p) as c:
        r=one(c,'SELECT * FROM assessments WHERE id=%(id)s::uuid',dict(id=str(assessment_id)))
        if not r: raise AppError('Assessment unavailable in your workspace.')
        return r

def tasks(p):
    with transaction(p) as c: return rows(c,'SELECT id,state,error_code,trace,result_id,created_at,finished_at FROM tasks ORDER BY created_at DESC LIMIT 50')
