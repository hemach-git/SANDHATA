"""Insights: cohort metrics, charts and outcome tables with their own data palette."""
from datetime import date,timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import plotly.express as px
import streamlit as st
from .config import AppError
from . import repository as repo
from .presentation import compact_chart
from .ui_common import md,private_download

# Neutral surfaces let the data colours stand out. Each status keeps one colour on every chart.
PALETTES=dict(
    light=dict(surface='#FFFFFF',ink='#1E293B',grid='#E2E8F0',on_data='#FFFFFF',weekly='#4F46E5',gap='#E11D48',
        status=dict(Saved='#64748B',Preparing='#0284C7',Applied='#4F46E5',Screening='#9333EA',Interviewing='#B45309',
            Offer='#0F766E',Hired='#15803D',Rejected='#E11D48',Withdrawn='#C2410C',Cancelled='#334155')),
    dark=dict(surface='#111827',ink='#E5E7EB',grid='#334155',on_data='#0B1120',weekly='#818CF8',gap='#FB7185',
        status=dict(Saved='#94A3B8',Preparing='#38BDF8',Applied='#818CF8',Screening='#C084FC',Interviewing='#FBBF24',
            Offer='#2DD4BF',Hired='#4ADE80',Rejected='#FB7185',Withdrawn='#FB923C',Cancelled='#CBD5E1')),
)
LABEL_LENGTH=46

def palette(): return PALETTES['dark' if st.session_state.get('sn_dark') else 'light']

def styled(figure,colors,rows=None):
    figure=compact_chart(figure,rows=rows)
    ink=colors['ink']
    figure.update_layout(paper_bgcolor=colors['surface'],plot_bgcolor=colors['surface'],font_color=ink,title_font_color=ink,
        hoverlabel=dict(bgcolor=colors['surface'],bordercolor=colors['grid'],font_color=ink),
        modebar=dict(bgcolor=colors['surface'],color=ink,activecolor=colors['weekly']))
    figure.update_xaxes(gridcolor=colors['grid'],zerolinecolor=colors['grid'],automargin=True)
    figure.update_yaxes(gridcolor=colors['grid'],zerolinecolor=colors['grid'],automargin=True)
    return figure

def whole_numbers(update,highest):
    """Counts are integers; step by one only while that stays readable."""
    update(tickformat='d',rangemode='tozero',dtick=1 if highest<=10 else None)

def pipeline_chart(current,colors):
    frame=pd.DataFrame(current)
    figure=px.pie(frame,names='status',values='n',hole=.62,title='Current pipeline · all saved applications',
        color='status',color_discrete_map=colors['status'],category_orders=dict(status=repo.STATUSES))
    figure.update_traces(textinfo='value',textposition='inside',insidetextorientation='horizontal',sort=False,
        textfont=dict(color=colors['on_data'],size=13),marker=dict(line=dict(color=colors['surface'],width=3)),
        hovertemplate='%{label}: %{value} (%{percent})<extra></extra>')
    figure.add_annotation(text=f"<b>{frame['n'].sum()}</b><br>saved",showarrow=False,x=.5,y=.5,font=dict(size=15,color=colors['ink']))
    figure=styled(figure,colors)
    figure.update_layout(height=290,legend=dict(orientation='v',x=1,y=.5,yanchor='middle',title_text=''))
    return figure

def weekly_chart(weekly,colors):
    frame=pd.DataFrame(weekly)
    frame['week']=pd.to_datetime(frame['week']).dt.strftime('%b %d, %Y')
    figure=px.bar(frame,x='week',y='applications',text='applications',title='Weekly applications')
    figure.update_traces(marker_color=colors['weekly'],textposition='outside',cliponaxis=False,hovertemplate='Week of %{x}: %{y}<extra></extra>')
    figure=styled(figure,colors)
    figure.update_layout(height=290,bargap=.45)
    figure.update_xaxes(title_text='Week starting',type='category')
    figure.update_yaxes(title_text='')
    whole_numbers(figure.update_yaxes,frame['applications'].max())
    return figure

def progression_chart(applied,interview,offer,colors):
    frame=pd.DataFrame({'Stage':['Applied','Interview','Offer'],'Applications':[applied,interview,offer]})
    figure=px.bar(frame,x='Applications',y='Stage',orientation='h',text='Applications',title='Observed cohort progression')
    figure.update_traces(marker_color=[colors['status'][s] for s in ('Applied','Interviewing','Offer')],textposition='outside',
        hovertemplate='%{y}: %{x}<extra></extra>')
    figure=styled(figure,colors,rows=3)
    figure.update_yaxes(autorange='reversed',title_text='')
    figure.update_xaxes(title_text='Applications')
    whole_numbers(figure.update_xaxes,applied)
    return figure

def gap_labels(texts):
    """Short, unique axis labels. Angle brackets are escaped because Plotly reads markup in text."""
    safe=lambda value:value.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
    labels=[]
    for number,text in enumerate(texts,1):
        flat=' '.join(text.split())
        short=flat if len(flat)<=LABEL_LENGTH else flat[:LABEL_LENGTH-1]+'…'
        label=safe(short)
        labels.append(f'{label} ({number})' if label in labels else label)
    return labels,[safe(' '.join(t.split())) for t in texts]

def gap_chart(gaps,colors):
    labels,full=gap_labels([text for text,_ in gaps])
    counts=[count for _,count in gaps]
    figure=px.bar(x=counts,y=labels,orientation='h',text=counts,title='Frequently not evidenced requirements')
    figure.update_traces(marker_color=colors['gap'],textposition='outside',customdata=full,hovertemplate='%{customdata}<br>Roles: %{x}<extra></extra>')
    figure=styled(figure,colors,rows=len(gaps))
    figure.update_yaxes(autorange='reversed',title_text='')
    figure.update_xaxes(title_text='Roles asking')
    whole_numbers(figure.update_xaxes,max(counts))
    return figure

def show(column,figure): column.plotly_chart(figure,use_container_width=True,theme=None)

def table(column,frame):
    """A static table follows the page palette; every text cell is shown literally."""
    shown=frame.copy()
    for name in shown.columns:
        if not pd.api.types.is_numeric_dtype(shown[name]): shown[name]=shown[name].map(lambda v:md(v) if pd.notna(v) else '')
    shown.columns=[c.replace('_',' ').capitalize() for c in shown.columns]
    column.table(shown.set_index(shown.columns[0]))

def kpi(column,key,label,value):
    column.container(key='sn_kpi_'+key).metric(label,value)

def insights(p):
    st.header('Your search insights')
    with st.container(key='sn_insights'):
        a,b=st.columns(2)
        start=a.date_input('Applied cohort from',date.today()-timedelta(days=90));end=b.date_input('Through',date.today())
        if end<start: raise AppError('The end date must be on or after the start date.')
        metrics=repo.tracker_metrics(p,start,end);cohort=metrics['cohort'];n=len(cohort)
        interview=sum(bool(x['interview']) for x in cohort);offer=sum(bool(x['offer']) for x in cohort)
        a,b,c=st.columns(3)
        kpi(a,'applied','Applications in cohort',n);kpi(b,'interview','Reached interview',f'{interview}/{n}');kpi(c,'offer','Recorded offer',f'{offer}/{n}')
        st.caption(f'Applied-date cohort in {p.timezone}. Later recorded events are observed through now. Small samples do not establish which resume or source causes better outcomes.')
        if n<10: st.info('Small sample: fewer than ten applications in this cohort.')
        colors=palette()
        a,b=st.columns(2)
        if metrics['current']: show(a,pipeline_chart(metrics['current'],colors))
        if metrics['weekly']: show(b,weekly_chart(metrics['weekly'],colors))
        progression_col,gap_col=st.columns(2) if n and metrics['gaps'] else (st.container(),st.container())
        if n: show(progression_col,progression_chart(n,interview,offer,colors))
        if metrics['gaps']: show(gap_col,gap_chart(metrics['gaps'],colors))
        if n:
            frame=pd.DataFrame(cohort)
            with st.expander('Application report details'):
                details=frame[['title','company','location','work_arrangement','salary_description','job_type','recruiter','applied_at']].copy()
                details['applied_at']=details['applied_at'].map(lambda v:f'{v.astimezone(ZoneInfo(p.timezone)):%b %d, %Y}' if pd.notna(v) else '')
                with st.container(height=min(360,90+45*len(details)),border=False): table(st,details)
            st.subheader('Source and resume outcomes')
            a,b=st.columns(2)
            table(a,frame.groupby('source').agg(applications=('id','count'),interviews=('interview','sum'),offers=('offer','sum')).reset_index())
            frame['resume_label']=frame['resume_label'].fillna('Not recorded')
            table(b,frame.groupby('resume_label').agg(applications=('id','count'),interviews=('interview','sum'),offers=('offer','sum')).reset_index())
            private_download(p,'Export applied cohort','cohort',params=f'?start={start.isoformat()}&end={end.isoformat()}')
        if not n and not metrics['current']: st.info('Your charts will populate from saved jobs and recorded application events.')
