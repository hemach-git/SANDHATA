"""Build the paired Markdown and Word FDE document set from one content source."""
from pathlib import Path
import re, json, zipfile, hashlib, argparse
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
WORD = ROOT / 'deliverables' / 'word'
ASSETS = DOCS / 'assets'
for p in (DOCS, WORD, ASSETS): p.mkdir(parents=True, exist_ok=True)

META = 'Version 0.2 | October 26 2026 | Prepared for Hema Chepuri | Design baseline'
STATUS = ('This document specifies the intended implementation. Application code, test results, '
          'live integrations, GitHub publication and production deployment are not established by this document. '
          'Dates are delivery targets in America/New_York, subject to the release gates.')
SOURCES = '''
## Verified source references

Access checked October 26 2026. Recheck access conditions before enabling a connector.

- Remotive API: https://github.com/remotive-com/remote-jobs-api
- Greenhouse Job Board API: https://docs.greenhouse.io/job-board.html
- Lever Postings API: https://github.com/lever/postings-api
- Ashby public postings: https://developers.ashbyhq.com/docs/public-job-posting-api
- LinkedIn automated activity policy: https://www.linkedin.com/help/linkedin/answer/a1340567/automated-activity-on-linkedin?lang=en
- Ladders terms: https://www.theladders.com/corporate/terms
- Indeed developer agreement: https://docs.indeed.com/legal-terms/developer-agreement
- LangGraph overview: https://docs.langchain.com/oss/python/langgraph/overview
- Streamlit container deployment: https://docs.streamlit.io/deploy/tutorials/docker
- MCP security: https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices
- Promptfoo assertions: https://www.promptfoo.dev/docs/configuration/expected-outputs/
- Langfuse self hosting: https://langfuse.com/self-hosting
'''

CONTENT = {p.stem: p.read_text(encoding='utf-8') for p in DOCS.glob('*.md')}

# Native code-generated diagrams keep the architecture editable and legible in Word.
FONT_DIR = Path('C:/Windows/Fonts')
def font(n=22, bold=False):
    for f in (('arialbd.ttf' if bold else 'arial.ttf'), 'segoeui.ttf'):
        if (FONT_DIR/f).exists(): return ImageFont.truetype(str(FONT_DIR/f), n)
    return ImageFont.load_default()

def wrap(draw, text, maxw, ft):
    out=[]
    for para in text.split('\n'):
        line=''
        for word in para.split():
            trial=(line+' '+word).strip()
            if draw.textlength(trial,font=ft)>maxw and line: out.append(line); line=word
            else: line=trial
        out.append(line)
    return out

def label(draw, xy, text, ft, fill='#123263', width=300, center=False):
    lines=wrap(draw,text,width,ft); y=xy[1]
    for line in lines:
        x=xy[0] - draw.textlength(line,font=ft)/2 if center else xy[0]
        draw.text((x,y),line,font=ft,fill=fill); y+=ft.size+7

def box(d, rect, title, body='', fill='#FFFFFF'):
    d.rounded_rectangle(rect, radius=14, fill=fill, outline='#F4C430',width=2)
    label(d,(rect[0]+18,rect[1]+16),title,font(24,True),width=rect[2]-rect[0]-36)
    if body: label(d,(rect[0]+18,rect[1]+57),body,font(20),width=rect[2]-rect[0]-36)

def arrow(d,a,b,caption=''):
    import math
    d.line([a,b],fill='#164B99',width=4)
    angle=math.atan2(b[1]-a[1],b[0]-a[0]); length=13
    pts=[b,(b[0]-length*math.cos(angle-.45),b[1]-length*math.sin(angle-.45)),(b[0]-length*math.cos(angle+.45),b[1]-length*math.sin(angle+.45))]
    d.polygon(pts,fill='#164B99')
    if caption: label(d,((a[0]+b[0])/2+8,(a[1]+b[1])/2-28),caption,font(17),width=220)

def canvas(title,w=1400,h=900):
    im=Image.new('RGB',(w,h),'white'); d=ImageDraw.Draw(im)
    label(d,(35,22),title,font(30,True),width=w-70)
    return im,d

def diagrams():
    im,d=canvas('SANDHĀTĀ application architecture',1400,850)
    box(d,(35,105,330,255),'User browsers','Search, resume, tracker, insights')
    box(d,(420,105,1000,255),'Authenticated Streamlit UI','OIDC sign-in, membership gate and protected views')
    arrow(d,(330,180),(420,180))
    box(d,(420,335,1000,480),'Domain services and coordinator','Principal checks, deterministic writes and scoring')
    arrow(d,(710,255),(710,335))
    box(d,(35,335,330,500),'Background worker','Persisted queue, leases and bounded model calls')
    arrow(d,(420,410),(330,410))
    box(d,(1070,105,1370,300),'Source adapters','Remotive, employer feeds and assisted import')
    arrow(d,(1000,365),(1070,265))
    box(d,(1070,365,1370,530),'Model adapter','Local or owner-selected hosted endpoint')
    arrow(d,(1000,420),(1070,420))
    box(d,(420,600,1000,775),'Protected data and evidence','PostgreSQL RLS and search, protected uploads, history and run records')
    arrow(d,(710,480),(710,600))
    box(d,(35,610,330,775),'Local MCP client','Principal-bound stdio tools through shared services')
    d.line([(330,690),(370,690),(370,450)],fill='#164B99',width=4)
    arrow(d,(370,450),(420,450))
    im.save(ASSETS/'architecture.png')

    im,d=canvas('User identity and protected data relationships',1400,800)
    nodes=[((40,100,390,240),'User','Stable OIDC issuer and subject'),((520,100,870,240),'Membership','Tenant, role, state and auth_version'),((1010,100,1360,240),'Tenant','Invited user household'),((40,355,390,500),'Protected Job','tenant_id and owner_user_id'),((520,355,870,500),'ResumeVersion','User-scoped original and evidence'),((1010,355,1360,500),'MatchAssessment','Owned job and resume versions'),((40,610,390,755),'Application','Owned job and submitted resume'),((520,610,870,755),'StatusEvent','Same-owner application history'),((1010,610,1360,755),'AdminAuditEvent','Safe metadata; append-only writes')]
    for rect,t,b in nodes: box(d,rect,t,b)
    for aa,bb in [((390,170),(520,170)),((870,170),(1010,170)),((695,240),(695,355)),((870,425),(1010,425)),((215,500),(215,610)),((390,680),(520,680)),((1185,240),(1185,355))]: arrow(d,aa,bb)
    d.line([(520,215),(455,215),(455,310),(215,310)],fill='#164B99',width=4)
    arrow(d,(215,310),(215,355))
    im.save(ASSETS/'data_model.png')

    seqs={
      'sequence_search':('Search and intake sequence',['Owner UI','Coordinator','Connector','Data store'],[(0,1,'Search profile and refresh'),(1,2,'Fetch allowed sources or cached results'),(2,1,'Candidates and per-source outcomes'),(1,3,'Validate, deduplicate and store versions'),(3,1,'Canonical jobs and evidence IDs'),(1,0,'Cards, freshness and assisted imports')]),
      'sequence_compare':('Resume comparison sequence',['Owner UI','Services','Worker and model','Data store'],[(0,1,'Choose job and resume versions'),(1,3,'Check versions and cache key'),(1,2,'Queue bounded comparison'),(2,3,'Retrieve scoped passages'),(2,1,'Validated judgments or failure'),(1,3,'Compute and persist assessment'),(1,0,'Score, coverage, gaps and citations')]),
      'sequence_tracker':('Tracker update and analytics sequence',['Owner UI','Tracker service','Data store','Analytics'],[(0,1,'Explicit status command and date'),(1,2,'Idempotent state and event transaction'),(2,1,'Committed revision'),(1,0,'Current status and history'),(0,3,'Request filtered metrics'),(3,2,'Query distinct applied cohort and events'),(3,0,'Charts, definitions and exclusions')])}
    for name,(title,actors,messages) in seqs.items():
        im,d=canvas(title,1400,220+len(messages)*88)
        xs=[170,520,870,1220]
        for x,a in zip(xs,actors):
            box(d,(x-145,90,x+145,165),a)
            d.line((x,165,x,im.height-25),fill='#F4C430',width=2)
        for i,(a,b,msg) in enumerate(messages):
            y=215+i*88
            d.rectangle((min(xs[a],xs[b])+5,y-31,max(xs[a],xs[b])-5,y-2),fill='white')
            label(d,((xs[a]+xs[b])/2,y-32),f'{i+1}  {msg}',font(19),width=abs(xs[a]-xs[b])-10,center=True)
            arrow(d,(xs[a],y+20),(xs[b],y+20))
        im.save(ASSETS/(name+'.png'))

    im,d=canvas('Protected single host deployment',1400,820)
    box(d,(40,120,390,270),'User browsers','Invited member HTTPS session')
    box(d,(520,120,970,270),'TLS and identity gate','TLS proxy and OIDC identity; app membership checks')
    arrow(d,(390,195),(520,195))
    d.rounded_rectangle((430,340,1370,780),radius=20,outline='#F4C430',width=3)
    label(d,(455,355),'Protected host and container network',font(25,True),width=850)
    box(d,(475,420,850,565),'Application','One Streamlit instance')
    box(d,(930,420,1325,565),'Worker and model adapter','One worker; protected model access')
    d.line([(745,270),(745,310),(410,310),(410,490)],fill='#164B99',width=4)
    arrow(d,(410,490),(475,490))
    box(d,(475,635,1325,745),'Persistent local volume','Protected PostgreSQL, user-scoped files and coordinated backups')
    arrow(d,(665,565),(665,635)); arrow(d,(1130,565),(1130,635))
    im.save(ASSETS/'deployment.png')

    im,d=canvas('SANDHĀTĀ Discover screen concept',1500,1000)
    d.rectangle((0,75,270,1000),fill='#FFFFFF',outline='#F4C430',width=3)
    label(d,(24,105),'SANDHĀTĀ',font(30,True),fill='#164B99',width=225)
    label(d,(24,152),'Career Intelligence',font(18),fill='#123263',width=225)
    for i,t in enumerate(['Discover','Resume Library','Tracker','Insights','Diagnostics']):
        y=245+i*80
        if i==0: d.rounded_rectangle((15,y-10,255,y+45),radius=8,fill='#FFF8DD',outline='#F4C430')
        label(d,(30,y),t,font(22),fill='#164B99',width=220)
    label(d,(310,110),'Discover your next opportunity',font(31,True),width=1100)
    box(d,(310,180,1450,265),'Search saved jobs','Role, company, skills or notes')
    box(d,(310,300,1450,400),'Source status','Remotive automatic | Premium portals assisted | Last refresh visible')
    label(d,(315,435),'Selected resume  AI Engineering v2',font(23,True),width=1100)
    for i,(t,c,s) in enumerate([('Senior AI Engineer','Example Company | US remote | Salary not disclosed','Python | RAG | Evaluation'),('Applied AI Architect','Example Labs | New York hybrid | USD 160k to 190k yearly','Architecture | Python | Cloud')]):
        y=490+i*220
        box(d,(310,y,1450,y+190),t,c)
        label(d,(330,y+100),s,font(21),width=1000)
        label(d,(330,y+145),'View details     Original posting     Compare resume     Save',font(20,True),fill='#164B99',width=1050)
    label(d,(310,955),'Design concept with synthetic jobs  |  No live results or measured scores shown',font(17),width=1100)
    im.save(ASSETS/'ui_discover.png')

    im,d=canvas('User access and administrator boundaries',1400,840)
    box(d,(35,115,360,260),'Invited member','Independent OIDC identity')
    box(d,(520,115,900,260),'Authentication and Principal','Active membership, role and auth_version')
    arrow(d,(360,185),(520,185))
    box(d,(1030,115,1370,285),'Protected workspace','Own resumes, jobs, matches and tracker')
    arrow(d,(900,185),(1030,185))
    box(d,(35,415,360,565),'Administrator','Active admin role rechecked server-side')
    box(d,(520,415,900,565),'Admin services','Users, quotas and bounded housekeeping')
    arrow(d,(360,490),(520,490))
    box(d,(1030,415,1370,590),'Safe operations data','Redacted health, usage and append-only audit')
    arrow(d,(900,490),(1030,490))
    arrow(d,(710,260),(710,415),'Authorize admin action')
    box(d,(300,685,1120,800),'PostgreSQL RLS and protected files','Scope enforced before queries, downloads, retrieval and worker steps')
    d.line([(1200,285),(1200,320),(1385,320),(1385,640),(950,640)],fill='#164B99',width=4)
    arrow(d,(950,640),(950,685))
    arrow(d,(710,565),(710,685))
    im.save(ASSETS/'access_model.png')

def hyperlink(p, text, target):
    part=p.part
    rid=part.relate_to(target,'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink',is_external=True)
    h=OxmlElement('w:hyperlink'); h.set(qn('r:id'),rid)
    r=OxmlElement('w:r'); pr=OxmlElement('w:rPr')
    color=OxmlElement('w:color'); color.set(qn('w:val'),'164B99'); pr.append(color)
    r.append(pr); t=OxmlElement('w:t'); t.text=text; r.append(t); h.append(r); p._p.append(h)

def inline(p,text):
    parts=re.split(r'(\[[^\]]+\]\([^)]+\)|\*\*.*?\*\*|`[^`]+`|https?://\S+)',text)
    for part in parts:
        if not part: continue
        m=re.fullmatch(r'\[([^\]]+)\]\(([^)]+)\)',part)
        if m:
            label_,target=m.groups()
            if target.startswith('../deliverables/word/'):
                target=target.rsplit('/',1)[-1]
            elif target.endswith('.md'): target='../../docs/'+target
            hyperlink(p,label_,target)
        elif part.startswith('http'): hyperlink(p,part,part)
        else:
            r=p.add_run(part[2:-2] if part.startswith('**') else part[1:-1] if part.startswith('`') else part)
            if part.startswith('**'): r.bold=True
            if part.startswith('`'): r.font.name='Consolas'; r.font.size=Pt(9)

def table(doc,rows):
    cols=len(rows[0]); t=doc.add_table(rows=0,cols=cols)
    t.alignment=WD_TABLE_ALIGNMENT.CENTER; t.autofit=False
    widths={2:[2.0,4.8],3:[1.55,2.65,2.6]}.get(cols,[6.8/cols]*cols)
    if rows[0]==['Document','Markdown source','Word version']:
        widths=[4.6,1.1,1.1]
    for col,width in zip(t.columns,widths): col.width=Inches(width)
    for i,row in enumerate(rows):
        cells=t.add_row().cells
        for j,cell in enumerate(cells):
            cell.width=Inches(widths[j]); cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            tcpr=cell._tc.get_or_add_tcPr()
            sh=OxmlElement('w:shd'); sh.set(qn('w:fill'),'164B99' if i==0 else 'FFFFFF' if i%2==0 else 'FFFFFF'); tcpr.append(sh)
            margins=OxmlElement('w:tcMar')
            for side,val in [('top','85'),('bottom','85'),('left','110'),('right','110')]:
                e=OxmlElement('w:'+side); e.set(qn('w:w'),val); e.set(qn('w:type'),'dxa'); margins.append(e)
            tcpr.append(margins)
            p=cell.paragraphs[0]; p.paragraph_format.space_after=Pt(2); p.paragraph_format.space_before=Pt(2)
            inline(p,row[j] if j<len(row) else '')
            for r in p.runs:
                r.font.size=Pt(9)
                if i==0: r.bold=True; r.font.color.rgb=RGBColor(255,255,255)
        trpr=t.rows[-1]._tr.get_or_add_trPr()
        if i==0: trpr.append(OxmlElement('w:tblHeader'))
        trpr.append(OxmlElement('w:cantSplit'))
    borders=OxmlElement('w:tblBorders')
    for side in ('top','left','bottom','right','insideH','insideV'):
        e=OxmlElement('w:'+side); e.set(qn('w:val'),'single'); e.set(qn('w:sz'),'4'); e.set(qn('w:color'),'F4C430'); borders.append(e)
    t._tbl.tblPr.append(borders)
    doc.add_paragraph().paragraph_format.space_after=Pt(2)

def word(name,md):
    doc=Document(); sec=doc.sections[0]
    sec.page_width=Inches(8.5); sec.page_height=Inches(11)
    sec.top_margin=sec.bottom_margin=Inches(.7); sec.left_margin=sec.right_margin=Inches(.8)
    styles=doc.styles
    for border in list(styles.element.iter(qn('w:pBdr'))):
        border.getparent().remove(border)
    for n in ('Normal','Title','Subtitle','Heading 1','Heading 2','Heading 3'):
        styles[n].font.name='Calibri'; styles[n].font.color.rgb=RGBColor(0,0,0)
    styles['Normal'].font.size=Pt(10.5)
    styles['Normal'].paragraph_format.space_after=Pt(7)
    styles['Normal'].paragraph_format.line_spacing=1.08
    styles['Title'].font.color.rgb=RGBColor.from_string('164B99'); styles['Title'].font.size=Pt(26); styles['Title'].font.bold=True
    styles['Title'].paragraph_format.space_after=Pt(12)
    for n,sz in [('Heading 1',15),('Heading 2',12),('Heading 3',11)]:
        styles[n].font.color.rgb=RGBColor.from_string('164B99'); styles[n].font.size=Pt(sz); styles[n].font.bold=True
        styles[n].paragraph_format.space_before=Pt(13); styles[n].paragraph_format.space_after=Pt(6)
    header=sec.header.paragraphs[0]; header.add_run('SANDHĀTĀ   |   FDE DELIVERY BASELINE').font.size=Pt(8)
    footer=sec.footer.paragraphs[0]; footer.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    footer.add_run('Design baseline 0.2   |   Page ').font.size=Pt(8)
    fld=OxmlElement('w:fldSimple'); fld.set(qn('w:instr'),'PAGE'); footer._p.append(fld)
    lines=md.splitlines(); i=0; code=False
    while i<len(lines):
        line=lines[i]
        if line.startswith('```'): code=not code; i+=1; continue
        if code:
            p=doc.add_paragraph(); p.paragraph_format.space_after=Pt(2)
            p.paragraph_format.line_spacing=1
            r=p.add_run(line); r.font.name='Consolas'; r.font.size=Pt(8)
            i+=1; continue
        if not line.strip(): i+=1; continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].startswith('|'):
                if not re.match(r'^\|\s*:?-',lines[i]): rows.append([s.strip() for s in lines[i].strip('|').split('|')])
                i+=1
            table(doc,rows); continue
        if line.startswith('!['):
            m=re.match(r'!\[([^\]]*)\]\(([^)]+)\)',line)
            if m:
                p=doc.add_paragraph(); p.paragraph_format.keep_with_next=True
                p.add_run().add_picture(str(DOCS/m.group(2)),width=Inches(6.75))
                c=doc.add_paragraph(m.group(1)); c.paragraph_format.space_after=Pt(10)
                for r in c.runs: r.italic=True; r.font.size=Pt(9)
            i+=1; continue
        if line.startswith('# '): doc.add_paragraph(line[2:],'Title')
        elif line.startswith('## '): doc.add_heading(line[3:],1)
        elif line.startswith('### '): doc.add_heading(line[4:],2)
        else:
            style='List Bullet' if line.startswith('- ') else 'List Paragraph' if re.match(r'^\d+\. ',line) else None
            text=line[2:] if style=='List Bullet' else line
            p=doc.add_paragraph(style=style); inline(p,text)
        i+=1
    doc.core_properties.title=md.splitlines()[0][2:]
    doc.core_properties.author='Prepared for Hema Chepuri'
    doc.core_properties.subject='SANDHĀTĀ Forward Deployed Engineering delivery baseline'
    doc.save(WORD/(name+'.docx'))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only',nargs='*',help='Rebuild Word only for matching document prefixes')
    args=parser.parse_args()
    diagrams()
    idx=['| Document | Markdown source | Word version |','| --- | --- | --- |']
    for name in sorted(CONTENT):
        if name.startswith('00'): continue
        title=CONTENT[name].splitlines()[0][2:]
        idx.append(f'| {title} | [Markdown]({name}.md) | [Word](../deliverables/word/{name}.docx) |')
    CONTENT['00_Document_Index']=re.sub(r'(## Documents\n\n).*?(\n## Format and change discipline)', lambda m: m.group(1)+'\n'.join(idx)+'\n'+m.group(2), CONTENT['00_Document_Index'], flags=re.S)
    manifest=[]
    for name,md in sorted(CONTENT.items()):
        p=DOCS/(name+'.md')
        if p.exists() and not name.startswith('00'):
            md=p.read_text(encoding='utf-8')
        p.write_text(md,encoding='utf-8')
        if not args.only or any(name.startswith(prefix) for prefix in args.only): word(name,md)
        manifest.append({'name':name,'markdown':str(p.relative_to(ROOT)).replace('\\','/'),'word':f'deliverables/word/{name}.docx','source_sha256':hashlib.sha256(md.encode()).hexdigest(),'words':len(md.split())})
    (ROOT/'deliverables'/'manifest.json').write_text(json.dumps({'version':'0.2','date':'2026-10-26','documents':manifest,'application_status':'local_pilot_experimental_ai','qa_status':'pending_render'},indent=2),encoding='utf-8')
    print(json.dumps({'documents':len(manifest),'words':sum(m['words'] for m in manifest),'word_directory':str(WORD)},ensure_ascii=True))

if __name__=='__main__': main()
