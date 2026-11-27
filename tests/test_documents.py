"""Document types, active flags and audited administrator access."""
from datetime import datetime,timezone
import uuid
import pytest
from starlette.testclient import TestClient
from streamlit.testing.v1 import AppTest
from sandhata import repository as r,identity as a
from sandhata.config import AppError
from sandhata.private_api import app
from sandhata.worker import enqueue

REASON='Synthetic support request'

def upload(p,data,label='Fixture',kind='resume'): return r.upload_resume(p,data,'r.docx',label,kind)

def test_types_are_listed_and_only_active_resumes_are_offered(family,docx_bytes):
    p=family[1];resume=upload(p,docx_bytes,'Resume');letter=upload(p,docx_bytes,'Letter','cover_letter')
    assert {d['doc_type'] for d in r.list_documents(p)}=={'resume','cover_letter'}
    assert [str(x['id']) for x in r.list_resumes(p)]==[resume]
    assert {str(x['parent_id']) for x in r.retrieve(p,'Python')}=={resume}
    r.update_document(p,resume,'Renamed',False)
    assert r.list_resumes(p)==[] and {d['label'] for d in r.list_documents(p)}=={'Renamed','Letter'}
    assert r.resume_download(p,letter)[0]==docx_bytes

def test_invalid_type_and_label_rejected(family,docx_bytes):
    p=family[1]
    with pytest.raises(AppError): upload(p,docx_bytes,'x','portfolio')
    rid=upload(p,docx_bytes)
    with pytest.raises(AppError): r.update_document(p,rid,label='   ')

def test_inactive_resumes_and_cover_letters_cannot_be_compared(family,docx_bytes,job_text):
    p=family[1];jid=r.import_job(p,'Engineer','Fixture',job_text);version=r.job_detail(p,jid)['version_id']
    resume=upload(p,docx_bytes);letter=upload(p,docx_bytes,'Letter','cover_letter')
    with pytest.raises(AppError): enqueue(p,version,letter)
    r.update_document(p,resume,active=False)
    with pytest.raises(AppError): enqueue(p,version,resume)
    r.update_document(p,resume,active=True)
    assert enqueue(p,version,resume)
    tracked=r.save_to_tracker(p,jid)
    with pytest.raises(AppError): r.update_application(p,tracked,'Applied','',datetime.now(timezone.utc),'letter',resume_id=letter)

def test_members_cannot_reach_other_documents(family,docx_bytes):
    admin,member,other=family;rid=upload(member,docx_bytes)
    assert r.list_documents(other)==[] and r.list_documents(admin)==[]
    with pytest.raises(AppError): r.update_document(other,rid,active=False)
    with pytest.raises(AppError): r.admin_list_documents(other)
    for operation in ('view','download','deactivate','delete'):
        with pytest.raises(AppError): r.admin_document(other,rid,operation,REASON)
    # Claiming the role in the application is not enough; the database checks membership.
    from dataclasses import replace
    with pytest.raises(AppError): r.admin_document(replace(other,role='admin'),rid,'view',REASON)
    assert r.list_documents(member)[0]['active']

def test_admin_access_requires_reason_and_is_audited(family,docx_bytes):
    admin,member,_=family;rid=upload(member,docx_bytes,'Member resume')
    listed=r.admin_list_documents(admin)
    assert [(str(d['id']),str(d['owner_user_id'])) for d in listed]==[(rid,member.user_id)]
    assert 'body' not in listed[0]
    with pytest.raises(AppError): r.admin_document(admin,rid,'view','no')
    assert a.audit_events(admin)==[]
    opened=r.admin_document(admin,rid,'view',REASON)
    assert 'Python' in opened['body'] and 'object_key' not in opened
    r.admin_document(admin,rid,'deactivate',REASON);assert r.list_resumes(member)==[]
    r.admin_document(admin,rid,'activate',REASON);assert len(r.list_resumes(member))==1
    assert r.admin_download(admin,rid,REASON)[0]==docx_bytes
    events=a.audit_events(admin)
    assert sorted(e['action'] for e in events)==['document_activate','document_deactivate','document_download','document_view']
    assert all(e['reason']==REASON and e['metadata']['owner']==member.user_id for e in events)

def test_admin_delete_removes_evidence_and_keeps_tracker(family,docx_bytes,job_text):
    admin,member,_=family;rid=upload(member,docx_bytes)
    jid=r.import_job(member,'Engineer','Fixture',job_text);version=r.job_detail(member,jid)['version_id']
    enqueue(member,version,rid);tracked=r.save_to_tracker(member,jid)
    r.update_application(member,tracked,'Applied','',datetime.now(timezone.utc),'applied',resume_id=rid)
    r.admin_document(admin,rid,'delete',REASON)
    assert r.list_documents(member)==[] and r.retrieve(member,'Python',parent_id=rid)==[] and r.tasks(member)==[]
    assert r.list_applications(member)[0]['resume_id'] is None
    with pytest.raises(AppError): r.admin_document(admin,rid,'view',REASON)
    with pytest.raises(AppError): r.admin_document(admin,str(uuid.uuid4()),'view',REASON)

def test_download_service_enforces_admin_and_reason(family,docx_bytes):
    admin,member,other=family;rid=upload(member,docx_bytes);client=TestClient(app)
    def get(p,query): return client.get(f'/download/admin-document/{rid}{query}',headers={'Authorization':'Bearer '+a.issue_capability(p)})
    assert get(other,'?reason=Synthetic+request').status_code==403
    assert get(admin,'').status_code==400
    assert get(admin,'?reason=no').status_code==403
    response=get(admin,'?reason=Synthetic+request')
    assert response.status_code==200 and response.content==docx_bytes

def screen(user,tenant,role,page):
    from sandhata import ui
    from sandhata.db import Principal
    p=Principal(user,tenant,role,1,'Fixture')
    if page=='library': ui.document_library(p,'',lambda *args:None)
    else: ui.admin_documents(p,lambda *args:None)

def test_library_and_admin_screens(family,docx_bytes):
    admin,member,_=family
    def render(p,page):
        view=AppTest.from_function(screen,args=(p.user_id,p.tenant_id,p.role,page),default_timeout=30).run()
        assert not view.exception,[e.message for e in view.exception]
        return view
    render(member,'library');render(admin,'admin')
    upload(member,docx_bytes,'Member resume')
    assert any('Member resume' in e.label for e in render(member,'library').expander)
    view=render(admin,'admin')
    button=next(b for b in view.button if b.label=='View text')
    assert button.disabled and a.audit_events(admin)==[]
    next(t for t in view.text_input if t.label.startswith('Reason')).input(REASON).run()
    next(b for b in view.button if b.label=='View text').click().run()
    view.run()
    assert not view.exception and any('Python' in t.value for t in view.text_area)
    assert [e['action'] for e in a.audit_events(admin)]==['document_view']
