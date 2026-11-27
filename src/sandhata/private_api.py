"""Authenticated private downloads; no resume or export bytes enter Streamlit's public media cache."""
import os,sys
from datetime import date
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import Response,JSONResponse
from starlette.middleware.cors import CORSMiddleware
from .config import AppError
from .identity import capability_principal,audit_events
from .repository import resume_download,admin_download,list_jobs,list_applications,tracker_metrics

def csv_bytes(records):
    import pandas as pd
    frame=pd.DataFrame(records)
    for col in frame.select_dtypes(include='object'):
        frame[col]=frame[col].map(lambda v:"'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v)
    return frame.to_csv(index=False).encode('utf-8-sig')

async def health(request): return JSONResponse({'service':'SANDHATA-downloads','status':'ready'})

async def download(request):
    header=request.headers.get('authorization','')
    if not header.startswith('Bearer '): return JSONResponse({'error':'Authentication required'},status_code=401)
    try:
        p=capability_principal(header[7:])
        kind=request.path_params['kind'];identifier=request.path_params.get('identifier','')
        if kind=='resume':
            data,ext=resume_download(p,identifier); filename='SANDHATA_DOCUMENT'+ext;media='application/octet-stream'
        elif kind=='admin-document':
            # The service verifies the administrator role and records the reason before releasing bytes.
            data,ext=admin_download(p,identifier,request.query_params['reason']); filename='SANDHATA_DOCUMENT'+ext;media='application/octet-stream'
        elif kind=='jobs':
            data=csv_bytes([{k:v for k,v in j.items() if k not in ('body','raw_html')} for j in list_jobs(p)])
            filename='SANDHATA_JOBS.csv';media='text/csv'
        elif kind=='tracker': data=csv_bytes(list_applications(p));filename='SANDHATA_APPLICATIONS.csv';media='text/csv'
        elif kind=='audit': data=csv_bytes(audit_events(p));filename='SANDHATA_AUDIT.csv';media='text/csv'
        elif kind=='cohort':
            start=date.fromisoformat(request.query_params['start']);end=date.fromisoformat(request.query_params['end'])
            data=csv_bytes(tracker_metrics(p,start,end)['cohort']);filename='SANDHATA_COHORT.csv';media='text/csv'
        else: return JSONResponse({'error':'Not found'},status_code=404)
        return Response(data,media_type=media,headers={'Content-Disposition':f'attachment; filename="{filename}"','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
    except AppError: return JSONResponse({'error':'Unavailable or access revoked'},status_code=403)
    except (ValueError,KeyError): return JSONResponse({'error':'Invalid request'},status_code=400)
    except Exception: return JSONResponse({'error':'Download unavailable'},status_code=503)

app=Starlette(routes=[Route('/health',health),Route('/download/{kind}',download),Route('/download/{kind}/{identifier}',download)])
app.add_middleware(CORSMiddleware,allow_origins=[os.getenv('SANDHATA_APP_URL','http://localhost:8605')],allow_methods=['GET'],allow_headers=['Authorization'],expose_headers=['Content-Disposition'])
