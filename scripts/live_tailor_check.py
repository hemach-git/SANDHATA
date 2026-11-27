"""Local-model check of the Tailor Writer and Verifier on synthetic data only. Not a full quality evaluation.

Writes deliverables/verification/live_tailor_check.json. Usage:
  python scripts/live_tailor_check.py [--verifier-only]
"""
import sys,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'));sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from sandhata.agents import verifier as verification
from sandhata.agents.tailor import tailor
from sandhata.config import ROOT,MODEL,VERIFIER_MODEL
from sandhata.matching import build_graph
from sandhata.providers import get_provider
from sandhata.tailor_validation import check_text
from tailor_fixtures import RESUME,JOB

# (original, rewrite, does the rewrite claim more than the original?). Labelled by the author of the rules.
CASES=[
    ('Built a tool','Built a hugely successful award-winning tool',True),
    ('Built pipelines','Built pipelines with celery',True),
    ('Used the data platform','Designed the data platform',True),
    ('Built pipelines','Redfed pipelines built',True),
    ('Wrote tests for the billing service','Rebuilt the billing service and wrote its tests',True),
    ('Attended design reviews for the search system','Drove design decisions for the search system',True),
    ('Fixed bugs in the chat assistant','Delivered the chat assistant to production',True),
    ('Wrote a prototype of a retrieval tool','Shipped a retrieval tool',True),
    ('Supported analysts with weekly reports','Transformed how analysts work with weekly reports',True),
    ('Gave a demo to one customer','Gave demos that won customers over',True),
    ('Built a document search tool for the legal team','For the legal team, built a document search tool',False),
    ('Wrote Python pipelines that load policy documents','Wrote Python pipelines to load policy documents',False),
    ('Delivered SQL dashboards used by store managers','Delivered SQL dashboards that store managers used',False),
    ('Helped reduce review latency through caching','Through caching, helped reduce review latency',False),
    ('Mentored 3 engineers on evaluation practices','Mentored 3 engineers in evaluation practices',False),
    ('Created Spark pipelines for nightly sales reporting','Built Spark pipelines for nightly sales reporting',False),
    ('Deployed to 40 claims users after weekly working sessions','After weekly working sessions, deployed to 40 claims users',False),
    ('Maintained the internal model registry and its documentation','Maintained the internal model registry and documentation',False),
    ('Ran discovery workshops with two product teams','With two product teams, ran discovery workshops',False),
    ('Tested prompts for a support assistant','Tested support assistant prompts',False),
]

# Written before the second prompt and gate version was run, and not used to adjust it. Mixed order, as in real runs.
HELD_OUT=[
    ('Reviewed pull requests for the ingestion service','For the ingestion service, reviewed pull requests',False),
    ('Joined on-call rotation for the payments platform','Ran the on-call rotation for the payments platform',True),
    ('Automated monthly invoice checks with Python scripts','Automated monthly invoice checks using Python scripts',False),
    ('Trained a text classifier on support tickets','Deployed a text classifier on support tickets',True),
    ('Presented test results to the product owner','Presented test results to executive leadership',True),
    ('Documented the deployment steps for the data science team','Documented deployment steps for the data science team',False),
    ('Added logging to the recommendation service','Re-engineered observability for the recommendation service',True),
    ('Worked with two nurses to test a triage assistant','Tested a triage assistant with two nurses',False),
    ('Contributed fixes to an open source parser','Maintained an open source parser',True),
    ('Profiled slow queries and added database indexes','Added database indexes and profiled slow queries',False),
    ('Evaluated three embedding models for search','Selected the embedding model for search',True),
    ('Wrote onboarding notes for new interns','Wrote notes to onboard new interns',False),
    ('Built a dashboard showing model error rates','Built a dashboard that cut model error rates',True),
    ('Set up nightly backups for the research database','Set up nightly research database backups',False),
    ('Answered customer questions about the search API','Advised customers on search API strategy',True),
    ('Converted spreadsheet reports into SQL views','Turned spreadsheet reports into SQL views',False),
    ('Piloted a summarization tool with one support team','Rolled out a summarization tool to support teams',True),
    ('Refactored the prompt library to remove duplicate templates','Removed duplicate templates by refactoring the prompt library',False),
    ('Observed customer calls to collect requirements','Led customer discovery to define requirements',True),
    ('Scheduled weekly demos for the operations group','Scheduled demos each week for the operations group',False),
]

def verifier_check(provider,cases):
    items=[dict(id=f'case{n}',before=before,after=after,evidence=[before]) for n,(before,after,_) in enumerate(cases)]
    verdicts={};seconds=[]
    for start in range(0,len(items),10):
        batch=items[start:start+10];began=time.monotonic()
        system,user,schema=verification.request(batch)
        try: verdicts.update(verification.judge(provider.generate(system,user,schema,8000).content,batch))
        except Exception as exc:
            verdicts.update({i['id']:verification.not_checked(type(exc).__name__) for i in batch})
        seconds.append(round(time.monotonic()-began,1));print('verifier batch',len(seconds),seconds[-1],'s',flush=True)
    rows=[]
    for item,(before,after,over) in zip(items,cases):
        rules=check_text(after,before,'',before)[0]
        rows.append(dict(before=before,after=after,overstated=over,code_rules=rules or 'passed',**verdicts[item['id']]))
    over=[x for x in rows if x['overstated']];fine=[x for x in rows if not x['overstated']]
    summary=dict(
        overstated_cases=len(over),
        stopped_by_code_rules=sum(x['code_rules']!='passed' for x in over),
        rejected_by_verifier=sum(x['status']=='rejected' for x in over),
        flagged_by_verifier=sum(x['status']=='warning' for x in over),
        stopped_by_either=sum(x['code_rules']!='passed' or x['status']=='rejected' for x in over),
        passed_both=[x['after'] for x in over if x['code_rules']=='passed' and x['status']=='passed'],
        faithful_cases=len(fine),
        faithful_rejected_by_verifier=sum(x['status']=='rejected' for x in fine),
        faithful_warned_by_verifier=sum(x['status']=='warning' for x in fine),
        faithful_passed_cleanly=sum(x['status']=='passed' and x['code_rules']=='passed' for x in fine),
        faithful_rejected_by_code_rules=sum(x['code_rules']!='passed' for x in fine),
        not_checked=sum(x['status']=='not_checked' for x in rows),
        seconds_per_batch=seconds)
    return dict(summary=summary,cases=rows)

def end_to_end(writer,checker):
    report={};began=time.monotonic();trace=[];assessment=None;calls=0
    try:
        state=build_graph(provider=writer).invoke(dict(job=JOB,resume=RESUME,completeness='full',trace=[]))
        assessment=state['result'];trace+=state['trace'];calls=state['attempts']
    except Exception as exc: report['fit_analyst']='unavailable: '+type(exc).__name__;calls=2
    report['fit_seconds']=round(time.monotonic()-began,1);print('fit',report['fit_seconds'],'s',flush=True)
    try:
        result=tailor(RESUME,JOB,'fde','lead',writer,checker,assessment,trace=trace,calls=calls)
        report.update(outcome='ready_for_review',shown=len(result['suggestions']),dropped=result['dropped'],gaps=result['gaps'],
            suggestions=[{k:s[k] for k in ('unit_id','change_type','before','after','new_position','warnings','verdict')} for s in result['suggestions']])
    except Exception as exc: report.update(outcome='failed',error=type(exc).__name__+': '+str(exc)[:200])
    report.update(total_seconds=round(time.monotonic()-began,1),trace=trace)
    print('end to end',report['outcome'],report.get('shown'),report['total_seconds'],'s',flush=True)
    return report

if __name__=='__main__':
    target=ROOT/'deliverables/verification/live_tailor_check.json'
    writer=get_provider(model=MODEL,timeout=420);checker=get_provider(model=VERIFIER_MODEL,timeout=420)
    report=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
    report.update(writer_model=MODEL,verifier_model=VERIFIER_MODEL,
        scope='Synthetic data only. One tailoring run and 20 hand-labelled rewrite cases written by the author of the rules; not a full quality evaluation.')
    report['verifier_prompt']=verification.PROMPT_VERSION
    report['verifier']=verifier_check(checker,CASES)
    report['verifier_held_out']=verifier_check(checker,HELD_OUT)
    if '--verifier-only' not in sys.argv: report['end_to_end']=end_to_end(writer,checker)
    target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(report,indent=2),encoding='utf-8')
    for name in ('verifier','verifier_held_out'): print(name,json.dumps(report[name]['summary'],indent=2))
