"""Honest live-agent benchmark. Saves every result, failure, timestamp and raw trace."""
import argparse
import json
from datetime import datetime,timezone
from agent.aws_clients import ROOT,settings
from agent.runner import run_baseline,run_proof
from scenarios.catalog import make_spec

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--runs',type=int,default=10); args=parser.parse_args()
    if not 1<=args.runs<=100: raise ValueError('Runs must be 1-100')
    report={'started_at':datetime.now(timezone.utc).isoformat(),'model_id':settings()['model_id'],'runs_per_scenario':args.runs,'records':[]}
    path=ROOT/'recorded'/'benchmark.json'
    if not settings()['model_id']:
        report.update(status='BLOCKED',reason='Bedrock preflight has not verified an accessible model. No agent benchmark was run.')
        path.write_text(json.dumps(report,indent=2)); print(report['reason']); return
    for scenario in 'ABC':
        for i in range(args.runs):
            record={'scenario':scenario,'run':i+1,'timestamp':datetime.now(timezone.utc).isoformat()}
            spec=make_spec(scenario)
            for name,runner in [('baseline',run_baseline),('proof',run_proof)]:
                try: record[name]=runner(spec)
                except Exception as e: record[name]={'error':str(e)}
            report['records'].append(record);path.write_text(json.dumps(report,indent=2))
            print(scenario,i+1,'saved',flush=True)
            failures=[v['error'] for v in record.values() if isinstance(v,dict) and 'error' in v]
            if any('use case details' in error or 'account is currently being verified' in error for error in failures):
                report.update(status='BLOCKED',reason='AWS account/model access requires user action; remaining runs were not attempted.')
                path.write_text(json.dumps(report,indent=2));print(report['reason'],flush=True);return
    report['status']='COMPLETE';report['completed_at']=datetime.now(timezone.utc).isoformat()
    report['summary']={s:{'baseline_valid':sum(r.get('baseline',{}).get('checker',{}).get('valid',False) for r in report['records'] if r['scenario']==s),
        'proof_verified_sat':sum(r.get('proof',{}).get('verified',False) for r in report['records'] if r['scenario']==s),
        'proof_faithful_unsat':sum(r.get('proof',{}).get('result',{}).get('status')=='UNSAT' and r.get('proof',{}).get('fidelity',{}).get('matches',False) for r in report['records'] if r['scenario']==s)} for s in 'ABC'}
    path.write_text(json.dumps(report,indent=2)); print(json.dumps(report['summary'],indent=2))

if __name__=='__main__': main()
