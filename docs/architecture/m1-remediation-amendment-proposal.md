# M1 remediation amendment — PROPOSAL (returned for founder approval)

**Status: PROPOSAL. Nothing here is frozen or active.** It is returned for founder review
**before** any June lockbox access. It **preserves every existing numeric band** in
`specs/gates/probability-m1.yaml` (`numeric_bands_v1`) unchanged — it only defines *how M1
closes* given three evidence sources, and *what June must show*. No band is widened,
narrowed, moved, or added. If the founder approves, the closure rule below is copied into a
frozen `probability-m1` amendment; until then M1 remains **CONTINUE** by construction.

## Why an amendment is needed

M1 on the temperature-only calibrated F2 returned **CONTINUE**: 14/15 bands passed but the
overall calibration-in-the-large was **+0.02328**, outside the frozen ±0.02 band (one-parameter
temperature scaling has no intercept and cannot move the mean). The registered affine
remediation (`calibration-policy-v2`) adds exactly an intercept; on the pre-June remediation
scorecard the residual falls to **+0.00406**, inside band, and every other band remains met
(`docs/evidence/stage2c-affine-remediation/`, digest
`sha256:6001657753c8a26ea2ba53e3d323c0a132b1034161b6708d65c2c45e30284470`).

**But that scorecard is REMEDIATION / DEVELOPMENT evidence** — the affine method was chosen
*after* observing the temperature-only shortfall, so it cannot itself close M1 (Stage 2C §4).
M1 closure therefore needs an *external* confirmation that the fix transfers, and June is the
only untouched period available. This amendment defines that closure rule.

## The three evidence sources M1 closure rests on

- **(A) Frozen pre-June adequacy evidence** — the honest nested-crossfit OOF scorecard on the
  selected model (structural + proper-scoring items that were pre-registered before results
  were read): coverage/exclusion completeness, lawful reproducibility, F3-vs-F2 confirmatory
  recorded, cold-start cohorts characterised, ATP/WTA both evaluated. (`stage2b-f3-confirmatory/`.)
- **(B) Affine remediation scorecard** — pre-June, labelled REMEDIATION; demonstrates the
  affine map brings calibration-in-the-large, slope, reliability, per-tour and temporal-transfer
  bands into range on development data. Development evidence — necessary, not sufficient.
- **(C) Future untouched June external-transfer check** — the frozen affine-calibrated F2
  evaluated once on the sealed June block (Stage A of the staged opening runbook), *before* and
  *independent of* any M2 computation. This is the confirmation that (B) was not overfit to the
  development period.

## Proposed closure rule (bands unchanged; only the evaluation partitioning is defined)

M1 is an AND over independent items (existing `precedence`). This amendment assigns each item
to the partition it is judged on. **The band values are exactly `numeric_bands_v1`.**

### Evaluated on pre-June evidence (A)+(B) — necessary preconditions

These read no June data and must already hold on the frozen/remediation scorecards:

| Item | Source | Band (unchanged) |
|---|---|---|
| `lawful_reproducible` | A | provenance complete; Gate -1 PASS in scope |
| `coverage_and_exclusions_complete` | A | full funnel; missing preds in denominator |
| `f3_vs_f2_confirmatory_recorded` | A | recorded (FAIL_HARM); selection = F2 |
| `honest_outer_fold_proper_scores` | A+B | overall log loss < ln2; Brier < 0.25 |
| `calibration_in_the_large` | B | overall ∈ [−0.02, 0.02]; per-tour ∈ [−0.03, 0.03] |
| `calibration_slope` | B | overall ∈ [0.90, 1.10]; per-tour ∈ [0.85, 1.15] |
| `reliability_by_band` | B | \|obs−pred\| ≤ 0.05 for bands ≥ 500 preds |
| `temporal_stability` | B | validation − OOF log loss ≤ 0.01; no ≥1000-pred annual block ll ≥ ln2 |
| `atp_wta_cohort_stability` | A+B | both tours meet their bands |
| `cold_start_behaviour_characterised` | A+B | cohorts reported; no ≥500 cohort ll > ln2+0.02 silently |

All of these are **met** on the current pre-June + affine remediation evidence — so the pre-June
preconditions for M1 are satisfied, pending the June transfer check.

### Must transfer on June (C) — the external confirmation

On the June block, with the model and calibration **frozen** (no fitting), M1 requires that the
frozen affine-calibrated F2 does not materially degrade:

1. **Overall proper scores** hold: June log loss < ln2 and Brier < 0.25 (same bands).
2. **Calibration-in-the-large** on June ∈ [−0.02, 0.02] (same band) — the specific quantity the
   remediation targeted; this is the load-bearing transfer check.
3. **Calibration slope** on June ∈ [0.90, 1.10] (same band).
4. **Reliability** within ±0.05 for any June band with ≥ 500 predictions.
5. **No annual/temporal veto** (June is one month, so this reduces to the overall June block).

### Minimum counts for any June cohort / reliability band

A June sub-metric is **evaluated only if it has enough support**, else it is **CONTINUE for that
sub-metric, never fabricated**:

- **Reliability band:** ≥ 500 predictions (identical to the pre-June `reliability.
  adaptive_band_min_predictions`). Bands below 500 are **diagnostic only** (unchanged rule).
- **Per-tour band (ATP / WTA):** evaluated only if that tour has ≥ 500 June predictions;
  otherwise that tour's calibration bands return **CONTINUE**, not PASS and not FAIL.
- **Cold-start cohort:** the ll>ln2+0.02 → CONTINUE trigger applies only to cohorts with ≥ 500
  June predictions (unchanged threshold); smaller cohorts are reported, not gated.
- **Overall June block:** the prospective June F2-valid count is ~1,218 (intersection with a
  committed market is ~1,027, but M1 needs only a valid F2 prediction, not a market price).
  Even so, June is a **single month** — see the veto/underpowering handling below.

### How unsupported June sub-metrics behave

Any band whose June support is below its minimum count returns **CONTINUE for that item**
(existing `on_false: CONTINUE` semantics), and the overall gate follows the existing precedence
(`adequacy_items_incomplete_or_underpowered -> CONTINUE`). **No default, no fabricated value, no
borrowed number** is ever substituted for a missing June sub-metric (SPEC-038 discipline;
evidence.md). Missing June predictions stay in the denominator as abstentions.

### What constitutes a June veto (→ not PASS)

- **FAIL_HARM** if June shows *material degradation*: overall June calibration-in-the-large
  outside a **harm band** of [−0.05, 0.05] (2.5× the adequacy band — proposed as the *harm*
  boundary, distinct from and never replacing the ±0.02 adequacy band), or overall June log loss
  ≥ ln2 (worse than the structural null), or a reproducibility/lawfulness item false.
- **CONTINUE** if June is merely *underpowered or incomplete*: calibration-in-the-large lands in
  (±0.02, ±0.05], or key bands lack the minimum counts, or the single-month sample cannot resolve
  the transfer. An underpowered June is **CONTINUE by design**, exactly as for M2.
- **PASS** only if all pre-June preconditions hold **and** the June transfer items 1–5 hold at
  their unchanged bands with adequate counts.

### Hard invariants

- **No band is altered.** Every number above is copied from `numeric_bands_v1`; the only new
  numbers are the *harm* boundary (±0.05) and the reused ≥500 minimum count — both are
  degradation/support thresholds, not adequacy bands, and both are returned here for founder
  approval rather than assumed.
- **No model or calibration parameter may change after June is opened.** The frozen affine
  parameters (ATP intercept 0.025399, temperature 1.218638; WTA intercept 0.029204,
  temperature 1.150681) and F2 K are applied unchanged. No recalibration on June — that would
  convert the external check into an in-sample fit and void M1.
- **M1 is evaluated in Stage A only**, before any M2 computation; June is opened once (looking
  burns the lockbox, SPEC-092). If M1 is not PASS, M2 is not computed and its alpha is not spent.
- **No LLM decides M1.** The SPEC-093 deterministic evaluator maps the frozen items to the
  digest-pinned evidence.

## What is requested of the founder

1. Approve (or amend) the **partition assignment** of M1 items to pre-June vs June-transfer.
2. Approve (or amend) the two **non-band thresholds**: the June calibration-in-the-large **harm**
   boundary (±0.05) and the ≥ 500 **minimum-count** rule for June sub-metrics.
3. Confirm that **no existing band is altered** by this amendment (it is not).

On approval, this becomes a frozen `probability-m1` amendment; until then M1 stays CONTINUE.
