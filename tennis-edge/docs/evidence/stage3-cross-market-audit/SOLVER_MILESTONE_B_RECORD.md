# STAGE3-0006C-B — Solver Milestone B closure record

**Verdict: `MILESTONE_B_COMPLETE`** (with the disclosed §5/§7 vocabulary divergence preserved
explicitly per §7's escape clause — NOT `STOP_CONTRACT_DRIFT`).

Milestone B extracted and wired the identification solver's inner numerics into named,
individually-testable seams **byte-for-byte identically**, reducing the mutation surface of the
money-critical `solver.py` so future gates target small, fast seam modules instead of the
~2-hour full-solver run. No behaviour changed; no test was weakened; exception→status behaviour is
untouched. **No founder approval of any mutation survivor** (`approved_by: null` throughout).
Milestones C and D are NOT begun. £0 spend; synthetic-only; no outcome read; no p_market_info /
V0 change; staged and import-quarantined from execution/pricing/V0.

## Seams extracted (`sport_tennis/coherence/solver_scan.py`, new)

| directive | seam | note |
|-----------|------|------|
| §4 | `build_scan_axis(lo, hi, n)` | coarse scan axis; byte-identical to the inline comprehension |
| §5 | — | **no independent seam** (see §5/§7 divergence); folded into §7 |
| §6 | `ResidualVector2.sum_of_squares` (Milestone A contract) wired into `_r2` | residual 2-norm |
| §7 | `rank_seed_nodes(grid, n_seed, cluster_r)` | residual-norm node ranking + Chebyshev clustering |
| §8a | `perturbation_points(p, e, lo, hi)` | clamped central-difference points |
| §8b | `jacobian_from_differences(...) → Jacobian2x2` | difference quotients; determinant via contract |
| §9 | `is_singular(det, tol)` + `Jacobian2x2.condition_scale` | singularity / conditioning |

`solver.py` wiring: `_r2` → `ResidualVector2.sum_of_squares`; `_jacobian_matrix` builds the
`Jacobian2x2` via the §8 seams; `_jacobian_det` and the Newton step use `Jacobian2x2.determinant`;
singularity tests use `is_singular`. **`_jacobian` keeps its exact 4-tuple `(d11,d21,d12,d22)`
signature as a thin adapter** so the pre-existing direct pin (`test_solver_units_fast::
test_jacobian_exact`) is unchanged by the extraction — no test was altered to fit the refactor.

## §5/§7 vocabulary divergence (disclosed)

The directive's ScanCell four-corner residuals (§5) and SIGN_CHANGE candidate regions (§7) do NOT
describe this solver. It evaluates the residual **2-norm at each grid node** (`grid[i][j]`) and
**ranks/clusters the lowest-norm nodes** as refinement seeds — no cells, no sign-change
classification. Implementing §5/§7 literally would REPLACE the algorithm → `STOP_CONTRACT_DRIFT`.
Per §7's explicit escape clause the actual rule is preserved verbatim in `rank_seed_nodes`; §5 has
no independent seam and micro-gate 5 (`Jacobian2x2.determinant` orientation) stands in its place as
the sixth money-critical gate. Recorded in `SOLVER_MILESTONE_B_PRECHANGE.json` (`finding_5_7`).

## Byte-identity evidence

- **Golden oracle** (`test_solver_golden.py`, 2 cases: `derived_targets` ×60 + `identify` ×6):
  PASS byte-for-byte after wiring.
- **Independent semantic-equivalence check** (`SOLVER_MILESTONE_B_DIFFERENTIAL.json`): 290
  deterministic samples across all five seams compared by EXACT float equality to literal
  recomputation of the pre-refactor inline expressions — **0 mismatches**.
- Full solver / reference-independence / immutability suites green; `ruff`/`mypy`/`pylint W0613`
  clean; coherence import-quarantine (7 checks) still OK.
- Source restored + proven byte-identical to HEAD after every mutation run
  (`tools/run_hardened_mutation.sh`; audited clean by `tools/mutation_audit.py --require-clean`).
- `solver_contracts.py` content sha256 unchanged from the freeze
  (`de9e9e72598bc2770f361a1e82e0a28bc51f5e73097e7a43f7aa916db031ce6d`).

## Mutation gate (§13/§14)

Two hardened foreground sessions, both audited clean (all NORMAL, 0 untested, 0 non-normal):

| module | specs | killed | survived |
|--------|------:|-------:|---------:|
| `solver_scan.py` | 227 | 226 | 1 |
| `solver_contracts.py` | 197 | 197 | 0 |
| **total** | **424** | **423** | **1** |

**One survivor**, classified `STABLE_SORT_TERTIARY_KEY_ALGEBRAIC_EQUIVALENT`
(`SOLVER_MILESTONE_B_SCAN_SURVIVORS.json`, `approved_by: null`): a `NumberReplacer` on the tertiary
sort-key index `t[2]` in `rank_seed_nodes`. The sort input is generated in strictly lexicographic
`(i, j)` order and Python's sort is stable, so the tertiary key never reorders anything relative to
`(t[0], t[1])`; the two surviving replacements (`t[2]→t[1]`, `t[2]→0`) produce byte-identical output
for **every** grid (no grid can distinguish them), and the only other replacement (`t[2]→3`) raises
`IndexError` → KILLED. **Unkillable equivalent, not a test gap** — a strong exact proof preferred
over a vague high-kill claim (§12).

Hardening rounds: **1** (three behavioural tests added, killing 14 of the original 15 survivors;
no assertion weakened). Reconciliation (`SOLVER_MILESTONE_B_RECONCILIATION.json`):
`missing=extra=duplicate=stale=unclassified=nonnormal=untested=0`, `all_zero_discrepancies=true`.

## Artifacts

`SOLVER_MILESTONE_B_PRECHANGE.json` · `SOLVER_MILESTONE_B_DIFFERENTIAL.json` ·
`SOLVER_MILESTONE_B_MUTATION_CONSOLIDATION.json` · `SOLVER_MILESTONE_B_CLASS_INDEX.md` ·
`SOLVER_MILESTONE_B_RECONCILIATION.json` · `SOLVER_MILESTONE_B_SCAN_SURVIVORS.json` (+ scan class
index / reconciliation) · `scripts/` (configs, classification, differential + consolidation
builders). All reproducible; nothing left running.
