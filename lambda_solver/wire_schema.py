"""Portable JSON Schema, with enums resolved from each submitted domain."""
def json_schema(spec=None):
    spec=spec or {}
    shift_codes=[s['code'] for s in spec.get('shifts',[]) if isinstance(s,dict) and isinstance(s.get('code'),str)] or ['D','E','N']
    staff_ids=[s['id'] for s in spec.get('staff',[]) if isinstance(s,dict) and isinstance(s.get('id'),str)]
    skills=sorted({v for s in spec.get('staff',[]) if isinstance(s,dict) for v in s.get('skills',[]) if isinstance(v,str)}) or ['doctor','nurse']
    def obj(properties,required=None): return {'type':'object','properties':properties,'required':required or list(properties),'additionalProperties':False}
    def integer(lo=0,hi=744):return {'type':'integer','minimum':lo,'maximum':hi}
    def enum(values):return {'type':'string','enum':values}
    def array(items,lo=1,hi=31):return {'type':'array','items':items,'minItems':lo,'maxItems':hi,'uniqueItems':True}
    def all_or_list(items):return {'oneOf':[{'const':'ALL'},array(items)]}
    person=enum(staff_ids) if staff_ids else {'type':'string','minLength':1,'maxLength':80}
    day=integer(0,spec.get('horizon_days',31)-1)
    types={
        'COVERAGE':obj({'shift':enum(shift_codes),'days':all_or_list(day),'skill':enum(skills),'min':integer()},['shift','days','min']),
        'MIN_REST_HOURS':obj({'hours':integer()}),
        'MAX_CONSECUTIVE_DAYS':obj({'max':integer()}),
        'MAX_SHIFTS_IN_WINDOW':obj({'window_days':integer(1,spec.get('horizon_days',31)),'max':integer()}),
        'MAX_SHIFT_TYPE_COUNT':obj({'shift':enum(shift_codes),'max':integer(),'staff':all_or_list(person)}),
        'UNAVAILABLE':obj({'staff':all_or_list(person),'days':all_or_list(day),'shifts':array(enum(shift_codes),hi=3)},['staff','days']),
        'MIN_SHIFTS_TOTAL':obj({'min':integer(),'staff':all_or_list(person)}),
    }
    rule={'oneOf':[obj({'id':{'type':'string','minLength':1},'text':{'type':'string','minLength':1},'type':{'const':kind},'params':params}) for kind,params in types.items()]}
    result=obj({'horizon_days':integer(1,31),
        'shifts':array(obj({'code':enum(['D','E','N']),'start_hour':integer(0,23),'duration_h':integer(1,24)}),hi=3),
        'staff':array(obj({'id':{'type':'string','minLength':1,'maxLength':80},'name':{'type':'string','minLength':1},'skills':array(enum(['doctor','nurse']),hi=2)}),hi=20),
        'rules':array(rule,lo=0,hi=60)})
    result['$schema']='https://json-schema.org/draft/2020-12/schema'
    return result
