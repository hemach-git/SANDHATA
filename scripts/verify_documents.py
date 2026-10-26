"""Render every Word file and create internal contact sheets for review."""
from pathlib import Path
import os, sys, subprocess, json, argparse
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
QA=ROOT/'deliverables'/'qa'/'v0.2'
QA.mkdir(parents=True,exist_ok=True)
RENDER=Path('C:/Users/Chepuri/.codex/plugins/cache/openai-primary-runtime/documents/26.1025.11240/skills/documents/render_docx.py')
env=os.environ.copy()
env['PATH']='C:/Program Files/LibreOffice/program;'+env['PATH']
tmp=QA/'tmp'
tmp.mkdir(exist_ok=True)
env['TEMP']=env['TMP']=str(tmp)

def render(p):
    target=QA/p.stem
    if target.exists():
        for old in list(target.glob('page-*.png'))+list(target.glob('*.pdf')):
            old.unlink()
    result=subprocess.run([sys.executable,str(RENDER),str(p),'--output_dir',str(target),'--width','1200','--emit_pdf'],env=env,capture_output=True,text=True)
    (QA/(p.stem+'.log')).write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
    pages=sorted(target.glob('page-*.png'),key=lambda x:int(x.stem.split('-')[-1]))
    print(p.stem,result.returncode,len(pages),flush=True)
    return {'document':p.name,'returncode':result.returncode,'pages':len(pages),'paths':[str(x.relative_to(ROOT)) for x in pages]}

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--only',nargs='*',help='Render only matching filename prefixes')
args=parser.parse_args()
files=sorted((ROOT/'deliverables'/'word').glob('*.docx'))
if args.only:
    files=[p for p in files if any(p.stem.startswith(prefix) for prefix in args.only)]
with ThreadPoolExecutor(max_workers=4) as pool:
    results=list(pool.map(render,files))
if args.only and (QA/'render_results.json').exists():
    old=json.loads((QA/'render_results.json').read_text(encoding='utf-8'))
    merged={r['document']:r for r in old}
    merged.update({r['document']:r for r in results})
    results=[merged[k] for k in sorted(merged)]
(QA/'render_results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
allpages=[(r['document'],ROOT/p) for r in results for p in r['paths']]
for start in range(0,len(allpages),6):
    group=allpages[start:start+6]
    thumbw=600; thumbh=790
    sheet=Image.new('RGB',(3*thumbw,2*(thumbh+35)),'#D5DDE2'); d=ImageDraw.Draw(sheet)
    for j,(name,p) in enumerate(group):
        im=Image.open(p); im.thumbnail((thumbw-12,thumbh))
        x=(j%3)*thumbw; y=(j//3)*(thumbh+35)
        d.text((x+8,y+7),name[:35]+' / '+p.stem,fill='black')
        sheet.paste(im,(x+6,y+30))
    sheet.save(QA/f'contact-{start//6+1:02}.png')
print(json.dumps({'documents':len(results),'pages':len(allpages),'failed':sum(r['returncode']!=0 for r in results)}))
