# Solver partial mutation session — closure record (STAGE3-0006B §2)

**Reason for closure:** `SOURCE_REFACTOR_SUPERSEDES_MUTATION_SESSION`

This partial session is preserved as an **operational artifact only**. It is **NOT final gate
evidence** and no result in it is founder-approved. The solver source is being refactored
(STAGE3-0006B §5–§13) to reduce the mutation surface; a new set of bounded micro-gates against the
refactored source will produce the governed solver gate evidence. This closure is a **change in
mutation-testing strategy**, not a defect in the mathematical model.

## Exact session state

| field | value |
|-------|-------|
| session file | `scratchpad/cr_solver_hardened.sqlite` (preserved; NOT deleted) |
| session DB sha256 | `d8eee8f22d5e29918272af58c699cacc24aeb73360c5c8a15dfc74dff25b4163` |
| harness | hardened (`tools/run_hardened_mutation.sh` → `isolated_exec`-wrapped test-command) |
| total jobs | **1113** |
| completed jobs | **338** |
| pending jobs | **775** |
| NORMAL / KILLED | **253** |
| NORMAL / SURVIVED | **85** |
| non-normal (timeout / worker_error / incompetent) | **0** |
| untested (no work_result) | **775** |
| source under test | `sport_tennis/coherence/solver.py` blob `8eef77f395e6a66e9631c1e46196d864d0c9a022` (== HEAD; restored byte-identical after each interruption) |
| runtime environment | CPython 3.11.15, cosmic-ray 8.4.6, Linux |

Every completed job is `worker_outcome=NORMAL` (no timeout/worker-error/incompetent). Confirmed via
`tools/mutation_audit.py`.

## Per-job snapshot

Deterministic per-job status snapshot exported to
`SOLVER_MUTATION_PARTIAL_SESSION_JOBS.json` (1113 rows: 253 KILLED, 85 SURVIVED, 775 UNTESTED;
ordered by module, line, occurrence, operator).
- snapshot sha256: `ac2e7b40096a328c670abcc009feeca8f1deb93d3dd3a76c4e6b76db5ca629cc`

## Interruptions encountered

The unattended long run was killed repeatedly by the execution environment, none of which is a
solver-mathematics fault (see `MUTATION_RUNNER_INCIDENT_2026-07-22.md`,
`MUTATION_HARNESS_PROCESS_ISOLATION_DEFECT`):
1. an earlier unhardened solver exec died over a multi-hour idle gap and left `solver.py` mutated
   (restored byte-identical to HEAD `8eef77f`); that incomplete DB (`cr_solver_v2`, 626/1113) was
   already discarded;
2. the hardened solver run was interrupted by a **container restart** at 302/302 match + partial
   solver, then resumed to 338/1113, then interrupted again.

## Confirmations

- No result in this session was treated as founder-approved (`approved_by: null` throughout; no
  solver survivor packet was built from it).
- The partial database is **not** final gate evidence and will be superseded by micro-gates against
  the refactored solver.
- The database is preserved (not deleted).
- The closure is a mutation-testing strategy change, not a mathematical-model failure.
