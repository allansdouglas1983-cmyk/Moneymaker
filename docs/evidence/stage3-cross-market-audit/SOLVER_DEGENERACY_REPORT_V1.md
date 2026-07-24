# STAGE3-0006C-D-A2 — Synthetic root-degeneracy characterisation report

**Verdict: `AMENDMENT_DISCRETISATION_STABILITY_REQUIRED`** (the §12 decision rule, computed by
the pinned truth-table function from the recorded facts; duplicate-run byte-identical).

## The disputed fixture (frozen, test-pinned)

Targets derived from the symmetric pair (0.5, 0.5): match-odds target 0.5, total-games target
≈ 0.551875114440918, BO3 line 22.5, domain (0.35, 0.90). No market data, no outcomes.

## Production lattice sensitivity (§5/§6) — DISCRETISATION_SENSITIVE

| lattice | axis | roots | status |
|---------|------|-------|--------|
| G0 FROZEN_PRODUCTION | 13 | **3** (0.49626, 0.49967, 0.50434 diagonal) | MULTIPLE_ROOTS |
| G1 NESTED_DOUBLE_DENSITY | 25 | **4** (0.49481, 0.49670, 0.50003, 0.50335) | MULTIPLE_ROOTS |
| G2 HALF_CELL_PHASE_SHIFT | 13 | **3** (0.49626, 0.49967, 0.50361) | MULTIPLE_ROOTS |
| G3 DOUBLE_DENSITY_PHASE_SHIFT | 25 | **4** (0.49692, 0.50003, 0.50292, 0.50564) | MULTIPLE_ROOTS |

The public root COUNT changes (3 vs 4) and representatives fail one-to-one pairing under the
existing strict 1e-3 relation, purely from the scan-lattice choice on the same mathematical
target. The harness is fidelity-pinned: its G0 run reproduces production `identify()` float-equal.

## Reference resolution audit (§7) — REFERENCE_STABLE

R0 (n=27), R1 (n=53), R2 (n=53 phase-shifted): all three converge to the IDENTICAL deepest point
(0.5, 0.5) with determinant ≈ −0.0 (singular under the existing 5e-3 predicate) →
NON_IDENTIFIABLE at every resolution.

## Finite surface/path diagnostics (§8/§9) — SYNTHETIC_FINITE_DIAGNOSTIC_EVIDENCE

- Bounding box: p_a and p_b ∈ [0.49381, 0.50664] (all G/R roots + 1e-3 padding).
- 129×129 residual matrix: `LOW_RESIDUAL_REGION_EXTENDED = true` (many non-adjacent converged
  cells).
- All **15/15** pairwise straight paths between the six canonical production roots are
  sub-tolerance at every one of 257 samples: `CONNECTED_SUBTOLERANCE_PATH_OBSERVED` on every
  pair — the sampled roots live in ONE connected sub-tolerance valley.
- Determinant sign-change bisection localises a zero at p ≈ 0.5 on every centre-crossing path,
  with the residual CONVERGED at the zero: `SINGULAR_POINT_ON_SUBTOLERANCE_PATH_OBSERVED = true`.
- `CONDITION_FAILURE_ON_SUBTOLERANCE_PATH_OBSERVED = true`.

## Mechanism (§10 provenance audit)

Denser/shifted lattices place more ranked seeds along the same flat diagonal valley; each seed's
refinement lands at a different sub-tolerance point ≥ 1e-3 from its neighbours; V2 dedup then
correctly reports them as distinct clusters. The count of clusters is therefore a property of
seed COVERAGE of the valley (different seed coordinates and basin entries per lattice — recorded
per candidate in SOLVER_DEGENERACY_CANDIDATE_PROVENANCE_V1.json), not of the target. "Same
valley" is used here strictly in the §9-diagnostic sense: 15/15 connected sub-tolerance paths +
the extended-region matrix.

## Determinism (§14)

The complete diagnostic ran twice from clean temporary directories: **14/14 machine-readable
artifacts byte-identical** after removing only the isolated `generated_at_utc` field (runtimes
live in a separate non-compared sidecar). Proof: SOLVER_DEGENERACY_DUPLICATE_RUN_PROOF_V1.json.

## Integrity

Production source, root_dedup.py, V1 and V2 goldens byte-identical throughout (freeze digests =
HEAD digests; V2 golden suite re-run green). All analysis code is test-only (architecture-tested);
no June, no outcomes, no p_market_info, no V0, no spend.

## Proposal (§13 — return only, NOT implemented)

`docs/architecture/cross-market-coherence-degeneracy-amendment-proposal-v1.md`: a deterministic
production stability check over a REGISTERED scan-variant set (proposed {G1, G2}, PENDING
FOUNDER) with conservative refusal to the existing NON_IDENTIFIABLE (internal reason
DISCRETISATION_UNSTABLE_ROOT_SET, PENDING FOUNDER) when variants disagree; stable systems emit
the G0 result byte-identically; no new tolerance, no new public status; V3 golden vintage policy
included.
