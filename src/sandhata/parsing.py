from io import BytesIO
from zipfile import ZipFile,BadZipFile
from bs4 import BeautifulSoup
from pypdf import PdfReader
from docx import Document
import hashlib,re
from .config import AppError

def plain_html(raw):
    soup=BeautifulSoup(raw,'html.parser')
    for e in soup(['script','style','iframe','object']): e.decompose()
    return soup.get_text('\n',strip=True)

def parse_resume(data:bytes,filename:str):
    if not data or len(data)>10*1024*1024: raise AppError('Upload a nonempty PDF or DOCX of at most 10 MB.')
    try:
        if filename.lower().endswith('.pdf') and data.startswith(b'%PDF'):
            r=PdfReader(BytesIO(data))
            if r.is_encrypted or len(r.pages)>50: raise AppError('Encrypted PDFs and documents over 50 pages are not supported.')
            text='\n\n'.join(p.extract_text() or '' for p in r.pages); ext='pdf'; parser='pypdf-v1'
        elif filename.lower().endswith('.docx') and data.startswith(b'PK'):
            with ZipFile(BytesIO(data)) as z:
                if sum(i.file_size for i in z.infolist())>30*1024*1024 or '[Content_Types].xml' not in z.namelist(): raise AppError('DOCX archive exceeds the safe extraction limit.')
            doc=Document(BytesIO(data))
            text='\n'.join([p.text for p in doc.paragraphs]+[' | '.join(c.text for c in row.cells) for table in doc.tables for row in table.rows]); ext='docx'; parser='python-docx-v1'
        else: raise AppError('The file type does not match a supported PDF or DOCX.')
    except AppError: raise
    except Exception as exc: raise AppError('This document could not be parsed. Try an unencrypted text PDF or DOCX.') from exc
    text=text.replace('\x00','').strip()
    if len(text)<80: raise AppError('Not enough text was extracted. Scanned documents need OCR before upload.')
    return dict(body=text,ext=ext,parser_version=parser,file_hash=hashlib.sha256(data).hexdigest())

def passages(text,size=1800,overlap=150):
    start=0
    while start<len(text):
        end=min(start+size,len(text))
        if end<len(text):
            boundary=text.rfind('\n',start+size//2,end)
            if boundary>start: end=boundary
        yield start,text[start:end]
        if end==len(text): break
        start=max(start+1,end-overlap)

def salary_yearly(text):
    """Only compare explicit USD annual ranges; unknown stays unknown."""
    t=text.lower().replace(',','')
    if not ('$' in t or 'usd' in t) or not any(x in t for x in ['year','annual','/yr','per annum']): return None
    values=[]
    for num,k in re.findall(r'(\d+(?:\.\d+)?)\s*(k?)',t):
        n=float(num)*(1000 if k else 1)
        if n>=1000: values.append(n)
    return (min(values),max(values)) if values else None
