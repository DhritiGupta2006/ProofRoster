import copy
import io
import json
import time
from unittest.mock import patch
from fastapi.testclient import TestClient
from strands import Agent
from strands.models import Model
from agent.runner import fidelity,parse_roster,run_proof,run_baseline
from agent.aws_clients import invoke_solver
from scenarios.catalog import make_spec
from lambda_solver.solver import solve
from dashboard.app import app

def test_fidelity_does_not_confuse_solver_validity_with_translation():
    canonical=make_spec(); altered=copy.deepcopy(canonical)
    altered['rules'][0]['params']['min']=0
    report=fidelity(altered,canonical)
    assert not report['matches']
    assert report['differences'][0]['path']=='$.rules[0].params.min'

def test_json_parsing():
    assert parse_roster('note\n```json\n{"asha":["D"]}\n```')=={'asha':['D']}

def test_lambda_wire_contract():
    spec=make_spec();result=solve(spec)
    class Lambda:
        def invoke(self,**kwargs):
            assert json.loads(kwargs['Payload'])==spec
            assert kwargs['InvocationType']=='RequestResponse'
            return {'Payload':io.BytesIO(json.dumps(result).encode())}
    with patch('agent.aws_clients.client',return_value=Lambda()): assert invoke_solver(spec)==result

def test_dashboard_local_sse_and_replay():
    client=TestClient(app)
    assert client.get('/').status_code==200
    assert client.get('/static/app.js').status_code==200
    assert client.get('/api/scenarios/X').status_code==400
    assert client.post('/api/runs',json={'scenario':'X'}).status_code==422
    response=client.post('/api/runs',json={'scenario':'A','mode':'local'})
    assert response.status_code==200
    job_id=response.json()['id']
    with client.stream('GET',f'/api/runs/{job_id}/events') as stream:
        body=''.join(stream.iter_text())
    assert 'event: complete' in body
    output=client.get(f'/api/runs/{job_id}').json()['result']
    assert output['proof']['checker']['valid']
    response=client.post('/api/runs',json={'scenario':'A','mode':'replay'})
    job_id=response.json()['id']
    with client.stream('GET',f'/api/runs/{job_id}/events') as stream:
        body=''.join(stream.iter_text())
    assert '"replay": true' in body

class ScriptedAgent:
    """Exercises our integration boundary without claiming a real Bedrock run."""
    def __init__(self,**kwargs): self.kwargs=kwargs
    def __call__(self,prompt):
        if self.kwargs['tools']: self.kwargs['tools'][0](spec=make_spec())
        return '```json\n'+json.dumps({s['id']:['-']*14 for s in make_spec()['staff']})+'\n```'

def test_exactly_one_tool_and_tool_authoritative_output():
    constructions=[]
    def build(**kwargs): constructions.append(kwargs);return ScriptedAgent(**kwargs)
    with patch('agent.runner.Agent',side_effect=build),patch('agent.runner.model',return_value=None),patch('agent.runner.invoke_solver',side_effect=solve):
        baseline=run_baseline(make_spec());proof=run_proof(make_spec())
    assert constructions[0]['tools']==[]
    assert len(constructions[1]['tools'])==1
    assert constructions[1]['tools'][0].tool_name=='solve_roster'
    assert constructions[1]['tools'][0].tool_spec['inputSchema']['json']['properties']['spec']['additionalProperties'] is False
    assert not baseline['checker']['valid']
    assert proof['verified'] and proof['result']['schedule_by_staff']!=baseline['roster']

class ToolCallingModel(Model):
    def __init__(self): self.calls=0
    def update_config(self,**kwargs): pass
    def get_config(self): return {'context_window_limit':200000}
    async def structured_output(self,*args,**kwargs):
        raise NotImplementedError
        yield
    async def stream(self,messages,tool_specs=None,system_prompt=None,**kwargs):
        self.calls+=1
        yield {'messageStart':{'role':'assistant'}}
        if self.calls==1:
            assert [s['name'] for s in tool_specs]==['solve_roster']
            yield {'contentBlockStart':{'contentBlockIndex':0,'start':{'toolUse':{'toolUseId':'test-1','name':'solve_roster'}}}}
            yield {'contentBlockDelta':{'contentBlockIndex':0,'delta':{'toolUse':{'input':json.dumps({'spec':make_spec()})}}}}
            yield {'contentBlockStop':{'contentBlockIndex':0}}
            yield {'messageStop':{'stopReason':'tool_use'}}
        else:
            assert any('toolResult' in c for m in messages for c in m['content'])
            yield {'contentBlockDelta':{'contentBlockIndex':0,'delta':{'text':'The tool returned SAT.'}}}
            yield {'contentBlockStop':{'contentBlockIndex':0}}
            yield {'messageStop':{'stopReason':'end_turn'}}
        yield {'metadata':{'usage':{'inputTokens':1,'outputTokens':1,'totalTokens':2},'metrics':{'latencyMs':1}}}

def test_real_strands_tool_loop_with_deterministic_model():
    events=[]
    with patch('agent.runner.model',return_value=ToolCallingModel()),patch('agent.runner.invoke_solver',side_effect=solve):
        proof=run_proof(make_spec(),lambda kind,data:events.append(kind))
    assert proof['verified']
    assert 'tool_call' in events and 'tool_result' in events
    assert len(proof['traces'])==1

def test_fidelity_ignores_order_but_not_rule_content():
    spec=make_spec();reordered=copy.deepcopy(spec)
    reordered['rules'].reverse();reordered['staff'].reverse();reordered['shifts'].reverse()
    assert fidelity(reordered,spec)['matches']

def test_dashboard_saves_failed_aws_run_without_replay_success(tmp_path,monkeypatch):
    import importlib
    dashboard=importlib.import_module('dashboard.app')
    (tmp_path/'recorded').mkdir()
    monkeypatch.setattr(dashboard,'ROOT',tmp_path)
    def timeout(spec): raise RuntimeError('Test Lambda timeout')
    monkeypatch.setattr(dashboard,'invoke_solver',timeout)
    client=TestClient(app)
    response=client.post('/api/runs',json={'scenario':'A','mode':'lambda'})
    job_id=response.json()['id']
    with client.stream('GET',f'/api/runs/{job_id}/events') as stream:
        body=''.join(stream.iter_text())
    assert 'event: error' in body and 'event: complete' not in body
    saved=json.loads((tmp_path/'recorded'/f'failed-run-{job_id}.json').read_text())
    assert saved['error']=='Test Lambda timeout'
    assert not list((tmp_path/'recorded').glob('run-*.json'))
