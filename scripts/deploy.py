"""Idempotent private Lambda deployment. No public function URL or extra services."""
import json
import time
from boto3.s3.transfer import TransferConfig
from agent.aws_clients import client,settings,ROOT

def main():
    cfg=settings(); name=cfg['function_name']; role_name='ProofRoster-LambdaExecution'
    iam=client('iam'); lam=client('lambda'); logs=client('logs')
    archive=ROOT/'build'/'proofroster-lambda.zip'
    if not archive.exists(): raise RuntimeError('Run python -m scripts.package_lambda first')
    account=client('sts').get_caller_identity()['Account']
    # Multipart staging avoids unreliable 40 MB base64 bodies in Lambda's API.
    bucket=f"proofroster-artifacts-{account}-{cfg['region']}"; s3=client('s3')
    try: s3.head_bucket(Bucket=bucket)
    except s3.exceptions.ClientError as exc:
        if exc.response['Error']['Code'] not in ('404','NoSuchBucket'): raise
        s3.create_bucket(Bucket=bucket,CreateBucketConfiguration={'LocationConstraint':cfg['region']})
    s3.put_public_access_block(Bucket=bucket,PublicAccessBlockConfiguration=dict(BlockPublicAcls=True,IgnorePublicAcls=True,BlockPublicPolicy=True,RestrictPublicBuckets=True))
    s3.put_bucket_lifecycle_configuration(Bucket=bucket,LifecycleConfiguration={'Rules':[{'ID':'ExpireBuilds','Status':'Enabled','Filter':{'Prefix':'builds/'},'Expiration':{'Days':1},'AbortIncompleteMultipartUpload':{'DaysAfterInitiation':1}}]})
    key='builds/proofroster-lambda.zip'
    s3.upload_file(str(archive),bucket,key,ExtraArgs={'ServerSideEncryption':'AES256'},Config=TransferConfig(multipart_chunksize=5*1024*1024,max_concurrency=3))
    print('Uploaded private Lambda package',flush=True)
    # Lambda execution role follows AWS's documented Lambda service trust policy.
    trust={'Version':'2012-10-17','Statement':[{'Effect':'Allow','Principal':{'Service':'lambda.amazonaws.com'},'Action':'sts:AssumeRole'}]}
    try: role=iam.get_role(RoleName=role_name)['Role']
    except iam.exceptions.NoSuchEntityException:
        role=iam.create_role(RoleName=role_name,AssumeRolePolicyDocument=json.dumps(trust),Description='ProofRoster solver, CloudWatch logging only',Tags=[{'Key':'Application','Value':'ProofRoster'}])['Role']
    group='/aws/lambda/'+name
    try: logs.create_log_group(logGroupName=group,tags={'Application':'ProofRoster'})
    except logs.exceptions.ResourceAlreadyExistsException: pass
    logs.put_retention_policy(logGroupName=group,retentionInDays=7)
    policy={'Version':'2012-10-17','Statement':[{'Effect':'Allow','Action':['logs:CreateLogStream','logs:PutLogEvents'],'Resource':f"arn:aws:logs:{cfg['region']}:{account}:log-group:{group}:*"}]}
    iam.put_role_policy(RoleName=role_name,PolicyName='ProofRoster-ScopedLogs',PolicyDocument=json.dumps(policy))
    config=dict(FunctionName=name,Role=role['Arn'],Runtime='python3.12',Handler='lambda_solver.solver.handler',Timeout=60,MemorySize=1536)
    try:
        existing=lam.get_function_configuration(FunctionName=name)
        if existing.get('Description')!='ProofRoster private Z3 solver': raise RuntimeError('Existing function is not managed by ProofRoster; refusing to overwrite')
        lam.update_function_code(FunctionName=name,S3Bucket=bucket,S3Key=key)
        lam.get_waiter('function_updated_v2').wait(FunctionName=name,WaiterConfig={'Delay':2,'MaxAttempts':30})
        result=lam.update_function_configuration(**config)
    except lam.exceptions.ResourceNotFoundException:
        for attempt in range(6):
            try:
                result=lam.create_function(**config,Code={'S3Bucket':bucket,'S3Key':key},Architectures=['x86_64'],Description='ProofRoster private Z3 solver',Tags={'Application':'ProofRoster'})
                break
            except lam.exceptions.InvalidParameterValueException as exc:
                if 'cannot be assumed' not in str(exc) or attempt==5: raise
                time.sleep(5)
    lam.get_waiter('function_active_v2').wait(FunctionName=name,WaiterConfig={'Delay':2,'MaxAttempts':30})
    (ROOT/'recorded'/'deployment.json').write_text(json.dumps({'function_arn':result['FunctionArn'],'region':cfg['region'],'runtime':'python3.12','memory_mb':1536,'timeout_seconds':60,'public_url':False},indent=2))
    print('Deployed private Lambda:',result['FunctionArn'])

if __name__=='__main__': main()
