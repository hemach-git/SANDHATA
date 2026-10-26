import pytest
from sandhata.parsing import parse_resume,plain_html,salary_yearly,passages
from sandhata.connectors import matches_filters,employer_feed,premium_search_links
from sandhata.config import AppError
from sandhata.private_api import csv_bytes

def test_text_docx_extraction(docx_bytes):
    assert 'Python' in parse_resume(docx_bytes,'resume.docx')['body']

@pytest.mark.parametrize('data,name',[(b'not-pdf','x.pdf'),(b'','empty.docx'),(b'PKbad','bad.docx'),(b'fake','resume.exe')])
def test_invalid_uploads_rejected(data,name):
    with pytest.raises(AppError): parse_resume(data,name)

def test_html_scripts_removed():
    assert plain_html('<p>Python required</p><script>steal()</script>')=='Python required'

def test_passage_offsets_are_real():
    text='A'*1700+'\n'+'B'*3000
    for offset,chunk in passages(text): assert text[offset:offset+len(chunk)]==chunk

@pytest.mark.parametrize('salary,expected',[('USD 150k to 180k per year',(150000,180000)),('$80 per hour',None),('Not disclosed',None),('EUR 150000 annually',None)])
def test_salary_units(salary,expected): assert salary_yearly(salary)==expected

def test_filter_unknown_salary_policy():
    job=dict(title='Python Engineer',company_name='Example',description='Python SQL',candidate_required_location='United States',salary='')
    assert matches_filters(job,dict(title='Engineer',required_skills='Python, SQL',location='United States',minimum_salary=150000,include_unknown_salary=True))
    assert not matches_filters(job,dict(minimum_salary=150000,include_unknown_salary=False))
    assert not matches_filters(job,dict(required_skills='Kubernetes'))

@pytest.mark.parametrize('token',['http://127.0.0.1','../../private','board?token=secret','localhost:8080'])
def test_board_tokens_cannot_be_urls(token):
    with pytest.raises(AppError): employer_feed(None,'Greenhouse',token)

def test_premium_search_is_link_only():
    links=premium_search_links('AI Engineer','New York')
    assert set(links)=={'LinkedIn','Ladders','Indeed'} and all(x.startswith('https://') for x in links.values())

def test_csv_formula_injection_escaped():
    data=csv_bytes([dict(title='=1+1')]).decode('utf-8-sig')
    assert "'=1+1" in data
