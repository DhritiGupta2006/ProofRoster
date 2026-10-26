import copy
import json
import re
import time
from datetime import datetime, timezone
from strands import Agent, tool
from strands.models import BedrockModel
from botocore.config import Config
from .aws_clients import session, settings, invoke_solver
from lambda_solver.schema import TYPES, spec_hash
from lambda_solver.wire_schema import json_schema
from checker.validate import check_roster
from scenarios.catalog import prompt_for

COMMON='''You are a rostering assistant for a rural clinic. Follow the user's numbered rules exactly.
Use the given staff IDs and zero-based days. Explain your conclusion briefly and honestly.
'''
BASELINE='''Produce a short note and a fenced JSON object mapping staff_id to one shift code per day (D/E/N/-).
If the rules appear impossible, explain that and still provide your best attempted roster for independent validation.
'''
WITH_TOOL='''Convert the English request into the exact spec and call solve_roster. You have exactly one tool.
Never write or edit a roster yourself. Say 'satisfies all stated rules, independently verified' only if the tool
returns SAT and only subject to independent validation and faithful translation. On UNSAT explain only the returned
core rules and relaxation flags. On UNKNOWN say the solver could not decide. On INVALID_SPEC correct and retry at most 3 times.
Spec fields: horizon_days integer, shifts [{code,start_hour,duration_h}], staff [{id,name,skills}], rules [{id,text,type,params}].
Preserve original text verbatim and IDs, including R8b. skills enum doctor/nurse; shift enum D/E/N.
Rule vocabulary and required/optional parameter keys: '''+json.dumps({k:{'required':sorted(v[0]),'optional':sorted(v[1])} for k,v in TYPES.items()})+'''
For COVERAGE days is ALL or integer list. For staff selection use ALL or ID list. UNAVAILABLE days is integer list.
Unknown fields are rejected. MIN_REST_HOURS applies to consecutive-day shifts using absolute intervals.
Encode a person never working a particular shift as MAX_SHIFT_TYPE_COUNT with max=0 and the selected staff list.
Use UNAVAILABLE for leave on specified days. Do not substitute one rule type for another even when equivalent.
'''

def fidelity(submitted,canonical):
    differences=[]
    def walk(a,b,path):
        if type(a)!=type(b): differences.append(dict(path=path,submitted=a,canonical=b)); return
        if isinstance(a,dict):
            for key in sorted(a.keys()|b.keys()):
                if key not in a or key not in b: differences.append(dict(path=path+'.'+key,submitted=a.get(key),canonical=b.get(key)))
                else: walk(a[key],b[key],path+'.'+key)
        elif isinstance(a,list):
            if len(a)!=len(b): differences.append(dict(path=path+'.length',submitted=len(a),canonical=len(b)))
            for i,(x,y) in enumerate(zip(a,b)): walk(x,y,f'{path}[{i}]')
        elif a!=b: differences.append(dict(path=path,submitted=a,canonical=b))
    def normalized(value):
        value=copy.deepcopy(value)
        if not isinstance(value,dict): return value
        for key,identity in [('rules','id'),('staff','id'),('shifts','code')]:
            items=value.get(key)
            if isinstance(items,list) and all(isinstance(x,dict) and isinstance(x.get(identity),str) for x in items):
                value[key]=sorted(items,key=lambda x:x[identity])
        for member in value.get('staff',[]):
            if isinstance(member,dict) and isinstance(member.get('skills'),list): member['skills']=sorted(member['skills'],key=str)
        for rule in value.get('rules',[]):
            if not isinstance(rule,dict) or not isinstance(rule.get('params'),dict): continue
            for key in ('staff','days','shifts'):
                if isinstance(rule['params'].get(key),list): rule['params'][key]=sorted(rule['params'][key],key=str)
        return value
    walk(normalized(submitted),normalized(canonical),'$')
    return dict(matches=not differences,differences=differences,canonical_hash=spec_hash(canonical),submitted_hash=spec_hash(submitted))

def parse_roster(text):
    candidates=re.findall(r'```(?:json)?\s*(.*?)```',text,re.S)+[text]
    decoder=json.JSONDecoder()
    for item in candidates:
        for match in re.finditer(r'\{',item):
            try:
                value,_=decoder.raw_decode(item[match.start():])
                if isinstance(value,dict) and value and all(isinstance(v,list) for v in value.values()): return value
            except json.JSONDecodeError: pass
    raise ValueError('No parseable roster JSON')

def model():
    cfg=settings()
    if not cfg['model_id']: raise RuntimeError('Set BEDROCK_MODEL_ID or run scripts.preflight')
    return BedrockModel(model_id=cfg['model_id'],boto_session=session(),temperature=0,max_tokens=6000,streaming=True,
        boto_client_config=Config(connect_timeout=10,read_timeout=120,retries={'mode':'adaptive','total_max_attempts':3}))

def run_baseline(spec,emit=lambda *args:None):
    start=time.perf_counter(); events=[]
    def callback(**event):
        if event.get('data'): emit('token',dict(agent='baseline',text=event['data']))
    agent=Agent(model=model(),system_prompt=COMMON+BASELINE,tools=[],callback_handler=callback)
    text=str(agent(prompt_for(spec))); retries=0
    try: roster=parse_roster(text)
    except ValueError:
        retries=1; emit('retry',dict(agent='baseline',reason='Unparseable JSON'))
        text=str(agent('Return the roster as a fenced JSON object mapping each staff ID to a list of shift codes.'))
        try: roster=parse_roster(text)
        except ValueError: roster={}
    return dict(source='Bedrock / Strands, no tools',text=text,roster=roster,checker=check_roster(spec,roster),retries=retries,elapsed_ms=round((time.perf_counter()-start)*1000))

def run_proof(spec,emit=lambda *args:None):
    traces=[]; count=0
    @tool
    def solve_roster(spec: dict) -> dict:
        """Solve a strict roster specification through private AWS Lambda; return SAT, UNSAT, UNKNOWN or INVALID_SPEC.

        Args:
            spec: Object with horizon_days, shifts, staff and numbered rules in the supported vocabulary.
        """
        nonlocal count
        count+=1
        if count>3: raise RuntimeError('Maximum 3 solver calls reached')
        submitted=copy.deepcopy(spec); t=time.perf_counter()
        trace=dict(input=submitted,started_at=datetime.now(timezone.utc).isoformat())
        traces.append(trace); emit('tool_call',trace)
        result=invoke_solver(submitted)
        trace.update(result=result,latency_ms=round((time.perf_counter()-t)*1000))
        emit('tool_result',trace)
        return result
    solve_roster.tool_spec['inputSchema']['json']['properties']['spec']=json_schema()
    def callback(**event):
        if event.get('data'): emit('token',dict(agent='proof',text=event['data']))
    agent=Agent(model=model(),system_prompt=COMMON+WITH_TOOL,tools=[solve_roster],callback_handler=callback)
    text=str(agent(prompt_for(spec)))
    if not traces or 'result' not in traces[-1]: raise RuntimeError('Agent did not complete a solve_roster call')
    trace=traces[-1]; result=trace['result']; match=fidelity(trace['input'],spec)
    report=check_roster(spec,result['schedule_by_staff']) if result['status']=='SAT' else None
    verified=result['status']=='SAT' and match['matches'] and report['valid']
    return dict(source='Bedrock / Strands + private Lambda',text=text,result=result,traces=traces,fidelity=match,checker=report,verified=verified)
