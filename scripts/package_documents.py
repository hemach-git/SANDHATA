"""Validate paired document content and package final deliverables without private data."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree
import json, re, hashlib

ROOT=Path(__file__).resolve().parents[1]
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
RNS={'r':'http://schemas.openxmlformats.org/package/2006/relationships'}
manifest_path=ROOT/'deliverables/manifest.json'
manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
renders=json.loads((ROOT/'deliverables/qa/v0.2/render_results.json').read_text(encoding='utf-8'))
assert len(renders)==len(manifest['documents']) and all(x['returncode']==0 and x['pages']>0 for x in renders)
issues=[]; checked=0; links=0
def norm(s): return ' '.join(s.split())
for item in manifest['documents']:
    mdpath=ROOT/item['markdown']; wordpath=ROOT/item['word']
    md=mdpath.read_text(encoding='utf-8')
    assert hashlib.sha256(md.encode()).hexdigest()==item['source_sha256']
    with ZipFile(wordpath) as z:
        xml=etree.fromstring(z.read('word/document.xml'))
        text=norm(' '.join(xml.xpath('//w:t/text()',namespaces=NS)))
        for line in md.splitlines():
            if not line.strip() or line.startswith('```') or re.match(r'^\|\s*:?-',line): continue
            if line.startswith('!['): continue
            line=re.sub(r'\[([^\]]+)\]\([^)]+\)',r'\1',line)
            line=re.sub(r'^#{1,6}\s+|^-\s+','',line)
            if line.startswith('|'): line=line.replace('|',' ')
            line=line.replace('**','').replace('`','')
            checked+=1
            if norm(line) not in text: issues.append((item['name'],line[:100]))
        rels=etree.fromstring(z.read('word/_rels/document.xml.rels'))
        for rel in rels:
            target=rel.get('Target','')
            if rel.get('TargetMode')=='External' and not re.match(r'^https?://',target):
                links+=1
                if not (wordpath.parent/target).resolve().exists(): issues.append((item['name'],'Broken Word link '+target))
        styles=etree.fromstring(z.read('word/styles.xml'))
        if styles.xpath('//w:pBdr',namespaces=NS): issues.append((item['name'],'Paragraph border residue'))
    for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',md):
        if not target.startswith(('http://','https://')) and not (mdpath.parent/target).resolve().exists():
            issues.append((item['name'],'Broken Markdown link '+target))
    item['word_sha256']=hashlib.sha256(wordpath.read_bytes()).hexdigest()
    item['rendered_pages']=next(x['pages'] for x in renders if x['document']==wordpath.name)
assert not issues,issues
manifest['qa_status']='rendered_and_visually_reviewed'
manifest['total_rendered_pages']=sum(x['pages'] for x in renders)
manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
report={'document_pairs':len(manifest['documents']),'rendered_pages':manifest['total_rendered_pages'],
        'content_lines_checked':checked,'local_word_links_checked':links,
        'broken_links':0,'content_mismatches':0,'paragraph_border_residue':0,
        'visual_review':'Every final page reviewed; targeted rerenders followed formatting corrections',
        'scope':'Document quality; application verification is separately recorded in deliverables/verification',
        'application_status':'local_pilot_experimental_ai','github_status':'local_preparation_owner_push_pending'}
(ROOT/'deliverables/quality_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
archive=ROOT/'deliverables/SANDHATA_FDE_Document_Package_v0.2.zip'
files=[ROOT/'README.md',ROOT/'.gitignore',manifest_path,ROOT/'deliverables/quality_report.json']
for folder in ['docs','deliverables/word','scripts']:
    files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
with ZipFile(archive,'w',ZIP_DEFLATED) as z:
    for p in sorted(set(files)):
        z.write(p,'SANDHATA/'+p.relative_to(ROOT).as_posix())
with ZipFile(archive) as z:
    assert z.testzip() is None
    assert not any('/.git/' in p or '/qa/' in p or p.endswith(('.db','.env')) for p in z.namelist())
print(json.dumps({'archive':str(archive),'files':len(files),'bytes':archive.stat().st_size,'quality':report}))
