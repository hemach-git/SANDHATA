import json
import httpx
import pytest
from sandhata.config import AppError,MODEL
from sandhata.providers import OllamaProvider,get_provider
from sandhata.matching import local_analysis,build_graph,assessment_key

ANALYSIS={'requirements':[dict(category='required_skills',requirement_quote='Python',status='supported',
    resume_quote='Built Python pipelines.',rationale='Synthetic')],'eligibility_flags':[]}

def provider(handler,model='fixture-model'):
    return OllamaProvider(model=model,url='http://ollama.test',transport=httpx.MockTransport(handler))

def reply(content):
    return lambda request: httpx.Response(200,json=dict(message=dict(content=content),prompt_eval_count=11,eval_count=7))

def test_ollama_request_and_usage():
    seen={}
    def handler(request):
        seen.update(json.loads(request.content),url=str(request.url))
        return reply('{}')(request)
    out=provider(handler).generate('system text','user text',{'type':'object'},max_tokens=50)
    assert seen['url']=='http://ollama.test/api/chat' and seen['model']=='fixture-model'
    assert seen['options']['temperature']==0 and seen['options']['num_predict']==50 and seen['stream'] is False
    assert out.usage==dict(input_tokens=11,output_tokens=7)

def test_analysis_goes_through_the_provider():
    data,usage=local_analysis('Python','Built Python pipelines.',provider=provider(reply(json.dumps(ANALYSIS))))
    assert data['requirements'][0]['status']=='supported' and usage['output_tokens']==7

@pytest.mark.parametrize('handler',[reply('not json'),lambda r: httpx.Response(500,text='secret internal detail')])
def test_provider_failure_is_worded_safely(handler):
    with pytest.raises(AppError) as error: local_analysis('Python','Built Python pipelines.',provider=provider(handler))
    assert 'secret' not in str(error.value)

def test_result_records_provider_and_model_actually_used():
    chosen=provider(reply(json.dumps(ANALYSIS)))
    out=build_graph(provider=chosen).invoke(dict(job='Python',resume='Built Python pipelines.',completeness='full',trace=[]))
    assert out['result']['provider']=='ollama' and out['result']['model']=='fixture-model'

def test_hosted_provider_is_not_enabled():
    assert get_provider().name=='ollama'
    with pytest.raises(AppError): get_provider('openai')

def test_cache_key_changes_with_model_and_provider():
    base=assessment_key('a','b')
    assert base==assessment_key('a','b','ollama',MODEL)
    assert len({base,assessment_key('a','b','ollama','other-model'),assessment_key('a','b','openai',MODEL)})==3
