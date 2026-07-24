# STAGE3-0006C-C-REV1 — Solver Milestone C closure record

**Verdict: `MILESTONE_C_COMPLETE`.**

Milestone C extracted the solver's genuinely-existing Newton-polish semantics into named,
individually-testable seams **byte-for-byte identically**, under the revised, reality-bound
directive (REV1, which accepted the premise mismatch and withdrew the damping machinery).
No behaviour changed; no test was weakened; no damping was invented; Milestone D is NOT begun.
**No mutation survivor exists** in this milestone (229/229 killed), so there is nothing to approve;
`approved_by: null` stands wherever the field appears. The Milestone-B stable-sort survivor
remains unapproved per the founder's standing instruction.

*Procedural note:* the REV1 directive text arrived truncated mid-§5 (after the
`SOLVER_MILESTONE_C_PRECHANGE.json` filename). The executed scope is REV1 §1–§5 as received plus
the superseded directive's still-applicable machinery (red-tests-first, wiring, differential,
independent checks, micro-gates, artifacts, verification, return) minus everything REV1 §1
withdrew. No damping construct was created anywhere.

## Reality-bound findings (REV1 §1, recorded in the amended freeze)

`STEP_TOLERANCE_NOT_USED` · `DAMPING_SCHEDULE_NOT_USED` · `DAMPING_FACTOR_NOT_USED` ·
`MAXIMUM_DAMPING_ATTEMPTS_NOT_USED` · `MULTI_FACTOR_LINE_SEARCH_NOT_USED` ·
`PER_STEP_IMPROVEMENT_ACCEPTANCE_NOT_USED` · `FIRST_ACCEPTED_FACTOR_POLICY_NOT_USED`
(+ `DOMAIN_HANDLING_IS_CLAMP_PROJECTION`). Descriptive findings about the frozen implementation;
no placeholder production fields were added for any of them.

**§2 comment correction (representational only):** the `_NEWTON_ITERS` comment was corrected from
`bounded damped-Newton polish iterations` to `bounded undamped clamp-projected Newton polish
iterations`. Value 40 unchanged; no arithmetic, status, diagnostic or output changed.

## Seams extracted (`sport_tennis/coherence/solver_iteration.py`, new)

| REV1 §3 | seam | frozen rule preserved |
|---------|------|----------------------|
| 1 | `residual_norm2_within_tolerance` / `newton_converged` | `r2 <= tol*tol`, INCLUSIVE, residual-only; NaN never converges |
| 2 | `iteration_is_permitted` / `next_iteration_index` | `range(40)` semantics; +1 increment; bool/non-int refused |
| 3 | `propose_newton_step` → `NewtonStep2` | exact 2×2 Cramer, rows (MO,TG) × cols (p_A,p_B), subtracted deltas |
| 4 | `clamp_scalar` / `apply_step_clamped` | silent clamp projection; full step at factor 1.0; signed-zero & NaN passthrough frozen |
| 5 | `is_stagnant` | `abs(Δ) < 1e-15` strict, AND, both axes (named `_STAGNATION_TOL`, value unchanged) |
| 6 | wired one-step transition in `_refine` | while + seams, byte-identical to the frozen for-range loop |
| 7 | singularity | unchanged Milestone-B `is_singular` before every step |
| 8 | `prefer_newton_candidate` | final grid-vs-Newton, strict `<`, ties keep grid |
| 9 | exhaustion | loop ends after 40 iterations; **no exception**; no status remap |

`_solve_one`'s root acceptance also routes through `residual_norm2_within_tolerance` (same frozen
rule, single home). `_clamp` is a thin adapter over `clamp_scalar` so the pre-existing direct pin
(`test_clamp_exact`) is untouched. **No test was altered.** Milestone-B seams and
`rank_seed_nodes` untouched (`solver_scan.py` and `solver_contracts.py` sha256 identical to the
freeze). Closed contract introduced: `NewtonStep2` only — `ConvergencePolicy`/`IterationBudget`
were deliberately NOT created as stored config objects (the constants already have a single frozen
home in `solver.py`; wrapping them would add invented surface, contra REV1 §1).

## Byte-identity evidence (§16)

- **Golden oracle**: PASS byte-for-byte post-wiring (2 tests).
- **Frozen-loop differential** (`SOLVER_MILESTONE_C_DIFFERENTIAL.json`, digest `e6def3ed…`):
  a literal reimplementation of the frozen `_refine` (constants hardcoded from the freeze) vs
  production over 8 real fixtures — final `(p_a, p_b, r2)` **exactly equal 8/8**, `_residual`
  evaluation counts **equal 8/8** (identical iteration behaviour), and **all four termination
  reasons exercised**: CONVERGED, BUDGET_EXHAUSTED (exactly 40 iterations, raising nothing),
  STAGNANT, SINGULAR — the §14 non-convergence/exhaustion fixtures. 63 pure-seam literal samples,
  0 mismatches.
- **Independent checks** (§17): `iteration_reference.py` computes expected values from literal
  equations and exact Decimal Cramer only, imports nothing from `sport_tennis` (enforced by an
  AST architecture test); boundary sweeps + residual reconstruction (J·d ≈ F) all pass.
- 174 solver-touching/coherence tests green; ruff, mypy (incl. `--strict` on the new module),
  pylint W0613 clean; all 7 import-quarantine checks pass.

## Mutation micro-gates (§18, revised — damping gate withdrawn)

One hardened foreground session (isolated_exec harness; source restored & proven byte-identical;
audited clean): **229 specs, 229 killed, 0 survivors, 0 non-normal, 0 untested. Hardening
rounds: 0.**

| gate | seam | killed |
|------|------|-------:|
| 1 | convergence | 18 |
| 2 | iteration budget | 32 |
| 3 | Newton step + NewtonStep2 (incl. 2 frozen-decorator mutants) | 97 |
| 4 | clamp projection + step application | 38 |
| 5 | stagnation + final selection | 44 |
| 6 | transition/non-convergence | frozen-loop differential + golden (see disclosure) |

**Gate-6 disclosure:** the wired transition loop lives in `solver.py`, whose module-wide mutation
campaign was superseded (`SOLVER_MUTATION_PARTIAL_SESSION_CLOSURE.md`) and is not resumed per
REV1 §21. Its transition/non-convergence behaviour is proven here by the frozen-loop differential
(exact finals + equal call counts + all termination reasons) and the golden; its mutation evidence
is deferred to the final consolidated solver packet.

Reconciliation (`SOLVER_MILESTONE_C_RECONCILIATION.json`):
`missing = extra = duplicate = stale = unclassified = non-normal = untested = 0`. Survivor
classes: none. Behavioural survivors: 0. Unexplained survivors: 0.

## Artifacts

`SOLVER_MILESTONE_C_PRECHANGE.json` (amended, `29abda9b…`) · `SOLVER_MILESTONE_C_DIFFERENTIAL.json`
(`e6def3ed…`) · `SOLVER_MILESTONE_C_MUTATION_CONSOLIDATION.json` (`e68e8ff7…`) ·
`SOLVER_MILESTONE_C_CLASS_INDEX.md` (`c39756b9…`) · `SOLVER_MILESTONE_C_RECONCILIATION.json`
(`bd255be6…`) · `scripts/` (freeze/differential/consolidation builders + cosmic-ray config).

`FULL_VERIFY_PENDING_DEDICATED_FOREGROUND_TURN` — targeted verification only in this milestone;
full `make verify` remains reserved for the dedicated turn.

## Constraint confirmations

Milestone B unchanged · xmarket unchanged · no real June coherence run · no outcome read ·
`p_market_info` and V0 unchanged · no tip/EV/ROI/P&L/CLV/stake/order/paid action · £0 spend ·
no background execution; nothing left running · clean working tree · Milestone D not begun.
