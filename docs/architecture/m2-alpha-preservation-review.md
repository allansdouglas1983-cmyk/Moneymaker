# M2 alpha-preservation review — one-shot vs anytime-valid sequential (Stage 2D §8)

**Returned for founder selection BEFORE June is opened. Neither option is implemented here.**
The existing one-shot gate (`specs/gates/probability-m2.yaml`) is **not** altered or discarded.
Do not open June or spend alpha on the strength of this document.

## Why this review exists

The prospective June M2 intersection is **1,027 matches across 30 UTC calendar-day clusters**
(`docs/evidence/stage2c-june-intersection/`). At the pre-registered δ = 0.0007 nats and the
planning σ_d ≈ 0.04075, a decisive one-sided test needs ≈ 32,212 paired decision units. June is
therefore **~30× underpowered** and, on its own, is expected to return **CONTINUE / INCONCLUSIVE**.
The question is whether to spend the family's last 0.025 of alpha on that one underpowered shot,
or to preserve it across several untouched months under an anytime-valid design.

## OPTION A — frozen one-shot June M2 (the existing gate)

- Uses `specs/gates/probability-m2.yaml` exactly as frozen.
- Spends alpha **0.025 once** on the June block (multiplicity: 0.025 × (1 prior F3 trial + 1) =
  0.05 = family budget; exhausted).
- **High probability of CONTINUE / INCONCLUSIVE** given the power shortfall.
- Can still detect a **very large** positive effect (or material harm) if one exists — a genuinely
  huge combined-vs-market gain would clear even 30× underpowering; a catastrophic degradation would
  trip FAIL_HARM.
- After it resolves, **no confirmatory family-wise alpha remains**; any further superiority claim
  needs a newly governed programme, a new lockbox, and a human-controlled multiplicity reset.
- **Engineering cost: zero** — the gate, evaluator, clustered bootstrap, and intersection manifest
  already exist.

## OPTION B — anytime-valid sequential M2 (retain the same 0.025 total)

Keep the **same** total alpha 0.025, but treat June as the **first** untouched monthly evidence
block and permit later untouched months to be appended under a pre-registered anytime-valid
procedure, so the test can accumulate power without spending alpha per look.

- **Proposed statistical method:** a **testing-by-betting e-process** on the paired
  choice-set endpoint — a non-negative test supermartingale whose running product of per-block
  e-values yields an **always-valid** level-α test (equivalently, a confidence sequence on mean
  d). An e-process is the natural fit because it is valid under **optional stopping and optional
  continuation** and composes multiplicatively across blocks. (A Ville/Robbins mixture or a
  calibrated one-sided GRO e-value against δ = 0.0007 are the concrete candidates; the exact
  construction is registered before the first look.)
- **Unit of sequential evidence:** one **untouched calendar month** (June first), each internally
  reduced to a **UTC-calendar-day-clustered** statistic — the tennis correlation-cluster key
  (SPEC-090). Blocks enter in chronological order.
- **Cluster treatment:** within a block, the per-day clusters are the resampling/summary unit
  (no selection-level independence); across blocks, months are independent evidence increments in
  the supermartingale. Both the within-block clustering and the between-block product must be
  specified before the first look.
- **Validity under optional stopping:** guaranteed by the supermartingale property — the type-I
  error is controlled at α **simultaneously for all stopping times** (Ville's inequality), so
  "peek after each month and stop when convincing" does not inflate α. This is exactly what a
  fixed-sample bootstrap cannot license.
- **How δ = 0.0007 enters:** the e-value is built to test H0: mean improvement ≤ 0 against a
  point/mixture alternative anchored at the **minimum economically meaningful effect δ = 0.0007
  nats**; the GRO/mixture is centred so the process grows fastest when the true effect is ≈ δ.
  PASS is declared when the e-process crosses 1/α = 40 (for α = 0.025) with the effect on the
  δ-positive side.
- **PASS / CONTINUE / FUTILITY / HARM:**
  - **PASS** — e-process ≥ 1/α on the improvement side (combined beats market by ≥ δ, always-valid).
  - **CONTINUE** — process below the boundary and above the harm floor; more months may be added.
  - **FAIL_FUTILITY** — a registered futility e-process (or a projected-information rule) shows δ is
    effectively excluded, or the pre-committed maximum number of months is reached without crossing.
  - **FAIL_HARM** — a symmetric harm e-process crosses on the degradation side.
- **Engineering cost:** **material and non-trivial.** SPEC-096 (anytime-valid monitoring) is
  registered **`planned` and UNIMPLEMENTED**; only the *contract* (`anytime_valid_bounds_v1` in
  `specs/gates/v1.yaml`, consumed by the SPEC-093 evaluator) exists. Building Option B means:
  implementing the e-process/confidence-sequence producer, its determinism + replay tests, its
  mutation coverage (money-critical), a per-block clustered reduction, and a governed block-append
  ledger — then **activating SPEC-096**, which is a human-controlled specification change. This is
  a genuine slice, not a config tweak.
- **Additional months** remain **individually founder-approved** and individually purchased (one
  month at a time; **no bulk purchase is implied**). Stopping may occur for **PASS, HARM,
  FUTILITY, or budget/'max-months' exhaustion**.
- **Hard invariant:** no model, calibration parameter, combination coefficient, eligibility
  policy, or benchmark may change between blocks — every appended month is scored by the *same*
  frozen artefacts, or the sequential validity is void.

### How many monthly blocks might Option B need?

Under the planning σ_d ≈ 0.04075 and δ = 0.0007, the fixed-sample requirement is ≈ 32,212 paired
units. At the observed June yield of ~1,027 scorable combined-vs-market matches per month, that is
**≈ 31 months** of comparable data to reach fixed-sample power — and an anytime-valid procedure
pays a modest additional penalty for the always-valid guarantee, so the realistic expectation is
**several years of monthly blocks** to resolve an effect *as small as* δ. Option B only resolves
**sooner** if the true effect is **larger** than δ (fewer months) — it never manufactures power
that the data volume does not contain. This is the honest cost of a δ this small at tennis monthly
volumes.

## Recommendation framing (founder decides)

- **Option A** is zero-cost, honest, and almost certainly CONTINUE — it *documents* that June
  could not resolve δ and closes the family-wise budget.
- **Option B** preserves the ability to *eventually* resolve δ, but at real engineering cost, a
  SPEC-096 activation, and a multi-year cadence of founder-approved monthly purchases — and it only
  pays off if the effect is either sizeable (resolves fast) or the programme genuinely intends to
  run for years.

**Neither is implemented. Return your selection before June is opened. The existing one-shot gate
stays intact until you choose.**
