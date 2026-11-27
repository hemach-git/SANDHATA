"""The tailor graph and Verifier with fake models: bounded calls, code gates first, nothing silently passed."""
import json
import pytest
from sandhata.agents import tailor as graph
from sandhata.agents import verifier as verification
from sandhata.config import AppError
from tailor_fixtures import RESUME,JOB
from tailor_fakes import Writer,Checker,assessment,proposal,standard_draft,B2,B4,GOOD_B2,GOOD_B4,REQUIRED

def run(writer=None,checker=None,**extra):
    writer=writer or Writer(); checker=checker or Checker()
    return graph.tailor(RESUME,JOB,'fde','lead',writer,checker,assessment(),**extra),writer,checker

def ids(result): return [s['unit_id'] for s in result['suggestions']]
def components(result): return [t['component'] for t in result['trace']]

def test_good_draft_reaches_review_with_two_model_calls():
    result,writer,checker=run()
    assert ids(result)==['r1.b4','r1.b2','k2'] and [s['rank'] for s in result['suggestions']]==[0,1,2]
    assert (len(writer.requests),len(checker.requests))==(1,1)
    for name in ('segmenter','planner','tailor_writer','evidence_validator','verifier','verifier_gate','ranker'):
        assert name in components(result)
    assert result['suggestions'][0]['verdict']['status']=='passed'
    assert result['suggestions'][2]['verdict']['status']=='not_needed'
    assert result['gaps']

def test_trace_holds_no_document_text():
    result,_,_=run()
    text=json.dumps(result['trace'])
    assert 'claims' not in text and 'customers' not in text

def test_contact_details_never_reach_either_model():
    _,writer,checker=run()
    sent=json.dumps([writer.requests,checker.requests])
    assert 'sam.example@example.com' not in sent and '704-555-0100' not in sent

def test_verifier_sees_evidence_but_not_the_job_posting():
    _,_,checker=run()
    sent=json.dumps(checker.requests)
    assert B2 in sent and 'Forward Deployed' not in sent and 'Terraform' not in sent

def test_only_rewritten_text_goes_to_the_verifier():
    _,_,checker=run()
    assert sorted(i['id'] for i in checker.requests[0])==['r1.b2','r1.b4']

def test_one_repair_at_most():
    bad=[proposal('r1.b2',GOOD_B2+', 90%')]
    result,writer,checker=run(Writer(bad))
    assert len(writer.requests)==2 and not checker.requests
    assert result['suggestions']==[] and result['dropped']=={'unsupported_fact':1}

def test_repair_sends_reasons_and_can_recover():
    result,writer,_=run(Writer([proposal('r1.b2',GOOD_B2+', 90%'),proposal('r1.b4',GOOD_B4,job_quote=REQUIRED)],
                               [proposal('r1.b2',GOOD_B2)]))
    note=writer.requests[1]['REJECTED']
    assert [n['unit_id'] for n in note]==['r1.b2'] and note[0]['reason']=='unsupported_fact' and '90%' in note[0]['details']
    assert [t['unit_id'] for t in writer.requests[1]['TARGETS']]==['r1.b2']
    assert ids(result)==['r1.b4','r1.b2'] and result['dropped']=={}

def test_repair_cannot_return_units_that_were_not_sent_back():
    result,_,_=run(Writer([proposal('r1.b2',GOOD_B2+', 90%')],[proposal('r1.b4',GOOD_B4,job_quote=REQUIRED)]))
    assert result['suggestions']==[] and result['dropped']=={'unsupported_fact':1}

def test_verifier_rejection_is_repaired_and_rechecked():
    stronger='Mentored 3 engineers, transforming evaluation practices for retrieval quality'
    result,writer,checker=run(Writer([proposal('r1.b4',stronger,job_quote=REQUIRED)],[proposal('r1.b4',GOOD_B4,job_quote=REQUIRED)]),
                              Checker({'transforming':'overstated'}))
    assert writer.requests[1]['REJECTED'][0]['reason']=='verifier_rejected'
    assert len(checker.requests)==2 and ids(result)==['r1.b4'] and result['dropped']=={}

def test_verifier_rejection_that_persists_is_dropped():
    stronger='Mentored 3 engineers, transforming evaluation practices for retrieval quality'
    result,writer,checker=run(Writer([proposal('r1.b4',stronger,job_quote=REQUIRED)]),Checker({'transforming':'overstated'}))
    assert result['suggestions']==[] and result['dropped']=={'verifier_rejected':1}
    assert (len(writer.requests),len(checker.requests))==(2,2)

def test_verifier_doubt_is_shown_as_a_warning():
    result,writer,_=run(checker=Checker({'After weekly':'unsure'}))
    suggestion=next(s for s in result['suggestions'] if s['unit_id']=='r1.b2')
    assert suggestion['verdict']['status']=='warning' and 'unsure' in suggestion['warnings'][-1]
    assert len(writer.requests)==1

def test_verifier_outage_is_visible_never_passed():
    result,_,_=run(checker=Checker(fail=True))
    checked=[s for s in result['suggestions'] if s['change_type']=='rephrase']
    assert checked and all(s['verdict']['status']=='not_checked' for s in checked)
    assert all('did not run' in s['warnings'][-1] for s in checked)

def test_verifier_cannot_rescue_what_code_rejected():
    class Approves(Checker): pass
    result,_,checker=run(Writer([proposal('r1.b2',GOOD_B2+' with Terraform')]),Approves())
    assert result['suggestions']==[] and not checker.requests

@pytest.mark.parametrize('bad',[
    proposal('r2.b9','Anything',evidence=[B2]),
    proposal('r1.b2','','deemphasize') | dict(change_type='summary'),
    dict(unit_id=['r1.b2'],change_type='rephrase'),
    'not an object',
])
def test_untargeted_or_malformed_proposals_are_refused(bad):
    result,_,_=run(Writer([bad]))
    assert result['suggestions']==[] and sum(result['dropped'].values())>=1

def test_rewrite_that_changes_the_line_structure_is_refused():
    body='Summary\nEngineer who builds services.\n\nExperience\nEngineer | Synthetic Co\nJan 2020 - Present\nBuilt Python services for the platform team\nWrote SQL reports for the finance team\n'
    bad=dict(unit_id='r1.b1',change_type='rephrase',after='For the platform team, Python services',job_quote='Python platform role.',
             evidence=[dict(quote='Built Python services for the platform team')])
    result=graph.tailor(body,'Python platform role.','ai_engineer','senior',Writer([bad]),Checker())
    assert result['suggestions']==[] and result['dropped']=={'length_or_format':1}

def test_unreadable_draft_gets_one_retry():
    result,writer,_=run(Writer('not json',standard_draft()))
    assert len(writer.requests)==2 and len(result['suggestions'])==3 and 'REJECTED' not in writer.requests[1]

@pytest.mark.parametrize('broken',['not json','{"other":1}',RuntimeError('synthetic outage')])
def test_two_unusable_drafts_fail_the_run(broken):
    writer=Writer(broken)
    with pytest.raises(AppError,match='local model'): run(writer)
    assert len(writer.requests)==2

def test_empty_draft_is_a_valid_answer():
    result,writer,checker=run(Writer([]))
    assert result['suggestions']==[] and len(writer.requests)==1 and not checker.requests

def test_failed_repair_keeps_the_good_proposals():
    result,_,_=run(Writer([proposal('r1.b2',GOOD_B2+', 90%'),proposal('r1.b4',GOOD_B4,job_quote=REQUIRED)],RuntimeError('outage')))
    assert ids(result)==['r1.b4'] and result['dropped']=={'unsupported_fact':1}

def test_revoked_authority_stops_before_any_model_call():
    def revoked(): raise AppError('Access changed')
    writer=Writer()
    with pytest.raises(AppError,match='Access changed'): run(writer,authority_check=revoked)
    assert not writer.requests

def test_call_budget_skips_optional_steps():
    result,writer,checker=run(calls=graph.MAX_CALLS-1)
    assert len(writer.requests)==1 and not checker.requests
    assert all(s['verdict']['status']=='not_checked' for s in result['suggestions'] if s['change_type']=='rephrase')
    assert any(t.get('outcome')=='budget_exhausted' for t in result['trace'])

def test_exhausted_budget_fails_instead_of_saving_nothing_quietly():
    with pytest.raises(AppError): run(calls=graph.MAX_CALLS)

def test_long_documents_are_split_by_role(monkeypatch):
    monkeypatch.setattr(graph,'DOCUMENT_LIMIT',1750)
    writer=Writer([])
    # Without an assessment the Kubernetes bullet of the older role is a target too.
    graph.tailor(RESUME,JOB,'fde','lead',writer,Checker())
    assert len(writer.requests)>=2
    targeted=[t['unit_id'] for request in writer.requests for t in request['TARGETS']]
    assert len(targeted)==len(set(targeted))
    assert all(sum(len(json.dumps(u)) for u in r['RESUME_UNITS'])+len(r['JOB'])<=1750 for r in writer.requests)

def test_too_long_for_the_model_is_an_error_not_a_cut(monkeypatch):
    monkeypatch.setattr(graph,'DOCUMENT_LIMIT',200)
    with pytest.raises(AppError,match='silently truncated'): run()

# Verifier reply handling

ITEM=dict(id='r1.b2',before='Used the data platform',after='Designed the data platform for teams',evidence=['Used the data platform'])

def judged(*verdicts): return verification.judge(json.dumps(dict(verdicts=list(verdicts))),[ITEM])['r1.b2']['status']

def verdict(kind,phrase=''): return dict(id='r1.b2',verdict=kind,phrase=phrase,reason='x'*900)

@pytest.mark.parametrize('reply,status',[
    (verdict('supported'),'passed'),
    (verdict('overstated','Designed'),'rejected'),
    (verdict('overstated','"designed"'),'rejected'),
    (verdict('overstated','Invented the'),'warning'),
    (verdict('overstated','data platform'),'warning'),
    (verdict('overstated','data platform for'),'warning'),
    (verdict('overstated','Designed the data platform for teams'),'rejected'),
    (verdict('overstated','for teams'),'rejected'),
    (verdict('overstated'),'warning'),
    (verdict('unsure'),'warning'),
    (verdict('approve'),'not_checked'),
    (dict(id='other',verdict='supported'),'not_checked'),
])
def test_verdicts_are_gated_by_code(reply,status):
    assert judged(reply)==status

def test_conflicting_verdicts_take_the_strictest():
    assert judged(verdict('overstated','Designed'),verdict('supported'))=='rejected'

@pytest.mark.parametrize('content',['nonsense','[]','{"verdicts":"yes"}','{}'])
def test_unreadable_review_is_not_checked(content):
    assert verification.judge(content,[ITEM])['r1.b2']['status']=='not_checked'

def test_long_reasons_are_shortened():
    assert len(verification.judge(json.dumps(dict(verdicts=[verdict('unsure')])),[ITEM])['r1.b2']['reason'])==300

def test_moved_words_alone_cannot_reject_a_rewrite():
    item=dict(id='r1.b2',before='Built a search tool for the legal team',after='For the legal team, built a search tool',evidence=[])
    reply=dict(verdicts=[dict(id='r1.b2',verdict='overstated',phrase=item['after'],reason='x')])
    assert verification.judge(json.dumps(reply),[item])['r1.b2']['status']=='warning'

def test_writer_is_told_the_length_limit():
    _,writer,_=run()
    limits={t['unit_id']:t.get('max_chars') for t in writer.requests[0]['TARGETS']}
    assert limits['r1.b2']==int(len(B2)*1.4) and limits['k2'] is None
