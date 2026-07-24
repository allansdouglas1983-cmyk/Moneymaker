# Cross-market coherence — discretisation-stability amendment PROPOSAL v1

**Status: PROPOSAL ONLY — NOT IMPLEMENTED.** Produced under STAGE3-0006C-D-A2 §13 after verdict
`AMENDMENT_DISCRETISATION_STABILITY_REQUIRED`. No production YAML amendment is created by this
document; implementation requires a separate founder directive under the full amendment protocol.

## Evidence base (SOLVER_DEGENERACY_* artifacts, commit-pinned, duplicate-run byte-identical)

On the frozen disputed fixture (targets derived from (0.5, 0.5), BO3, line 22.5, domain
(0.35, 0.90)):

- Production is **DISCRETISATION_SENSITIVE**: the four predeclared lattices give root counts
  **G0 = 3, G1 = 4, G2 = 3, G3 = 4** (status `MULTIPLE_ROOTS` throughout), with representatives
  unpairable one-to-one across lattices under the existing strict 1e-3 relation.
- The reference is **REFERENCE_STABLE**: R0/R1/R2 all converge to the identical deepest point
  (0.5, 0.5) with determinant ≈ −0.0 (singular) → `NON_IDENTIFIABLE`.
- The finite diagnostics show one **extended sub-tolerance region**: all 15 pairwise straight
  paths between the six canonical production roots are sub-tolerance at every one of 257 samples
  (`CONNECTED_SUBTOLERANCE_PATH_OBSERVED` on every path); a residual-converged determinant zero
  is localised at p ≈ 0.5 on every path crossing the centre
  (`SINGULAR_POINT_ON_SUBTOLERANCE_PATH_OBSERVED`); `CONDITION_FAILURE_ON_SUBTOLERANCE_PATH_
  OBSERVED` and `LOW_RESIDUAL_REGION_EXTENDED` both hold. Labelled
  SYNTHETIC_FINITE_DIAGNOSTIC_EVIDENCE, not a continuum proof.
- Mechanism (candidate provenance): denser/shifted lattices place more clustered seeds along the
  same flat diagonal valley; each seed refines to a different sub-tolerance point ≥ 1e-3 apart;
  the count of such points — and hence the public root multiplicity — is a property of the seed
  layout, not of the mathematical target.

## Exact old behaviour

`identify` runs the single registered G0 scan (13-node `build_scan_axis`), refines the ranked
seeds, accepts every sub-tolerance point, canonically deduplicates (V2), and reports the
resulting count/status. On extended-valley systems the count (3 vs 4) and root locations depend
on the lattice, though each lattice is individually deterministic.

## Exact new behaviour (proposed)

1. The registered solve runs the existing G0 scan **unchanged** (identical numerics, identical
   candidates, identical V2 dedup).
2. A deterministic **stability check** additionally runs the identical production algorithm on a
   REGISTERED set of scan variants (proposed: exactly {G1 NESTED_DOUBLE_DENSITY,
   G2 HALF_CELL_PHASE_SHIFT} as predeclared in A2 §5 — **final variant set PENDING FOUNDER**).
3. Agreement rule (all existing machinery, no new tolerance): every variant must produce the
   same public status, the same root-cluster count, and a one-to-one pairing of representatives
   under the EXISTING strict Chebyshev `< _DEDUP_TOL` relation (the A2 §6 comparison, already
   implemented and tested in the diagnostic harness).
4. If all registered variants agree → emit the G0 result **byte-identically as today** (stable
   systems, including all six current V2 golden identify fixtures if verified so, are unaffected).
5. If any registered variant disagrees → the solve REFUSES with the existing public
   `NON_IDENTIFIABLE` and a structured INTERNAL reason `DISCRETISATION_UNSTABLE_ROOT_SET`
   (mirroring the A1 `AMBIGUOUS_ROOT_TOLERANCE_CHAIN` pattern; **no new public SolverStatus**,
   no public serialization change).

## Mathematical justification

A root count that changes under lattice refinement/translation on the same target is not a
set-defined property of the system; reporting it as `MULTIPLE_ROOTS` asserts multiplicity the
evidence cannot support. Conservative refusal under the existing `NON_IDENTIFIABLE` vocabulary is
exactly the semantics already chosen (and founder-ratified) for the A1 non-transitive-chain case:
when the root set is not well-defined, refuse rather than publish an artifact of discretisation.
The disputed fixture's valley carries a genuine Jacobian sign-change singularity at its centre,
so refusal also matches the reference's independent classification.

## Constants and machinery reused (no new numeric thresholds)

`_COARSE_N`, `build_scan_axis`, `rank_seed_nodes`, `_N_SEED`, `_CLUSTER_R`, `_refine`, Newton
seams, `_ROOT_TOL`, `_DEDUP_TOL` (strict), V2 `deduplicate_roots`, `classify_per_solve` /
`classify_overall`, `NON_IDENTIFIABLE`. Lattice constructions G1/G2 exactly as predeclared in A2
§5. **Genuinely new items, both PENDING FOUNDER:** (a) the registered variant set; (b) the
internal reason name `DISCRETISATION_UNSTABLE_ROOT_SET`. No new tolerance is introduced anywhere.

## Contract interactions

- **Public status mapping:** unchanged vocabulary; the refusal maps to `NON_IDENTIFIABLE`
  dominance exactly as A1 ambiguity does (per-solve and identify-level).
- **First-server:** the stability check runs per assignment inside the existing dual-solve;
  union semantics unchanged; `FIRST_SERVER_SENSITIVE_PENDING_THRESHOLD` untouched.
- **V2 root dedup:** untouched and reused verbatim for every variant.
- **Golden vintage policy:** V2 retained unmodified as the prior vintage; a V3
  (`SOLVER_GOLDEN_V3_DISCRETISATION_STABLE`) is minted post-implementation; a classified
  differential (expected classes: `EXPECTED_STATUS_CHANGE_DISCRETISATION_REFUSAL` only;
  `UNEXPECTED_CHANGE = 0`) is required.
- **Expected affected fixtures:** only extended-valley/degenerate systems (the disputed fixture
  and its class); every fixture whose variants agree is byte-identical — the six existing V2
  identify fixtures must be verified unaffected during implementation and any change classified.

## Cost note (for founder weighing)

The stability check multiplies solve cost by ≈ 1 + Σ(variant grid+refine cost)/G0 cost (≈ 3-4×
for {G1, G2}); the coherence engine is an offline synthetic research layer, so wall-clock is the
only cost. If this is unacceptable, the A2 verdict-E fallback (deterministic book-quality rules
instead of latent identification) remains available to choose instead.

## Required protocol on implementation (unchanged discipline)

Append-only YAML amendment (`cross-market-coherence-discretisation-stability-amendment-v1.yaml`);
red tests first (stability-agreement fixtures, disagreement-refusal fixtures incl. the frozen
disputed fixture, variant-lattice pins, internal-reason pin, no-public-schema-change pin);
property tests (variant-agreement determinism, permutation invariance, refusal monotonicity —
adding a disagreeing variant never un-refuses); hardened mutation micro-gates (variant
construction, agreement comparison, refusal mapping, wiring) with the standard survivor classes
and `approved_by: null`; V2→V3 differential with `UNEXPECTED_CHANGE = 0`; stop conditions
`STOP_CONTRACT_DRIFT` / `STOP_REFERENCE_DISAGREEMENT`; foreground-only; June remains prohibited
throughout — this amendment is synthetic-only and touches no market data, no outcomes, no
p_market_info, no V0.
