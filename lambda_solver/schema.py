"""Strict bounded wire schema, using only the standard library."""
import hashlib
import json

TYPES={
 'COVERAGE':({'shift','days','min'},{'skill'}),
 'MIN_REST_HOURS':({'hours'},set()),
 'MAX_CONSECUTIVE_DAYS':({'max'},set()),
 'MAX_SHIFTS_IN_WINDOW':({'window_days','max'},set()),
 'MAX_SHIFT_TYPE_COUNT':({'shift','max','staff'},set()),
 'UNAVAILABLE':({'staff','days'},{'shifts'}),
 'MIN_SHIFTS_TOTAL':({'min','staff'},set()),
}

def spec_hash(spec):
    return hashlib.sha256(json.dumps(spec,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def validate(spec):
    errors=[]
    def err(path,msg): errors.append(dict(path=path,message=msg))
    def obj(value,required,optional,path):
        if not isinstance(value,dict): err(path,'Expected object'); return False
        for k in required-value.keys(): err(path+'.'+k,'Required field')
        for k in value.keys()-required-optional: err(path+'.'+k,'Unknown field')
        return not (required-value.keys())
    def integer(value,lo,hi,path):
        if type(value) is not int or not lo<=value<=hi: err(path,f'Expected integer in [{lo}, {hi}]'); return False
        return True
    if not obj(spec,{'horizon_days','shifts','staff','rules'},set(),'$'): return errors
    h=spec['horizon_days']
    if not integer(h,1,31,'$.horizon_days'): return errors
    shifts=spec['shifts']; staff=spec['staff']; rules=spec['rules']
    if not isinstance(shifts,list) or not 1<=len(shifts)<=3: err('$.shifts','Expected 1-3 shifts'); return errors
    codes=set()
    for i,s in enumerate(shifts):
        p=f'$.shifts[{i}]'
        if not obj(s,{'code','start_hour','duration_h'},set(),p): continue
        if s['code'] not in ('D','E','N') or s['code'] in codes: err(p+'.code','Expected unique D/E/N code')
        else: codes.add(s['code'])
        integer(s['start_hour'],0,23,p+'.start_hour'); integer(s['duration_h'],1,24,p+'.duration_h')
    if not isinstance(staff,list) or not 1<=len(staff)<=20: err('$.staff','Expected 1-20 staff'); return errors
    ids=set(); skills=set()
    for i,s in enumerate(staff):
        p=f'$.staff[{i}]'
        if not obj(s,{'id','name','skills'},set(),p): continue
        if not isinstance(s['id'],str) or not s['id'] or len(s['id'])>80 or s['id'] in ids: err(p+'.id','Expected unique nonempty ID')
        else: ids.add(s['id'])
        if not isinstance(s['name'],str) or not s['name']: err(p+'.name','Expected name')
        if not isinstance(s['skills'],list) or not s['skills'] or any(v not in ('doctor','nurse') for v in s['skills']) or len(set(s['skills']))!=len(s['skills']): err(p+'.skills','Expected unique doctor/nurse skills')
        else: skills.update(s['skills'])
    if not isinstance(rules,list) or len(rules)>60: err('$.rules','Expected up to 60 rules'); return errors
    seen=set()
    for i,r in enumerate(rules):
        path=f'$.rules[{i}]'
        if not obj(r,{'id','text','type','params'},set(),path): continue
        if not isinstance(r['id'],str) or not r['id'] or r['id'] in seen: err(path+'.id','Expected unique rule ID')
        else: seen.add(r['id'])
        if not isinstance(r['text'],str) or not r['text']: err(path+'.text','Expected original rule text')
        if not isinstance(r['type'],str) or r['type'] not in TYPES: err(path+'.type','Unknown rule type'); continue
        req,opt=TYPES[r['type']]; p=r['params']
        if not obj(p,req,opt,path+'.params'): continue
        for k in ('min','max','hours','window_days'):
            if k in p: integer(p[k],1 if k=='window_days' else 0, h if k=='window_days' else 744,path+'.params.'+k)
        if 'shift' in p and (not isinstance(p['shift'],str) or p['shift'] not in codes): err(path+'.params.shift','Unknown shift')
        if 'skill' in p and (not isinstance(p['skill'],str) or p['skill'] not in skills): err(path+'.params.skill','Unknown skill')
        for k,allowed in [('staff',ids),('days',set(range(h))),('shifts',codes)]:
            if k not in p: continue
            val=p[k]
            if val=='ALL' and k in ('staff','days'): continue
            if not isinstance(val,list) or not val or any(type(v) is not int if k=='days' else not isinstance(v,str) for v in val): err(path+'.params.'+k,'Expected nonempty list'); continue
            if any(v not in allowed for v in val) or len(set(val))!=len(val): err(path+'.params.'+k,'Unknown or duplicate entry')
    return errors
