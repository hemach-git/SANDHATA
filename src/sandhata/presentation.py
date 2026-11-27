"""SANDHĀTĀ visual identity and application-authored presentation copy."""
import html
from pathlib import Path
import re
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
import streamlit.components.v1 as components

BRAND='SANDHĀTĀ'
EMERALD='#047857'
INK='#064E3B'
GOLD='#F4C430'
BORDER='#059669'
EXPANSION=('Search','Analyze','Navigate','Discover','Highlight','Apply','Track','Advance')
WHITE='#FFFFFF'
ASSETS=Path(__file__).parent/'assets'
FEATURES=(
    ('search','Watch target companies','Scan your chosen employer boards and spot new roles.'),
    ('source','Bring your sources together','Save complete postings from your premium searches.'),
    ('document','Choose your resume','Keep versions organized and inspect the extracted text.'),
    ('target','Compare with evidence','See alignment, gaps and the quotations behind each result.'),
    ('chart','Act on today','See follow-ups due, quiet applications and new matches.'),
    ('trend','Understand your progress','Explore trends, source outcomes and recurring skill gaps.'),
)
CAPABILITIES=(
    ('search','Job discovery','Your companies and searches, in one list.','Build a company watchlist and filter new roles.'),
    ('document','Resume library','The right resume for each opportunity.','Upload, label and select a version.'),
    ('target','Evidence-based fit','Understand the match behind the number.','Review supported skills and evidence gaps.'),
    ('check','Daily actions and tracker','Keep your next action in sight.','Review what is due today and update each application.'),
    ('chart','Career insights','Turn activity into useful perspective.','Explore your pipeline and application trends.'),
    ('source','Evidence search','Return to the details that matter.','Find saved passages with source references.'),
)
PATHS={
    'search':'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    'source':'<path d="M5 3h10l4 4v14H5Z"/><path d="M14 3v5h5M8 12h8M8 16h6"/>',
    'document':'<path d="M5 3h14v18H5Z M8 7h8M8 11h8M8 15h5"/>',
    'target':'<circle cx="11" cy="13" r="8"/><circle cx="11" cy="13" r="4"/><path d="m11 13 10-10M16 3h5v5"/>',
    'chart':'<path d="M3 3v18h18M7 17v-5M12 17V7M17 17V4"/>',
    'trend':'<path d="m3 17 6-6 4 3 8-10M16 4h5v5"/>',
    'check':'<rect x="4" y="3" width="16" height="18" rx="2"/><path d="m8 11 3 3 6-7M8 18h8"/>',
}

def icon(name):
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+PATHS[name]+'</svg>'

def mark():
    return '<svg class="sn-mark" viewBox="0 0 48 48" aria-hidden="true"><circle cx="24" cy="24" r="20" fill="#FFFFFF" stroke="#F4C430" stroke-width="2"/><path d="m31 13-4 16-13 6 6-14Z" fill="#047857"/><path d="m31 13-4 16-7-8Z" fill="#F4C430"/><circle cx="24" cy="25" r="2" fill="#FFFFFF"/></svg>'

def hero_markup():
    words=EXPANSION
    expansion=''.join('<div>'+'<i aria-hidden="true"> · </i>'.join('<span><b>'+w[0]+'</b>'+w[1:]+'</span>' for w in words[i:i+4])+'</div>' for i in (0,4))
    features=''.join('<div class="sn-feature">'+icon(kind)+'<strong>'+title+'</strong><span>'+description+'</span></div>' for kind,title,description in FEATURES)
    return '<section class="sn-intro" aria-label="SANDHĀTĀ introduction"><div class="sn-brand">'+mark()+'<h1>SANDHĀTĀ</h1><span class="sn-descriptor">Career Intelligence</span></div><p class="sn-tagline">Find your direction. Advance with confidence.</p><div class="sn-expansion" aria-label="The meaning of SANDHĀTĀ">'+expansion+'</div><p class="sn-summary">Discover opportunities, compare your strengths, and bring every next step into focus.</p></section><section class="sn-features" aria-label="Career intelligence features"><h2>Built for your next chapter</h2>'+features+'</section>'

def capabilities_markup():
    cards=''.join('<article class="sn-capability">'+icon(kind)+'<div><h3>'+title+'</h3><p>'+summary+'</p><p class="sn-example">'+example+'</p></div></article>' for kind,title,summary,example in CAPABILITIES)
    return '<section class="sn-capabilities" aria-label="Workspace capabilities"><h2>One workspace. Every next step.</h2><p class="sn-section-summary">From the first search to your next opportunity.</p><div class="sn-card-grid">'+cards+'</div></section><footer class="sn-footer"><span>Evidence-led career decisions. Your next move stays yours.</span><span>SANDHĀTĀ · Career Intelligence</span></footer>'

def chart_height(rows, minimum=170, maximum=350):
    return min(maximum,max(minimum,78+28*rows))

def compact_chart(figure, rows=None):
    palette=pio.templates['SANDHATA'].layout
    figure.update_layout(paper_bgcolor=palette.paper_bgcolor,plot_bgcolor=palette.plot_bgcolor)
    figure.update_layout(height=chart_height(rows) if rows is not None else 245,
        margin=dict(l=12,r=18,t=42,b=44),bargap=.38,
        title=dict(font=dict(size=15)),font=dict(size=12,weight=650,color=palette.font.color),
        legend=dict(orientation='h',y=-.12),autosize=True)
    figure.update_xaxes(automargin=True,title_standoff=6)
    figure.update_yaxes(title_standoff=6)
    if rows is not None:
        figure.update_yaxes(automargin=True,tickfont=dict(size=12))
        figure.update_xaxes(dtick=1,tickformat='d')
        figure.update_traces(cliponaxis=False)
    return figure

def configure_visuals():
    if 'sn_dark' not in st.session_state:
        st.session_state.sn_dark=st.context.cookies.get('SANDHATA_THEME','light')=='dark'
    st.sidebar.toggle('Dark mode',key='sn_dark',help='Remember this appearance on this browser.')
    dark=st.session_state.sn_dark
    mode='dark' if dark else 'light'
    components.html('<script>document.cookie="SANDHATA_THEME='+mode+'; Path=/; Max-Age=31536000; SameSite=Lax";</script>',height=0)
    st.html('<span class="sn-theme-'+mode+'"></span><style>'+(ASSETS/'theme.css').read_text(encoding='utf-8')+'</style>')
    surface='#06150F' if dark else WHITE
    text='#ECFDF5' if dark else '#0B2A1F'
    title='#FFE07A' if dark else INK
    accent='#6EE7B7' if dark else EMERALD
    grid='#1E4A36' if dark else '#D7EFE3'
    pio.templates['SANDHATA']=go.layout.Template(layout=dict(
        colorway=['#34D399' if dark else EMERALD,GOLD,'#6EE7B7' if dark else '#34D399','#A7F3D0' if dark else '#065F46','#FDBA74' if dark else '#B45309','#FFE07A' if dark else '#A7F3D0'],
        paper_bgcolor=surface,plot_bgcolor=surface,font=dict(family='Arial, sans-serif',color=text),
        title=dict(font=dict(color=title,size=15)),
        xaxis=dict(gridcolor=grid,zerolinecolor=grid),
        yaxis=dict(gridcolor=grid,zerolinecolor=grid),
        hoverlabel=dict(bgcolor=surface,bordercolor='#34D399' if dark else BORDER,font_color=text),
        modebar=dict(bgcolor=surface,color=accent,activecolor=GOLD)))
    pio.templates.default='SANDHATA'

def landing(auth_ready):
    with st.container(key='sn_landing'):
        st.markdown('<span class="sn-landing-marker" aria-hidden="true"></span>',unsafe_allow_html=True)
        intro,account=st.columns([1.7,1],gap='large')
        with intro: st.markdown(hero_markup(),unsafe_allow_html=True)
        with account:
            with st.container(key='sn_account',border=True):
                st.markdown('<div class="sn-account-eyebrow">YOUR NEXT CHAPTER</div>',unsafe_allow_html=True)
                st.subheader('Your career workspace')
                st.write('Bring your opportunities, resume evidence and application progress together.')
                st.markdown('<div class="sn-account-rule"></div>',unsafe_allow_html=True)
                st.caption('SIGN IN TO CONTINUE')
                if not auth_ready: st.warning('Configure your identity provider to enable sign-in.')
                st.button('Sign in to your workspace',on_click=st.login,args=('keycloak',),type='primary',disabled=not auth_ready,use_container_width=True)
                st.caption('Use your own account. New users need an administrator invitation.')
                st.markdown('<div class="sn-account-note">Your goals. Your strengths. Your next opportunity.</div>',unsafe_allow_html=True)
        st.markdown(capabilities_markup(),unsafe_allow_html=True)

def display_name(value):
    # Only application-owned sample names are normalized; source evidence stays literal.
    return 'Administrator' if value in ('Family Administrator','Family Administrator Family','Administrator Family') else str(value)

def workspace_brand():
    return '<div class="sn-workspace-brand">'+mark()+'<div><strong>SANDHĀTĀ</strong><span>CAREER INTELLIGENCE</span></div></div><div class="sn-workspace-tagline">'+' · '.join('<span><b>'+w[0]+'</b>'+w[1:]+'</span>' for w in EXPANSION)+'</div>'
