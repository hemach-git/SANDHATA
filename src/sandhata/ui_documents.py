"""Screens for member documents and audited administrator document access."""
from urllib.parse import urlencode
import pandas as pd
import streamlit as st
from . import repository as repo

STATUS=('All','Active','Inactive')

def _visible(item,kind,status):
    return (kind=='All' or item['doc_type']==kind) and (status=='All' or item['active']==(status=='Active'))

def _filters(key):
    a,b=st.columns(2)
    kind=a.selectbox('Document type',['All',*repo.DOC_TYPES],format_func=lambda v:repo.DOC_TYPES.get(v,v),key=key+'_type')
    status=b.selectbox('Status',STATUS,key=key+'_status')
    return kind,status

def document_library(p,query,download):
    st.header('Your document library')
    st.caption('Resumes, cover letters and other files. Workspace administrators can also open and manage them; each such action is recorded with a reason.')
    st.caption('Each upload is a new version. Only active resumes are offered for comparisons and applications.')
    with st.form('document_upload',clear_on_submit=True):
        a,b=st.columns(2)
        kind=a.selectbox('Upload as',list(repo.DOC_TYPES),format_func=repo.DOC_TYPES.get)
        label=b.text_input('Version label',placeholder='AI Engineering Manager · November 2026')
        file=st.file_uploader('PDF or DOCX · text documents up to 10 MB',type=['pdf','docx'])
        if st.form_submit_button('Upload and parse',type='primary'):
            if file is None: st.error('Choose a document first.')
            else:
                repo.upload_resume(p,file.getvalue(),file.name,label,kind);st.toast('Document saved');st.rerun()
    documents=repo.list_documents(p)
    if not documents:
        st.info('Upload your first resume to start comparing roles.');return
    kind,status=_filters('library')
    shown=[d for d in documents if _visible(d,kind,status) and (not query or query.lower() in d['label'].lower())]
    st.caption(f'{len(shown)} of {len(documents)} documents shown.')
    for d in shown:
        key=str(d['id'])
        title=' · '.join([d['label'],repo.DOC_TYPES[d['doc_type']],'Active' if d['active'] else 'Inactive',d['created_at'].strftime('%b %d %Y')])
        with st.expander(title):
            with st.form('document_edit_'+key):
                a,b=st.columns([3,1])
                renamed=a.text_input('Label',value=d['label'],max_chars=100,key='label_'+key)
                active=b.checkbox('Active',value=d['active'],key='active_'+key)
                if st.form_submit_button('Save changes'):
                    repo.update_document(p,d['id'],renamed,active);st.toast('Document updated');st.rerun()
            detail=repo.resume_detail(p,d['id'])
            st.text_area('Extracted text',detail['body'],height=220,disabled=True,key='body_'+key)
            st.caption('Parser: '+detail['parser_version']+' · Content fingerprint '+d['file_hash'][:12])
            download(p,'Download your original','resume',d['id'])
            confirm=st.checkbox('Delete this document and its comparison evidence',key='deleteconfirm_'+key)
            if st.button('Delete document',key='delete_'+key,disabled=not confirm): repo.delete_resume(p,d['id']);st.rerun()

def admin_documents(p,download):
    st.caption("Open and manage any member's documents. A reason is required and recorded in the audit log.")
    message=st.session_state.pop('admin_document_message',None)
    if message: st.success(message)
    documents=repo.admin_list_documents(p)
    if not documents:
        st.info('No documents have been uploaded in this workspace.');return
    owners={str(d['owner_user_id']):f"{d['owner_name']} · {d['owner_email']}" for d in documents}
    owner=st.selectbox('Member',['All',*owners],format_func=lambda v:owners.get(v,'All members'),key='admin_doc_owner')
    kind,status=_filters('admin_doc')
    shown=[d for d in documents if _visible(d,kind,status) and (owner=='All' or str(d['owner_user_id'])==owner)]
    if not shown:
        st.info('No documents match these filters.');return
    table=pd.DataFrame([dict(member=d['owner_name'],email=d['owner_email'],label=d['label'],type=repo.DOC_TYPES[d['doc_type']],
                             status='Active' if d['active'] else 'Inactive',uploaded=d['created_at']) for d in shown])
    st.dataframe(table,hide_index=True,use_container_width=True,height=min(320,38+36*len(table)))
    chosen=st.selectbox('Document to manage',shown,format_func=lambda d:f"{d['owner_name']} · {d['label']} · {str(d['id'])[:6]}")
    key=str(chosen['id'])
    reason=st.text_input('Reason for access (recorded)',key='admin_doc_reason_'+key,max_chars=300)
    ready=len(reason.strip())>=5
    a,b=st.columns(2)
    if a.button('View text',disabled=not ready,use_container_width=True):
        # Fetch once so that later screen refreshes do not add audit entries.
        st.session_state['admin_document_view']=repo.admin_document(p,key,'view',reason)
    action='deactivate' if chosen['active'] else 'activate'
    if b.button(action.title(),disabled=not ready,use_container_width=True):
        repo.admin_document(p,key,action,reason)
        st.session_state['admin_document_message']=f'Document {action}d.';st.rerun()
    opened=st.session_state.get('admin_document_view')
    if opened and opened['id']==key:
        st.text_area('Document text',opened['body'],height=300,disabled=True,key='admin_body_'+key)
        if st.button('Close document'):
            del st.session_state['admin_document_view'];st.rerun()
    if ready:
        st.caption('Each download is recorded.')
        download(p,'Download original file','admin-document',key,'?'+urlencode({'reason':reason.strip()}))
    confirm=st.checkbox('Permanently delete this document and its comparison evidence',key='admin_doc_confirm_'+key)
    if st.button('Delete member document',disabled=not(ready and confirm)):
        repo.admin_document(p,key,'delete',reason)
        st.session_state.pop('admin_document_view',None)
        st.session_state['admin_document_message']='Document deleted.';st.rerun()
