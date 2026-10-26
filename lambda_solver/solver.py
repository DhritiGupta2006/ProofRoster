"""Z3 guarded feasibility, deletion-minimal conflict, full-spec relaxation checks."""
import time
from z3 import Bool, Solver, Sum, If, Implies, Not, And, sat, unsat
from .schema import validate, spec_hash

def solve(spec, check_ms=10000, budget_ms=45000):
    start=time.perf_counter(); deadline=start+budget_ms/1000
    result=dict(status='INVALID_SPEC',solve_ms=0,spec_hash=spec_hash(spec))
    def finish():
        result['solve_ms']=round((time.perf_counter()-start)*1000,2)
        return result
    errors=validate(spec)
    if errors: result['errors']=errors; return finish()
    h=spec['horizon_days']; people=spec['staff']; shifts={s['code']:s for s in spec['shifts']}
    ids=[s['id'] for s in people]; codes=list(shifts); rules=spec['rules']
    x={(p,d,t):Bool(f'x_{i}_{d}_{t}') for i,p in enumerate(ids) for d in range(h) for t in codes}
    solver=Solver(); guards=[Bool(f'g_{i}') for i in range(len(rules))]
    def count(seq): return Sum([If(v,1,0) for v in seq])
    def work(p,d): return count(x[p,d,t] for t in codes)
    for p in ids:
        for d in range(h): solver.add(work(p,d)<=1)
    for index,r in enumerate(rules):
        p=r['params']; kind=r['type']; cs=[]
        selected=ids if p.get('staff','ALL')=='ALL' else p['staff']
        days=range(h) if p.get('days','ALL')=='ALL' else p['days']
        if kind=='COVERAGE':
            eligible=[s['id'] for s in people if 'skill' not in p or p['skill'] in s['skills']]
            cs=[count(x[a,d,p['shift']] for a in eligible)>=p['min'] for d in days]
        elif kind=='MIN_REST_HOURS':
            for a in ids:
                for d in range(h-1):
                    for t,s in shifts.items():
                        end=d*24+s['start_hour']+s['duration_h']
                        for u,v in shifts.items():
                            next_start=(d+1)*24+v['start_hour']
                            if next_start-end<p['hours']: cs.append(Not(And(x[a,d,t],x[a,d+1,u])))
        elif kind in ('MAX_CONSECUTIVE_DAYS','MAX_SHIFTS_IN_WINDOW'):
            window=p['max']+1 if kind=='MAX_CONSECUTIVE_DAYS' else p['window_days']
            cs=[Sum([work(a,d) for d in range(begin,begin+window)])<=p['max'] for a in ids for begin in range(h-window+1)]
        elif kind=='MAX_SHIFT_TYPE_COUNT':
            cs=[count(x[a,d,p['shift']] for d in range(h))<=p['max'] for a in selected]
        elif kind=='UNAVAILABLE':
            cs=[Not(x[a,d,t]) for a in selected for d in days for t in p.get('shifts',codes)]
        elif kind=='MIN_SHIFTS_TOTAL':
            cs=[Sum([work(a,d) for d in range(h)])>=p['min'] for a in selected]
        solver.add(Implies(guards[index],And(cs)))
    def check(indices):
        remaining=int((deadline-time.perf_counter())*1000)
        if remaining<=0: return None
        solver.set(timeout=max(1,min(check_ms,remaining)))
        chosen=set(indices)
        return solver.check(*[g if i in chosen else Not(g) for i,g in enumerate(guards)])
    all_indices=list(range(len(rules))); answer=check(all_indices)
    if answer==sat:
        model=solver.model(); result['status']='SAT'
        result['schedule_by_staff']={a:[next((t for t in codes if bool(model.eval(x[a,d,t],model_completion=True))),'-') for d in range(h)] for a in ids}
    elif answer==unsat:
        result['status']='UNSAT'; initial={str(g) for g in solver.unsat_core()}
        core=[i for i,g in enumerate(guards) if str(g) in initial]; complete=True
        minimize_end=min(deadline,time.perf_counter()+30)
        for i in list(core):
            if time.perf_counter()>=minimize_end: complete=False; break
            status=check([j for j in core if j!=i])
            if status==unsat: core.remove(i)
            elif status!=sat: complete=False
        relax=[]
        for i in core:
            status=check([j for j in all_indices if j!=i])
            relax.append(dict(rule_id=rules[i]['id'],feasible_if_removed=True if status==sat else False if status==unsat else None,status='SAT' if status==sat else 'UNSAT' if status==unsat else 'UNKNOWN'))
        result['conflict']=dict(rule_ids=[rules[i]['id'] for i in core],rules=[dict(id=rules[i]['id'],text=rules[i]['text']) for i in core],minimal=complete,relaxation=relax)
    else:
        result['status']='UNKNOWN'; result['reason']='Time budget exhausted' if answer is None else solver.reason_unknown()
    return finish()

def handler(event,context):
    remaining=max(1,context.get_remaining_time_in_millis()-3000) if context else 45000
    return solve(event,budget_ms=min(45000,remaining))
