"""The Tailor screen with fake models: start, review one at a time, edit, create a version, link it."""
from sandhata import repository as r
from sandhata import tailoring as t
from sandhata.ui_tailor import diff_html,highlighted
from sandhata.worker import run_once
from tailor_fakes import Writer,Checker,analyzer,B2,GOOD_B2
from test_tailoring_service import setup,reviewed
from test_ui_screens import start,check,click,metrics

def captions(app): return ' '.join(c.value for c in app.caption)
def pages(app): return app.radio(key='sn_page').options
def pick(app,run,suggestion):
    return check(app.selectbox(key='tailor_proposal_'+run).set_value(suggestion).run())

def test_page_guides_an_empty_workspace(family):
    app=start(family[1],'Tailor')
    assert 'Tailor' in pages(app)
    assert any('Upload a resume' in i.value for i in app.info) and any('No tailoring runs yet' in i.value for i in app.info)

def test_unmigrated_database_shows_a_notice_not_an_error(family,monkeypatch):
    monkeypatch.setattr(t,'available',lambda p: False)
    app=start(family[1],'Tailor')
    assert any('database update' in w.value for w in app.warning)
    check(app.radio(key='sn_page').set_value('Diagnostics').run())

def test_start_a_run_and_follow_its_progress(family):
    p=family[1];resume,version=setup(p)
    app=start(p,'Tailor')
    assert app.selectbox(key='tailor_track_'+version).value=='fde' and app.selectbox(key='tailor_level_'+version).value=='lead'
    app=click(app,'Start tailoring')
    assert len(t.list_runs(p))==1 and any('Waiting for the worker' in i.value for i in app.info)
    run_once(analyzer,Writer(),Checker())
    app=click(app,key='tailor_refresh')
    assert metrics(app)['Proposals']=='3' and metrics(app)['Waiting for you']=='3'

def test_review_has_single_decisions_only_and_advances(family):
    p=family[1];_,_,found,s=reviewed(p);run=str(found['id'])
    app=start(p,'Tailor')
    labels=[b.label.lower() for b in app.button]
    assert not [x for x in labels if 'all' in x.split()]
    assert [x for x in labels if x.startswith('approve this')]==['approve this change']
    assert app.button(key='tailor_compose').disabled
    first=app.selectbox(key='tailor_proposal_'+run).value
    app=click(app,key='approve_'+first)
    assert app.selectbox(key='tailor_proposal_'+run).value!=first
    assert metrics(app)['Approved']=='1' and metrics(app)['Waiting for you']=='2'
    second=app.selectbox(key='tailor_proposal_'+run).value
    app=click(app,key='reject_'+second)
    decisions=[x['decision'] for x in t.get_run(p,run)['suggestions']]
    assert sorted(d or '' for d in decisions)==['','approve','reject']

def test_proposal_shows_evidence_and_second_check(family):
    p=family[1];_,_,found,s=reviewed(p,checker=Checker({'After weekly':'unsure'}));run=str(found['id'])
    app=pick(start(p,'Tailor'),run,s['r1.b2'])
    assert any('unsure' in w.value for w in app.warning)
    assert found['suggestions'][1]['job_quote'] in [x.value for x in app.text]
    assert 'a passed check is not proof' in captions(app)

def test_edit_needing_a_statement_requires_the_tick(family):
    p=family[1];_,_,found,s=reviewed(p);run=str(found['id']);sid=s['r1.b2'];text=B2+' and trained 12 new staff'
    app=pick(start(p,'Tailor'),run,sid)
    app.text_area(key='edit_'+sid).set_value(text)
    app=click(app,key='save_edit_'+sid)
    assert any('says more than' in w.value for w in app.warning)
    assert app.button(key='save_attest_'+sid).disabled and t.get_run(p,run)['suggestions'][1]['decision'] is None
    check(app.checkbox(key='attest_'+sid).check().run())
    app=click(app,key='save_attest_'+sid)
    saved=next(x for x in t.get_run(p,run)['suggestions'] if str(x['id'])==sid)
    assert saved['decision']=='edit_approve' and saved['user_attested'] and saved['final_text']==text

def test_create_version_then_link_and_compare(family):
    p=family[1];resume,_,found,s=reviewed(p);run=str(found['id'])
    app=pick(start(p,'Tailor'),run,s['r1.b2'])
    app=click(app,key='approve_'+s['r1.b2'])
    app=click(app,key='tailor_compose')
    assert any(x.value=='Your tailored version' for x in app.subheader) and len(r.list_documents(p))==2
    assert metrics(app)['Left undecided']=='2' and any(m.value.startswith('**Version created**') for m in app.markdown)
    assert not [b for b in app.button if b.key and b.key.startswith(('approve_','reject_','tailor_compose'))]
    app=click(app,key='tailor_link')
    new=str(t.get_run(p,run)['composed']['id'])
    assert [str(a['resume_id']) for a in r.list_applications(p)]==[new]
    assert r.list_applications(p)[0]['status']=='Saved'
    app=click(app,key='tailor_compare')
    assert len(r.tasks(p))==1

def test_failed_run_explains_and_restarts(family):
    p=family[1];resume,version=setup(p);run=t.start_run(p,resume,version)
    run_once(analyzer,Writer(RuntimeError('outage')),Checker())
    app=start(p,'Tailor')
    assert any('Check that Ollama is running' in w.value for w in app.warning)
    click(app,key='tailor_retry')
    assert [x['state'] for x in t.list_runs(p)]==['queued'] and t.list_runs(p)[0]['id']!=run

def test_empty_result_is_explained(family):
    p=family[1];reviewed(p,writer=Writer([]))
    app=start(p,'Tailor')
    assert any('nothing to change' in i.value for i in app.info)

def test_diagnostics_reports_tailoring_measures(family):
    p=family[1];_,_,found,s=reviewed(p);t.decide(p,found['id'],s['r1.b2'],'approve')
    measured=t.measures(p)
    assert measured['runs']==1 and sum(x['approved'] for x in measured['decisions'])==1
    assert sum(x['undecided'] for x in measured['decisions'])==2
    app=start(p,'Diagnostics')
    assert metrics(app)['Tailoring runs']=='1' and metrics(app)['Completed']=='0'

def test_markup_in_documents_is_shown_as_text():
    hostile='<img src=x onerror=alert(1)> Built a tool'
    old,new=diff_html(hostile,hostile+' <script>x</script>')
    assert '<img' not in old+new and '<script' not in new and '&lt;script&gt;' in new
    shown=highlighted(hostile,[(0,5)],(0,len(hostile)))
    assert '<img' not in shown and '&lt;img' in shown

def test_highlight_marks_evidence_and_keeps_all_text():
    import html,re
    body='Alpha line\nBeta <b> line\nGamma line\n'
    shown=highlighted(body,[(0,5)],(11,24))
    assert html.unescape(re.sub(r'</?mark[^>]*>','',shown))==body
    assert '<mark class="sn-cited">Alpha</mark>' in shown and 'sn-target' in shown

def test_other_members_see_no_runs(family):
    reviewed(family[1])
    app=start(family[2],'Tailor')
    assert any('No tailoring runs yet' in i.value for i in app.info)
