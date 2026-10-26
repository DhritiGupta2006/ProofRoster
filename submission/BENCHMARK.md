# Real paired-agent benchmark

Model: apac.amazon.nova-pro-v1:0

Status: COMPLETE

| Scenario | Attempts | Baseline valid | Tool verified SAT | Faithful UNSAT | Tool errors |
|---|---:|---:|---:|---:|---:|
| A | 10 | 0 | 10 | 0 | 0 |
| B | 10 | 0 | 0 | 10 | 0 |
| C | 10 | 0 | 10 | 0 | 0 |

Baseline format errors: 3/30 attempts. These remain in the denominator.

Full evidence: ../recorded/benchmark.json. UNSAT scenario B cannot have a valid roster; report conflict accuracy separately. The comparison is a small sample on fixed synthetic scenarios, not a general reliability guarantee.
