"""Write submission artifacts from actual benchmark evidence, never estimated scores."""
import json
from pathlib import Path
from agent.aws_clients import ROOT,settings

CHALLENGE='https://builder.aws.com/build/hackathons/2e275689-b202-316e-93b8-10cd6d6d1e4a/weekend-challenge-give-your-agent-a-tool'

def main():
    out=ROOT/'submission';out.mkdir(exist_ok=True)
    bench=json.loads((ROOT/'recorded'/'benchmark.json').read_text())
    summary=bench.get('summary',{})
    rows=['| Scenario | Attempts | Baseline valid | Tool verified SAT | Faithful UNSAT | Tool errors |','|---|---:|---:|---:|---:|---:|']
    for key in 'ABC':
        s=summary.get(key,{})
        rows.append('| '+key+' | '+' | '.join(str(s.get(k,'Pending')) for k in ['attempted','baseline_valid','proof_verified_sat','proof_faithful_unsat','proof_errors'])+' |')
    table='\n'.join(rows)
    malformed=sum(bool(r.get('baseline',{}).get('checker',{}).get('format_errors')) for r in bench['records'])
    attempts=len(bench['records'])
    report=f'''# ProofRoster: From plausible rosters to checked decisions

## Short description

One new solver tool gives a Strands scheduling agent the ability to produce independently checked rosters, explain conflicting requirements, and test a repair on AWS.

## The agent I started with

The starting agent was a roster-writing assistant built with the Strands Agents SDK and Amazon Bedrock. It could read numbered English requirements and generate a day/evening/night schedule, but it had no tools. Its grid could look complete while missing coverage, leave, rest or work-limit constraints. The starting baseline is preserved as `run_baseline`, with an empty tool list.

## The one new tool

I added exactly one agent-callable tool: `solve_roster`. It sends the agent's structured interpretation to a private AWS Lambda function running Z3. The tool returns SAT with a schedule, UNSAT with a conflict, UNKNOWN on timeout, or structured validation errors. The checker, dashboard and fidelity comparison are infrastructure; they are not additional agent tools.

The missing capability was deciding whether these constraints can coexist. A better-looking answer does not solve that problem. Constraint solving does.

## What changed

The demonstration has three fixed scenarios. A is feasible but tight. B requires two nurses every night, prohibits Farid from nights, and caps each person at five nights. The remaining five nurses can provide at most 25 of the required 28 nurse-nights. Z3 independently returns the actual conflict R3/R10/R11. C changes the cap from five to six and re-solves.

The Lambda verifies the entire remaining specification after removing each conflict rule. All three single-rule removals are feasible in the canonical AWS checks. The conflict is deletion-minimal, not a claim of minimum cardinality.

## Same model, same request, real measurements

Both agents use `{bench['model_id']}` through Bedrock, with temperature 0 and the same English scenario prompt. The baseline has no tools; the upgraded agent has `solve_roster`. There are ten paired attempts per scenario. Raw responses, malformed rows, retries, tool arguments, results and timestamps are retained.

{table}

Benchmark status: **{bench['status']}**. Exact results are in `recorded/benchmark.json`. A baseline roster is valid only when the independent checker accepts it. For B, no valid roster exists, so the meaningful tool outcome is a faithful UNSAT explanation rather than a valid-roster count. A SAT output is counted as verified only when its canonical checker passes and its submitted specification matches. Errors and fidelity failures remain in the denominator.

Baseline format errors occurred in {malformed}/{attempts} completed attempts and are retained separately from rule violations. These are small-sample observations on three fixed scenarios, not a general reliability guarantee. Prompts and scenario numbers were not tightened in response to the final benchmark.

The model changed from planned Claude Sonnet to Amazon Nova Pro after Anthropic access was blocked. This change was authorized before the final benchmark, applied equally to both agents, and is disclosed here. These are Nova results, not Claude results. The initial Nova smoke run used a mathematically equivalent but differently encoded night ban; strict fidelity withheld its verified label. The final benchmark uses clarified extraction instructions and retains that earlier smoke record separately.

## Three layers of evidence

1. Z3 solves the submitted structured constraints.
2. A separate pure-Python checker uses direct loops to check the roster against the canonical requirements. It imports no Z3. Rest uses absolute shift start/end hours, including overnight shifts.
3. Specification fidelity compares what the agent submitted with the canonical specification. A valid solution to the wrong interpretation does not receive a verified badge.

The dashboard shows rule-by-rule evidence, baseline violation locations, the conflict and full-spec relaxation table, the exact night-cap change, and raw tool JSON. It renders the tool's schedule rather than transcribing the model's prose. Saved runs show a REPLAY banner and recording timestamp.

## AWS and reusable architecture

Local FastAPI dashboard → Strands + Bedrock → one tool → private Lambda + Z3. The Lambda runs Python 3.12 on x86_64, with 1536 MB memory and a 60-second timeout in ap-southeast-2. Its role permits scoped logging. It has no public function URL. The local caller invokes Lambda through IAM. The pinned Z3 Linux wheel is packaged separately from local development dependencies.

To reuse this pattern, replace the scheduling vocabulary with another bounded decision schema, keep a narrow `@tool` wrapper, return machine-readable outcomes, and independently validate against the source requirements. The useful upgrade is the ability to admit impossibility and support a concrete repair.

## Validation and limits

The test suite covers scenario acceptance, known bad schedules, malformed grids, strict schema, overnight rest, timeout behavior, the Strands tool loop, API/SSE/replay, and 200 randomized small specifications whose SAT schedules must pass the independent checker. Live Lambda checks reproduce A SAT, B UNSAT and C SAT.

This is a synthetic scheduling demonstration, not a clinical deployment. It has no fairness optimization, authentication, database or pre/post-horizon constraints. The guarantee is relative to the submitted requirements, the encoding and checker implementations, and Z3's correctness. A timeout is UNKNOWN. A fidelity mismatch is visible. I do not claim a general proof of clinical safety.

## Demo and source fields

- Public video URL: **requires upload of the prepared demo video before submission**.
- Public source URL: **requires a public repository or source archive link**.
- Local source archive: `ProofRoster-source.zip`.
- Local video and screenshots: see the submission folder and recorded evidence.

## AI assistance disclosure

Built with Codex assistance for implementation, debugging, tests, UI and this draft. Both runtime agents use Amazon Nova Pro via Bedrock. The benchmark reports generated outputs and actual tool/checker results.
'''
    (out/'AWS_SUBMISSION.md').write_text(report,encoding='utf-8')
    (out/'BENCHMARK.md').write_text('# Real paired-agent benchmark\n\nModel: '+bench['model_id']+'\n\nStatus: '+bench['status']+'\n\n'+table+f'\n\nBaseline format errors: {malformed}/{attempts} attempts. These remain in the denominator.\n\nFull evidence: ../recorded/benchmark.json. UNSAT scenario B cannot have a valid roster; report conflict accuracy separately. The comparison is a small sample on fixed synthetic scenarios, not a general reliability guarantee.\n',encoding='utf-8')
    (out/'benchmark-summary.csv').write_text('scenario,attempted,baseline_valid,tool_verified_sat,tool_faithful_unsat,tool_errors,fidelity_matches\n'+'\n'.join(key+','+','.join(str(summary.get(key,{}).get(k,'')) for k in ['attempted','baseline_valid','proof_verified_sat','proof_faithful_unsat','proof_errors','fidelity_matches']) for key in 'ABC')+'\n')
    (out/'SUBMIT_CHECKLIST.md').write_text(f'''# Submission handoff

Target: [AWS Weekend Challenge: Give your Agent a Tool]({CHALLENGE}).

The page lists October 26, 2026 at 20:00 UTC, equivalent to October 27 at 01:30 IST. The page's Live label does not replace the deadline. Check the actual submission form before assuming entries remain open.

1. Review AWS_SUBMISSION.md and BENCHMARK.md against recorded/benchmark.json.
2. Upload the prepared demo to a public video host. Put that public URL in the challenge's demo field. A local video path is not a public URL. Keep it under three minutes and keep the REPLAY banner visible for recorded runs.
3. Publish the source to a repository or shareable source location; no repository or public source URL was supplied in this chat. The local source archive is prepared.
4. Sign in to your AWS Builder Center profile, join the challenge if eligible, and use the project submission form. Fill title, description, demo and source fields from this package. Review the official rules and your own eligibility. No age/country/employee eligibility is inferred here.
5. This package has not been submitted or publicly published. The user's request was to prepare submissions.

The current DEV Week 4 theme is Ghost in the Machine. ProofRoster was not designed around that theme; do not claim it as a qualifying spooky/remembrance project without an actual fit. A general project write-up is included, rather than inventing partner integrations or competition eligibility.
''',encoding='utf-8')
    (out/'DEMO_SCRIPT.md').write_text('''# Demo narration (target 2 minutes 30 seconds)

0:00–0:15 — This is ProofRoster. My starting Strands agent could write a clinic roster, but a plausible table is not evidence that every rule holds.

0:15–0:45 — Here is the same feasible request with the same Nova Pro model. The baseline has no tools. Its actual checker findings are shown at left. The upgraded agent calls exactly one tool: solve_roster. Inspect its actual fidelity badge and independent checker result; describe the displayed outcome, including any mismatch.

0:45–1:10 — Expand the evidence panel. Rest, leave, staffing skills and work limits are checked against the original canonical requirements. Expand a baseline violation to show the exact day and person. The roster at right comes directly from Lambda, not copied from the model's answer.

1:10–1:50 — Now the impossible case. Two nurses per night require 28 nurse-nights. Farid cannot work nights, and five other nurses can each work at most five. The actual returned core is R3, R10 and R11. This table re-solves the full specification after removing each rule; these are computed flags, not suggestions invented by the model.

1:50–2:15 — Repair changes only the night cap from five to six. The canonical solver returns SAT and the independent checker finds zero violations. Show the actual selected agent recording and fidelity result; do not call a mismatched translation verified.

2:15–2:30 — Bedrock, Strands, private Lambda and Z3 provide the new capability. An independent checker and a visible translation comparison bound the claim. This pattern can support other planners that need checked decisions, conflicts and repairs.

Recording note: if using saved runs, say 'These are recorded real AWS runs' and keep the REPLAY timestamp banner visible. Do not narrate a benchmark number unless it matches BENCHMARK.md.
''',encoding='utf-8')
    (out/'PROJECT_FIELDS.json').write_text(json.dumps({'title':'ProofRoster — From Plausible Rosters to Checked Decisions','short_description':'One new Lambda solver tool upgrades a Strands agent with independently checked schedules, real conflict explanations and a repair loop.','built_with':['Amazon Bedrock','Amazon Nova Pro','Strands Agents SDK','AWS Lambda','Z3','FastAPI'],'demo_url':None,'source_url':None,'demo_file':'submission/ProofRoster-demo.webm','demo_duration_seconds':99,'demo_type':'Captioned real AWS replay; no audio narration','benchmark_status':bench['status'],'published':False},indent=2))
    print(out)

if __name__=='__main__':main()
