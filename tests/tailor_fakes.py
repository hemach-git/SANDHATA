"""Stand-ins for the local model, and a synthetic assessment. No network, no real model."""
import json
from sandhata.providers import Reply
from tailor_fixtures import RESUME

B1='Built a document Q&A tool using LangChain and OpenAI for the claims team'
B2='Deployed to 40 claims users after weekly working sessions with the team'
B3='Helped reduce review latency by 35% through caching and prompt changes'
B4='Mentored 3 engineers on evaluation practices for retrieval quality'
CUSTOMER='Work directly with customers to deploy AI solutions into production.'
REQUIRED='Required: Python, LangChain, retrieval evaluation and stakeholder management.'
PREFERRED='Experience with Kubernetes, Terraform and customer-facing delivery is preferred.'

GOOD_B2='After weekly working sessions with the team, deployed to 40 claims users'
GOOD_B4='Mentored 3 engineers in evaluation practices for retrieval quality'
GOOD_SKILLS='Tools: LangChain, Kubernetes, pgvector, Spark'

def assessment():
    def requirement(quote,status,resume=''):
        return dict(category='required_skills',requirement_quote=quote,status=status,resume_quote=resume,rationale='Synthetic',
                    resume_offset=RESUME.index(resume) if resume else None)
    return dict(requirements=[requirement(REQUIRED,'partial',B4),requirement(CUSTOMER,'supported',B2),
                              requirement(PREFERRED,'not_evidenced')],eligibility_flags=[])

def analyzer(job,resume,repair):
    """Fit Analyst stand-in for graph runs: the same judgments without offsets, which the validator adds."""
    return {'requirements':[{k:v for k,v in r.items() if k!='resume_offset'} for r in assessment()['requirements']]},{}

def proposal(unit_id,after,change_type='rephrase',evidence=None,job_quote=CUSTOMER,**extra):
    originals=dict([('r1.b1',B1),('r1.b2',B2),('r1.b3',B3),('r1.b4',B4),('k2','Tools: LangChain, pgvector, Spark, Kubernetes')])
    return dict(unit_id=unit_id,change_type=change_type,after=after,
                evidence=[dict(quote=q) for q in (evidence or [originals[unit_id]])],job_quote=job_quote,rationale='Synthetic',**extra)

def standard_draft():
    return [proposal('r1.b2',GOOD_B2),proposal('r1.b4',GOOD_B4,job_quote=REQUIRED),
            proposal('k2',GOOD_SKILLS,'skills_reorder',job_quote=PREFERRED)]

class Writer:
    """Replies with each scripted draft in turn; the last one repeats. A string is sent as is; an exception is raised."""
    name='ollama'; model='fake-writer'
    def __init__(self,*drafts):
        self.drafts=list(drafts) or [standard_draft()]; self.requests=[]
    def generate(self,system,user,schema,max_tokens=6000):
        self.requests.append(json.loads(user))
        draft=self.drafts[min(len(self.requests),len(self.drafts))-1]
        if callable(draft): draft=draft()
        if isinstance(draft,Exception): raise draft
        return Reply(draft if isinstance(draft,str) else json.dumps(dict(proposals=draft)),100,50)

class Checker:
    """Verifier stand-in. `flag` maps text found in AFTER to the verdict to return; everything else is supported."""
    name='ollama'; model='fake-verifier'
    def __init__(self,flag=None,fail=False):
        self.flag=flag or {}; self.fail=fail; self.requests=[]
    def generate(self,system,user,schema,max_tokens=6000):
        items=json.loads(user)['ITEMS']; self.requests.append(items)
        if self.fail: raise RuntimeError('synthetic outage')
        verdicts=[]
        for item in items:
            found=next(((text,verdict) for text,verdict in self.flag.items() if text in item['AFTER']),None)
            verdicts.append(dict(id=item['id'],verdict=found[1],phrase=found[0],reason='Synthetic') if found
                            else dict(id=item['id'],verdict='supported',phrase='',reason=''))
        return Reply(json.dumps(dict(verdicts=verdicts)),80,20)
