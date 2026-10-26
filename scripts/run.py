import argparse
import json
import uuid
from datetime import datetime,timezone
from agent.aws_clients import ROOT,settings
from agent.runner import run_baseline,run_proof
from scenarios.catalog import make_spec

def main():
    parser=argparse.ArgumentParser();parser.add_argument('scenario',choices=list('ABC'));parser.add_argument('--night-cap',type=int,default=6);args=parser.parse_args()
    spec=make_spec(args.scenario,args.night_cap)
    def emit(kind,data):
        if kind!='token': print(kind,json.dumps(data,default=str)[:300],flush=True)
    record={'scenario':args.scenario,'mode':'aws','model_id':settings()['model_id'],'recorded_at':datetime.now(timezone.utc).isoformat(),'spec':spec,
        'changes':[{'rule_id':'R11','before':5,'after':args.night_cap,'meaning':'Maximum nights per person'}] if args.scenario=='C' else []}
    print('Running baseline',flush=True);record['baseline']=run_baseline(spec,emit)
    print('Baseline violations:',record['baseline']['checker']['violation_count'],flush=True)
    print('Running ProofRoster agent',flush=True);record['proof']=run_proof(spec,emit)
    path=ROOT/'recorded'/f'run-aws-{args.scenario}-{uuid.uuid4().hex[:8]}.json'
    path.write_text(json.dumps(record,indent=2))
    print('Saved',path,'status',record['proof']['result']['status'],'verified',record['proof']['verified'],flush=True)

if __name__=='__main__':main()
