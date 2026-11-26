"""Deterministic job matching and priority ordering. No model calls, no storage."""
import re
from .parsing import salary_yearly

# Defaults for senior and lead AI roles; users can replace them with a saved search.
TARGET_FILTERS=dict(
    title='Forward Deployed, AI Engineer, Applied AI, AI Architect, AI Solutions, Machine Learning Engineer',
    company='',required_skills='',location='Charlotte; North Carolina; NC; US remote',
    minimum_salary=0,exclude='intern, internship, new grad',include_unknown_salary=True)
SENIORITY=('senior','sr','lead','staff','principal','manager','director','head')
# Employer boards that answered on 2026-11-26. Employers can move or close boards.
SUGGESTED_BOARDS=[
    ('Greenhouse','anthropic','Anthropic'),('Greenhouse','scaleai','Scale AI'),
    ('Greenhouse','databricks','Databricks'),('Greenhouse','stripe','Stripe'),
    ('Lever','palantir','Palantir'),('Ashby','openai','OpenAI'),('Ashby','perplexity','Perplexity'),
    ('Ashby','harvey','Harvey'),('Ashby','baseten','Baseten'),('Ashby','langchain','LangChain'),
]
US_MARKERS=('us','usa','u.s','u.s.a','united states','north america','americas')
ANYWHERE=('worldwide','anywhere')
US_STATE_CODE=re.compile(r',\s*(al|ak|az|ar|ca|co|ct|dc|de|fl|ga|hi|ia|id|il|in|ks|ky|la|ma|md|me|mi|mn|mo|ms|mt|nc|nd|ne|nh|nj|nm|nv|ny|oh|ok|or|pa|ri|sc|sd|tn|tx|ut|va|vt|wa|wi|wv|wy)\b')
US_PLACES=('new york','san francisco','seattle','boston','austin','chicago','atlanta','denver','charlotte',
    'north carolina','south carolina','california','texas','virginia','washington','massachusetts','illinois','georgia','colorado','florida')

def terms(value,separator=','):
    return [t.strip().lower() for t in (value or '').split(separator) if t.strip()]

def has_term(text,term):
    """Whole-term match, so 'nc' never matches 'France' and 'java' never matches 'javascript'."""
    return re.search(r'(?<![a-z0-9])'+re.escape(term)+r'(?![a-z0-9])',text) is not None

def title_matches(title,wanted):
    """Every word must appear, in any order. Words over three letters also match longer forms."""
    words=re.findall(r'[a-z0-9+#.]+',wanted)
    return bool(words) and all(
        re.search(r'(?<![a-z0-9])'+re.escape(w)+('' if len(w)>3 else r'(?![a-z0-9])'),title) for w in words)

def us_remote(location):
    for segment in re.split(r'[;|/]|\bor\b',location):
        if any(has_term(segment,a) for a in ANYWHERE): return True
        if not has_term(segment,'remote'): continue
        if any(has_term(segment,m) for m in US_MARKERS+US_PLACES) or US_STATE_CODE.search(segment): return True
        # A bare "Remote" names no country. "Remote - India" does, so it is not accepted.
        if not re.sub(r'\(travel[^)]*\)|remote|friendly|fully|first|[^a-z]','',segment): return True
    return False

def location_matches(location,wanted):
    """`wanted` holds alternatives separated by semicolons. 'US remote' covers US-eligible remote roles."""
    location=(location or '').lower()
    alternatives=terms(wanted,';')
    if not alternatives: return True
    if any(has_term(location,a) for a in ANYWHERE): return True
    return any(us_remote(location) if a=='us remote' else has_term(location,a) for a in alternatives)

def matches_filters(job,filters):
    title=job.get('title','').lower(); company=job.get('company_name',job.get('company','')).lower()
    body=(title+' '+company+' '+job.get('description','')).lower()
    location=job.get('candidate_required_location',job.get('location',''))
    wanted=terms(filters.get('title'))
    if wanted and not any(title_matches(title,t) for t in wanted): return False
    if filters.get('company') and filters['company'].lower() not in company: return False
    if not all(has_term(body,s) for s in terms(filters.get('required_skills'))): return False
    if any(has_term(body,s) for s in terms(filters.get('exclude'))): return False
    if not location_matches(location,filters.get('location','')): return False
    pay=salary_yearly(job.get('salary',''))
    if filters.get('minimum_salary') and (pay is None or pay[1]<float(filters['minimum_salary'])):
        return bool(pay is None and filters.get('include_unknown_salary',True))
    return True

def priority(job,filters=None):
    """Higher sorts first. An ordering aid only, not a measure of fit."""
    filters=filters or TARGET_FILTERS
    title=job.get('title','').lower()
    score=0
    if any(title_matches(title,t) for t in terms(filters.get('title'))): score+=4
    if has_term(title,'forward deployed'): score+=3
    if any(has_term(title,level) for level in SENIORITY): score+=2
    location=job.get('candidate_required_location',job.get('location',''))
    if filters.get('location') and location_matches(location,filters['location']): score+=1
    return score
