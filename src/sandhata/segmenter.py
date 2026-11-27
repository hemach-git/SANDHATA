"""Split parsed resume text into units with exact character offsets. No model calls, no storage.

Every unit satisfies body[unit.start:unit.end] == unit.text. When a line is ambiguous it becomes
a locked unit, so a wrong guess can stop an edit but never allow one.
"""
import re
from dataclasses import dataclass

from .config import AppError

EDITABLE=('summary','bullet','skills')

SECTIONS={
    'summary':('summary','professional summary','executive summary','career summary','profile','professional profile','about','about me','objective'),
    'experience':('experience','professional experience','work experience','employment','employment history','work history','relevant experience','career experience','projects','selected projects','key projects'),
    'skills':('skills','technical skills','core skills','key skills','core competencies','competencies','technologies','tools and technologies','areas of expertise'),
    'education':('education','certifications','certification','licenses','licenses and certifications','education and certifications','training','credentials'),
    'other':('awards','publications','patents','volunteer','volunteering','languages','interests','affiliations','achievements','honors','speaking'),
}
HEADINGS={name:section for section,names in SECTIONS.items() for name in names}

BULLET=re.compile(r'^\s*(?:[•‣▪▫●◦⁃∙·]|[-*–](?=\s)|\d{1,2}[.)](?=\s))\s*')
MONTH=r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?'
DATE_RANGE=re.compile(
    r'(?:'+MONTH+r'\s*|\d{1,2}/)?\b(?:19|20)\d{2}\s*(?:-|–|—|\bto\b)\s*(?:(?:'+MONTH+r'\s*|\d{1,2}/)?(?:19|20)\d{2}|present|current|now)',re.I)
EMAIL=re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
PHONE=re.compile(r'(?<![\w/])\+?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b|(?<![\w/])\+\d{1,3}[\s.-]?\d[\d\s.-]{7,}\d')
LINK=re.compile(r'(?:https?://|www\.)\S+|\b(?:linkedin|github)\.com/\S+',re.I)
# Opening words that mark an unbulleted line (common in DOCX lists) as work done rather than a role title.
ACTIONS=frozenset('built led ran drove grew cut set won wrote made oversaw designed delivered developed created managed owned'.split())

@dataclass(frozen=True)
class Unit:
    unit_id: str
    kind: str
    start: int
    end: int
    text: str
    section: str
    role: int=0

    @property
    def editable(self): return self.kind in EDITABLE

def contains_contact(text):
    return bool(EMAIL.search(text) or PHONE.search(text) or LINK.search(text))

def mask_contact(text):
    for pattern in (EMAIL,LINK,PHONE): text=pattern.sub('[removed]',text)
    return text

def _lines(body):
    """Yield (start, end, text) for each non-blank line with surrounding space excluded."""
    position=0
    for raw in body.split('\n'):
        stripped=raw.strip()
        if stripped:
            start=position+raw.index(stripped[0])
            yield start,start+len(stripped),stripped
        else: yield position,position,''
        position+=len(raw)+1

def _heading(line):
    key=re.sub(r'\s+',' ',line.rstrip(' :').replace('&','and')).strip().casefold()
    return HEADINGS.get(key) if len(key)<=40 else None

def _starts_with_action(line):
    word=re.match(r'[A-Za-z-]+',line)
    if not word: return False
    first=word.group().casefold()
    return first in ACTIONS or (len(first)>4 and first.endswith('ed'))

def segment(body):
    units=[]; counts={}; section='preamble'; role=0; role_has_work=False; open_unit=None; glyphs_seen=False

    def add(kind,start,end,key,number=None):
        counts[key]=counts.get(key,0)+1
        unit_id=f'r{role}.{key}{counts[key]}' if number else f'{key}{counts[key]}'
        units.append(Unit(unit_id,kind,start,end,body[start:end],section,role if number else 0))
        return len(units)-1

    def extend(index,end):
        u=units[index]; units[index]=Unit(u.unit_id,u.kind,u.start,end,body[u.start:end],u.section,u.role)

    for start,end,line in _lines(body):
        if not line: open_unit=None; continue
        heading=_heading(line)
        if heading:
            section=heading; open_unit=None; add('heading',start,end,'g')
            if section=='experience' and role:
                # A second work section starts a new role, so its bullets never join the previous one.
                role+=1; role_has_work=False
                for key in ('b','h'): counts.pop(key,None)
            continue
        glyph=BULLET.match(line)
        if section=='preamble':
            # A long line without contact details is an untitled summary; everything else identifies the person.
            if len(line)>=120 and not contains_contact(line): add('summary',start,end,'s')
            else: add('contact',start,end,'c')
        elif section=='summary':
            if open_unit is None: open_unit=add('summary',start,end,'s')
            else: extend(open_unit,end)
        elif section=='skills':
            offset=start+(glyph.end() if glyph else 0)
            if offset<end: add('skills',offset,end,'k')
        elif section=='experience':
            if glyph and glyph.end()<len(line):
                glyphs_seen=True; role=role or 1; role_has_work=True
                open_unit=add('bullet',start+glyph.end(),end,'b',number=True); continue
            dated=bool(DATE_RANGE.search(line))
            if open_unit is not None and not dated:
                previous=units[open_unit].text
                wrapped=line[0].islower() or previous.endswith((',',' and',' the',' of',' to',' with',' for',' a'))
                # In glyph-bulleted text, an unfinished long bullet followed by an unmarked line is a wrap.
                wrapped=wrapped or (glyphs_seen and len(previous)>=60 and not previous.endswith(('.',';',':')) and line.endswith('.'))
                if wrapped: extend(open_unit,end); continue
            sentence='|' not in line and (len(line)>=80 or (len(line)>=40 and line.endswith('.'))
                or (len(line.split())>=4 and _starts_with_action(line)))
            if not dated and not glyphs_seen and role and sentence:
                role_has_work=True; open_unit=add('bullet',start,end,'b',number=True)
            else:
                if role==0 or role_has_work:
                    role+=1; role_has_work=False
                    for key in ('b','h'): counts.pop(key,None)
                open_unit=None; add('role_header',start,end,'h',number=True)
        elif section=='education':
            add('education',start,end,'e')
        else:
            add('other',start,end,'o')

    if not any(u.kind in ('bullet','summary') for u in units):
        raise AppError('No summary or experience bullets were found. Check the parsed text; scanned documents need OCR before upload.')
    return units

def model_view(units):
    """What may be sent to a model: contact units are left out and stray contact details are masked."""
    return [dict(unit_id=u.unit_id,kind=u.kind,editable=u.editable,text=mask_contact(u.text)) for u in units if u.kind!='contact']
