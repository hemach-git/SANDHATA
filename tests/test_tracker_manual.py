from datetime import datetime,timezone
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from sandhata import repository as repo
from sandhata.db import Principal

def test_manual_application_duplicate_preserves_history(family):
    _,member,other=family
    args=dict(title='Engineer',company='Example',url='https://www.linkedin.com/jobs/view/123/?trackingId=abc',location='Charlotte, NC',arrangement='Hybrid',notes='Recruiter reached out')
    assert repo.create_manual_application(member,**args)['added']==1
    app=repo.list_applications(member)[0]
    assert app['status']=='Saved' and app['applied_at'] is None
    assert app['source']=='LinkedIn' and app['original_url']=='https://www.linkedin.com/jobs/view/123'
    repo.update_application(member,app['id'],'Applied','Submitted',datetime.now(timezone.utc),'submit')
    history=repo.application_history(member,app['id'])
    assert repo.create_manual_application(member,**args)['skipped']==1
    assert repo.list_applications(member)[0]['notes']=='Submitted'
    assert repo.application_history(member,app['id'])==history
    assert repo.list_applications(other)==[]

def test_reset_clears_draft_without_saving():
    app=AppTest.from_string('''
from sandhata.ui import new_application
from sandhata.db import Principal
import streamlit as st
st.session_state['saved_history']=['Saved','Applied']
new_application(Principal('user','tenant','member',1))
''').run(timeout=15)
    app.text_input(key='tracker_new_title').set_value('Unsaved role')
    app.text_input(key='tracker_new_company').set_value('Example')
    with patch.object(repo,'create_manual_application') as create:
        next(b for b in app.button if b.label=='Reset draft').click().run(timeout=15)
        create.assert_not_called()
    assert not app.exception
    assert app.text_input(key='tracker_new_title').value==''
    assert app.text_input(key='tracker_new_company').value==''
    assert app.session_state['saved_history']==['Saved','Applied']

def test_manual_validation_keeps_draft():
    from sandhata.config import AppError
    app=AppTest.from_string('''
from sandhata.ui import new_application
from sandhata.db import Principal
new_application(Principal('user','tenant','member',1))
''').run(timeout=15)
    app.text_input(key='tracker_new_title').set_value('My role')
    with patch.object(repo,'create_manual_application',side_effect=AppError('Employer required')):
        next(b for b in app.button if b.label=='Save new application').click().run(timeout=15)
    assert not app.exception and app.error[0].value=='Employer required'
    assert app.text_input(key='tracker_new_title').value=='My role'

def test_update_reset_restores_stored_values_without_writes():
    app=AppTest.from_string('''
from sandhata import ui,repository as repo
from sandhata.db import Principal
from unittest.mock import patch
with patch.object(repo,'list_applications',return_value=[dict(id='app',job_id='job',title='Engineer',company='Example',location='Charlotte',work_arrangement='Hybrid',salary_description='$150k base',job_type='Full Time',recruiter='Jane Smith',status='Saved',notes='Stored note',applied_at=None,follow_up=None)]), patch.object(repo,'job_detail',return_value=dict(title='Engineer',company='Example',original_url='',body='Posting')), patch.object(repo,'application_history',return_value=[dict(status='Saved')]), patch.object(repo,'update_application',side_effect=AssertionError('Reset must never write')), patch.object(ui,'private_download'):
    ui.tracker(Principal('user','tenant','member',1),[],'')
''').run(timeout=15)
    assert not app.exception
    app.text_area(key='tracker_edit_app_notes').set_value('Discard me')
    app.text_input(key='tracker_edit_app_location').set_value('Elsewhere')
    app.text_input(key='tracker_edit_app_salary').set_value('Unsaved salary')
    app.selectbox(key='tracker_edit_app_job_type').set_value('Contract')
    next(b for b in app.button if b.label=='Reset unsaved changes').click().run(timeout=15)
    assert not app.exception
    assert app.text_area(key='tracker_edit_app_notes').value=='Stored note'
    assert app.text_input(key='tracker_edit_app_location').value=='Charlotte'
    assert app.text_input(key='tracker_edit_app_salary').value=='$150k base'
    assert app.selectbox(key='tracker_edit_app_job_type').value=='Full Time'


    app.text_input(key='tracker_search').set_value('Anthony Charlotte').run(timeout=15)
    next(b for b in app.button if b.label=='Clear search / filters').click().run(timeout=15)
    assert not app.exception
    assert app.text_input(key='tracker_search').value==''
    assert app.multiselect(key='tracker_status_filter').value==[]
