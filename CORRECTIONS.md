# Approved revisions and implementation decisions

On October 27, the user authorized an alternative model to finish the benchmark. Both agents now use Amazon Nova Pro (`apac.amazon.nova-pro-v1:0`) through Bedrock, with temperature 0. Strands, the single Lambda solver tool and independent checking are unchanged. Claude results are not claimed. The first Nova smoke test found an equivalent but differently encoded Farid night ban; strict fidelity correctly withheld verification. The extraction instructions now require zero shift-type caps for never-working-a-shift rules, before the final benchmark.

1. Both the Z3 encoder and independent checker calculate absolute end and start hours for consecutive-day shifts, including overnight shifts. Tests explicitly cover E→D, N→D, N→E, D→D and N→N.
2. Canonical scenarios are solved before agent integration. A is SAT. B is UNSAT with deletion-minimal core R3/R10/R11. All three full-spec single-rule removals are SAT. C, with night cap raised from 5 to 6, is SAT. Results are computed, not assumed.
3. The dashboard has an evidence panel with each rule's pass/fail state, baseline violation locations, actual UNSAT core, full-spec relaxation results, and the specific change from B to C.
4. Solver validity and specification fidelity are separate. A faithful translation plus SAT plus a passing checker is required for the verified badge. The UI renders the tool's roster rather than parsing the agent's explanation.

The original R8 combines different leave dates for two people, while the fixed UNAVAILABLE vocabulary accepts one shared day set. It is split into R8 (Chitra days 3–5) and R8b (Esha days 9–10). The prompt and canonical spec contain the same separate atomic rules. No leave dates changed.

AWS region is ap-southeast-2, per the user's later instruction. The dashboard stays local. AWS MCP's us-east-1 endpoint is unrelated to the application's region. The minimal model test discovered `au.anthropic.claude-sonnet-4-5-20250929-v1:0` in the account. It uses an Australian inference profile.

The original 4:30 PM IST build target was already past when implementation resumed after AWS setup. Competition time conversion: 1 PM PDT October 26 corresponds to 1:30 AM IST October 27; this document does not independently confirm the event's deadline.
