"""AWS adapter: authenticated API Gateway routes and S3-triggered dataset runs."""
import csv, hashlib, io, json, os, urllib.parse, uuid
from datetime import datetime, timezone
import boto3
from boto3.dynamodb.conditions import Key

s3=boto3.client('s3'); ddb=boto3.resource('dynamodb')
table=lambda: ddb.Table(os.environ['RESULTS_TABLE'])
def stamp(): return datetime.now(timezone.utc).isoformat()

def process_s3(event, context):
    """Triggered by raw/ CSV object creation. Persist source hash and computed evidence."""
    from app.engine import compute
    results=[]
    for record in event.get('Records',[]):
        bucket=record['s3']['bucket']['name']; key=urllib.parse.unquote_plus(record['s3']['object']['key'])
        if not key.startswith('raw/') or not key.lower().endswith('.csv'): continue
        obj=s3.get_object(Bucket=bucket,Key=key); raw=obj['Body'].read()
        reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
        fields={x.strip().lower():x for x in (reader.fieldnames or [])}
        uc=next((fields[x] for x in ('user_id','user','uid') if x in fields),None)
        pc=next((fields[x] for x in ('permission_id','permission','resource_id','rid') if x in fields),None)
        if not uc or not pc: raise ValueError('CSV must include user_id and permission_id columns')
        pairs=set()
        for row in reader:
            u=(row.get(uc) or '').strip(); p=(row.get(pc) or '').strip()
            if not u or not p: raise ValueError('Blank user/permission row; source must be corrected')
            pairs.add((u,p))
        did=key.split('/')[1]; result=compute(did,list(pairs)); sha=hashlib.sha256(raw).hexdigest(); ts=stamp()
        t=table()
        source=(obj.get('Metadata',{}).get('source-url') or 'Operator supplied upload')
        name=(obj.get('Metadata',{}).get('dataset-name') or key.rsplit('/',1)[-1])
        license_note=(obj.get('Metadata',{}).get('license-note') or 'Not provided')
        t.put_item(Item={'pk':f'DATASET#{did}','sk':'META','name':name,'source_url':source,'license_note':license_note,'sha256':sha,'s3_key':key,'uploaded_at':ts,'run_id':did,'counts':result['counts']})
        result_key=f'results/{did}.json'
        s3.put_object(Bucket=bucket,Key=result_key,Body=json.dumps(result,separators=(',',':')).encode(),ContentType='application/json',ServerSideEncryption='AES256')
        t.put_item(Item={'pk':f'DATASET#{did}','sk':'ANALYSIS','result_key':result_key,'created_at':ts})
        results.append({'dataset_id':did,'sha256':sha,'counts':result['counts']})
    return results

def api_handler(event, context):
    """API Gateway HTTP API. JWT authorization is enforced by API Gateway Cognito authorizer."""
    method=event.get('requestContext',{}).get('http',{}).get('method','GET')
    path=event.get('rawPath','/'); t=table()
    try:
        if method=='POST' and path.endswith('/datasets/presign'):
            body=json.loads(event.get('body') or '{}'); filename=os.path.basename(body.get('filename','dataset.csv'))
            if not filename.lower().endswith('.csv'): return response(400,{'error':'CSV only'})
            did=str(uuid.uuid4()); key=f"raw/{did}/{filename}"
            url=s3.generate_presigned_url('put_object',Params={'Bucket':os.environ['RAW_BUCKET'],'Key':key,'ContentType':'text/csv','Metadata':{'source-url':str(body.get('source_url') or 'operator-upload')[:512],'dataset-name':str(body.get('name') or filename)[:200],'license-note':str(body.get('license_note') or 'Not provided')[:512]}},ExpiresIn=300)
            return response(200,{'dataset_id':did,'upload_url':url,'s3_key':key,'expires_seconds':300,'next':'PUT the CSV to upload_url; S3 event runs analysis.'})
        if method=='GET' and path.endswith('/datasets'):
            # This project-scale scan is intentionally bounded by DynamoDB pagination; production should use a GSI.
            data=t.scan(FilterExpression='sk = :meta',ExpressionAttributeValues={':meta':'META'},Limit=100)
            return response(200,{'datasets':[simplify(x) for x in data.get('Items',[])]})
        if method=='GET' and '/analytics/' in path:
            did=path.rsplit('/',1)[-1]
            row=t.get_item(Key={'pk':f'DATASET#{did}','sk':'ANALYSIS'}).get('Item')
            if not row: return response(404,{'error':'Dataset analysis is not ready or does not exist'})
            meta=t.get_item(Key={'pk':f'DATASET#{did}','sk':'META'}).get('Item',{})
            result=s3.get_object(Bucket=os.environ['RAW_BUCKET'],Key=row['result_key'])['Body'].read()
            return response(200,{'dataset':simplify(meta),'analysis':json.loads(result)})
        if method=='POST' and path.endswith('/security/validate'):
            body=json.loads(event.get('body') or '{}'); document=body.get('policy_document')
            if not isinstance(document,(dict,str)): return response(400,{'error':'policy_document must be a JSON object or JSON string'})
            doc=json.dumps(document) if isinstance(document,dict) else document
            result=boto3.client('access-analyzer').validate_policy(policyType='IDENTITY_POLICY',policyDocument=doc)
            return response(200,{'findings':result.get('findings',[]),'scope':'IAM Access Analyzer policy validation findings; not a proof that access is safe or least-privilege.'})
        return response(404,{'error':'Route not found'})
    except Exception as e:
        return response(400,{'error':str(e)})

def simplify(item):
    return {k:item[k] for k in ('name','source_url','license_note','sha256','uploaded_at','counts','run_id') if k in item}|{'dataset_id':item['pk'].removeprefix('DATASET#')}
def response(status,body):
    return {'statusCode':status,'headers':{'content-type':'application/json','cache-control':'no-store'},'body':json.dumps(body,default=str)}
