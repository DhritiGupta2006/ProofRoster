# One tool, three kinds of evidence

```mermaid
flowchart LR
  P[Same English prompt] --> A[Baseline Strands agent\nNova Pro · no tools]
  P --> B[Upgraded Strands agent\nSame Nova Pro · one tool]
  B --> T[solve_roster]
  T --> L[Private AWS Lambda\nZ3 feasibility solver]
  L --> R[SAT roster / UNSAT core\nUNKNOWN / validation errors]
  A --> C[Independent Python checker]
  R --> C
  K[Canonical requirements] --> C
  K --> F[Specification fidelity comparison]
  T --> F
  C --> D[Local FastAPI dashboard\nEvidence + conflicts + repair]
  F --> D
  R --> D
```

The checker and fidelity comparison are dashboard infrastructure, not tools exposed to either agent. Only the upgraded agent can invoke `solve_roster`. Lambda is accessed using IAM; it has no public function URL. Recorded runs remain labelled REPLAY with their original timestamps.
