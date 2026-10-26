import copy
import random
import pytest
from lambda_solver.solver import solve
from lambda_solver.schema import validate
from checker.validate import check_roster
from scenarios.catalog import make_spec, rule

def test_canonical_sequence():
    a=make_spec('A'); b=make_spec('B'); c=make_spec('C')
    ra=solve(a); rb=solve(b); rc=solve(c)
    assert ra['status']=='SAT',ra
    assert check_roster(a,ra['schedule_by_staff'])['valid']
    assert rb['status']=='UNSAT',rb
    assert rb['conflict']['minimal']
    assert len(rb['conflict']['rule_ids'])<=4
    assert sum(x['feasible_if_removed'] is True for x in rb['conflict']['relaxation'])>=2
    assert rc['status']=='SAT',rc
    assert check_roster(c,rc['schedule_by_staff'])['valid']

@pytest.mark.parametrize('first,second,gap',[('E','D',8),('N','D',0),('N','E',8),('D','D',16),('N','N',16)])
def test_absolute_intervals(first,second,gap):
    spec=make_spec(); spec['horizon_days']=2; spec['staff']=spec['staff'][:1]
    spec['rules']=[rule('rest','11 hours','MIN_REST_HOURS',hours=11)]
    report=check_roster(spec,{'asha':[first,second]})
    assert report['valid']==(gap>=11)

def test_known_bad_all_days():
    spec=make_spec(); grid={s['id']:['D']*14 for s in spec['staff']}
    report=check_roster(spec,grid)
    assert {'R2','R3','R6','R7','R8','R8b'}<=set(v['rule_id'] for v in report['violations'])

def test_malformed_missing_cells_still_checks_coverage():
    report=check_roster(make_spec(),{'asha':[['D','N']]})
    assert report['format_errors'] and report['violations']
    assert not report['valid']

@pytest.mark.parametrize('mutation',[lambda s:s.update(extra=1), lambda s:s['rules'][0]['params'].update(extra=1),lambda s:s['rules'][0]['params'].update(shift='X'),lambda s:s.update(horizon_days=True),lambda s:s['rules'][0]['params'].update(days=[True])])
def test_invalid_spec(mutation):
    spec=make_spec(); mutation(spec)
    assert solve(spec)['status']=='INVALID_SPEC'

def test_exported_json_schema():
    from jsonschema import Draft202012Validator
    from lambda_solver.wire_schema import json_schema
    spec=make_spec(); validator=Draft202012Validator(json_schema(spec))
    assert not list(validator.iter_errors(spec))
    bad=copy.deepcopy(spec);bad['rules'][0]['params']['shift']='X'
    assert list(validator.iter_errors(bad))
    bad=copy.deepcopy(spec);bad['staff'][0]['extra']=1
    assert list(validator.iter_errors(bad))

def test_timeout_is_unknown_not_unsat():
    result=solve(make_spec(),budget_ms=0)
    assert result['status']=='UNKNOWN'

def test_differential_200_random_specs():
    rng=random.Random(1234)
    for _ in range(200):
        spec=make_spec(); h=rng.randint(2,6); spec['horizon_days']=h
        spec['staff']=spec['staff'][:rng.randint(2,5)]; spec['rules']=[]
        people=[s['id'] for s in spec['staff']]
        spec['rules']=[rule('c','coverage','COVERAGE',shift=rng.choice('DEN'),days='ALL',min=rng.randint(0,3)),
          rule('r','rest','MIN_REST_HOURS',hours=rng.choice([0,8,11,16,24])),
          rule('s','streak','MAX_CONSECUTIVE_DAYS',max=rng.randint(1,h)),
          rule('w','window','MAX_SHIFTS_IN_WINDOW',window_days=rng.randint(1,h),max=rng.randint(0,h)),
          rule('t','night cap','MAX_SHIFT_TYPE_COUNT',staff='ALL',shift='N',max=rng.randint(0,h)),
          rule('u','leave','UNAVAILABLE',staff=[rng.choice(people)],days=[rng.randrange(h)]),
          rule('m','minimum','MIN_SHIFTS_TOTAL',staff='ALL',min=rng.randint(0,h))]
        result=solve(spec,check_ms=500,budget_ms=1000)
        if result['status']=='SAT':
            report=check_roster(spec,result['schedule_by_staff'])
            assert report['valid'],(spec,result,report)
