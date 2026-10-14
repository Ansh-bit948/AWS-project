"""Configure and verify the authorized AWS demo. Never print credentials or tokens."""
import argparse
import json
import secrets
import sys
import time
from pathlib import Path
import boto3
import httpx
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--setup-login',action='store_true')
    parser.add_argument('--username')
    parser.add_argument('--verify',action='store_true')
    parser.add_argument('--region',default='us-east-1')
    parser.add_argument('--stack',default='ieai-alp')
    args=parser.parse_args()
    session=boto3.Session(region_name=args.region)
    stack=session.client('cloudformation').describe_stacks(StackName=args.stack)['Stacks'][0]
    outputs={x['OutputKey']:x['OutputValue'] for x in stack['Outputs']}
    config={'apiUrl':outputs['ApiUrl'],'region':args.region,'clientId':outputs['UserPoolClientId']}
    (ROOT/'app/static/config.js').write_text('window.IEAI_CONFIG = '+json.dumps(config,indent=2)+';\n',encoding='utf-8')
    local=ROOT/'.local';local.mkdir(exist_ok=True)
    credfile=local/'demo-login.json'
    cognito=session.client('cognito-idp')
    if args.setup_login:
        if not args.username:parser.error('--username is required with --setup-login')
        password=secrets.token_urlsafe(28)+'aA9!'
        cognito.admin_set_user_password(UserPoolId=outputs['UserPoolId'],Username=args.username,Password=password,Permanent=True)
        credfile.write_text(json.dumps({'username':args.username,'password':password},indent=2),encoding='utf-8')
        # Private ignored file. Caller can replace this password with their own.
        import os
        if os.name!='nt':credfile.chmod(0o600)
        print('Demo login saved in the ignored .local/demo-login.json file.')
    resources=session.client('cloudformation').describe_stack_resources(StackName=args.stack)['StackResources']
    logs=session.client('logs')
    for resource in resources:
        if resource['ResourceType']=='AWS::Lambda::Function':
            try:logs.put_retention_policy(logGroupName='/aws/lambda/'+resource['PhysicalResourceId'],retentionInDays=7)
            except logs.exceptions.ResourceNotFoundException:pass
    if not args.verify:return
    creds=json.loads(credfile.read_text(encoding='utf-8'))
    auth=cognito.initiate_auth(ClientId=outputs['UserPoolClientId'],AuthFlow='USER_PASSWORD_AUTH',
                              AuthParameters={'USERNAME':creds['username'],'PASSWORD':creds['password']})
    token=auth['AuthenticationResult']['IdToken']
    client=httpx.Client(base_url=outputs['ApiUrl'],headers={'authorization':'Bearer '+token},timeout=30)
    def request(method,path,**kw):
        for attempt in range(6):
            r=client.request(method,path,**kw)
            if r.status_code!=429:break
            time.sleep(.5*(attempt+1))
        if r.is_error:
            raise RuntimeError(f'{method} {path}: HTTP {r.status_code}: '+r.text[:400])
        return r.json()
    unauth=httpx.get(outputs['ApiUrl']+'/datasets',timeout=15)
    assert unauth.status_code==401
    preflight=httpx.options(outputs['ApiUrl']+'/datasets',headers={'Origin':'http://127.0.0.1:8000','Access-Control-Request-Method':'GET','Access-Control-Request-Headers':'authorization'},timeout=15)
    assert preflight.status_code in (200,204),preflight.text
    assert preflight.headers.get('access-control-allow-origin')=='http://127.0.0.1:8000'
    raw=(ROOT/'data/processed/firewall1_upa.csv').read_bytes()
    presign=request('POST','/datasets/presign',json={'filename':'firewall1_upa.csv','name':'Firewall1 validated demo',
                    'source_url':'https://onlinerbacfixing.github.io/cybersecurity2019/','license_note':'CC BY 4.0; published RBAC Maintenance variant'})
    upload=httpx.put(presign['upload_url'],headers=presign['headers'],content=raw,timeout=30)
    assert upload.status_code==200,upload.text[:300]
    did=presign['dataset_id']
    for _ in range(45):
        rows=request('GET','/datasets')['datasets']
        row=next((d for d in rows if d['dataset_id']==did),None)
        if row and row['status']=='failed':raise RuntimeError(row['error'])
        if row and row['status']=='ready':break
        time.sleep(2)
    else:raise RuntimeError('AWS analysis did not become ready')
    data=request('GET','/analytics/'+did)
    assert data['analysis']['engine_version']=='2.0.0'
    assert data['analysis']['counts']['assignments']==31919
    role=data['analysis']['roles'][0];u,p=role['users'][0],role['permissions'][0]
    def check():
        return request('POST','/authorize/'+did,json={'user_id':u,'permission_id':p})['allowed']
    assert check()
    body={'dataset_id':did,'user_id':u,'permission_id':p,'decision':'revoke','expected_version':1,'purpose':'validation'}
    revoked=request('POST','/decisions',json=body)
    assert revoked['policy_version']==2 and not check()
    body.update(decision='retain',expected_version=2)
    restored=request('POST','/decisions',json=body)
    assert restored['policy_version']==3 and check()
    final=request('GET','/analytics/'+did)
    assert final['analysis']['counts']==data['analysis']['counts']
    assert final['dataset']['sha256']==data['dataset']['sha256']
    # No feedback is fabricated; validation decisions must not train the model.
    r=client.post('/rl/train/'+did,json={'episodes':500})
    if r.status_code==429:time.sleep(2);r=client.post('/rl/train/'+did,json={'episodes':500})
    assert r.status_code==400 and 'genuine' in r.text
    validations=request('POST','/security/validate',json={'policy_document':{'Version':'2012-10-17','Statement':[{'Effect':'Allow','Action':'s3:GetObject','Resource':f"arn:aws:s3:::{outputs['RawBucket']}/raw/*"}]}})
    report={'stack_status':stack['StackStatus'],'region':args.region,'dataset_id':did,'dataset_sha256':data['dataset']['sha256'],
            'counts':final['analysis']['counts'],'optimized':final['analysis']['optimized'],
            'checks':{'unauthenticated_denied':True,'browser_cors_preflight':True,'signed_s3_upload':True,'lambda_source_analysis':True,'cognito_sign_in':True,
                      'revoke_denies_access':True,'restore_allows_access':True,'source_hash_unchanged':True,'validation_excluded_from_learning':True,
                      'dynamodb_audit_versions':len(request('GET','/policy-versions/'+did)['items'])},
            'iam_validation_findings':len(validations['findings'])}
    (ROOT/'docs/aws-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
