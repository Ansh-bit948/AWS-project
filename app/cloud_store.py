"""Private S3 artifacts and atomic DynamoDB version/audit transactions."""
import json
import os
import time
import uuid
from functools import lru_cache
import boto3
from boto3.dynamodb.conditions import Key, Attr
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError
from .local_store import Conflict, stamp

s3 = boto3.client('s3')
ddb = boto3.resource('dynamodb')
transaction_client = boto3.client('dynamodb')
serializer = TypeSerializer()

@lru_cache(maxsize=8)
def artifact(bucket,key):
    return json.loads(s3.get_object(Bucket=bucket,Key=key)['Body'].read())

class CloudStore:
    def __init__(self):
        self.bucket = os.environ['RAW_BUCKET']
        self.table = ddb.Table(os.environ['RESULTS_TABLE'])
    def datasets(self):
        args = {'FilterExpression':Attr('sk').eq('META'),'ConsistentRead':True}
        rows = []
        while True:
            data = self.table.scan(**args)
            rows.extend(data.get('Items',[]))
            if not data.get('LastEvaluatedKey'):
                break
            args['ExclusiveStartKey'] = data['LastEvaluatedKey']
        return sorted([self.simplify(x) for x in rows],key=lambda x:x.get('uploaded_at',''),reverse=True)
    def simplify(self,item):
        return {k:v for k,v in item.items() if k not in ('pk','sk')} | {'dataset_id':item['pk'].removeprefix('DATASET#')}
    def item(self,did,sk):
        return self.table.get_item(Key={'pk':f'DATASET#{did}','sk':sk},ConsistentRead=True).get('Item')
    def get(self,did):
        meta = self.item(did,'META')
        if not meta:
            raise KeyError('Dataset not found')
        if meta.get('status','ready') != 'ready':
            raise ValueError(meta.get('error') or 'Dataset analysis is pending')
        row = self.item(did,'ANALYSIS')
        key = meta.get('active_key') or (row or {}).get('result_key')
        if not key:
            raise ValueError('Dataset analysis is pending')
        try:
            a = artifact(self.bucket,key).copy()
        except ClientError as e:
            if e.response['Error']['Code'] in ('NoSuchKey','404'):
                raise KeyError('Dataset artifact expired. Reimport source data.') from e
            raise
        a['policy_version'] = int(meta.get('policy_version',1))
        return self.simplify(meta),a
    def source_pairs(self,did):
        meta = self.item(did,'META')
        row = self.item(did,'ANALYSIS') or {}
        source = artifact(self.bucket,meta.get('source_result_key') or row['result_key'])
        return sorted({(u,p) for r in source['roles'] for u in r['users'] for p in r['permissions']})
    def query(self,did,prefix):
        args = {'KeyConditionExpression':Key('pk').eq(f'DATASET#{did}') & Key('sk').begins_with(prefix),'ConsistentRead':True}
        rows = []
        while True:
            data = self.table.query(**args)
            rows.extend(data.get('Items',[]))
            if not data.get('LastEvaluatedKey'):
                break
            args['ExclusiveStartKey'] = data['LastEvaluatedKey']
        return rows
    def decisions(self,did):
        return self.query(did,'DECISION#')
    def history(self,did):
        rows = self.query(did,'VERSION#')
        if not rows:
            meta = self.item(did,'META')
            return [{'version':1,'parent_version':None,'change_summary':'Imported baseline','actor':'dataset-import','created_at':meta['uploaded_at']}]
        return sorted(rows,key=lambda x:int(x['version']),reverse=True)
    def audit(self,did):
        return sorted(self.query(did,'AUDIT#'),key=lambda x:x['created_at'],reverse=True)
    def put_artifact(self,key,result):
        s3.put_object(Bucket=self.bucket,Key=key,Body=json.dumps(result,separators=(',',':')).encode(),
                      ContentType='application/json',ServerSideEncryption='AES256')
    def commit(self,did,expected,decision,analysis,changed,actor):
        meta = self.item(did,'META')
        ts,token = stamp(),str(uuid.uuid4())
        version = expected + int(changed)
        active_key = meta.get('active_key') or self.item(did,'ANALYSIS')['result_key']
        if changed:
            active_key = f'results/{did}/policy-{version}-{token}.json'
            self.put_artifact(active_key,analysis)
        pk,expiry = f'DATASET#{did}',int(time.time()) + 30*86400
        dec_key = 'DECISION#' + uuid.uuid5(uuid.NAMESPACE_URL,decision['user_id']+'\0'+decision['permission_id']).hex
        items = [
            {'Update':{'TableName':self.table.name,'Key':{'pk':{'S':pk},'sk':{'S':'META'}},
                       'UpdateExpression':'SET policy_version=:new, active_key=:key',
                       'ConditionExpression':'policy_version=:old OR (attribute_not_exists(policy_version) AND :old=:one)',
                       'ExpressionAttributeValues':{':new':{'N':str(version)},':old':{'N':str(expected)},':one':{'N':'1'},':key':{'S':active_key}}}},
            {'Put':{'TableName':self.table.name,'Item':self.serialize({'pk':pk,'sk':dec_key,**decision,'version':version,'created_at':ts,'expires_at':expiry})}},
            {'Put':{'TableName':self.table.name,'Item':self.serialize({'pk':pk,'sk':'AUDIT#'+ts+'#'+token,'id':token,'actor':actor,'action':'permission_decision','details':decision|{'policy_version':version},'created_at':ts,'expires_at':expiry})}}
        ]
        if changed:
            items.append({'Put':{'TableName':self.table.name,'Item':self.serialize({'pk':pk,'sk':f'VERSION#{version:08d}','version':version,'parent_version':expected,
                'change_summary':json.dumps(decision),'actor':actor,'created_at':ts,'result_key':active_key,'expires_at':expiry})}})
        try:
            transaction_client.transact_write_items(TransactItems=items)
        except ClientError as e:
            if e.response['Error']['Code'] in ('TransactionCanceledException','ConditionalCheckFailedException'):
                raise Conflict('Policy changed. Reload and review the latest version.') from e
            raise
    def serialize(self,item):
        return {k:serializer.serialize(v) for k,v in item.items()}
    def save_model(self,did,report,actor):
        mid,ts = str(uuid.uuid4()),stamp()
        report['model_id'] = mid
        key = f'results/{did}/model-{mid}.json'
        self.put_artifact(key,report)
        self.table.put_item(Item={'pk':f'DATASET#{did}','sk':'MODEL#'+mid,'created_at':ts,'result_key':key,'expires_at':int(time.time())+30*86400})
        self.table.put_item(Item={'pk':f'DATASET#{did}','sk':'AUDIT#'+ts+'#'+mid,'actor':actor,'action':'feedback_rl_run',
                                 'details':{'model_id':mid,'feedback_sha256':report['feedback_sha256']},'created_at':ts,'expires_at':int(time.time())+30*86400})
        return report
