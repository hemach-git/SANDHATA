"""Apply approved changes to resume text by character offset, verify the result and build the DOCX. No model.

Moving a bullet exchanges whole bullet blocks between the places bullets already occupy, so headings,
dates and spacing stay where they were.
"""
import re
from collections import Counter
from dataclasses import dataclass
from io import BytesIO

from docx import Document
from docx.shared import Inches,Pt

from .config import AppError
from .segmenter import segment

@dataclass(frozen=True)
class Change:
    unit_id: str
    kind: str            # 'text', 'move' or 'lower'
    text: str=''
    position: int|None=None

@dataclass(frozen=True)
class Span:
    start: int
    end: int
    replacement: str
    unit_ids: tuple      # approved changes that explain this span

def _line_start(source,unit): return source.rfind('\n',0,unit.start)+1

def keeps_shape(source,units,unit,text):
    """True when the rewritten text still reads as the same kind of unit, so later runs and the DOCX stay correct."""
    changed=source[:unit.start]+text+source[unit.end:]
    try: found=segment(changed)
    except AppError: return False
    return ([u.kind for u in found]==[u.kind for u in units]
            and any(u.start==unit.start and u.text==text for u in found))

def compose_text(source,units,changes):
    """Return (new_text, spans, blocks). Blocks are (kind, text) in output order, used to build the document."""
    by_id={u.unit_id:u for u in units}; wanted={}
    for change in changes:
        unit=by_id.get(change.unit_id)
        if unit is None or not unit.editable or change.unit_id in wanted or source[unit.start:unit.end]!=unit.text:
            raise AppError('An approved change no longer matches the source resume.')
        if change.kind!='text' and unit.kind!='bullet': raise AppError('Only experience bullets can be moved.')
        wanted[change.unit_id]=change
    spans=[];placed={u.unit_id:u.unit_id for u in units}
    moved_roles={by_id[k].role for k,c in wanted.items() if c.kind!='text'}
    for role in moved_roles:
        slots=[u for u in units if u.kind=='bullet' and u.role==role]
        ids=[u.unit_id for u in slots]; order=list(ids)
        mine=[wanted[i] for i in ids if i in wanted]
        for change in sorted((c for c in mine if c.kind=='move'),key=lambda c:c.position):
            if change.position is None or not 0<=change.position<len(ids): raise AppError('An approved move is outside its role.')
            order.remove(change.unit_id);order.insert(change.position,change.unit_id)
        for change in (c for c in mine if c.kind=='lower'):
            order.remove(change.unit_id);order.append(change.unit_id)
        def block(unit_id):
            u=by_id[unit_id];c=wanted.get(unit_id)
            return source[_line_start(source,u):u.start]+(c.text if c and c.kind=='text' else u.text)
        for slot,unit_id in zip(slots,order):
            placed[slot.unit_id]=unit_id
            start=_line_start(source,slot);replacement=block(unit_id)
            if replacement==source[start:slot.end]: continue
            explained=(unit_id,) if unit_id in wanted else tuple(c.unit_id for c in mine if c.kind!='text')
            spans.append(Span(start,slot.end,replacement,explained))
    for unit_id,change in wanted.items():
        u=by_id[unit_id]
        if u.kind=='bullet' and u.role in moved_roles: continue
        spans.append(Span(u.start,u.end,change.text,(unit_id,)))
    spans.sort(key=lambda s:s.start)
    parts=[];position=0
    for s in spans:
        if s.start<position: raise AppError('Approved changes overlap.')
        parts+=[source[position:s.start],s.replacement];position=s.end
    parts.append(source[position:])
    blocks=[]
    for u in units:
        source_unit=by_id[placed[u.unit_id]];change=wanted.get(source_unit.unit_id)
        blocks.append((u.kind,change.text if change and change.kind=='text' else source_unit.text))
    return ''.join(parts),tuple(spans),tuple(blocks)

def verify(source,output,units,changes,spans):
    """Independent checks on a composed text. Any mismatch stops the compose; nothing is written."""
    def fail(why): raise AppError('The tailored version failed verification and was not saved: '+why)
    approved={c.unit_id:c for c in changes}
    read=written=0
    for s in spans:
        if not s.unit_ids or not set(s.unit_ids)<=set(approved): fail('a change has no approval')
        untouched=source[read:s.start]
        if output[written:written+len(untouched)]!=untouched: fail('unapproved text changed')
        written+=len(untouched)
        if output[written:written+len(s.replacement)]!=s.replacement: fail('an approved change was not applied exactly')
        written+=len(s.replacement);read=s.end
    if output[written:]!=source[read:]: fail('unapproved text changed')
    # Content check that does not rely on the spans: every unit's final text appears, none is lost or duplicated.
    expected=Counter(approved[u.unit_id].text if u.unit_id in approved and approved[u.unit_id].kind=='text' else u.text
                     for u in units if u.editable)
    for text,times in expected.items():
        if output.count(text)<times: fail('resume content is missing')
    locked=[u.text for u in units if not u.editable]
    position=0
    for text in locked:
        position=output.find(text,position)
        if position<0: fail('a locked line moved or changed')
        position+=len(text)
    if len(output.split('\n'))-len(source.split('\n'))!=sum(
            c.text.count('\n')-next(u.text for u in units if u.unit_id==c.unit_id).count('\n') for c in changes if c.kind=='text'):
        fail('lines were added or removed')

_XML_UNSAFE=re.compile(r'[^\t\n\r\x20-퟿-�\U00010000-\U0010ffff]')

def _plain(text): return _XML_UNSAFE.sub('',' '.join(text.split()))

def build_docx(blocks):
    """A single-column document that resume parsers read easily. The original styling is not kept."""
    document=Document()
    for section in document.sections:
        section.left_margin=section.right_margin=Inches(0.75);section.top_margin=section.bottom_margin=Inches(0.6)
    normal=document.styles['Normal'];normal.font.name='Calibri';normal.font.size=Pt(10.5)
    first=True
    for kind,raw in blocks:
        text=_plain(raw)
        if kind=='contact' and first: document.add_heading(text,0)
        elif kind=='heading': document.add_heading(text,1)
        elif kind=='bullet': document.add_paragraph(text,style='List Bullet')
        elif kind=='role_header': document.add_paragraph().add_run(text).bold=True
        else: document.add_paragraph(text)
        first=False
    out=BytesIO();document.save(out);return out.getvalue()
