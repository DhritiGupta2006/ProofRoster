"""Test an explicit Bedrock model or discover Sonnet profiles; verify streaming too."""
import json
import argparse
from datetime import datetime,timezone
from agent.aws_clients import client, settings, ROOT

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model-id');args=parser.parse_args()
    identity=client('sts').get_caller_identity()
    print('AWS identity verified:',identity['Account'],flush=True)
    profiles=[p for page in client('bedrock').get_paginator('list_inference_profiles').paginate() for p in page['inferenceProfileSummaries'] if 'sonnet' in p['inferenceProfileId'] and p['status']=='ACTIVE' and not p['inferenceProfileId'].startswith('global.')]
    profiles.sort(key=lambda p:('4-5' not in p['inferenceProfileId'],'4' not in p['inferenceProfileId'],p['inferenceProfileId']))
    if args.model_id: profiles=[{'inferenceProfileId':args.model_id}]
    errors=[]
    for profile in profiles:
        identifier=profile['inferenceProfileId']; print('Testing:',identifier,flush=True)
        try:
            result=client('bedrock-runtime').converse(modelId=identifier,messages=[{'role':'user','content':[{'text':'Reply with OK.'}]}],inferenceConfig={'maxTokens':8,'temperature':0})
            stream=client('bedrock-runtime').converse_stream(modelId=identifier,messages=[{'role':'user','content':[{'text':'Reply with OK.'}]}],inferenceConfig={'maxTokens':8,'temperature':0})
            try:
                stream_events=list(stream['stream'])
            finally:
                stream['stream'].close()
        except Exception as e:
            errors.append({'model_id':identifier,'error':str(e)}); print(str(e),flush=True)
            (ROOT/'recorded'/'aws-preflight-failure.json').write_text(json.dumps({'recorded_at':datetime.now(timezone.utc).isoformat(),'region':settings()['region'],'errors':errors},indent=2))
            cfg=settings();cfg.pop('profile',None);cfg['model_id']=identifier;cfg['streaming_verified']=False
            (ROOT/'aws-settings.json').write_text(json.dumps(cfg,indent=2))
            if 'account is currently being verified' in str(e) or 'use case details' in str(e):
                raise RuntimeError('AWS account/model access pending. See recorded/aws-preflight-failure.json') from e
            continue
        cfg=settings(); cfg['model_id']=identifier
        cfg['verified_at']=datetime.now(timezone.utc).isoformat()
        cfg['streaming_verified']=True
        cfg.pop('profile',None)
        (ROOT/'aws-settings.json').write_text(json.dumps(cfg,indent=2))
        evidence={'verified_at':cfg['verified_at'],'region':cfg['region'],'model_id':identifier,'response':result,'stream_events':stream_events,'failed_attempts':errors}
        (ROOT/'recorded'/'aws-preflight.json').write_text(json.dumps(evidence,indent=2,default=str))
        print('Verified model saved:',identifier); return
    raise RuntimeError('No accessible Sonnet profile. '+json.dumps(errors))

if __name__=='__main__': main()
