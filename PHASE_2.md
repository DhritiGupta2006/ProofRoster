# ProofRoster: Phase 2 Specification

**Deadline check (important):** 1:00 PM PDT is 8:00 PM UTC, which is **1:30 AM IST on Oct 27**, not 5:30 PM IST. 5:30 PM IST would be 5:00 AM PDT. The page you pasted says 1:00 PM PDT / 8:00 PM UTC, but confirm on the Rules tab. The plan below leaves ~11 hours but puts a **draft submission at 5:30 PM IST** as insurance, in case the page is wrong or editing closes early.

---

## 1. Architecture and stack

```
Dashboard (local web UI)  <-SSE->  FastAPI backend (local, Python 3.12)
                                      |-- Agent A "Baseline": Strands + Bedrock, tools=[]
                                      |-- Agent B "ProofRoster": Strands + Bedrock, tools=[solve_roster]
                                      |         '-- boto3 lambda.invoke --> AWS Lambda (Z3)
                                      '-- Independent Checker (pure Python, no LLM, no Z3)
```

| Decision | Choice |
|---|---|
| Region | us-east-1 (Bedrock and Lambda together) |
| Model | One Claude Sonnet-class model on Bedrock, `[MODEL_ID]` confirmed in the console. Same model, temperature 0, for both agents |
| Agent framework | Strands Agents SDK, Python |
| New tool | `solve_roster`, a Strands `@tool` wrapping a private Lambda invoke (IAM, no public URL) |
| Lambda | Python 3.12, x86_64, 1536 MB, 60 s timeout, `z3-solver` pinned |
| Dashboard | FastAPI + static HTML/CSS/vanilla JS, SSE for live traces. No frontend framework |
| Hosting | Everything runs locally except Lambda and Bedrock. The video is the public demo |
| Deploy | AWS CLI script. Lambda role: basic execution only |

**Exactly one new tool:** Agent B's tool list is `[solve_roster]` and nothing else. The checker is dashboard infrastructure that the agent cannot call.

---

## 2. MVP scope

**In:**
- Two agents, same model, same user prompt. System prompts differ only in the tool-use rules.
- Three fixed scenarios (Section 6), each runnable live.
- Independent checker with per-violation detail.
- Dashboard with split view, tool trace, conflict panel, and a labelled **Replay** mode.
- Baseline benchmark script (10 runs per scenario).

**Out:** optimization or fairness objectives, auth, database, multi-user support, free-form rule types beyond the vocabulary, hosting the dashboard publicly.

**Cut line:** if you are behind schedule at 6:30 PM IST, drop dashboard polish before dropping the checker or the benchmark.

---

## 3. Domain model (fixed)

- Horizon: 14 days (day 0 = Monday). Shifts: **D** 07:00–15:00, **E** 15:00–23:00, **N** 23:00–07:00 (8 h each). `-` means off.
- Staff (8): Asha (doctor), Bala (doctor), Chitra, Dev, Esha, Farid, Gita, Hari (nurses).
- **Built-in assumption (not a rule, shown in UI):** at most one shift per person per day.

---

## 4. Constraint vocabulary (7 types)

Every rule has: `id` (R1…), `text` (original English), `type`, `params`.

| Type | Params | Meaning |
|---|---|---|
| `COVERAGE` | shift, days (`"ALL"` or list), skill (optional), min | At least `min` staff (with `skill` if given) on that shift on those days |
| `MIN_REST_HOURS` | hours | Gap between consecutive-day shifts at least `hours`, computed from shift times |
| `MAX_CONSECUTIVE_DAYS` | max | No one works more than `max` days in a row |
| `MAX_SHIFTS_IN_WINDOW` | window_days, max | In any rolling window, each person works at most `max` shifts |
| `MAX_SHIFT_TYPE_COUNT` | shift, max, staff (`"ALL"` or list) | Cap on how many of a shift type a person works over the horizon |
| `UNAVAILABLE` | staff, days, shifts (optional) | Person cannot work those days/shifts |
| `MIN_SHIFTS_TOTAL` | min, staff (`"ALL"` or list) | Minimum shifts per person over the horizon |

Rest-hour computation (so ChatGPT doesn't improvise): gap = (next day's start + 24) − (this shift's start + 8). With 11 h required, this forbids E→D, N→D and N→E on consecutive days.

---

## 5. Tool contract

**Input `solve_roster(spec)`:**
`horizon_days`, `shifts[]` (code, start_hour, duration_h), `staff[]` (id, name, skills[]), `rules[]` as in Section 4. Strict JSON schema with enums on `type`, `shift` and `skill`. Unknown fields are rejected.

**Output:**

| Field | Present when | Content |
|---|---|---|
| `status` | always | `SAT` / `UNSAT` / `UNKNOWN` (timeout) / `INVALID_SPEC` |
| `solve_ms`, `spec_hash` | always | Timing and a hash of the submitted spec |
| `schedule_by_staff` | SAT | `{staff_id: ["D","-","N",...]}`, 14 entries each |
| `conflict.rule_ids` + `conflict.rules[{id,text}]` | UNSAT | The core |
| `conflict.minimal` | UNSAT | `true` only if the deletion pass completed (see below) |
| `conflict.relaxation[{rule_id, feasible_if_removed}]` | UNSAT | Real re-solve of the **full spec** minus each core rule |
| `errors[{path,message}]` | INVALID_SPEC | Lets the agent self-correct and retry |

**Solver design (Lambda):**
1. One Bool `x[s][d][t]` per staff/day/shift, plus one guard Bool per rule. Assert `guard_i → rule_i constraints`.
2. Check with all guards as assumptions. If UNSAT, take `unsat_core()`.
3. **Deletion-based minimization:** try dropping each core rule. If the rest is still UNSAT, drop it permanently. Mark `minimal=true` only if every rule was tested within the time budget (10 s per check, 30 s total).
4. Relaxation: re-solve the whole spec without each core rule.

The guarantee is relative to the submitted spec and to Z3's correctness. Say this plainly in the write-up.

---

## 6. Scenarios (canonical specs stored in repo, not LLM-generated)

Prompts are plain English with numbered rules (R1…) so conflicts map back to rule text.

**A. "Feasible but tight"**: R1 D≥2 daily; R2 E≥1; R3 N≥1 nurse; R4 ≥1 doctor on D daily; R5 rest ≥11 h; R6 ≤5 consecutive days; R7 ≤5 shifts per 7 days; R8 Chitra off days 3–5, Esha off days 9–10; R9 everyone ≥6 shifts; R10 Farid never works nights.

**B. "Impossible"**: A with R3 changed to *≥2 nurses every night*, plus new *R11: max 5 nights per person*. R10 stays. Hand check: Farid is out, so 5 nurses × 5 = 25 < 28 nurse-nights. Expected core is {R3, R10, R11}.

**C. "Repair"**: continuation of B. After the UNSAT, the user picks a relaxation (e.g. raise the night cap to 6) and the agent re-solves.

**These numbers are my design and are not yet solver-verified.** Acceptance tests ChatGPT must pass before anything else is built:
- A returns SAT. B returns UNSAT with a minimal core of ≤4 rules, ideally the three above.
- At least two of the core rules show `feasible_if_removed = true`.
- C returns SAT after the chosen relaxation.

If a test fails, **adjust the scenario numbers, not the results.**

---

## 7. Checker (the credibility piece)

- Pure Python, separate module, **no z3 import**, written as direct loops over the grid (not a translation of the Z3 encoding).
- Checks each canonical rule plus the one-shift-per-day assumption. Returns `[{rule_id, staff, day, shift, message}]`.
- Always checks against the **canonical** spec, so an LLM that mis-extracts rules is caught instead of rewarded.
- Malformed baseline rows (wrong length or invalid codes) are reported separately as format errors. Missing cells count as `-`, so coverage violations still show.
- **Self-tests:** hand-built rosters with known violations, plus differential testing: ~200 random small specs where every Z3 SAT output must pass the checker. Any mismatch means a bug in one of them.

---

## 8. Agents

- **Baseline:** system prompt as rostering assistant for a rural clinic. Output a short note plus a fenced JSON roster `{staff_id: [14 codes]}`. One retry on unparseable JSON, logged.
- **ProofRoster:** same prompt plus rules: convert rules into the spec exactly (keep the R-ids), call `solve_roster`, never write or edit a schedule yourself, claim "satisfies all rules" **only** on `SAT`, on `UNSAT` explain using **only** the returned core rules and relaxation flags, on `INVALID_SPEC` fix and retry (max 3), on `UNKNOWN` say so.
- The dashboard renders Agent B's roster **from the tool result**, not from the LLM's text, which avoids transcription errors.
- Capture tool calls and results via Strands callbacks/hooks (ChatGPT should check current docs for the exact API). Show the **real** JSON in the trace.
- **Spec fidelity badge:** diff the agent's submitted spec against the canonical one and display "matches" or the differences.

---

## 9. Dashboard (judge-facing)

Single page, dark/light-neutral, minimal text:
1. **Header:** scenario tabs (A / B / C) and Run button.
2. **Rules panel:** numbered English rules, each with a status chip (✓ satisfied / ✗ violated / ⚑ in conflict).
3. **Split view:** "Without tool" vs "With solve_roster". Each has an 8×14 grid colored by shift, violating cells outlined red, a large violation count, and a verdict line.
4. **Tool trace strip:** the call, latency, status, and spec fidelity badge, with collapsible raw JSON.
5. **Conflict panel (B/C):** core rules highlighted, a relaxation table with real flags, and the re-solve result.
6. **Footer:** "Scored by an independent checker: not the LLM, not Z3."
7. **Replay mode:** loads saved runs, with a visible "REPLAY, recorded [timestamp]" banner. Use it only as a safety net for the video, never as the primary demo.

---

## 10. AWS setup and prerequisites

- AWS account with Bedrock access enabled for `[MODEL_ID]` in us-east-1, **verified in the first 15 minutes**. This is the biggest unknown.
- Local credentials permitting `bedrock:InvokeModel` (and streaming) and `lambda:InvokeFunction` on the one function.
- Build the Lambda zip with `pip install --platform manylinux2014_x86_64 --only-binary=:all: --target`. If the zip exceeds 50 MB, upload via a temporary S3 bucket.
- Pre-record a warm-up invoke before filming (cold start imports Z3).

---

## 11. Implementation blueprint (for ChatGPT)

Each step has an acceptance check. Don't advance until it passes.

1. **Repo and env:** folders `lambda_solver/`, `agent/`, `checker/`, `scenarios/`, `dashboard/`, `scripts/`, `recorded/`. ✔ `import strands, boto3, fastapi` works; `aws sts get-caller-identity` and a Bedrock test call succeed.
2. **Scenario files:** canonical specs and prompt texts for A, B, C. ✔ Rule IDs line up between prompt and spec.
3. **Checker + self-tests.** ✔ Known-bad rosters give the expected violations.
4. **Lambda solver locally:** validation, encoding, guard Bools, core, minimization, relaxation. ✔ A is SAT, B is UNSAT with the core, and the SAT output passes the checker.
5. **Differential test** (checker vs solver). ✔ Zero mismatches.
6. **Package and deploy Lambda.** ✔ Live invoke returns the same results as local.
7. **Strands tool wrapper + both agents + prompts.** ✔ CLI run of A shows baseline with violations and ProofRoster with SAT and 0 violations.
8. **Run B and C via the agent.** ✔ UNSAT with the real core, then SAT after the relaxation.
9. **Benchmark:** 10 baseline runs per scenario, results saved with timestamps. ✔ Report honestly. If the baseline passes often, tighten the scenario rules rather than hide it.
10. **Backend (SSE) + dashboard.** ✔ All three scenarios run end to end from the UI.
11. **Save one replay set** from a real good run.
12. **Hardening:** error states (Bedrock throttle, Lambda timeout) shown cleanly, and a README with a 3-command quickstart.

---

## 12. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Z3 won't import in Lambda | Build with the manylinux flags above. One fallback only: container image |
| Bedrock model access or throttling | Verify in minute 15. Retry with backoff. Replay set as video safety net |
| Baseline accidentally passes | Benchmark first. Tighten scenario rules. Never fake failures |
| Agent mis-extracts the spec | Strict schema, R-id echo, fidelity badge, checker uses canonical spec |
| Core isn't what I predicted | Acceptance tests in Section 6. Change numbers, not outputs |
| Minimization too slow | Time budgets plus `minimal=false` labelling |
| Checker and solver share a bug | Separate implementations plus differential tests |
| Overclaiming | Wording: "satisfies all stated rules, independently verified" and "no valid roster exists under these rules". Never "proven correct" |

---

## 13. Competition-focused additions (all cheap)

- **Benchmark stat** in the write-up: "baseline: X/10 valid; ProofRoster: 10/10, 0 violations."
- **Repair loop:** UNSAT → real relaxation flags → re-solve. This is the differentiator.
- **Reusable pattern section:** "drop this `@tool` and this Lambda into any Strands planner agent."
- **Limits section:** what the guarantee covers and what it doesn't. Judges tend to trust this.
- **Video storyboard (<3 min):** 0:00–0:20 problem. 0:20–1:00 baseline fails (live count). 1:00–1:40 same prompt with tool, 0 violations. 1:40–2:30 impossible case, conflict, repair. 2:30–2:55 reuse and wrap-up.

---

## 14. Timeline (IST, today)

| Time | Work |
|---|---|
| 14:30–15:00 | Prereqs, Bedrock access, repo (steps 1–2) |
| 15:00–16:30 | Checker, Lambda logic, local tests (3–5) |
| 16:30–17:15 | Deploy, agents, CLI runs (6–8) |
| **17:30** | **Draft submission** (text and repo, video placeholder) |
| 17:30–19:30 | Dashboard (10) |
| 19:30–20:15 | Benchmark, replay set, hardening (9, 11–12) |
| 20:15–21:30 | Record and edit video |
| 21:30–22:30 | Write-up, README, upload video publicly |
| 22:30–23:30 | Final submit, verify links in an incognito window |
| 23:30–01:30 | Buffer |

---

**Honest assessment:** the design is sound, but I haven't run the solver. The scenario numbers and my predicted core are reasoned, not verified, and Step 4 will settle that. The biggest risks are Bedrock access and Z3 packaging, so both are checked first.

**Please approve, or send changes.** I won't start Phase 3 until you do.