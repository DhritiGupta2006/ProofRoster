import asyncio
import json
import queue
import threading
import uuid
import time
from datetime import datetime,timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,ConfigDict,Field
from typing import Literal
from agent.aws_clients import ROOT,settings,invoke_solver
from agent.runner import run_baseline,run_proof,fidelity
from checker.validate import check_roster
from lambda_solver.solver import solve
from scenarios.catalog import make_spec,prompt_for

app=FastAPI(title='ProofRoster',docs_url='/api/docs')
jobs={}; active=threading.Lock()
class RunRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    scenario:Literal['A','B','C']='A'
    mode:Literal['aws','local','lambda','replay']='aws'
    night_cap:int=Field(default=6,ge=0,le=14)

@app.get('/')
def index(): return FileResponse(ROOT/'dashboard'/'index.html')

@app.get('/api/config')
def config():
    cfg=settings(); cfg.pop('profile',None)
    return {**cfg,'live_ready':bool(cfg['model_id'] and cfg['streaming_verified']),'replays':replay_list()}

@app.get('/api/scenarios/{key}')
def scenario(key:str,night_cap:int=6):
    if key not in 'ABC' or len(key)!=1 or not 0<=night_cap<=14: raise HTTPException(400,'Unknown scenario or cap')
    spec=make_spec(key,night_cap)
    return {'spec':spec,'prompt':prompt_for(spec)}

def replay_list():
    return [p.name for p in sorted((ROOT/'recorded').glob('run-*.json'))]

@app.get('/api/replays/{name}')
def saved_replay(name:str):
    if Path(name).name!=name or not name.startswith('run-') or not name.endswith('.json'): raise HTTPException(400,'Invalid replay name')
    path=ROOT/'recorded'/name
    if not path.is_file(): raise HTTPException(404,'Replay not found')
    return {**json.loads(path.read_text(encoding='utf-8')),'replay':True}

def worker(job_id,req):
    job=jobs[job_id]
    def emit(kind,data): job['events'].put({'event':kind,'data':data})
    try:
        spec=make_spec(req.scenario,req.night_cap)
        output={'scenario':req.scenario,'mode':req.mode,'model_id':settings()['model_id'] if req.mode=='aws' else None,'recorded_at':datetime.now(timezone.utc).isoformat(),'spec':spec,'changes':([{'rule_id':'R11','before':5,'after':req.night_cap,'meaning':'Maximum nights per person'}] if req.scenario=='C' else [])}
        emit('phase',{'message':'Starting '+req.mode+' run'})
        if req.mode=='replay':
            candidates=[]
            for p in (ROOT/'recorded').glob('run-*.json'):
                record=json.loads(p.read_text())
                if record['scenario']==req.scenario and fidelity(record['spec'],spec)['matches']: candidates.append(record)
            if not candidates: raise RuntimeError('No matching saved run. Run this scenario first.')
            output=max(candidates,key=lambda r:r['recorded_at']); output={**output,'replay':True}
        elif req.mode=='aws':
            try:
                output['baseline']=run_baseline(spec,emit); emit('baseline',output['baseline'])
            except Exception as exc:
                output['baseline']={'error':str(exc)}; emit('baseline',output['baseline'])
            emit('phase',{'message':'Running the agent with solve_roster'})
            output['proof']=run_proof(spec,emit)
        else:
            emit('phase',{'message':'Solving canonical spec directly; no AI baseline in this mode'})
            started=time.perf_counter()
            result=invoke_solver(spec) if req.mode=='lambda' else solve(spec)
            latency_ms=round((time.perf_counter()-started)*1000,2)
            report=check_roster(spec,result['schedule_by_staff']) if result['status']=='SAT' else None
            output['proof']={'source':'Direct AWS Lambda' if req.mode=='lambda' else 'Local Z3 (no AWS / no LLM)',
                'result':result,'fidelity':{**fidelity(spec,spec),'origin':'Canonical input supplied directly; not AI translation'},'checker':report,
                'verified':bool(report and report['valid']),'traces':[{'input':spec,'result':result,'latency_ms':latency_ms}]}
            output['baseline']={'unavailable':'This mode does not invoke an AI baseline.'}
        if req.mode!='replay':
            (ROOT/'recorded'/f'run-{job_id}.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
        job['result']=output; emit('complete',output)
    except Exception as exc:
        job['error']=str(exc); emit('error',{'message':str(exc)})
        failure={'recorded_at':datetime.now(timezone.utc).isoformat(),'scenario':req.scenario,'mode':req.mode,'error':str(exc),'partial_result':locals().get('output')}
        (ROOT/'recorded'/f'failed-run-{job_id}.json').write_text(json.dumps(failure,indent=2),encoding='utf-8')
    finally:
        job['done']=True; active.release()

@app.post('/api/runs')
def start_run(req:RunRequest):
    if not active.acquire(blocking=False): raise HTTPException(409,'A run is in progress. Please wait.')
    for key in list(jobs):
        if len(jobs)>100 and jobs[key]['done']: del jobs[key]
    job_id=uuid.uuid4().hex; jobs[job_id]={'events':queue.Queue(),'done':False}
    threading.Thread(target=worker,args=(job_id,req),daemon=True).start()
    return {'id':job_id}

@app.get('/api/runs/{job_id}')
def get_run(job_id:str):
    if job_id not in jobs: raise HTTPException(404,'Unknown run')
    job=jobs[job_id]
    return {k:v for k,v in job.items() if k!='events'}

@app.get('/api/runs/{job_id}/events')
async def events(job_id:str):
    if job_id not in jobs: raise HTTPException(404,'Unknown run')
    job=jobs[job_id]
    async def stream():
        while True:
            try:
                item=job['events'].get_nowait()
                yield f"event: {item['event']}\ndata: {json.dumps(item['data'])}\n\n"
            except queue.Empty:
                if job['done']: break
                yield ': heartbeat\n\n'; await asyncio.sleep(.25)
    return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

app.mount('/static',StaticFiles(directory=ROOT/'dashboard'),name='static')
