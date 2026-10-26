"""Save actual solver runs for the UI; clearly labelled as local, without an AI baseline."""
import json
from datetime import datetime,timezone
from agent.aws_clients import ROOT
from agent.runner import fidelity
from lambda_solver.solver import solve
from checker.validate import check_roster
from scenarios.catalog import make_spec

def main():
    for scenario in 'ABC':
        spec=make_spec(scenario);result=solve(spec)
        check=check_roster(spec,result['schedule_by_staff']) if result['status']=='SAT' else None
        record={'scenario':scenario,'mode':'local','recorded_at':datetime.now(timezone.utc).isoformat(),'spec':spec,
            'changes':[{'rule_id':'R11','before':5,'after':6,'meaning':'Maximum nights per person'}] if scenario=='C' else [],
            'baseline':{'unavailable':'No AI baseline was invoked in this local solver recording.'},
            'proof':{'source':'Local Z3 (no AWS / no LLM)','result':result,'checker':check,'verified':bool(check and check['valid']),
                'fidelity':fidelity(spec,spec),'traces':[{'input':spec,'result':result,'latency_ms':result['solve_ms']}]}}
        (ROOT/'recorded'/f'run-local-{scenario}.json').write_text(json.dumps(record,indent=2))
        print(scenario,result['status'],flush=True)

if __name__=='__main__': main()
