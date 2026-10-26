"""Explicit public source adapters. Premium portal URLs are never scraped."""
import re,json
from urllib.parse import quote,urlencode
from datetime import datetime,timezone
import httpx
from .config import AppError
from .db import transaction,one
from .repository import import_job
from .parsing import salary_yearly

def fetch_json(url,params=None):
    try:
        with httpx.Client(timeout=20,follow_redirects=False,headers={'User-Agent':'Sandhata personal-family career workspace'}) as client:
            r=client.get(url,params=params)
            r.raise_for_status()
            if len(r.content)>15*1024*1024: raise AppError('Source response exceeds the supported size.')
            return r.json()
    except AppError: raise
    except Exception as exc: raise AppError('Source unavailable. Existing saved jobs remain available; try again later.') from exc

def remotive(p):
    # One deployment-wide cache and lock; private queries never go to this shared cache.
    with transaction(p) as c:
        c.exec_driver_sql("SELECT pg_advisory_xact_lock(hashtextextended('remotive-public-refresh',0))")
        cached=one(c,"SELECT data,updated_at FROM public_cache WHERE key='remotive'")
        if cached and (datetime.now(timezone.utc)-cached['updated_at']).total_seconds()<21600:
            return cached['data'],cached['updated_at'],False
        try: data=fetch_json('https://remotive.com/api/remote-jobs')['jobs']
        except AppError:
            if cached: return cached['data'],cached['updated_at'],True
            raise
        c.exec_driver_sql("INSERT INTO public_cache(key,data) VALUES('remotive',%(data)s::jsonb) ON CONFLICT(key) DO UPDATE SET data=EXCLUDED.data,updated_at=now()",dict(data=json.dumps(data)))
        return data,datetime.now(timezone.utc),False

def matches_filters(job,filters):
    title=job.get('title','').lower(); company=job.get('company_name',job.get('company','')).lower()
    body=(title+' '+company+' '+job.get('description','')).lower()
    location=job.get('candidate_required_location',job.get('location','')).lower()
    if filters.get('title') and not any(t.strip().lower() in title for t in filters['title'].split(',') if t.strip()): return False
    if filters.get('company') and filters['company'].lower() not in company: return False
    required=[s.strip().lower() for s in filters.get('required_skills','').split(',') if s.strip()]
    if required and not all(s in body for s in required): return False
    if any(s.strip().lower() in body for s in filters.get('exclude','').split(',') if s.strip()): return False
    if filters.get('location') and filters['location'].lower() not in location and location not in ('worldwide','anywhere'): return False
    pay=salary_yearly(job.get('salary',''))
    if filters.get('minimum_salary') and (pay is None or pay[1]<float(filters['minimum_salary'])):
        return bool(pay is None and filters.get('include_unknown_salary',True))
    return True

def search_remotive(p,filters):
    data,checked,stale=remotive(p)
    found=[j for j in data if matches_filters(j,filters)][:50]
    for j in found:
        import_job(p,j['title'],j['company_name'],j['description'],'Remotive',j['url'],
                   j.get('candidate_required_location',''),j.get('salary',''),str(j['id']),True,'Remote')
    return dict(count=len(found),checked=checked,stale=stale,source='Remotive',feed_delay='24 hours')

def employer_feed(p,provider,board):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',board): raise AppError('Enter only the employer board token, without a URL.')
    token=quote(board,safe='')
    if provider=='Greenhouse':
        jobs=fetch_json(f'https://boards-api.greenhouse.io/v1/boards/{token}/jobs',{'content':'true'})['jobs']
        parsed=[dict(title=j['title'],company=board,description=j.get('content',''),url=j['absolute_url'],location=j.get('location',{}).get('name',''),key=str(j['id'])) for j in jobs]
    elif provider=='Lever':
        jobs=fetch_json(f'https://api.lever.co/v0/postings/{token}',{'mode':'json'})
        parsed=[dict(title=j['text'],company=board,description=j.get('description','')+'\n'+''.join('<h3>'+s['text']+'</h3>'+s['content'] for s in j.get('lists',[]))+'\n'+j.get('additional',''),url=j['hostedUrl'],location=j.get('categories',{}).get('location',''),key=j['id']) for j in jobs]
    elif provider=='Ashby':
        jobs=fetch_json(f'https://api.ashbyhq.com/posting-api/job-board/{token}',{'includeCompensation':'true'})['jobs']
        parsed=[dict(title=j['title'],company=board,description=j.get('descriptionHtml',j.get('descriptionPlain','')),url=j['jobUrl'],location=j.get('location',''),key=j.get('id',j['jobUrl'])) for j in jobs if j.get('isListed',True)]
    else: raise AppError('Unsupported employer provider.')
    count=0
    for j in parsed[:50]:
        if len(j['description'])<40: continue
        import_job(p,j['title'],j['company'],j['description'],provider,j['url'],j['location'],source_key=j['key']); count+=1
    return count

def premium_search_links(title,location):
    return {
        'LinkedIn':'https://www.linkedin.com/jobs/search/?'+urlencode({'keywords':title,'location':location}),
        'Indeed':'https://www.indeed.com/jobs?'+urlencode({'q':title,'l':location}),
        'Ladders':'https://www.theladders.com/jobs/searchjobs?'+urlencode({'title':title,'location':location})
    }
