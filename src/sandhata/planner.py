"""Choose which resume units to tailor, and which gaps to show. Deterministic: no model, no storage.

Gaps are shown to the user and are never given to the writer as something to fill.
"""
import json,re
from dataclasses import dataclass
from pathlib import Path

from .tailor_validation import POLICY,_has_stem,_skill_items,_has

LENSES=json.loads((Path(__file__).parent/'assets'/'tailor_lenses.json').read_text(encoding='utf-8'))
LENS_VERSION=LENSES['version']
TRACKS=('fde','ai_engineer')
LEVELS=('senior','lead','manager')
MAX_TARGETS=15
QUOTE_LIMIT=600

@dataclass(frozen=True)
class Target:
    unit_id: str
    job_quote: str
    change_types: tuple
    why: str
    priority: float

@dataclass(frozen=True)
class Plan:
    targets: tuple
    gaps: tuple

def lens(track,level):
    """Terms accumulate through `extends`; expectations list the level's own items first."""
    key=f'{track}.{level}'; terms=[]; expects=[]; label=LENSES['lenses'][key]['label']
    while key:
        entry=LENSES['lenses'][key]
        terms+=entry['terms']; expects+=entry['expects']; key=entry.get('extends')
    return dict(label=label,terms=tuple(dict.fromkeys(terms)),expects=tuple(expects))

def default_track_level(title):
    """A suggestion from the job title; the user may change it."""
    track='fde' if re.search(r'forward[\s-]*deployed|\bfde\b',title,re.I) else 'ai_engineer'
    if re.search(r'\b(manager|head|director)\b',title,re.I): level='manager'
    elif re.search(r'\b(lead|principal|staff)\b',title,re.I): level='lead'
    else: level='senior'
    return track,level

def _job_lines(job_text):
    """Literal pieces of the job text that can be cited."""
    found=[]
    for line in job_text.split('\n'):
        line=line.strip()
        if len(line)>=3: found.append(line[:QUOTE_LIMIT].rstrip())
    return found

def _shared_terms(text,job_text):
    return [t for t in dict.fromkeys(POLICY['claim_terms']+POLICY['tech_terms']) if _has_stem(job_text,t) and _has_stem(text,t)]

def plan(units,job_text,assessment,track,level):
    view=lens(track,level)
    requirements=(assessment or {}).get('requirements',[])
    lines=_job_lines(job_text)
    cited=[r['requirement_quote'][:QUOTE_LIMIT].rstrip() for r in requirements
           if r['status']!='not_evidenced' and r['requirement_quote'] in job_text]
    cited=[q for q in cited if len(q)>=3]
    # A line carrying a requirement the resume does not evidence is a gap, so it is never offered as a rewrite target.
    missing=[r['requirement_quote'] for r in requirements if r['status']=='not_evidenced' and r['requirement_quote']]
    lines=[line for line in lines if not any(line in quote or quote in line for quote in missing)]
    fallback=(cited or lines or [''])[0]
    roles={}
    for u in units:
        if u.kind=='bullet': roles.setdefault(u.role,[]).append(u)
    chosen={}

    def add(unit,quote,change_types,why,priority):
        if len(quote)<3 or quote not in job_text or not change_types: return
        found=chosen.get(unit.unit_id)
        if found:
            best=found if found.priority>=priority else Target(unit.unit_id,quote,(),why,priority)
            merged=tuple(dict.fromkeys(found.change_types+tuple(change_types)))
            chosen[unit.unit_id]=Target(unit.unit_id,best.job_quote,merged,best.why,best.priority)
        else: chosen[unit.unit_id]=Target(unit.unit_id,quote,tuple(change_types),why,priority)

    def boost(unit): return sum(1 for t in view['terms'] if _has_stem(unit.text,t))

    def bullet_changes(unit):
        siblings=roles[unit.role]
        return ('rephrase','reorder') if len(siblings)>1 else ('rephrase',)

    for r in requirements:
        status=r['status']; offset=r.get('resume_offset')
        if status not in ('partial','supported') or offset is None: continue
        unit=next((u for u in units if u.start<=offset<u.end),None)
        if unit is None or not unit.editable: continue
        quote=r['requirement_quote'][:QUOTE_LIMIT].rstrip()
        if unit.kind=='bullet':
            low=roles[unit.role].index(unit)>0
            if status=='partial': add(unit,quote,bullet_changes(unit),'partly evidenced requirement',100+boost(unit))
            elif low: add(unit,quote,bullet_changes(unit),'evidence for a requirement sits low in its role',60+boost(unit))

    for unit in units:
        if unit.kind=='bullet':
            shared=_shared_terms(unit.text,job_text); hits=boost(unit)
            if shared:
                quote=next((line for term in shared for line in lines if _has_stem(line,term)),None)
                if quote: add(unit,quote,bullet_changes(unit),'shares terms with the job: '+', '.join(shared[:3]),20+2*len(shared)+hits)
            elif not hits and unit.unit_id not in chosen and unit!=roles[unit.role][-1]:
                add(unit,fallback,('deemphasize',),'no overlap with the job or the target level',1)
        elif unit.kind=='skills':
            label,_,rest=unit.text.rpartition(':')
            items=[i.strip() for i in re.split(r'[,;|•·]',rest) if i.strip()]
            wanted=[i for i in items if _has(job_text,i)]
            # Worth reordering only when a job skill currently sits behind one the job does not mention.
            if wanted and items[:len(wanted)]!=wanted and sum(_skill_items(unit.text)[1].values())>1:
                quote=next((line for line in lines if _has(line,wanted[0])),fallback)
                add(unit,quote,('skills_reorder',),'job skills can come first: '+', '.join(wanted[:3]),40+len(wanted))

    bullet_count=sum(len(v) for v in roles.values())
    for unit in units:
        # A summary must rest on at least two different bullets.
        if unit.kind=='summary' and bullet_count>=2:
            add(unit,fallback,('summary',),'summary for the target role',90); break

    targets=tuple(sorted(chosen.values(),key=lambda t:-t.priority)[:MAX_TARGETS])
    return Plan(targets,tuple(_gaps(units,requirements,job_text,view)))

def _gaps(units,requirements,job_text,view):
    gaps=[]; seen=set()
    for r in requirements:
        quote=r['requirement_quote']
        if r['status']=='not_evidenced' and quote in job_text and quote not in seen:
            seen.add(quote); gaps.append(dict(kind='skill',label=quote[:QUOTE_LIMIT],job_quote=quote[:QUOTE_LIMIT]))
    # Contact lines are not evidence of experience.
    text='\n'.join(u.text for u in units if u.kind not in ('contact','heading'))
    for expected in view['expects']:
        if not any(_has_stem(text,term) for term in expected['terms']):
            gaps.append(dict(kind='level',label=expected['label'],job_quote=''))
    return gaps
