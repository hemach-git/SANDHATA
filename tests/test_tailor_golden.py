"""The golden set and its scorer, checked without a model. A hostile writer tries every trap against the code rules alone."""
import csv,json,sys
from collections import Counter
import pytest
from sandhata.config import ROOT
from sandhata.agents.tailor import tailor
from sandhata.planner import TRACKS,LEVELS,lens
from sandhata.providers import Reply
from sandhata.segmenter import segment
sys.path.insert(0,str(ROOT/'scripts'))
import tailor_evals as evals
from tailor_fakes import Checker

CASES=evals.load_cases()

def test_set_has_the_designed_mix():
    assert len({c['id'] for c in CASES})==len(CASES)==40
    assert Counter(c['group'] for c in CASES)==dict(positive=12,fabrication=10,scope=6,level_gap=4,injection=4,edge=4)

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
def test_every_case_is_well_formed(case):
    units=segment(case['resume']);bullets=[u.text for u in units if u.kind=='bullet']
    assert case['track'] in TRACKS and case['level'] in LEVELS and 'synthetic' in (case['resume']+case['job']).lower()
    for wanted in case['expect'].get('unit_any',[]): assert wanted in bullets
    if 'keep' in case['expect']: assert case['expect']['keep']['unit'] in bullets
    labels={e['label'] for e in lens(case['track'],case['level'])['expects']}
    assert set(case['expect'].get('gaps',[]))<=labels
    assert case['expect'],'a case needs an expectation'

# Known limit: ordinary lowercase words outside the policy lists pass the code rules. Only the Verifier and the member can stop them.
SLIPS={'fabrication-03':'fine-tuned','fabrication-04':'streaming','fabrication-06':'regulated','gap-04':'scoped','injection-04':'example.com'}

class Hostile:
    """Tries to slip each forbidden word into every targeted line."""
    name='ollama';model='hostile-writer'
    def __init__(self,case): self.case=case
    def generate(self,system,user,schema,max_tokens=6000):
        sent=json.loads(user);units={u['unit_id']:u['text'] for u in sent['RESUME_UNITS']}
        terms=self.case['expect'].get('forbid',[]);proposals=[]
        for number,target in enumerate(sent['TARGETS']):
            kind=target['change_types'][0];unit=target['unit_id'];text=units[unit]
            if kind not in ('rephrase','summary','skills_reorder') or not terms: continue
            term=terms[number%len(terms)]
            proposals.append(dict(unit_id=unit,change_type=kind,after=f'{text.rstrip(".")}, {term}',evidence=[dict(quote=text)],job_quote=target['job_quote']))
        return Reply(json.dumps(dict(proposals=proposals)))

@pytest.mark.parametrize('case',[c for c in CASES if c['expect'].get('forbid')],ids=lambda c:c['id'])
def test_code_rules_alone_stop_every_trap(case):
    result=tailor(case['resume'],case['job'],case['track'],case['level'],Hostile(case),Checker())
    found=evals.check_case(case,result);slips=SLIPS.get(case['id'])
    # A listed slip must still happen, so this list shrinks when the rules improve.
    if slips: assert [x.split("'")[1] for x in found]==[slips],found
    else: assert not found,found

@pytest.mark.parametrize('case',[c for c in CASES if c['group']=='positive'],ids=lambda c:c['id'])
def test_planner_targets_the_expected_bullet(case):
    from sandhata.planner import plan
    units=segment(case['resume']);targets={t.unit_id for t in plan(units,case['job'],None,case['track'],case['level']).targets}
    assert any(u.unit_id in targets for u in units if u.text in case['expect']['unit_any'])

@pytest.mark.parametrize('case',[c for c in CASES if c['group']=='level_gap'],ids=lambda c:c['id'])
def test_level_gaps_are_planned(case):
    from sandhata.planner import plan
    shown={g['label'] for g in plan(segment(case['resume']),case['job'],None,case['track'],case['level']).gaps}
    assert set(case['expect']['gaps'])<=shown

def suggestion(**extra):
    return dict(dict(unit_id='r1.b1',change_type='rephrase',before='Helped build tools',after='Helped build tools',new_position=None,
                     verdict=dict(status='passed'),evidence=[dict(quote='Helped build tools')],warnings=[]),**extra)

def test_checks_report_each_kind_of_problem():
    case=dict(expect=dict(forbid=['led','tools'],keep=dict(unit='Helped build tools',any=['helped']),unit_any=['Other line'],gaps=['Hiring']))
    found=evals.check_case(case,dict(suggestions=[suggestion(after='Led build of tools')],gaps=[]))
    assert len(found)==4 and any("'led'" in x for x in found) and not any("'tools'" in x for x in found)

def result_row(case='c1',shown=3,targets=4,problems=()):
    return dict(id=case,group='positive',outcome='completed',seconds=10.0,targets=targets,problems=list(problems),dropped={'overclaim':1},
                suggestions=[suggestion(after='=cmd()' if n==0 else 'Helped build the tools') for n in range(shown)])

def test_summary_counts_come_from_results():
    failed=dict(id='c3',group='edge',outcome='failed',seconds=99.0,problems=['run failed'])
    found=evals.summarize([result_row(),result_row('c2',shown=1),failed],40)
    assert (found['completed'],found['failed'],found['proposals_shown'],found['dropped_after_repair'])==(2,1,4,2)
    assert found['drop_rate']==0.333 and found['share_with_three_or_more']==0.5 and found['p95_seconds']==99.0
    assert 'human review' in found['unsupported_claims']

def fill(path,answers):
    with path.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    for row,(unsupported,useful) in zip(rows,answers): row['unsupported (y/n)'],row['useful (y/n)']=unsupported,useful
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=evals.REVIEW_COLUMNS);w.writeheader();w.writerows(rows)

def test_review_sheet_is_safe_and_never_overwrites_a_reviewers_work(tmp_path):
    path=evals.write_review([result_row()],tmp_path/'sheet.csv')
    text=path.read_text(encoding='utf-8-sig')
    assert "'=cmd()" in text
    assert evals.write_review([result_row()],path)==path
    fill(path,[('n','y')])
    other=evals.write_review([result_row()],path)
    assert other!=path and evals.score_review(path)['reviewed']==1

def test_review_score_never_passes_early(tmp_path):
    path=evals.write_review([result_row(f'c{n}',shown=1) for n in range(100)],tmp_path/'sheet.csv')
    assert evals.score_review(path)['release_check'].startswith('INCOMPLETE: 0')
    fill(path,[('n','y')]*99);assert evals.score_review(path)['release_check'].startswith('INCOMPLETE')
    fill(path,[('n','y')]*60+[('n','n')]*40)
    found=evals.score_review(path);assert found['release_check']=='PASS' and found['useful_share']==0.6
    fill(path,[('y','n')])
    assert evals.score_review(path)['release_check'].startswith('FAIL')
