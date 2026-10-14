"""AWS adapters: authenticated routes and idempotent S3 ingestion."""
import base64
import json
import logging
import os
from pathlib import Path
import sys
import time
import types
import urllib.parse
import uuid
from decimal import Decimal

# SAM's app/ CodeUri places these files at Lambda root; provide the app package.
if 'app' not in sys.modules and __package__ in (None,''):
    package = types.ModuleType('app')
    package.__path__ = [str(Path(__file__).parent)]
    sys.modules['app'] = package
from app.cloud_store import CloudStore, s3
from app.engine import compute
from app.ingestion import MAX_BYTES, parse_csv
from app.local_store import stamp
from app.service import dispatch

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

def process_s3(event,context):
    store = CloudStore()
    results = []
    for record in event.get('Records',[]):
        bucket = record['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(record['s3']['object']['key'])
        if not key.startswith('raw/') or not key.lower().endswith('.csv'):
            continue
        did = key.split('/')[1]
        prior = store.item(did,'META')
        if prior and prior.get('status') == 'ready':
            results.append({'dataset_id':did,'status':'already_processed'})
            continue
        try:
            obj = s3.get_object(Bucket=bucket,Key=key)
            pairs,quality = parse_csv(obj['Body'].read(MAX_BYTES+1))
            source_context = quality.pop('source_context', None)
            result = compute(did,pairs,source_context=source_context)
            result.update(policy_version=1,quality=quality)
            metadata,ts = obj.get('Metadata',{}),stamp()
            result_key = f'results/{did}/source.json'
            store.put_artifact(result_key,result)
            expiry = int(time.time()) + 30*86400
            meta = {'pk':f'DATASET#{did}','sk':'META','name':metadata.get('dataset-name',key.rsplit('/',1)[-1]),
                    'source_url':metadata.get('source-url','Operator supplied; not verified'),'license_note':metadata.get('license-note','Not provided'),
                    'sha256':quality['sha256'],'s3_key':key,'uploaded_at':ts,'run_id':did,'counts':result['counts'],
                    'policy_version':1,'source_result_key':result_key,'active_key':result_key,'status':'ready','expires_at':expiry}
            store.table.put_item(Item=meta)
            store.table.put_item(Item={'pk':f'DATASET#{did}','sk':'ANALYSIS','result_key':result_key,'created_at':ts,'expires_at':expiry})
            store.table.put_item(Item={'pk':f'DATASET#{did}','sk':'VERSION#00000001','version':1,'parent_version':None,
                                      'change_summary':'Imported immutable source grants','actor':'dataset-import','created_at':ts,'expires_at':expiry})
            store.table.put_item(Item={'pk':f'DATASET#{did}','sk':'AUDIT#'+ts,'actor':'dataset-import','action':'dataset_import',
                                      'details':quality,'created_at':ts,'expires_at':expiry})
            results.append({'dataset_id':did,'status':'ready','counts':result['counts']})
        except (ValueError,UnicodeDecodeError) as e:
            store.table.put_item(Item={'pk':f'DATASET#{did}','sk':'META','status':'failed','name':key.rsplit('/',1)[-1],
                                      'error':str(e),'uploaded_at':stamp(),'expires_at':int(time.time())+30*86400})
            log.warning('Dataset validation failed for %s: %s',did,e)
            results.append({'dataset_id':did,'status':'failed'})
    return results

def api_handler(event,context):
    if event.get('requestContext',{}).get('http',{}).get('method') == 'OPTIONS':
        return response(204,{})
    claims = event.get('requestContext',{}).get('authorizer',{}).get('jwt',{}).get('claims',{})
    if not claims.get('sub'):
        return response(401,{'error':'Authenticated Cognito administrator required'})
    method = event.get('requestContext',{}).get('http',{}).get('method','GET')
    path = event.get('rawPath','/').strip('/')
    try:
        raw = event.get('body') or '{}'
        if event.get('isBase64Encoded'):
            raw = base64.b64decode(raw).decode()
        body = json.loads(raw)
        if not isinstance(body,dict):
            raise ValueError('JSON object required')
        store = CloudStore()
        if method == 'POST' and path == 'datasets/presign':
            filename = str(body.get('filename','')).replace('\\','/').rsplit('/',1)[-1]
            if not filename.lower().endswith('.csv'):
                raise ValueError('CSV filename required')
            metadata = {k:str(body.get(v) or default)[:limit] for k,v,default,limit in [
                ('source-url','source_url','operator-upload',512),('dataset-name','name',filename,200),('license-note','license_note','Not provided',512)]}
            if any(not v.isascii() or '\n' in v or '\r' in v for v in metadata.values()):
                raise ValueError('S3 upload metadata must be single-line ASCII text')
            did,ts = str(uuid.uuid4()),stamp()
            key = f'raw/{did}/{filename}'
            url = s3.generate_presigned_url('put_object',Params={'Bucket':store.bucket,'Key':key,'ContentType':'text/csv',
                    'Metadata':metadata,'IfNoneMatch':'*'},ExpiresIn=300)
            store.table.put_item(Item={'pk':f'DATASET#{did}','sk':'META','name':metadata['dataset-name'],'status':'pending',
                                      'uploaded_at':ts,'expires_at':int(time.time())+30*86400})
            return response(200,{'dataset_id':did,'upload_url':url,'headers':{'content-type':'text/csv','if-none-match':'*',
                       **{'x-amz-meta-'+k:v for k,v in metadata.items()}},'max_bytes':MAX_BYTES,'expires_seconds':300})
        if method == 'POST' and path == 'security/validate':
            document = body.get('policy_document')
            if not isinstance(document,(dict,str)):
                raise ValueError('policy_document must be an IAM policy object or JSON string')
            import boto3
            result = boto3.client('accessanalyzer').validate_policy(policyType='IDENTITY_POLICY',policyDocument=json.dumps(document) if isinstance(document,dict) else document)
            return response(200,{'findings':result.get('findings',[]),'scope':'IAM policy validation; not a proof of dataset access safety'})
        status,payload = dispatch(method,path,event.get('queryStringParameters') or {},body,store,claims['sub'])
        return response(status,payload)
    except (ValueError,UnicodeDecodeError) as e:
        return response(400,{'error':str(e)})
    except Exception:
        log.exception('Request failed')
        return response(500,{'error':'AWS operation failed; see the Lambda log for this request','request_id':getattr(context,'aws_request_id',None)})

def json_default(value):
    if isinstance(value,Decimal):
        return int(value) if value == value.to_integral() else float(value)
    raise TypeError(f'Unsupported response type: {type(value).__name__}')

def response(status,body):
    encoded = json.dumps(body,default=json_default,separators=(',',':'))
    if len(encoded.encode()) > 5_500_000:
        return {'statusCode':413,'headers':{'content-type':'application/json'},'body':json.dumps({'error':'Response exceeds the demo API limit. Use compact=1 or paginated catalog endpoints.'})}
    return {'statusCode':status,'headers':{'content-type':'application/json','cache-control':'no-store'},'body':encoded}
