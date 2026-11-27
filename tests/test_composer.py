from io import BytesIO
import pytest
from docx import Document
from sandhata.composer import Change,Span,compose_text,verify,build_docx,keeps_shape
from sandhata.config import AppError
from sandhata.segmenter import segment
from tailor_fixtures import RESUME
from tailor_fakes import B1,B2,B3,B4,GOOD_B2

UNITS=segment(RESUME)
BY_ID={u.unit_id:u for u in UNITS}
B5=BY_ID['r1.b5'].text

def compose(*changes,source=RESUME):
    units=segment(source)
    output,spans,blocks=compose_text(source,units,list(changes))
    verify(source,output,units,list(changes),spans)
    return output,spans,blocks

def role_one(text): return [u.text for u in segment(text) if u.kind=='bullet' and u.role==1]

def test_no_changes_is_byte_identical():
    assert compose()[0]==RESUME

def test_text_change_touches_only_its_span():
    output,spans,_=compose(Change('r1.b2','text',GOOD_B2))
    assert output==RESUME.replace(B2,GOOD_B2) and len(spans)==1

def test_move_reorders_one_role_only():
    output,_,_=compose(Change('r1.b4','move',position=0))
    assert role_one(output)==[B4,B1,B2,B3,B5]
    assert output.split('Data Engineer')[1]==RESUME.split('Data Engineer')[1]
    assert output.split('• ')[0]==RESUME.split('• ')[0]

def test_lower_moves_to_the_end_of_the_role():
    assert role_one(compose(Change('r1.b1','lower'))[0])==[B2,B3,B4,B5,B1]

def test_move_lower_and_rewrite_together():
    output,_,blocks=compose(Change('r1.b4','move',position=0),Change('r1.b1','lower'),Change('r1.b2','text',GOOD_B2),
                            Change('s1','text','AI engineer who builds LLM tools with the claims team'))
    assert role_one(output)==[B4,GOOD_B2,B3,B5,B1]
    assert [t for k,t in blocks if k=='bullet'][:5]==role_one(output)
    assert 'AI engineer who builds LLM tools with the claims team' in output

def test_wrapped_bullets_move_whole():
    source=('Summary\nEngineer.\n\nExperience\nEngineer | Synthetic Co\nJan 2020 - Present\n'
            '• Built a long running service that handles the nightly loads for the\n  finance reporting team\n• Wrote SQL reports\n')
    output,_,_=compose(Change('r1.b2','move',position=0),source=source)
    assert output.index('Wrote SQL reports')<output.index('Built a long')
    assert 'for the\n  finance reporting team' in output

@pytest.mark.parametrize('change',[
    Change('r1.h1','text','Director'),Change('c1','text','Other Name'),Change('r9.b1','text','x'),
    Change('s1','move',position=0),Change('r1.b1','move',position=9),Change('r1.b1','move'),
])
def test_invalid_changes_are_refused(change):
    with pytest.raises(AppError): compose_text(RESUME,UNITS,[change])

def test_two_changes_to_one_unit_are_refused():
    with pytest.raises(AppError): compose_text(RESUME,UNITS,[Change('r1.b1','lower'),Change('r1.b1','text','x')])

CHANGES=[Change('r1.b2','text',GOOD_B2)]
OUTPUT,SPANS,_=compose_text(RESUME,UNITS,CHANGES)

@pytest.mark.parametrize('output,spans',[
    (OUTPUT.replace('Contoso','Fabrikam'),SPANS),
    (OUTPUT+'Extra line\n',SPANS),
    (OUTPUT.replace('40 claims users',"400 claims users"),SPANS),
    (OUTPUT.replace(B3+'\n',''),SPANS),
    (OUTPUT,(Span(SPANS[0].start,SPANS[0].end,SPANS[0].replacement,()),)),
    (OUTPUT,(Span(SPANS[0].start,SPANS[0].end,SPANS[0].replacement,('r1.b1',)),)),
    (RESUME.replace(B1,'Led everything'),(Span(BY_ID['r1.b1'].start,BY_ID['r1.b1'].end,'Led everything',('r1.b1',)),)),
])
def test_tampered_results_fail_verification(output,spans):
    with pytest.raises(AppError,match='failed verification'): verify(RESUME,output,UNITS,CHANGES,spans)

def test_docx_keeps_every_line_in_order():
    output,_,blocks=compose(Change('r1.b4','move',position=0),Change('r1.b2','text',GOOD_B2))
    document=Document(BytesIO(build_docx(blocks)))
    paragraphs=[p.text for p in document.paragraphs]
    assert paragraphs==[' '.join(u.text.split()) for u in segment(output)]
    assert paragraphs.index(B4)<paragraphs.index(B1)
    assert any(p.style.name=='List Bullet' and p.text==GOOD_B2 for p in document.paragraphs)

def test_docx_ignores_characters_word_cannot_store():
    assert build_docx([('summary','Engineer\x0b\x01 text')])

def test_shape_check_for_unmarked_bullets():
    source='Experience\nEngineer | Synthetic Co\nJan 2020 - Present\nBuilt Python services for the platform team\n'
    units=segment(source);unit=units[-1]
    assert keeps_shape(source,units,unit,'Developed Python services for the platform team')
    assert not keeps_shape(source,units,unit,'Python platform services')
    assert not keeps_shape(source,units,unit,'Experience')
