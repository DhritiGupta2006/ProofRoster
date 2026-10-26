import json
import os
from pathlib import Path
from functools import lru_cache
import boto3
from botocore.config import Config

ROOT=Path(__file__).resolve().parents[1]

def settings():
    saved=json.loads((ROOT/'aws-settings.json').read_text()) if (ROOT/'aws-settings.json').exists() else {}
    return dict(region=os.getenv('PROOFROSTER_REGION',saved.get('region','ap-southeast-2')),
        profile=os.getenv('AWS_PROFILE','default'),
        model_id=os.getenv('BEDROCK_MODEL_ID',saved.get('model_id','')),
        streaming_verified=saved.get('streaming_verified',False),
        function_name=os.getenv('PROOFROSTER_FUNCTION',saved.get('function_name','proofroster-solver')))

@lru_cache(maxsize=1)
def session():
    cfg=settings()
    return boto3.Session(profile_name=cfg['profile'],region_name=cfg['region'])

@lru_cache(maxsize=8)
def client(name):
    return session().client(name,config=Config(connect_timeout=10,read_timeout=90,retries={'mode':'adaptive','total_max_attempts':3}))

def invoke_solver(spec):
    response=client('lambda').invoke(FunctionName=settings()['function_name'],InvocationType='RequestResponse',Payload=json.dumps(spec).encode())
    with response['Payload'] as payload:
        body=json.loads(payload.read())
    if response.get('FunctionError'): raise RuntimeError('Lambda error: '+json.dumps(body))
    if not isinstance(body,dict) or body.get('status') not in ('SAT','UNSAT','UNKNOWN','INVALID_SPEC'): raise RuntimeError('Invalid Lambda response')
    return body
