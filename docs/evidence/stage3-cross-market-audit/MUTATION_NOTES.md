# STAGE3-0002 §17 — mutation results over the audit classification/sync/linkage code

Run: `run_mutation.py --report` (cosmic-ray) over the four core modules, killing suite
`tests/unit/xmarket`. Full survivor list: `MUTATION_REPORT.txt`.

| module | mutants | killed | survived | kill rate |
|---|---|---|---|---|
| `research/xmarket/parsers.py` (classification) | 200 | 159 | 41 | 79.5% |
| `research/xmarket/reconstruct.py` (synchronization/as-of) | 502 | 218 | 284 | 43.4% |
| `research/xmarket/linkage.py` (linkage) | 104 | 68 | 36 | 65.4% |
| `research/xmarket/redundancy.py` (co-timing) | 167 | 103 | 64 | 61.7% |
| **total** | **973** | **548** | **425** | **56.3%** |

## Scope and honesty

These are **outcome-blind research/audit modules**, not money modules. CLAUDE.md rule 1
reserves the 100%-non-equivalent-mutant-kill bar (with per-ID founder adjudication of
equivalents) for `l4b_fill/`, `l5_decision/`, `l5b_risk/`, `l6_broker/`, `l7_settle/`,
`l8_evidence/gates/`; the enforced CI `mutants-critical` path covers those, not
`research/xmarket`. This report is therefore **advisory** (`--report`, non-enforcing): it
is run because §17 asks for mutation over the classification/sync/linkage code, and its
result is reported faithfully rather than gated.

**A full Stage-2-style kill+classify pass over the 425 survivors is NOT performed in this
audit slice.** The audit's conclusions do not depend on it: the report is deterministic
(byte-identical digest across two runs) and the load-bearing invariants are unit-tested.

## The integrity-critical boundaries ARE pinned

Two survivors would have corrupted audit conclusions if the logic were wrong; both are now
killed by boundary tests, each verified by manual mutation (flip the operator → the new
test fails):

1. **Leakage boundary** (`reconstruct.py`, `if pt > cutoff_ms`): a message at
   `publish_time == commit_pt_ms` must be INCLUDED (rule is `pt <= cutoff`). Mutant
   `pt >= cutoff_ms` (which would drop the exactly-at-F0 message) →
   `test_message_exactly_at_cutoff_is_included` fails. **Killed.**
2. **Classification boundary** (`parsers.py`, `if max(magnitudes) <= _MAX_PLAUSIBLE_SET_HANDICAP`):
   a max |line| of exactly 3.0 must refuse (set handicap), 3.5 must accept (game). Mutant
   `<` → `test_game_handicap_classification_boundary_at_3_0` fails. **Killed.**

## Character of the residual survivors

The surviving mutants are dominated by:
- **Diagnostic book-quality arithmetic** in `reconstruct.book_quality` / `_ladder_prices`
  / `_tick_index` — spread-bps and tick summaries that are reported diagnostics, not
  decision inputs; the audit verdict does not turn on their exact value.
- **Audit-sensitivity threshold constants** (`redundancy` `_NON_REDUNDANT_FRACTION = 0.8`,
  window sizes; `_MIN_UPDATES_DEFAULT`) — `NumberReplacer` mutants on numbers the founder
  directive explicitly frames as *sensitivities, not policies*; pinning them to exact
  values is near-equivalent and not evidence-bearing.
- **Defensive branches** (isinstance/`bool` guards, empty-list early returns) that are
  belt-and-braces and not reachable from the corpus shapes.

Killing all of these to the money-module bar is a separate, sizeable follow-on and would be
warranted only if a future founder directive promotes these modules onto the enforced
mutation path (e.g. if the verdict later moves to a bounded implementation that builds on
them).
