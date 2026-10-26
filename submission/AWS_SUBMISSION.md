# ProofRoster: From plausible rosters to checked decisions

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

Both agents use `apac.amazon.nova-pro-v1:0` through Bedrock, with temperature 0 and the same English scenario prompt. The baseline has no tools; the upgraded agent has `solve_roster`. There are ten paired attempts per scenario. Raw responses, malformed rows, retries, tool arguments, results and timestamps are retained.

| Scenario | Attempts | Baseline valid | Tool verified SAT | Faithful UNSAT | Tool errors |
|---|---:|---:|---:|---:|---:|
| A | 10 | 0 | 10 | 0 | 0 |
| B | 10 | 0 | 0 | 10 | 0 |
| C | 10 | 0 | 10 | 0 | 0 |

Benchmark status: **COMPLETE**. Exact results are in `recorded/benchmark.json`. A baseline roster is valid only when the independent checker accepts it. For B, no valid roster exists, so the meaningful tool outcome is a faithful UNSAT explanation rather than a valid-roster count. A SAT output is counted as verified only when its canonical checker passes and its submitted specification matches. Errors and fidelity failures remain in the denominator.

Baseline format errors occurred in 3/30 completed attempts and are retained separately from rule violations. These are small-sample observations on three fixed scenarios, not a general reliability guarantee. Prompts and scenario numbers were not tightened in response to the final benchmark.

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
