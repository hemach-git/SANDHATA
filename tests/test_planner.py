import pytest
from sandhata.planner import plan,lens,default_track_level,TRACKS,LEVELS,MAX_TARGETS
from sandhata.segmenter import segment
from tailor_fixtures import RESUME,JOB
from tailor_fakes import assessment,B2,REQUIRED,CUSTOMER,PREFERRED

UNITS=segment(RESUME)
PLAN=plan(UNITS,JOB,assessment(),'fde','lead')
TARGETS={t.unit_id:t for t in PLAN.targets}

@pytest.mark.parametrize('title,expected',[
    ('Lead AI Forward Deployed Engineer',('fde','lead')),
    ('Senior FDE, Applied AI',('fde','senior')),
    ('AI Engineering Manager',('ai_engineer','manager')),
    ('Manager, Forward-Deployed Engineering',('fde','manager')),
    ('Staff AI Engineer',('ai_engineer','lead')),
    ('AI Engineer',('ai_engineer','senior')),
])
def test_track_and_level_are_suggested_from_the_title(title,expected):
    assert default_track_level(title)==expected

@pytest.mark.parametrize('track',TRACKS)
@pytest.mark.parametrize('level',LEVELS)
def test_every_lens_loads_with_terms_and_expectations(track,level):
    view=lens(track,level)
    assert view['terms'] and view['expects'] and view['label']

def test_assessment_targets_come_first():
    order=[t.unit_id for t in PLAN.targets]
    assert order[:3]==['r1.b4','s1','r1.b2']
    assert TARGETS['r1.b4'].job_quote==REQUIRED and 'rephrase' in TARGETS['r1.b4'].change_types
    assert TARGETS['r1.b2'].job_quote==CUSTOMER and 'reorder' in TARGETS['r1.b2'].change_types
    assert TARGETS['s1'].change_types==('summary',)

def test_only_editable_units_with_literal_job_quotes_are_targeted():
    by_id={u.unit_id:u for u in UNITS}
    for t in PLAN.targets:
        assert by_id[t.unit_id].editable and t.job_quote in JOB and t.change_types
    assert len(PLAN.targets)<=MAX_TARGETS

def test_skills_are_targeted_only_when_a_job_skill_sits_behind_others():
    assert TARGETS['k2'].change_types==('skills_reorder',) and 'k1' not in TARGETS

def test_unevidenced_requirements_become_gaps_not_targets():
    assert PREFERRED not in [t.job_quote for t in PLAN.targets]
    assert dict(kind='skill',label=PREFERRED,job_quote=PREFERRED) in PLAN.gaps

def test_level_gaps_list_only_what_the_resume_does_not_show():
    labels=[g['label'] for g in plan(UNITS,JOB,None,'fde','manager').gaps]
    assert 'Hiring' in labels and 'Engagement portfolio' in labels
    assert 'Prototype taken to production' not in labels  # "Deployed" is in the resume

def test_planning_works_without_an_assessment():
    found=plan(UNITS,JOB,None,'ai_engineer','senior')
    assert found.targets and all(t.job_quote in JOB for t in found.targets)
    assert not [g for g in found.gaps if g['kind']=='skill']

def test_last_bullet_of_a_role_is_never_moved_down():
    for track in TRACKS:
        for t in plan(UNITS,'Gardening and pottery only.\nMore pottery.',None,track,'senior').targets:
            if 'deemphasize' in t.change_types: assert t.unit_id not in ('r1.b5','r2.b2')

def test_target_count_is_capped():
    bullets=''.join(f'• Built Python service number {n} for the platform team\n' for n in range(30))
    units=segment('Summary\nEngineer who builds Python services.\n\nExperience\nEngineer | Synthetic Co\nJan 2020 - Present\n'+bullets)
    assert len(plan(units,'Python platform role.',None,'ai_engineer','senior').targets)==MAX_TARGETS

def test_assessment_offsets_outside_editable_text_are_ignored():
    data=assessment(); data['requirements'][0]['resume_offset']=RESUME.index('BS Computer')
    assert all(t.unit_id!='e1' for t in plan(UNITS,JOB,data,'fde','lead').targets)
