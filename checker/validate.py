"""Independent direct-loop checker. Deliberately imports neither solver nor Z3."""

def check_roster(spec, roster):
    h=spec['horizon_days']; people=spec['staff']; shifts={s['code']:s for s in spec['shifts']}
    errors=[]; violations=[]; grid={}
    if not isinstance(roster,dict):
        errors.append(dict(path='$',message='Roster must be an object')); roster={}
    expected={s['id'] for s in people}
    for key in roster.keys()-expected: errors.append(dict(path=str(key),message='Unknown staff ID'))
    for s in people:
        a=s['id']; row=roster.get(a,[])
        if not isinstance(row,list): errors.append(dict(path=a,message='Expected shift list')); row=[]
        if len(row)!=h: errors.append(dict(path=a,message=f'Expected {h} cells, got {len(row)}'))
        grid[a]=[]
        for d in range(h):
            value=row[d] if d<len(row) else '-'
            if not isinstance(value,str) or value not in [*shifts,'-']:
                errors.append(dict(path=f'{a}[{d}]',message='Invalid code or multiple shifts per day')); value='-'
            grid[a].append(value)
    def add(rid,message,staff=None,day=None,shift=None):
        violations.append(dict(rule_id=rid,staff=staff,day=day,shift=shift,message=message))
    for r in spec['rules']:
        rid=r['id']; p=r['params']; kind=r['type']
        selected=list(grid) if p.get('staff','ALL')=='ALL' else p['staff']
        if kind=='COVERAGE':
            days=range(h) if p['days']=='ALL' else p['days']
            for d in days:
                assigned=[s for s in people if grid[s['id']][d]==p['shift'] and ('skill' not in p or p['skill'] in s['skills'])]
                if len(assigned)<p['min']: add(rid,f"Day {d}: {len(assigned)} eligible staff; requires {p['min']}",day=d,shift=p['shift'])
        elif kind=='MIN_REST_HOURS':
            for a,row in grid.items():
                for d in range(h-1):
                    if row[d]=='-' or row[d+1]=='-': continue
                    before=shifts[row[d]]; after=shifts[row[d+1]]
                    absolute_end=24*d+before['start_hour']+before['duration_h']
                    absolute_start=24*(d+1)+after['start_hour']
                    rest=absolute_start-absolute_end
                    if rest<p['hours']: add(rid,f"{rest}h rest; requires {p['hours']}h",a,d+1,row[d+1])
        elif kind=='MAX_CONSECUTIVE_DAYS':
            for a,row in grid.items():
                streak=0
                for d,value in enumerate(row):
                    streak=0 if value=='-' else streak+1
                    if streak>p['max']: add(rid,f"{streak} consecutive work days; cap {p['max']}",a,d,value)
        elif kind=='MAX_SHIFTS_IN_WINDOW':
            w=p['window_days']
            for a,row in grid.items():
                for start in range(h-w+1):
                    n=sum(v!='-' for v in row[start:start+w])
                    if n>p['max']: add(rid,f"Days {start}-{start+w-1}: {n} shifts; cap {p['max']}",a,start)
        elif kind=='MAX_SHIFT_TYPE_COUNT':
            for a in selected:
                n=grid[a].count(p['shift'])
                if n>p['max']: add(rid,f"{n} {p['shift']} shifts; cap {p['max']}",a,shift=p['shift'])
        elif kind=='UNAVAILABLE':
            days=range(h) if p['days']=='ALL' else p['days']
            for a in selected:
                for d in days:
                    if grid[a][d] in p.get('shifts',list(shifts)): add(rid,'Assigned during unavailability',a,d,grid[a][d])
        elif kind=='MIN_SHIFTS_TOTAL':
            for a in selected:
                n=sum(v!='-' for v in grid[a])
                if n<p['min']: add(rid,f"{n} total shifts; requires {p['min']}",a)
    return dict(valid=not errors and not violations,format_errors=errors,violations=violations,
        violation_count=len(violations),format_error_count=len(errors),normalized_roster=grid,
        evidence=[dict(rule_id=r['id'],text=r['text'],passed=not any(v['rule_id']==r['id'] for v in violations),violation_count=sum(v['rule_id']==r['id'] for v in violations)) for r in spec['rules']],
        assumption=dict(text='At most one shift per person per day',passed=not errors))
