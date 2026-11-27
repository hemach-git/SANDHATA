"""Helpers shared by the workspace screens: escaping, tables, navigation and protected downloads."""
import html,json,os,re,time
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from . import identity as auth

DISCOVER_FILTERS=dict(discover_new=False,discover_company=[],discover_seniority=[],discover_source=[],
    discover_place='Any location',discover_min=0,discover_order='Role priority')

def md(value):
    """Show untrusted text inside Markdown as literal text on one line."""
    return re.sub(r'([!-/:-@\[-`{-~])',r'\\\1',' '.join(str(value or '').split()))

def safe_csv(records):
    frame=pd.DataFrame(records)
    for col in frame.select_dtypes(include='object'):
        frame[col]=frame[col].map(lambda v:"'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v)
    return frame.to_csv(index=False).encode('utf-8-sig')

def compact_dataframe(data,**kwargs):
    count=len(data.data) if hasattr(data,'data') else len(data)  # A pandas Styler wraps its frame.
    return st.dataframe(data,height=min(320,max(100,40+35*count)),**kwargs)

def toast(message): st.toast(message)

def flash(message,kind='success'):
    """Keep a message across the next rerun."""
    st.session_state.setdefault('sn_flash',[]).append((kind,message))

def show_flash():
    for kind,message in st.session_state.pop('sn_flash',[]): getattr(st,kind)(message)

# Navigation runs in button callbacks, before widgets are drawn, so their state can be set.
def navigate(page,**state):
    st.session_state['sn_page']=page
    for key,value in state.items(): st.session_state[key]=value

def open_application(app_id):
    """Open Tracker with one application selected and nothing filtering it out."""
    navigate('Tracker',tracker_selected=str(app_id),tracker_search='',tracker_status_filter=[],
        tracker_overdue_only=False,sn_query='',tracker_opened=str(app_id))

def open_discover(tab='Matches',new_only=False):
    state=dict(discover_tab=tab)
    if new_only: state.update(DISCOVER_FILTERS,discover_new=True,sn_query='')
    navigate('Discover',**state)

def confirm_button(container,label,key,question):
    """Two-step destructive action. Returns True only on the confirming click."""
    pending='confirm_'+key
    if not st.session_state.get(pending):
        container.button(label,key=key,on_click=st.session_state.__setitem__,args=(pending,True))
        return False
    container.markdown(question)
    row=container.container(horizontal=True)
    confirmed=row.button('Confirm removal',key=key+'_yes',type='primary')
    row.button('Keep',key=key+'_no',on_click=st.session_state.pop,args=(pending,None))
    if confirmed: st.session_state.pop(pending,None)
    return confirmed

def alignment_text(result):
    """Resume alignment is always shown with its coverage and provisional marker."""
    if not result: return 'Resume alignment: not compared'
    score='withheld' if result.get('score') is None else f"{result['score']:.0f}%"
    return f"Resume alignment **{score}**  \nCoverage {result['coverage']:.0f}%"+(' · Provisional' if result.get('provisional') else '')

def private_download(p,label,kind,identifier='',params=''):
    cache=st.session_state.get('download_capability')
    if not cache or time.time()-cache['created']>840:
        cache=dict(token=auth.issue_capability(p),created=time.time());st.session_state['download_capability']=cache
    url=os.getenv('SANDHATA_API_BASE_URL','http://localhost:8851')+'/download/'+kind+('/'+str(identifier) if identifier else '')+params
    # Bearer token is in a private authenticated component, never in a URL, HTML attribute, or access log.
    script='''<button id="download" style="font:700 13px sans-serif;padding:7px 12px;border:2px solid #059669;border-radius:8px;background:white;color:#064E3B;cursor:pointer">LABEL</button><span id="message" style="font:12px sans-serif;margin-left:8px"></span>
    <style>button:hover{background:#FDF0C3!important;color:#064E3B!important}button:focus-visible{outline:3px solid #047857;outline-offset:2px}</style><script>document.getElementById('download').onclick=async()=>{const m=document.getElementById('message');m.textContent='Authorizing…';try{const r=await fetch(URL,{headers:{Authorization:'Bearer '+TOKEN}});if(!r.ok)throw new Error('Access expired or file unavailable. Refresh this page.');const blob=await r.blob();const a=document.createElement('a');const u=URL_OBJECT.createObjectURL(blob);a.href=u;a.download=(r.headers.get('content-disposition')||'').split('filename="')[1]?.split('"')[0]||'SANDHATA-download';a.click();setTimeout(()=>URL_OBJECT.revokeObjectURL(u),1000);m.textContent='Downloaded';}catch(e){m.textContent=e.message;}};</script>'''
    script=script.replace('LABEL',html.escape(label)).replace('URL_OBJECT','window.URL').replace('URL,',json.dumps(url)+',').replace('TOKEN',json.dumps(cache['token']))
    if st.session_state.get('sn_dark'):
        script='<style>body{background:#06150F;color:#ECFDF5}#download{background:#081C13!important;color:#FFE07A!important;border-color:#34D399!important}#download:hover{background:#14442F!important}button:focus-visible{outline-color:#F4C430!important}</style>'+script
    components.html(script,height=48)
