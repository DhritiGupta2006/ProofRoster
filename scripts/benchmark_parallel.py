"""Real paired-agent benchmark, at most three runs in flight."""
import argparse
import json
import uuid
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from agent.aws_clients import ROOT,settings
from agent.runner import run_baseline,run_proof
from scenarios.catalog import make_spec

def paired_run(scenario,index):
    record={'scenario':scenario,'run':index,'timestamp':datetime.now(timezone.utc).isoformat()}
    spec=make_spec(scenario)
    for name,runner in [('baseline',run_baseline),('proof',run_proof)]:
        try: record[name]=runner(spec)
        except Exception as exc: record[name]={'error':str(exc)}
    if 'result' in record.get('proof',{}):
        replay={**record,'mode':'aws','model_id':settings()['model_id'],'recorded_at':record['timestamp'],'spec':spec,
            'changes':[{'rule_id':'R11','before':5,'after':6,'meaning':'Maximum nights per person'}] if scenario=='C' else []}
        (ROOT/'recorded'/f'run-aws-{scenario}-benchmark-{index}-{uuid.uuid4().hex[:6]}.json').write_text(json.dumps(replay,indent=2))
    return record

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runs',type=int,default=10);args=parser.parse_args()
    if not 1<=args.runs<=100: raise ValueError('Runs must be 1-100')
    now=datetime.now(timezone.utc);path=ROOT/'recorded'/'benchmark.json'
    if path.exists(): (ROOT/'recorded'/f'benchmark-archive-{now.strftime("%Y%m%d-%H%M%S")}.json').write_text(path.read_text())
    report={'started_at':now.isoformat(),'model_id':settings()['model_id'],'runs_per_scenario':args.runs,'temperature':0,'status':'RUNNING','records':[]}
    def save():path.write_text(json.dumps(report,indent=2))
    if not settings()['streaming_verified']:
        report.update(status='BLOCKED',reason='Streaming model access has not passed preflight.');save();return
    save()
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(paired_run,s,i) for i in range(1,args.runs+1) for s in 'ABC']
        for future in as_completed(futures):
            record=future.result();report['records'].append(record);save()
            print(record['scenario'],record['run'],'baseline',record.get('baseline',{}).get('checker',{}).get('violation_count','ERROR'),
                'proof',record.get('proof',{}).get('result',{}).get('status','ERROR'),'fidelity',record.get('proof',{}).get('fidelity',{}).get('matches',False),flush=True)
    report['status']='COMPLETE';report['completed_at']=datetime.now(timezone.utc).isoformat()
    report['summary']={s:{'attempted':sum(r['scenario']==s for r in report['records']),
        'baseline_valid':sum(r.get('baseline',{}).get('checker',{}).get('valid',False) for r in report['records'] if r['scenario']==s),
        'baseline_errors':sum('error' in r.get('baseline',{}) for r in report['records'] if r['scenario']==s),
        'proof_verified_sat':sum(r.get('proof',{}).get('verified',False) for r in report['records'] if r['scenario']==s),
        'proof_faithful_unsat':sum(r.get('proof',{}).get('result',{}).get('status')=='UNSAT' and r.get('proof',{}).get('fidelity',{}).get('matches',False) for r in report['records'] if r['scenario']==s),
        'proof_errors':sum('error' in r.get('proof',{}) for r in report['records'] if r['scenario']==s),
        'fidelity_matches':sum(r.get('proof',{}).get('fidelity',{}).get('matches',False) for r in report['records'] if r['scenario']==s)} for s in 'ABC'}
    save();print(json.dumps(report['summary'],indent=2))

if __name__=='__main__':main()
