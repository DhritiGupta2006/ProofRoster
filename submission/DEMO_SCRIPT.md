# Demo narration (target 2 minutes 30 seconds)

0:00–0:15 — This is ProofRoster. My starting Strands agent could write a clinic roster, but a plausible table is not evidence that every rule holds.

0:15–0:45 — Here is the same feasible request with the same Nova Pro model. The baseline has no tools. Its actual checker findings are shown at left. The upgraded agent calls exactly one tool: solve_roster. Inspect its actual fidelity badge and independent checker result; describe the displayed outcome, including any mismatch.

0:45–1:10 — Expand the evidence panel. Rest, leave, staffing skills and work limits are checked against the original canonical requirements. Expand a baseline violation to show the exact day and person. The roster at right comes directly from Lambda, not copied from the model's answer.

1:10–1:50 — Now the impossible case. Two nurses per night require 28 nurse-nights. Farid cannot work nights, and five other nurses can each work at most five. The actual returned core is R3, R10 and R11. This table re-solves the full specification after removing each rule; these are computed flags, not suggestions invented by the model.

1:50–2:15 — Repair changes only the night cap from five to six. The canonical solver returns SAT and the independent checker finds zero violations. Show the actual selected agent recording and fidelity result; do not call a mismatched translation verified.

2:15–2:30 — Bedrock, Strands, private Lambda and Z3 provide the new capability. An independent checker and a visible translation comparison bound the claim. This pattern can support other planners that need checked decisions, conflicts and repairs.

Recording note: if using saved runs, say 'These are recorded real AWS runs' and keep the REPLAY timestamp banner visible. Do not narrate a benchmark number unless it matches BENCHMARK.md.
