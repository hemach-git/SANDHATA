"""The authority on tailoring faithfulness. Pure rules: no model calls, no storage.

A proposal is shown to the user only if every rule passes. These rules compare words, so they
cannot catch every change of meaning; the user's review of each change remains the final control.
"""
import json,re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel,Field,ValidationError

from .segmenter import contains_contact

POLICY=json.loads((Path(__file__).parent/'assets'/'tailor_policy.json').read_text(encoding='utf-8'))
POLICY_VERSION=POLICY['version']

class Evidence(BaseModel):
    quote: str=Field(min_length=3,max_length=600)

class Proposal(BaseModel):
    unit_id: str=Field(min_length=1,max_length=40)
    change_type: Literal['rephrase','reorder','skills_reorder','summary','deemphasize']
    after: str=Field(default='',max_length=600)
    new_position: int|None=None
    evidence: list[Evidence]=Field(min_length=1,max_length=4)
    job_quote: str=Field(min_length=3,max_length=600)
    rationale: str=Field(default='',max_length=300)

class Draft(BaseModel):
    proposals: list[Proposal]=Field(default_factory=list,max_length=15)

@dataclass(frozen=True)
class Result:
    ok: bool
    proposal: dict
    reason: str=''
    details: tuple=()
    before: str=''
    start: int=0
    end: int=0
    evidence: tuple=()
    job_offset: int=0
    warnings: tuple=()

UNIT_KIND={'rephrase':'bullet','reorder':'bullet','deemphasize':'bullet','skills_reorder':'skills','summary':'summary'}
ORDER_ONLY=('reorder','deemphasize')

NUMBER_WORDS=dict(two=2,three=3,four=4,five=5,six=6,seven=7,eight=8,nine=9,ten=10,eleven=11,twelve=12,thirteen=13,
    fourteen=14,fifteen=15,sixteen=16,seventeen=17,eighteen=18,nineteen=19,twenty=20,thirty=30,forty=40,fifty=50,
    sixty=60,seventy=70,eighty=80,ninety=90,hundred=100,thousand=1000,million=1000000,billion=1000000000,dozen=12,
    dozens=12,hundreds=100,thousands=1000,millions=1000000,double=2,doubled=2,triple=3,tripled=3,half=0.5,halved=0.5)
SCALE=dict(k=1e3,thousand=1e3,m=1e6,million=1e6,b=1e9,bn=1e9,billion=1e9)
NUMBER=re.compile(r'(?<![A-Za-z0-9])(?<![A-Za-z]-)([$€£])?(\d[\d,]*(?:\.\d+)?)(?:\s?(%|percent\b|x\b|k\b|m\b|bn\b|b\b|thousand\b|million\b|billion\b))?(\+)?',re.I)
TOKEN=re.compile(r"[A-Za-z0-9][A-Za-z0-9+#./&'-]*[A-Za-z0-9+#]|[A-Za-z]")
PLAIN=re.compile(r"[^\W_]|[ .,;:'\"()\[\]/&+#%$\-–—‘’“”€£!?|•·_@~=<>]")

def _has(text,phrase):
    """Whole-word, case-insensitive containment; an optional plural s is allowed."""
    return re.search(r'(?<![A-Za-z0-9])'+re.escape(phrase)+r'(?:s|es)?(?![A-Za-z0-9+#])',text,re.I) is not None

def _stem(word):
    word=word.casefold().replace("'s",'')
    for suffix in ('ments','ment','ings','ing','ers','ed','es','er','s'):
        if word.endswith(suffix) and len(word)-len(suffix)>=4:
            word=word[:-len(suffix)]; break
    if len(word)>4 and word[-1]==word[-2] and word[-1] not in 'ls': word=word[:-1]
    return word[:-1] if len(word)>4 and word.endswith('e') else word

def _stemmed(text):
    return ' '+' '.join(_stem(w) for w in re.findall(r"[A-Za-z0-9+#']+",text))+' '

def _has_stem(text,phrase):
    return _stemmed(phrase) in _stemmed(text)

def numbers(text):
    """Every quantity as (value, unit). Digits inside names such as GPT-4 are handled as terms instead."""
    found=set()
    for currency,digits,suffix,plus in NUMBER.findall(text):
        value=float(digits.replace(',','')); unit=currency or ''; suffix=suffix.casefold()
        if suffix in ('%','percent'): unit='%'
        elif suffix=='x': unit='x'
        elif suffix in SCALE: value*=SCALE[suffix]
        found.add((value,unit+plus))
    for word in re.findall(r'[A-Za-z]+',text):
        if word.casefold() in NUMBER_WORDS: found.add((float(NUMBER_WORDS[word.casefold()]),''))
    return found

def _supported(term,support):
    if _has(support,term): return True
    for group in POLICY['aliases']:
        if term.casefold().rstrip('.') in group and any(_has(support,alias) for alias in group): return True
    if term.casefold().endswith("'s"): return _supported(term[:-2],support)
    parts=[p for p in re.split(r'[-/]',term) if p]
    if len(parts)>1:
        return all(p.casefold() in POLICY['neutral_words']+['based','driven','powered','facing','built','led','level'] or _supported(p,support) for p in parts)
    return False

def unsupported_facts(after,support):
    """Numbers, names, tools, credentials and titles in `after` that the support text does not contain."""
    supported_numbers=numbers(support)
    missing=[f'{value:g}{unit}' for value,unit in sorted(numbers(after)-supported_numbers)]
    text=after
    # Remove alias phrases that the evidence supports under another name, so their words are not re-checked.
    for group in POLICY['aliases']:
        if any(_has(support,alias) for alias in group):
            for alias in sorted((a for a in group if ' ' in a or '-' in a),key=len,reverse=True):
                text=re.sub(r'(?<![A-Za-z0-9])'+re.escape(alias)+r'(?![A-Za-z0-9])',' it ',text,flags=re.I)
    lexicon=set(POLICY['tech_terms'])
    named=set(POLICY['credential_terms'])|set(POLICY['title_terms'])
    for match in TOKEN.finditer(text):
        term=match.group().rstrip('.'); lower=term.casefold()
        if re.fullmatch(r'[\d.,]+(?:k|m|b|x)?',lower): continue
        before=text[:match.start()].rstrip()
        opens_sentence=not before or before[-1] in '.!?:'
        special=(any(c.isdigit() or c in '+#&' for c in term) or any(c.isupper() for c in term[1:])
                 or lower in lexicon or lower in named)
        if not special and term[0].isupper():
            # Ordinary sentence openers (verbs ending -ed or -ing, articles) are not names.
            ordinary=opens_sentence and (lower in POLICY['sentence_starters'] or lower.endswith(('ed','ing')))
            special=not ordinary
        if special and not _supported(term,support): missing.append(term)
    return list(dict.fromkeys(missing))

def scope_inflation(after,support,before=''):
    found=[]
    for forms in POLICY['scope_verbs'].values():
        used=[f for f in forms if _has(after,f)]
        if used and not any(_has(support,f) for f in forms): found+=used
    # "Helped reduce" must not become "Reduced": each kind of qualifier in the original has to survive in some form.
    for words in POLICY['qualifiers'].values():
        original=[w for w in words if _has(before,w)]
        if original and not any(_has(after,w) for w in words): found.append('dropped qualifier: '+original[0])
    return found

def overclaims(after,support):
    return [w for w in POLICY['absolute_words'] if _has(after,w) and not _has(support,w)]

def unevidenced_keywords(after,support):
    """Claim and technology words need resume evidence, whether or not the posting uses them."""
    terms=POLICY['claim_terms']+POLICY['tech_terms']
    return [t for t in dict.fromkeys(terms) if _has_stem(after,t)
            and not _has_stem(support,t) and not _supported(t,support)]

def sensitive_topics(after):
    return [p for p in POLICY['sensitive_patterns'] if re.search(p,after,re.I)]

def new_wording(after,support):
    """Words not found in the evidence. Allowed, but shown to the user so they can check the meaning."""
    known=set(_stemmed(support).split())
    return [w for w in dict.fromkeys(re.findall(r"[A-Za-z][A-Za-z'-]+",after))
            if w.casefold() not in POLICY['neutral_words'] and not set(_stemmed(w).split())<=known]

def check_text(after,support,job_text,before=''):
    """Content rules for rewritten text. Returns (reason, details), or ('', ()) when all pass.

    Also used to check text the user edits and, at compose time, every changed span.
    """
    checks=(('sensitive_topic',lambda: sensitive_topics(after)),
            ('unsupported_fact',lambda: unsupported_facts(after,support)),
            ('scope_inflation',lambda: scope_inflation(after,support,before)),
            ('overclaim',lambda: overclaims(after,support)),
            ('keyword_not_evidenced',lambda: unevidenced_keywords(after,support)))
    for reason,check in checks:
        found=check()
        if found: return reason,tuple(found)
    return '',()

def _locate(quote,text,units):
    """Return (offset, unit) for each whole-word occurrence of the quote inside a non-contact unit."""
    found=[]; start=text.find(quote)
    while start>=0:
        end=start+len(quote)
        cuts_word=((start>0 and quote[0].isalnum() and text[start-1].isalnum())
                   or (end<len(text) and quote[-1].isalnum() and text[end].isalnum()))
        unit=next((u for u in units if u.start<=start and end<=u.end),None)
        if not cuts_word and unit is not None and unit.kind!='contact': found.append((start,unit))
        start=text.find(quote,start+1)
    return found

def _skill_items(text):
    label,separator,rest=text.partition(':')
    if not separator: label,rest='',text
    return label.strip().casefold(),Counter(i.strip().casefold() for i in re.split(r'[,;|•·]',rest) if i.strip())

def _format_problem(after,before,kind):
    if not after.strip(): return 'empty text'
    limits=POLICY['limits']
    limit=limits['summary_chars'] if kind=='summary' else limits['bullet_chars']
    if len(after)>limit: return f'longer than {limit} characters'
    if len(after)>max(len(before)*limits['growth'],len(before)+20): return 'grew too much compared with the original'
    bad=sorted({c for c in after if not PLAIN.fullmatch(c)})
    if bad or '**' in after or '`' in after: return 'characters or markup that resume parsers may misread'
    if contains_contact(after) and not contains_contact(before): return 'adds contact details'
    return ''

def validate(proposal,units,resume_text,job_text):
    """Check one proposal against rules V1 to V9 and V11. V10 needs the whole set: see validate_all."""
    try: p=Proposal.model_validate(proposal)
    except ValidationError: return Result(False,dict(proposal) if isinstance(proposal,dict) else {},'invalid_schema')
    data=p.model_dump()
    def fail(reason,*details): return Result(False,data,reason,details)

    unit=next((u for u in units if u.unit_id==p.unit_id),None)
    if (unit is None or not unit.editable or unit.kind!=UNIT_KIND[p.change_type]
            or resume_text[unit.start:unit.end]!=unit.text): return fail('unknown_or_locked_unit')

    spans=[]; cited=[]
    for item in p.evidence:
        found=_locate(item.quote,resume_text,units)
        if not found: return fail('evidence_not_found',item.quote)
        # Prefer the occurrence in the edited unit, then in the same role, when text repeats.
        found.sort(key=lambda f:(f[1].unit_id!=unit.unit_id,f[1].role!=unit.role))
        offset,source=found[0]
        spans.append(dict(quote=item.quote,offset=offset,unit_id=source.unit_id)); cited.append(source)
    if p.job_quote not in job_text: return fail('job_quote_not_found',p.job_quote)
    if unit.kind=='bullet':
        # A tool or result from one job must never move into another.
        outside=[s.unit_id for s in cited if s.unit_id!=unit.unit_id and s.role!=unit.role]
        if outside: return fail('cross_role_evidence',*outside)

    def passed(warnings=()):
        return Result(True,data,before=unit.text,start=unit.start,end=unit.end,evidence=tuple(spans),
                      job_offset=job_text.index(p.job_quote),warnings=tuple(warnings))

    if p.change_type in ORDER_ONLY:
        if p.after: return fail('length_or_format','a move or removal must not rewrite text')
        if p.change_type=='reorder':
            siblings=[u for u in units if u.kind=='bullet' and u.role==unit.role]
            if p.new_position is None or not 0<=p.new_position<len(siblings): return fail('length_or_format','position outside this role')
            if siblings[p.new_position].unit_id==unit.unit_id: return fail('no_change')
        return passed()

    if p.after.strip()==unit.text.strip(): return fail('no_change')
    problem=_format_problem(p.after,unit.text,unit.kind)
    if problem: return fail('length_or_format',problem)
    if p.change_type=='skills_reorder':
        if _skill_items(p.after)!=_skill_items(unit.text): return fail('skills_changed','reordering must keep exactly the same items')
        return passed()

    support='\n'.join([unit.text]+[s['quote'] for s in spans])
    reason,details=check_text(p.after,support,job_text,unit.text)
    if reason: return fail(reason,*details)
    novel=new_wording(p.after,support)
    return passed(['New wording, check the meaning: '+', '.join(novel)] if novel else [])

def validate_all(proposals,units,resume_text,job_text):
    """Validate a draft. Returns (accepted, rejected); one proposal per unit, first valid one wins."""
    accepted=[]; rejected=[]; used=set()
    for proposal in proposals:
        result=validate(proposal,units,resume_text,job_text)
        if result.ok:
            unit_id=result.proposal['unit_id']
            if unit_id in used:
                result=Result(False,result.proposal,'conflict_or_thin_summary',('second proposal for this unit',))
            elif (result.proposal['change_type']=='summary'
                  and len({e['unit_id'] for e in result.evidence if '.b' in e['unit_id']})<2):
                result=Result(False,result.proposal,'conflict_or_thin_summary',('a summary needs two different experience bullets',))
            else: used.add(unit_id)
        (accepted if result.ok else rejected).append(result)
    return accepted,rejected

def drop_counts(rejected):
    """Reason codes and counts only, safe to log and store."""
    return dict(Counter(r.reason for r in rejected))
