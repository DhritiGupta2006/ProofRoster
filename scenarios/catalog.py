"""Canonical requirements. Agents receive English prompts, never these specs."""
import copy
import json
from pathlib import Path

NAMES = ['Asha', 'Bala', 'Chitra', 'Dev', 'Esha', 'Farid', 'Gita', 'Hari']

def rule(rid, text, kind, **params):
    return dict(id=rid, text=text, type=kind, params=params)

def make_spec(scenario='A', night_cap=6):
    spec = dict(horizon_days=14,
        shifts=[dict(code=c, start_hour=h, duration_h=8) for c,h in [('D',7),('E',15),('N',23)]],
        staff=[dict(id=n.lower(), name=n, skills=['doctor' if i<2 else 'nurse']) for i,n in enumerate(NAMES)],
        rules=[
            rule('R1','At least 2 staff on D every day.','COVERAGE',shift='D',days='ALL',min=2),
            rule('R2','At least 1 staff on E every day.','COVERAGE',shift='E',days='ALL',min=1),
            rule('R3','At least 1 nurse on N every day.','COVERAGE',shift='N',days='ALL',skill='nurse',min=1),
            rule('R4','At least 1 doctor on D every day.','COVERAGE',shift='D',days='ALL',skill='doctor',min=1),
            rule('R5','At least 11 hours rest between consecutive-day shifts.','MIN_REST_HOURS',hours=11),
            rule('R6','At most 5 consecutive working days per person.','MAX_CONSECUTIVE_DAYS',max=5),
            rule('R7','At most 5 shifts in every rolling 7-day window per person.','MAX_SHIFTS_IN_WINDOW',window_days=7,max=5),
            rule('R8','Chitra unavailable on days 3, 4, 5 (zero-based).','UNAVAILABLE',staff=['chitra'],days=[3,4,5]),
            rule('R9','Everyone works at least 6 shifts in total.','MIN_SHIFTS_TOTAL',staff='ALL',min=6),
            rule('R10','Farid works no night shifts.','MAX_SHIFT_TYPE_COUNT',staff=['farid'],shift='N',max=0),
            rule('R8b','Esha unavailable on days 9, 10 (zero-based).','UNAVAILABLE',staff=['esha'],days=[9,10]),
        ])
    # R8 is split into two atomic constraints because UNAVAILABLE has a single day set.
    if scenario in ('B','C'):
        spec['rules'][2]=rule('R3','At least 2 nurses on N every day.','COVERAGE',shift='N',days='ALL',skill='nurse',min=2)
        cap=5 if scenario=='B' else night_cap
        spec['rules'].append(rule('R11',f'At most {cap} night shifts per person over the horizon.','MAX_SHIFT_TYPE_COUNT',staff='ALL',shift='N',max=cap))
    return spec

def prompt_for(spec):
    lines=['Create a clinic roster. Day 0 is Monday. Horizon: '+str(spec['horizon_days'])+' days.',
           'At most one shift per person per day. Off is -. Shifts: '+json.dumps(spec['shifts']),
           'Staff IDs, names and skills: '+json.dumps(spec['staff']),
           'Preserve the following rule IDs and original text. Day numbers are zero-based.']
    lines += [r['id']+': '+r['text'] for r in spec['rules']]
    return '\n'.join(lines)

def write_scenarios():
    from lambda_solver.wire_schema import json_schema
    root=Path(__file__).parent
    (root/'spec.schema.json').write_text(json.dumps(json_schema(),indent=2),encoding='utf-8')
    for key in 'ABC':
        spec=make_spec(key)
        (root/f'{key}.json').write_text(json.dumps(spec,indent=2),encoding='utf-8')
        (root/f'{key}.txt').write_text(prompt_for(spec),encoding='utf-8')

if __name__=='__main__':
    write_scenarios()
