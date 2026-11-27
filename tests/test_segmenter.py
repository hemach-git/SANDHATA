from io import BytesIO
import pytest
from docx import Document
from sandhata.config import AppError
from sandhata.parsing import parse_resume
from sandhata.segmenter import segment,model_view
from tailor_fixtures import RESUME

def exact(body,units):
    assert all(body[u.start:u.end]==u.text for u in units)
    assert len({u.unit_id for u in units})==len(units)
    assert all(a.end<=b.start for a,b in zip(units,units[1:])), 'units overlap'

def of(units,kind): return [u for u in units if u.kind==kind]

def test_offsets_roles_and_locked_units():
    units=segment(RESUME);exact(RESUME,units)
    bullets=of(units,'bullet')
    assert [u.unit_id for u in bullets]==['r1.b1','r1.b2','r1.b3','r1.b4','r1.b5','r2.b1','r2.b2']
    assert bullets[0].text.startswith('Built a document'), 'the bullet glyph stays outside the editable text'
    assert len(of(units,'summary'))==1 and len(of(units,'skills'))==2
    for u in units:
        if u.kind in ('heading','role_header','education','contact','other'): assert not u.editable

def test_contact_details_never_reach_the_model():
    sent=str(model_view(segment(RESUME)))
    for private in ('Sam Example','sam.example@example.com','704-555-0100'): assert private not in sent
    assert 'Northwind Synthetic Insurance' in sent

def test_contact_details_inside_other_units_are_masked():
    body=RESUME.replace('with business teams.','with business teams. Reach me at sam@example.com or www.sam.example')
    sent=str(model_view(segment(body)))
    assert 'sam@example.com' not in sent and 'www.sam.example' not in sent

def test_wrapped_pdf_lines_stay_in_one_bullet():
    body=('Experience\nAI Engineer | Synthetic Co 2021 - Present\n'
          '• Built a retrieval service that answers questions about policy documents for\n'
          'the claims team and measures answer quality.\n'
          '• Delivered dashboards\n')
    units=segment(body);exact(body,units)
    bullets=of(units,'bullet')
    assert len(bullets)==2 and bullets[0].text.endswith('answer quality.') and '\n' in bullets[0].text

def test_word_lists_without_bullet_characters():
    d=Document()
    d.add_paragraph('Sam Example');d.add_heading('Professional Experience',1)
    d.add_paragraph('AI Engineer | Synthetic Co');d.add_paragraph('2021 - Present')
    d.add_paragraph('Built an agent evaluation harness',style='List Bullet')
    d.add_paragraph('Led weekly reviews with claims staff',style='List Bullet')
    d.add_paragraph('Initech Inc.');d.add_paragraph('2018 - 2020')
    d.add_paragraph('Delivered SQL reporting for store managers',style='List Bullet')
    d.add_heading('Technical Skills',1);d.add_paragraph('Python, SQL')
    out=BytesIO();d.save(out)
    body=parse_resume(out.getvalue(),'synthetic.docx')['body']
    units=segment(body);exact(body,units)
    assert [(u.unit_id,u.text) for u in of(units,'bullet')]==[
        ('r1.b1','Built an agent evaluation harness'),('r1.b2','Led weekly reviews with claims staff'),
        ('r2.b1','Delivered SQL reporting for store managers')]

def pdf_bytes(lines):
    """A minimal one-page text PDF, built by hand so tests need no extra library."""
    stream=b'BT /F1 10 Tf 40 760 Td 14 TL '+b''.join(b'('+l.encode('cp1252')+b') Tj T* ' for l in lines)+b'ET'
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
        b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>']
    out=b'%PDF-1.4\n';offsets=[]
    for number,item in enumerate(objects,1):
        offsets.append(len(out));out+=str(number).encode()+b' 0 obj\n'+item+b'\nendobj\n'
    xref=len(out)
    out+=b'xref\n0 6\n0000000000 65535 f \n'+b''.join(f'{o:010d} 00000 n \n'.encode() for o in offsets)
    return out+b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n'+str(xref).encode()+b'\n%%EOF'

def test_pdf_offsets_are_exact():
    body=parse_resume(pdf_bytes(['Sam Example','Experience','AI Engineer | Synthetic Co 2021 - Present',
        '• Built a retrieval service for the claims team','• Delivered evaluation dashboards','Skills','Python, SQL']),'synthetic.pdf')['body']
    units=segment(body);exact(body,units)
    assert len(of(units,'bullet'))==2 and len(of(units,'skills'))==1

def test_second_work_section_does_not_join_previous_role():
    body=('Experience\nAI Engineer | Synthetic Co 2021 - Present\n• Built a service\n'
          'Projects\n• Wrote a Terraform module for a side project\n')
    roles=[u.role for u in of(segment(body),'bullet')]
    assert roles==[1,2]

def test_sparse_text_is_refused():
    with pytest.raises(AppError): segment('Sam Example\nCharlotte, NC\n')
