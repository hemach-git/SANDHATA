from pathlib import Path
import re
import plotly.io as pio
from streamlit.testing.v1 import AppTest
from sandhata.presentation import hero_markup,capabilities_markup,BLUE,TURMERIC,WHITE

ROOT=Path(__file__).resolve().parents[1]

def test_landing_uses_reference_structure_and_neutral_uppercase_brand():
    markup=hero_markup()+capabilities_markup()
    assert '<h1>SANDHĀTĀ</h1>' in markup
    assert markup.count('class="sn-feature"')==6
    assert markup.count('class="sn-capability"')==6
    assert not re.search(r'\b(private|family)\b',markup,re.I)
    for word in ('Search','Analyze','Navigate','Discover','Highlight','Apply','Track','Advance'):
        assert '<b>'+word[0]+'</b>'+word[1:] in markup

def test_signed_out_page_renders_and_keeps_the_authentication_gate():
    app=AppTest.from_file(ROOT/'app.py').run(timeout=15)
    assert not app.exception
    assert not any(b.label=='Sign in to your workspace' for b in app.button)
    assert any('Loading SANDHĀTĀ sign-in' in c.value for c in app.caption)
    assert not app.file_uploader
    visible=' '.join(m.value for m in app.markdown)
    assert not re.search(r'\b(private|family)\b',visible,re.I)
    assert 'Shared light and dark appearance' not in visible
    template=(ROOT/'deploy/keycloak/themes/sandhata/login/login.ftl').read_text(encoding='utf-8')
    shell=(ROOT/'deploy/keycloak/themes/sandhata/login/sandhata-layout.ftl').read_text(encoding='utf-8')
    assert 'action="${url.loginAction}" method="post"' in template
    assert 'autocomplete="current-password"' in template
    assert 'messagesPerField' in template and 'kcSanitize' in template
    assert hero_markup() in shell and capabilities_markup() in shell
    assert '${url.loginRestartFlowUrl}' in shell
    assert '<iframe' not in shell and 'fetch(' not in template
    layout=pio.templates['SANDHATA'].layout
    assert layout.paper_bgcolor==WHITE and layout.plot_bgcolor==WHITE
    assert list(layout.colorway)[:2]==[BLUE,TURMERIC]

def test_theme_keeps_requested_palette_and_mobile_layout():
    css=(ROOT/'src/sandhata/assets/theme.css').read_text(encoding='utf-8')
    assert all(color in css for color in (BLUE,TURMERIC,WHITE))
    assert '@media(max-width:850px)' in css and '@media(max-width:520px)' in css
    assert '.sn-feature span{font-weight:700}' in css
    assert '.sn-capability{background:var(--sn-sandal)' in css
    assert '--sn-sandal:#F8E8B4' in css and 'border-top:5px solid var(--sn-sandal)' in css
    assert 'focus-visible' in css and 'prefers-reduced-motion' in css


def test_dark_appearance_updates_charts_and_keeps_chart_rows_readable():
    from sandhata.presentation import compact_chart,chart_height
    import plotly.express as px
    app=AppTest.from_file(ROOT/'app.py').run(timeout=15)
    app.toggle[0].set_value(True).run()
    assert not app.exception
    assert pio.templates['SANDHATA'].layout.paper_bgcolor=='#152238'
    assert pio.templates['SANDHATA'].layout.font.color=='#EEF3FC'
    figure=compact_chart(px.bar(x=[1,2],y=['Short','Long requirement label'],orientation='h'),rows=2)
    assert figure.layout.paper_bgcolor=='#152238'
    assert figure.layout.plot_bgcolor=='#152238'
    assert figure.layout.height==170
    assert chart_height(10)==350 and chart_height(1)==170
    assert figure.layout.yaxis.automargin
    app.toggle[0].set_value(False).run()
    assert pio.templates['SANDHATA'].layout.paper_bgcolor==WHITE
