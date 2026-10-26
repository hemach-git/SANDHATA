import pytest
from sandhata.matching import validate_evidence,score_evidence,build_graph,assessment_key
from sandhata.config import AppError

def req(status='supported',category='required_skills',quote='Python',resume='Built Python pipelines.'):
    return dict(category=category,requirement_quote=quote,status=status,resume_quote=resume if status in ('supported','partial') else '',rationale='Synthetic fixture judgment')

def test_literal_grounding():
    out=validate_evidence({'requirements':[req()]},'Required: Python','Built Python pipelines.')
    assert out['requirements'][0]['job_offset']==10
    assert out['requirements'][0]['resume_offset']==0

@pytest.mark.parametrize('job,resume', [('Required: Java','Built Python pipelines.'),('Required: Python','I have no stated credential.')])
def test_fabricated_quote_rejected(job,resume):
    with pytest.raises(AppError): validate_evidence({'requirements':[req()]},job,resume)

def test_duplicate_requirements_removed():
    a=validate_evidence({'requirements':[req(),req()]},'Python','Built Python pipelines.')
    assert len(a['requirements'])==1

@pytest.mark.parametrize('status,expected',[('supported',100),('partial',50),('not_evidenced',0),('unknown',None)])
def test_scores_are_deterministic(status,expected):
    assert score_evidence({'requirements':[req(status)],'eligibility_flags':[]})['score']==expected

def test_unknown_coverage_suppresses_score():
    a=score_evidence({'requirements':[req('supported','preferred_skills'),req('unknown','required_skills')],'eligibility_flags':[]})
    assert a['coverage']<50 and a['score'] is None

def test_absent_categories_renormalize():
    out=score_evidence({'requirements':[req('partial','education')],'eligibility_flags':[]})
    assert out['score']==50 and out['coverage']==100

def test_partial_description_labeled():
    assert score_evidence({'requirements':[req()],'eligibility_flags':[]},'partial')['provisional']

def test_repair_is_bounded():
    calls=[]
    def invalid(job,resume,repair): calls.append(repair);return {'requirements':[req(quote='Invented')]},{}
    with pytest.raises(AppError): build_graph(invalid).invoke({'job':'Python','resume':'Built Python pipelines.','completeness':'full','trace':[]})
    assert len(calls)==2

def test_graph_has_validated_result():
    def valid(*args): return {'requirements':[req()]},{}
    result=build_graph(valid).invoke({'job':'Python','resume':'Built Python pipelines.','completeness':'full','trace':[]})
    assert result['result']['score']==100

def test_cache_keys_include_both_documents():
    assert assessment_key('a','b')!=assessment_key('a','c')


def test_fabricated_eligibility_rejected():
    with pytest.raises(AppError):
        validate_evidence({'requirements':[req()],'eligibility_flags':['Review: Must have clearance']},'Python','Built Python pipelines.')

def test_schema_failure_gets_one_repair():
    calls=[]
    def invalid(*args):
        calls.append(1)
        raise AppError('Invalid structured response')
    with pytest.raises(AppError):
        build_graph(invalid).invoke({'job':'Python','resume':'Built Python pipelines.','completeness':'full','trace':[]})
    assert len(calls)==2

def test_revocation_checked_before_every_inference():
    calls=[]
    def revoked(): raise AppError('Revoked')
    def analyzer(*args): calls.append(1)
    with pytest.raises(AppError):
        build_graph(analyzer,revoked).invoke({'job':'Python','resume':'Python','completeness':'full','trace':[]})
    assert not calls
