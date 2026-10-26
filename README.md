# ProofRoster

Current runtime: **Amazon Nova Pro** (`apac.amazon.nova-pro-v1:0`) on Bedrock. The user authorized this alternative after Anthropic access remained blocked. Both agents use Nova Pro with identical settings. Sonnet references in the original specification describe the initial plan, not the completed benchmark. Submission artifacts are in `submission/`.

From AI-generated guesses to verified decisions. Two Strands agents receive the same English requirements and Bedrock model settings. The baseline has no tools; ProofRoster has exactly one tool, `solve_roster`, which privately invokes an AWS Lambda running Z3. An independent loop-based Python checker validates schedules against the canonical requirements.

## Quickstart (PowerShell, from this folder)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn dashboard.app:app --host 127.0.0.1 --port 8765
```

Open http://127.0.0.1:8765. Select **Local solver · no AI** to run without AWS. Local mode has no simulated baseline. **Live · Lambda only** invokes the deployed solver without an LLM. **Live · Bedrock + Lambda** runs both real agents. **Replay** shows a timestamp and the recorded source. A replay must exactly match the selected scenario and repair cap.

On this machine, `Start-ProofRoster.ps1` uses the already installed workspace environment. The saved settings contain identifiers only, never credentials. Authentication uses the existing AWS `default` profile; set `AWS_PROFILE` for a different profile. Do not paste credentials into code or chat.

`requirements.lock.txt` records the exact installed Windows development environment. Use `requirements.txt` for other platforms; the Lambda package installs only the separately pinned Linux Z3 dependency.

## Scenarios

- A: feasible, tight coverage, rest, work limits and leave. SAT, independently checked.
- B: two nurses required every night, Farid has no nights, everyone capped at five nights. The core R3/R10/R11 is deletion-minimal. Five eligible nurses × five nights gives 25, below the 28 required. The actual full-spec single-rule relaxation checks are saved.
- C: B with R11's night cap raised to six (or the user's selected cap). The default repair is SAT with zero checker violations.

R8's two leave calendars are separate atomic rules R8/R8b; see CORRECTIONS.md.

## AWS deployment

The app uses `ap-southeast-2`, Python 3.12 x86_64 Lambda, 1536 MB and a 60-second timeout. The Lambda has no public URL, needs only a scoped logging execution policy, and does not access Bedrock itself. The local caller needs Bedrock model invocation plus `lambda:InvokeFunction` on the deployed function. Deployment additionally needs scoped IAM role/pass-role, Lambda, CloudWatch Logs and S3 permissions.

```powershell
.\.venv\Scripts\python.exe -m scripts.preflight
.\.venv\Scripts\python.exe -m scripts.package_lambda
.\.venv\Scripts\python.exe -m scripts.deploy
.\.venv\Scripts\python.exe -m scripts.verify_scenarios --aws
```

Packaging pins Z3 and downloads its manylinux2014 x86_64 wheel for Python 3.12. Deployment stages the build in a private encrypted bucket with one-day artifact expiry; direct 30 MB Lambda upload was unreliable from this connection. CloudWatch retention is seven days. The bucket and function remain until explicitly removed; there is no provisioned concurrency or public hosting.

`aws-settings.json` is generated after preflight succeeds. Overrides: `PROOFROSTER_REGION`, `PROOFROSTER_FUNCTION`, `BEDROCK_MODEL_ID`, `AWS_PROFILE`. Both agents use the same configured Bedrock model, temperature 0, and explicit output-token limit. AWS SDK uses bounded timeouts and adaptive retries. For Nova, run preflight with `--model-id apac.amazon.nova-pro-v1:0`.

**AWS model access:** a minimal Converse test can succeed before streamed model access is fully available. If the agent reports missing Anthropic use-case details, complete the form in the Bedrock console and allow AWS's stated propagation time. The app surfaces the real error. No successful agent run or benchmark is claimed until it actually completes.

## Tests and recorded evidence

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m scripts.verify_scenarios
.\.venv\Scripts\python.exe -m scripts.run A
.\.venv\Scripts\python.exe -m scripts.run B
.\.venv\Scripts\python.exe -m scripts.run C
.\.venv\Scripts\python.exe -m scripts.benchmark_parallel --runs 10
```

`recorded/` contains computed solver outcomes, AWS deployment/model diagnostics, actual UI runs, screenshots and test reports. The benchmark saves every run and any errors. It stops with BLOCKED when account access needs action, and never replaces a failed baseline with invented output. Deterministic model tests exercise the actual Strands tool loop but are unit tests, not Bedrock benchmarks.

## Guarantee and limits

SAT means the submitted mathematical constraints admit the returned roster. The independent checker must also pass against the canonical original constraints, and the AI-generated specification must match. A mismatch withholds the verified claim even when Z3 says SAT. Comparisons ignore harmless ordering of rules, staff and shift definitions, but retain rule IDs, text and values. Raw input hashes still identify exactly what was submitted.

UNSAT cores are deletion-minimal only after every removal check completes; this is not a minimum-cardinality guarantee. Relaxation flags re-solve the entire specification minus each core rule. A timeout produces UNKNOWN, never SAT or UNSAT. Budgets are 10 seconds per check, 30 seconds for minimization, 45 seconds total, bounded further by Lambda's remaining time.

The checker imports no Z3 and implements all seven rule types independently. Rest is checked between consecutive-day shifts as specified; there are no constraints before or after the horizon. No fairness optimization, database, authentication or multi-user deployment is included. Bind the dashboard to localhost. The guarantee depends on the input requirements, the encoding, the checker and Z3's correctness; it is not a claim of general clinical scheduling safety.

## Demo sequence (under 3 minutes)

1. Show A with **Live · Bedrock + Lambda**. Inspect the baseline's real violations and ProofRoster's checker evidence and fidelity badge.
2. Show B's computed R3/R10/R11 conflict and the full-spec relaxation table.
3. Click repair, increase the night cap from 5 to 6, and run C. Show SAT and zero independent violations.
4. Expand the raw trace: the tool is reusable in another Strands planner. If using Replay, keep its timestamp/source banner visible throughout.

## Layout

`lambda_solver/` strict wire validation and Z3 encoding; `checker/` independent validation; `agent/` Strands + Bedrock and private Lambda tool; `scenarios/` canonical specs/prompts; `dashboard/` FastAPI SSE and buildless HTML/CSS/JS; `scripts/` deployment, verification, run recording and benchmark; `tests/` acceptance, malformed inputs, randomized differential cases, integration and API tests.
