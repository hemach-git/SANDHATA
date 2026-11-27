"""Golden-set evaluation of Resume Tailor with the local model. Synthetic data only.

Run through scripts/live_evals.py:
  python scripts/live_evals.py --suite tailor                 run the cases not yet saved for these versions
  python scripts/live_evals.py --suite tailor --fresh         run every case again
  python scripts/live_evals.py --suite tailor --score FILE    score a review sheet filled in by a person

Automatic checks cover forbidden words, kept qualifiers, gaps and expected targets. Whether a proposal is
truly supported or useful is a person's judgment, recorded in the review sheet. This script never fills it in.
"""
import csv,json,math,re,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from sandhata.agents.tailor import tailor,PROMPT_VERSION,REWRITES
from sandhata.agents.verifier import PROMPT_VERSION as VERIFIER_PROMPT_VERSION
from sandhata.config import ROOT,MODEL,VERIFIER_MODEL,AppError
from sandhata.matching import build_graph
from sandhata.planner import LENS_VERSION
from sandhata.providers import get_provider
from sandhata.segmenter import segment
from sandhata.tailor_validation import POLICY_VERSION

GOLDEN=ROOT/'evals/tailor_golden.jsonl'
OUT=ROOT/'deliverables/verification'
REVIEW_COLUMNS=['case','group','proposal','change','before','after','evidence','second_ai_check','unsupported (y/n)','useful (y/n)','reviewer note']
REVIEW_MINIMUM=100

def load_cases(path=GOLDEN):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]

def has(text,phrase):
    return re.search(r'(?<![A-Za-z0-9])'+re.escape(phrase)+r'(?![A-Za-z0-9])',text,re.I) is not None

def check_case(case,result):
    """Automatic pass or fail for one finished run. Returns a list of problems."""
    expect=case['expect'];problems=[]
    rewrites=[s for s in result['suggestions'] if s['change_type'] in REWRITES+('skills_reorder',)]
    for s in rewrites:
        for term in expect.get('forbid',[]):
            if has(s['after'],term) and not has(s['before'],term): problems.append(f"added '{term}' to {s['unit_id']}")
    keep=expect.get('keep')
    if keep:
        for s in rewrites:
            if s['before']==keep['unit'] and not any(has(s['after'],word) for word in keep['any']):
                problems.append('dropped the shared or planned qualifier from '+s['unit_id'])
    wanted=expect.get('unit_any')
    if wanted and not any(s['before'] in wanted for s in result['suggestions']): problems.append('no proposal for the expected bullet')
    shown={g['label'] for g in result['gaps'] if g['kind']=='level'}
    problems+=[f"gap '{label}' not shown" for label in expect.get('gaps',[]) if label not in shown]
    return problems

def run_case(case,writer,checker,with_fit=False):
    started=time.monotonic();trace=[];assessment=None;calls=0
    if with_fit:
        try:
            state=build_graph(provider=writer).invoke(dict(job=case['job'],resume=case['resume'],completeness='full',trace=[]))
            assessment=state['result'];trace+=state['trace'];calls=state['attempts']
        except AppError:
            calls=2;trace.append(dict(component='fit_analyst',outcome='unavailable_planning_without_it'))
    base=dict(id=case['id'],group=case['group'])
    try: result=tailor(case['resume'],case['job'],case['track'],case['level'],writer,checker,assessment,trace=trace,calls=calls)
    except AppError as exc:
        return dict(base,outcome='failed',error=str(exc)[:300],seconds=round(time.monotonic()-started,1),problems=['run failed'],trace=trace)
    targets=next((t['targets'] for t in result['trace'] if t['component']=='planner'),0)
    bodies={u.unit_id:u.text for u in segment(case['resume'])}
    shown=[dict(s,before=bodies[s['unit_id']]) for s in result['suggestions']]
    return dict(base,outcome='completed',seconds=round(time.monotonic()-started,1),targets=targets,
        problems=check_case(case,result),dropped=result['dropped'],gaps=result['gaps'],trace=result['trace'],
        suggestions=[{k:s[k] for k in ('unit_id','change_type','before','after','new_position','warnings','verdict','evidence')} for s in shown])

def percentile(values,fraction):
    ordered=sorted(values)
    return ordered[max(0,math.ceil(fraction*len(ordered))-1)] if ordered else None

def summarize(results,total):
    done=[r for r in results if r['outcome']=='completed']
    shown=sum(len(r['suggestions']) for r in done);dropped=sum(sum(r['dropped'].values()) for r in done)
    enough=[r for r in done if r['targets']>=3]
    groups={}
    for r in results:
        g=groups.setdefault(r['group'],dict(cases=0,passed=0));g['cases']+=1;g['passed']+=not r['problems']
    verdicts={}
    reasons={}
    for r in done:
        for s in r['suggestions']:
            status=s['verdict']['status'];verdicts[status]=verdicts.get(status,0)+1
        for reason,count in r['dropped'].items(): reasons[reason]=reasons.get(reason,0)+count
    seconds=[r['seconds'] for r in results]
    return dict(cases_in_set=total,cases_run=len(results),completed=len(done),failed=len(results)-len(done),groups=groups,
        automatic_failures=[dict(case=r['id'],problems=r['problems']) for r in results if r['problems']],
        proposals_shown=shown,rewrites_shown=sum(s['change_type'] in REWRITES for r in done for s in r['suggestions']),
        dropped_after_repair=dropped,dropped_reasons=reasons,
        drop_rate=round(dropped/(shown+dropped),3) if shown+dropped else None,
        runs_with_three_or_more=f'{sum(len(r["suggestions"])>=3 for r in enough)} of {len(enough)}',
        share_with_three_or_more=round(sum(len(r['suggestions'])>=3 for r in enough)/len(enough),3) if enough else None,
        median_seconds=percentile(seconds,0.5),p95_seconds=percentile(seconds,0.95),second_ai_check=verdicts,
        unsupported_claims='Needs human review: see the review sheet.',usefulness='Needs human review: see the review sheet.')

def write_review(results,path):
    """Never overwrite a sheet a person has started to fill in."""
    if path.exists():
        with path.open(encoding='utf-8-sig',newline='') as f:
            if any((row.get('unsupported (y/n)') or row.get('useful (y/n)') or '').strip() for row in csv.DictReader(f)):
                path=path.with_name(path.stem+'_'+time.strftime('%Y%m%d%H%M%S')+'.csv')
    def safe(text): return "'"+text if text.lstrip().startswith(('=','+','-','@')) else text
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(REVIEW_COLUMNS)
        for r in results:
            for number,s in enumerate(r.get('suggestions',[]),1):
                after=s['after'] or ('(move to position %d)'%(s['new_position']+1) if s['change_type']=='reorder' else '(move to end of role)')
                writer.writerow([r['id'],r['group'],number,s['change_type'],safe(s['before']),safe(after),
                    safe(' | '.join(e['quote'] for e in s['evidence'])),s['verdict']['status'],'','',''])
    return path

def score_review(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    def answer(row,column): return (row.get(column) or '').strip().lower()
    judged=[r for r in rows if answer(r,'unsupported (y/n)') in ('y','n')]
    useful=[r for r in rows if answer(r,'useful (y/n)') in ('y','n')]
    unsupported=[f"{r['case']} #{r['proposal']}" for r in judged if answer(r,'unsupported (y/n)')=='y']
    if unsupported: verdict='FAIL: unsupported claims found'
    elif len(judged)<REVIEW_MINIMUM: verdict=f'INCOMPLETE: {len(judged)} of {REVIEW_MINIMUM} proposals reviewed'
    else: verdict='PASS'
    return dict(rows=len(rows),reviewed=len(judged),unsupported=unsupported,
        useful_share=round(sum(answer(r,'useful (y/n)')=='y' for r in useful)/len(useful),3) if useful else None,
        useful_reviewed=len(useful),release_check=verdict)

def main(args):
    if args.score:
        report=score_review(args.score);print(json.dumps(report,indent=2))
        (OUT/'tailor_review_score.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        return
    cases=load_cases()
    chosen=[c for c in cases if not args.case or c['id'] in args.case][:args.limit or None]
    versions=dict(writer_model=MODEL,verifier_model=VERIFIER_MODEL,writer_prompt=PROMPT_VERSION,verifier_prompt=VERIFIER_PROMPT_VERSION,
        policy=POLICY_VERSION,lens=LENS_VERSION,fit_analyst='included' if args.with_fit else 'not included')
    OUT.mkdir(parents=True,exist_ok=True);target=OUT/'tailor_evals.json';saved={}
    if target.exists() and not args.fresh:
        old=json.loads(target.read_text(encoding='utf-8'))
        if old.get('versions')==versions: saved={r['id']:r for r in old['results']}
    writer=get_provider(model=MODEL,timeout=420);checker=get_provider(model=VERIFIER_MODEL,timeout=420)
    for number,case in enumerate(chosen,1):
        if case['id'] not in saved:
            saved[case['id']]=run_case(case,writer,checker,args.with_fit)
        r=saved[case['id']]
        print(f"{number}/{len(chosen)} {r['id']} {r['outcome']} {len(r.get('suggestions',[]))} shown {r['seconds']}s {'; '.join(r['problems'])}",flush=True)
        results=[saved[c['id']] for c in cases if c['id'] in saved]
        report=dict(scope='Synthetic golden set run on the local model. Automatic checks only; unsupported claims and usefulness need human review.',
            versions=versions,summary=summarize(results,len(cases)),results=results)
        target.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    sheet=write_review([saved[c['id']] for c in cases if c['id'] in saved],OUT/'tailor_review_sheet.csv')
    print(json.dumps(report['summary'],indent=2));print('Review sheet:',sheet)
