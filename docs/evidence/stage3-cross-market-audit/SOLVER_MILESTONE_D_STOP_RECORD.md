# STAGE3-0006C-D-REV1 — Milestone D stop record

**Verdict: `STOP_ROOT_DEDUP_CONTRACT_GAP`** (mandated by §4 + §9 + §21; stopped BEFORE any
production edit — no root-set extraction, no contract, no seam, no classification code was
written).

## §1 precondition — RESOLVED first (finding A)

**`STRUCTURALLY_UNREACHABLE_FROM_VALIDATED_PUBLIC_SOLVER`** — `NONFINITE_PASSTHROUGH_INCIDENTAL`
is resolved. Full proof: `SOLVER_MILESTONE_D_NONFINITE_AUDIT.json`
(`sha256:d8f9ee99e00d1510…`), 14-point call-path audit + 17 injection tests
(`test_solver_nonfinite_reachability.py`, committed `30155aa`). Four-layer invariant chain:

1. **Boundary refusal** — `validate_targets` / `validate_domain` / `_validate_line` refuse every
   non-finite public input (NaN Decimal line included).
2. **Finite arithmetic** — the entire residual/Jacobian chain contains exactly TWO divisions,
   both guarded (`_deuce_tail_first_win`: `total < _EPS → 0.5`; deuce closed form: `p²+q² ≥ 0.5`);
   no transcendentals; bounded DP sums/products; `check_normalized` explicitly refuses non-finite
   pmf mass; Jacobian denominators provably non-zero; Newton deltas bounded (det ≥ 1e-10 gate).
3. **Evaluation refusal** — injection proof: a non-finite candidate coordinate cannot even be
   residual-evaluated; `check_normalized` raises a typed `CoherenceMathError`
   (refusal-by-exception, NOT silent passthrough).
4. **Root gating** — `residual_norm2_within_tolerance` and `prefer_newton_candidate` are False
   for non-finite norms: no non-finite value can reach Root construction, dedup, selection
   output, or serialization even under injection.

The direct clamp helper's NaN/signed-zero passthrough remains incidental, private, and publicly
unreachable — not part of the public solver contract. Noted quirk (recorded, not corrected):
`Decimal("Infinity")` passes the line validator's multiple-of-0.5 check but yields only finite
outputs.

## §4 freeze — root semantics derived, and the gap found

`SOLVER_MILESTONE_D_PRECHANGE.json` (`sha256:ce989f2098d89e70…`) freezes the actual semantics:
existing `Root`/`ServerSolve`/`IdentificationResult` types; Chebyshev/inf-norm equivalence at
`_DEDUP_TOL = 1e-3`, strict `<`; greedy first-seen dedup; discovery-order output (no canonical
sort); boundary = edge distance `< 5e-3`; **no mirror machinery exists** (mirror pairs surface
generically as MULTIPLE_ROOTS); status precedence (NON_IDENTIFIABLE > MULTIPLE_ROOTS > union);
first-server union semantics; no built-in serialization; `CoherenceMathError` refusals; golden
digest.

**The §4/§9 order-dependence audit — EXECUTED against the real production `_dedup`:**

The equivalence relation is a tolerance relation and **not transitive**, and the greedy
first-seen dedup makes the kept set a function of the candidate **sequence**, not the candidate
**set**. Chain fixture A=(0.5, 0.5), B=(0.5009, 0.5), C=(0.5018, 0.5) (|A−B| = |B−C| = 9e-4 <
1e-3; |A−C| = 1.8e-3 ≥ 1e-3):

| candidate order | kept roots (p_a) | count |
|-----------------|------------------|------:|
| A, B, C | 0.5, 0.5018 | **2** |
| B, A, C | 0.5009 | **1** |
| C, B, A | 0.5018, 0.5 | 2 |

- **Root COUNT changes under a permutation of the same candidates** → the public status would
  change (2 kept → MULTIPLE_ROOTS; 1 kept → the single-root classification path).
- Even without chains, [A,B] keeps 0.5 while [B,A] keeps 0.5009 — a different public
  representative.
- `identify`'s first-server union dedup has the same property: it retains the A-serves-first
  representative whenever the two assignments agree within tolerance, solely because sa-roots
  are enumerated first.

**Production determinism (recorded honestly):** the production pipeline feeds `_dedup` a
deterministic candidate order, so the public result is a deterministic function of public inputs
and the golden remains stable. The gap is **semantic**: the deduplicated root set is
order-defined, not set-defined — exactly the condition §9 declares a contract gap requiring
founder adjudication, because any canonicalisation (canonical pre-sort, closest-pair merging,
transitive closure, or set-defined clustering) would **change public solver behaviour** and is a
separate governed amendment, not a refactor.

## What was and was not done

- Done: §1 audit + injection tests (committed); §4 freeze artifact (committed); this stop record.
- NOT done (stopped): §5 red tests, §6–§15 contracts/seams/classification, §16 reference solver,
  §17 differential, §18 mutation gates, §19 artifacts. No production file was touched in this
  milestone. Golden unchanged (no production edit — Milestone C's byte-identical PASS stands).
- Milestones A–C artifacts untouched; the Milestone-B stable-sort survivor remains
  `approved_by: null`.

## Decision required from the founder

Adjudicate the dedup contract gap — options (all governed amendments, none executed here):
(a) declare the current sequence-defined dedup the registered contract (freeze discovery order as
part of the spec); (b) amend to a set-defined canonical dedup (public-behaviour change; new golden
required; tests-first); (c) something else. Milestone D resumes only after that decision.
