"""Local administrator application; shared analytics and policy rules with AWS."""
import os
from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from .ingestion import MAX_BYTES, parse_csv
from .local_store import LocalStore
from .service import dispatch

ROOT = Path(__file__).resolve().parent.parent
store = LocalStore(os.getenv('IEAI_DB',ROOT/'data'/'ieai.sqlite3'))
app = FastAPI(title='IEAI-ALP',version='2.0.0',description='Auditable access-governance research application')

@app.middleware('http')
async def local_origin(request, call_next):
    origin = request.headers.get('origin')
    if request.url.path.startswith('/api') and origin and origin not in ('http://127.0.0.1:8000','http://localhost:8000'):
        return JSONResponse({'error':'Local administrator API requires a local origin'},status_code=403)
    return await call_next(request)

@app.get('/api/health')
def health():
    return {'status':'ok','service':'ieai-alp','data_loaded':bool(store.datasets()),'version':'2.0.0'}

@app.post('/api/datasets/import')
async def import_csv(file: UploadFile=File(...), name: str=Form(''), source_url: str=Form(''), license_note: str=Form('')):
    if not (file.filename or '').lower().endswith('.csv'):
        raise HTTPException(400,'Upload a CSV')
    raw = await file.read(MAX_BYTES + 1)
    try:
        pairs,quality = parse_csv(raw)
    except (ValueError,UnicodeDecodeError) as e:
        raise HTTPException(400,str(e)) from e
    return store.import_data(pairs,{'name':name or file.filename,'source_url':source_url or 'User supplied; provenance not independently verified','license_note':license_note or 'Not provided'},quality)

@app.api_route('/api/{path:path}',methods=['GET','POST'])
async def api(path: str, request: Request):
    try:
        body = await request.json() if request.method=='POST' else {}
    except Exception:
        return JSONResponse({'error':'Request body must be valid JSON'},status_code=400)
    if not isinstance(body,dict):
        return JSONResponse({'error':'JSON object required'},status_code=400)
    status,payload = dispatch(request.method,path,dict(request.query_params),body,store,'local-admin')
    return JSONResponse(payload,status_code=status)

@app.get('/')
def home():
    return FileResponse(ROOT/'app'/'static'/'index.html')

@app.get('/static/config.js')
def config():
    p = ROOT/'app'/'static'/'config.js'
    return FileResponse(p) if p.exists() else __import__('fastapi').Response('window.IEAI_CONFIG = null;',media_type='application/javascript')

app.mount('/static',StaticFiles(directory=ROOT/'app'/'static'),name='static')
