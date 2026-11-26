"""Explicit public source adapters. Premium portal URLs are never scraped."""
import re,json,html
from urllib.parse import quote,urlencode
from datetime import datetime,timezone
import httpx
from .config import AppError
from .db import transaction,one
from .repository import import_job,job_count,list_watchlist,record_scan
from .parsing import plain_html
from .targeting import matches_filters,priority

PROVIDERS=('Greenhouse','Lever','Ashby')

def fetch_json(url,params=None,limit_mb=15):
    try:
        with httpx.Client(timeout=20,follow_redirects=False,headers={'User-Agent':'SANDHATA career workspace'}) as client:
            r=client.get(url,params=params)
            r.raise_for_status()
            if len(r.content)>limit_mb*1024*1024: raise AppError('Source response exceeds the supported size.')
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

def search_remotive(p,filters):
    data,checked,stale=remotive(p)
    # Every Remotive role is remote, so its region list is matched as a remote location.
    found=[j for j in data if matches_filters(dict(j,candidate_required_location='Remote - '+j.get('candidate_required_location','')),filters)]
    found=sorted(found,key=lambda j:priority(j,filters),reverse=True)[:50]
    for j in found:
        import_job(p,j['title'],j['company_name'],j['description'],'Remotive',j['url'],
                   j.get('candidate_required_location',''),j.get('salary',''),str(j['id']),True,'Remote')
    return dict(count=len(found),checked=checked,stale=stale,source='Remotive',feed_delay='24 hours')

def check_board(provider,board):
    if provider not in PROVIDERS: raise AppError('Unsupported employer provider.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',board): raise AppError('Enter only the employer board token, without a URL.')
    return quote(board,safe='')

def with_remote(location,remote):
    if remote and 'remote' not in location.lower(): return (location+' (Remote)').strip()
    return location

def ashby_remote(job):
    # Ashby also sets isRemote on hybrid roles, so the workplace type wins when present.
    if job.get('workplaceType'): return job['workplaceType']=='Remote'
    return bool(job.get('isRemote'))

def parse_board(provider,board,payload):
    '''Normalize one public feed. Descriptions stay HTML; import_job removes the markup.'''
    if provider=='Greenhouse':
        # Greenhouse sends entity-escaped HTML, which must be unescaped before tags can be removed.
        return [dict(title=j['title'],company=board,description=html.unescape(j.get('content') or ''),url=j['absolute_url'],
                     location=(j.get('location') or {}).get('name') or '',salary='',key=str(j['id'])) for j in payload['jobs']]
    if provider=='Lever':
        return [dict(title=j['text'],company=board,
                     description=(j.get('description') or '')+'\n'+''.join('<h3>'+x['text']+'</h3>'+x['content'] for x in j.get('lists') or [])+'\n'+(j.get('additional') or ''),
                     url=j['hostedUrl'],location=with_remote((j.get('categories') or {}).get('location') or '',j.get('workplaceType')=='remote'),
                     salary='',key=j['id']) for j in payload]
    return [dict(title=j['title'],company=board,description=j.get('descriptionHtml') or j.get('descriptionPlain') or '',url=j['jobUrl'],
                 location=with_remote(j.get('location') or '',ashby_remote(j)),
                 salary=(j.get('compensation') or {}).get('compensationTierSummary') or '',key=j.get('id') or j['jobUrl'])
            for j in payload['jobs'] if j.get('isListed',True)]

def fetch_board(provider,board):
    token=check_board(provider,board)
    url,params={
        'Greenhouse':(f'https://boards-api.greenhouse.io/v1/boards/{token}/jobs',{'content':'true'}),
        'Lever':(f'https://api.lever.co/v0/postings/{token}',{'mode':'json'}),
        'Ashby':(f'https://api.ashbyhq.com/posting-api/job-board/{token}',{'includeCompensation':'true'}),
    }[provider]
    payload=fetch_json(url,params,limit_mb=40)
    try: return parse_board(provider,board,payload)
    except (KeyError,TypeError,AttributeError) as exc: raise AppError('The employer feed format was not recognized.') from exc

def employer_feed(p,provider,board,filters=None,limit=50,company=None):
    '''Filter the whole board first, then save the highest-priority matches.'''
    postings=fetch_board(provider,board)
    matched=[]
    for j in postings:
        text=plain_html(j['description'])
        if len(text)<40 or len(j['description'])>150000 or not j['url'].startswith('https://') or not j['title'].strip(): continue
        if filters and not matches_filters(dict(j,description=text),filters): continue
        matched.append(j)
    matched.sort(key=lambda j:priority(j,filters),reverse=True)
    saved=matched[:limit]
    before=job_count(p) if saved else 0
    for j in saved:
        import_job(p,j['title'][:300],company or j['company'],j['description'],provider,j['url'],j['location'],j['salary'],source_key=j['key'],flag_new=True)
    return dict(total=len(postings),matched=len(matched),count=len(saved),new=job_count(p)-before if saved else 0)

def scan_watchlist(p,filters,per_board=25):
    '''One board failing never stops the others.'''
    results=[]
    for w in list_watchlist(p):
        try:
            outcome=employer_feed(p,w['provider'],w['board'],filters,per_board,w['company'])
            note=f"{outcome['matched']} matched of {outcome['total']}; saved {outcome['count']}; {outcome['new']} new"
            results.append(dict(company=w['company'],ok=True,note=note,**outcome))
        except AppError as exc:
            note=str(exc); results.append(dict(company=w['company'],ok=False,note=note))
        record_scan(p,w['id'],note)
    return results

def premium_search_links(title,location):
    return {
        'LinkedIn':'https://www.linkedin.com/jobs/search/?'+urlencode({'keywords':title,'location':location}),
        'Indeed':'https://www.indeed.com/jobs?'+urlencode({'q':title,'l':location}),
        'Ladders':'https://www.theladders.com/jobs/searchjobs?'+urlencode({'title':title,'location':location})
    }
