import json
import argparse
from datetime import datetime,timezone
from agent.aws_clients import ROOT,invoke_solver
from lambda_solver.solver import solve
from checker.validate import check_roster
from scenarios.catalog import make_spec,write_scenarios

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--aws',action='store_true'); args=parser.parse_args()
    write_scenarios(); results={}; invoke=invoke_solver if args.aws else solve
    for key in 'ABC':
        spec=make_spec(key); result=invoke(spec)
        report=check_roster(spec,result['schedule_by_staff']) if result['status']=='SAT' else None
        results[key]={'result':result,'checker':report}
        print(key,result['status'],result.get('conflict',{}),flush=True)
        assert result['status']==('UNSAT' if key=='B' else 'SAT')
        if report: assert report['valid']
    b=results['B']['result']['conflict']
    assert b['minimal'] and len(b['rule_ids'])<=4
    assert sum(r['feasible_if_removed'] is True for r in b['relaxation'])>=2
    evidence={'source':'AWS Lambda' if args.aws else 'Local Z3','recorded_at':datetime.now(timezone.utc).isoformat(),'results':results}
    (ROOT/'recorded'/('aws-scenarios.json' if args.aws else 'local-scenarios.json')).write_text(json.dumps(evidence,indent=2))

if __name__=='__main__': main()
