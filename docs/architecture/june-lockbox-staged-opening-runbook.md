# June 2026 Tennis Lockbox — Staged Opening Runbook (PREPARATION ONLY)

**Status: NOT AUTHORISED FOR EXECUTION.** This is a preparation document. It describes,
in advance and in full, how the sealed June 2026 tennis lockbox
(`lockbox-june-2026-tennis-v1`, SPEC-092) would be opened in two ordered stages *if and
when* a separate explicit founder authorisation is recorded. Nothing in this file is a
trigger, a schedule, or a grant. No step below may be run until
`specs/evidence/lockbox-june-2026-tennis-v2.yaml` exists and authorises it.

Looking at the lockbox burns it. There is exactly one opening. Read this runbook end to
end, confirm every precondition is frozen, and understand the hard invariants before the
v2 authorisation is even drafted — because once June is read, none of it can be undone.

---

## 0. Scope and what this runbook is NOT

- This governs **probability-quality and information-gain evaluation only** (M1 external
  transfer, then M2 information gain). It is not a trading exercise.
- **No CLV, ROI, P&L, staking, stake sizing, or selection/tip analysis** appears in either
  stage. Those quantities are out of scope for M1 and M2 by construction and must not be
  computed, reported, or used to steer any decision here.
- **ADR 0015 blocks all live, real-money, and account activity — permanently and
  regardless of anything in this runbook.** Nothing here authorises, implies, or prepares
  any Betfair account activity, data purchase, or order placement. This is an offline
  evaluation of frozen artefacts against a sealed outcome set.
- No model, calibration, coefficient, threshold, feature, or gate parameter is created,
  fitted, tuned, reselected, or altered anywhere in this runbook. Every numeric input is
  **already frozen before June is opened** (Section 1). An LLM never estimates a
  probability, prices anything, or decides a gate (CLAUDE.md rule 3; SPEC-093).

---

## 1. Preconditions — ALL must be frozen BEFORE any opening

The runbook **cannot start** until every artefact below exists, is committed, and is
referenced by digest in the eventual v2 authorisation record. If any one is missing,
pending, or mutable, **STOP** — do not open June. These are entry gates, not checklist
niceties: an unfrozen precondition means a June result could be attributed to a
post-hoc choice, which is a contamination event.

| # | Precondition | Frozen artefact path | Notes |
|---|--------------|----------------------|-------|
| P1 | Selected F2 model record | `specs/programme/selected-model-record-v1.yaml` | The selected fundamental model. No reselection on June data, ever. |
| P2 | Affine calibration policy + final pre-June parameters | `specs/programme/calibration-policy-v2.yaml`; `docs/evidence/stage2c-affine-remediation/` | Final params: **ATP** intercept `0.025399`, temperature `1.218638`; **WTA** intercept `0.029204`, temperature `1.150681`. Frozen on pre-June data only. |
| P3 | F0 committed `p_market_info` snapshots | `docs/evidence/stage2b-f0-f2-runs/` | The frozen, versioned information price. Never re-derived from June. |
| P4 | SPEC-032 combination coefficients `alpha`, `beta` | `specs/programme/spec032-combination-registration-v1.yaml` | **MUST already be fitted on the pre-June market-development block and FROZEN.** The runbook cannot start until these exist. No fitting of `alpha`/`beta` on June. |
| P5 | M1 remediation amendment (approved) | M1 transfer requirements — `specs/gates/probability-m1.yaml` (`numeric_bands_v1`, frozen 2026-07-18) | The approved external-transfer requirements evaluated in Stage A. |
| P6 | M2 gate spec | `specs/gates/probability-m2.yaml` | Pre-registered; applied EXACTLY as written in Stage B. |
| P7 | Prospective June intersection manifest | `docs/evidence/stage2c-june-intersection/JUNE_M2_INTERSECTION_MANIFEST.json` | Final prospective intersection = **1027 markets, 30 UTC-day clusters**. Frozen before opening. |
| P8 | Code + data manifests (digests) | (bound into the v2 authorisation record) | Every opening is bound to `experiment_id` + model/feature/data manifests + gate spec version. |
| P9 | Alpha consumption ledger | `specs/programme/alpha-consumption-ledger-v1.yaml` | June-M2 reservation **0.025**, the sole remaining allocation. Multiplicity is debited here (SPEC-091). |

Additional standing preconditions:

- The lockbox seal itself is intact: `lockbox-june-2026-tennis-v1`, seal digest
  `sha256:24df4bd22ef28569ac8dd22c4d431725d0de010419c98f5a0402742f93878156`,
  `is_uncontaminated(lockbox-june-2026-tennis-v1)` returns true (GATE-1's deterministic
  input).
- Training-data rule holds: all model training, selection, hyperparameter, and calibration
  work used lawful data ending **before 2026-06-01** (lockbox v1 `training_data_rule`).
- Gate -1 source rights are PASS within attested scope (SPEC-101); the run is reproducible
  from immutable manifests and seeds (SPEC-104-style attestation to a commit hash).
- The v2 founder authorisation (`specs/evidence/lockbox-june-2026-tennis-v2.yaml`) exists
  and names this two-stage protocol, the `experiment_id`, and the bound manifests. **Absent
  v2, the governed extractor (`l8_evidence.tennis_outcomes`) structurally cannot represent a
  June scope — opening is impossible by construction, not merely by policy.**

---

## 2. The one opening (SPEC-092)

There is **one** read of June. The governed reader is
`l8_evidence.lockbox.LockboxRegistry.access`, GATE-1 only. Access is **log-then-grant**:
the access is logged and **the grant burns the lockbox**. After this single opening,
`is_uncontaminated(...)` is false forever and no unregistered model may be evaluated
against June — a later evaluation requires a NEW untouched period; this seal cannot be
reused.

Because there is only one opening, **both stages read the same already-granted June
outcome set within a single burned access.** Stage A reads first and decides whether Stage
B is even computed. The burn happens once, at the moment of opening in Stage A. Stage B, if
reached, does not constitute a second opening.

---

## 3. STAGE A — M1 External Transfer (do FIRST)

**Purpose:** evaluate the frozen, affine-calibrated F2 model's probability adequacy as it
transfers to the untouched June period, against the approved M1 transfer requirements
**only**.

**Steps:**

1. Confirm every Section 1 precondition is frozen and the v2 authorisation is in force.
   If not — STOP.
2. Open June via the governed reader `l8_evidence.lockbox.LockboxRegistry.access`
   (GATE-1 only). The access is logged; **the grant burns the lockbox.** This is the single
   opening (Section 2).
3. Evaluate the **FROZEN affine-calibrated F2** (P1 + P2, exact parameters above) against
   the **approved June M1 transfer requirements ONLY** — `specs/gates/probability-m1.yaml`,
   `numeric_bands_v1` (frozen 2026-07-18): overall and per-tour log loss `< ln2`, Brier
   `< 0.25`, calibration-in-the-large and slope bands, coverage floors, temporal transfer,
   reliability, and cold-start reporting. Evaluation is by the SPEC-093 deterministic
   evaluator. An LLM never decides this gate.
4. **ABSOLUTELY NO fitting, recalibration, temperature/intercept change, K reselection, or
   any model/parameter change on June data. NO M2 computation in Stage A.** June is read
   only to score the already-frozen model.

**Decision:**

- **If M1 does NOT return PASS (CONTINUE / FAIL_FUTILITY / FAIL_HARM) → STOP.**
  - Do **not** compute M2. Do **not** spend the reserved M2 alpha.
  - Record that June was **opened** and that **M2 was NOT evaluated** (in the alpha ledger
    and the experiment record).
  - Any later M2 requires a **NEW untouched period** — this seal is burned and cannot be
    reused (SPEC-092).
- **If M1 returns PASS → proceed to Stage B.**

---

## 4. STAGE B — M2 Information Gain (ONLY if Stage A returned PASS)

**Purpose:** evaluate whether the frozen, pre-fitted combined model gains information over
the frozen market-only baseline on the June intersection.

**Preconditions to enter Stage B:** Stage A returned **PASS**, and no model, calibration,
or coefficient has changed since June was opened (Section 5, invariant H2).

**Steps:**

1. On the frozen June intersection manifest (P7 — 1027 markets, 30 UTC-day clusters),
   compare the **FROZEN market-only `p_market_info`** (P3) against the **FROZEN pre-fitted
   combined `p_combined`** (P1 + P3 + P4 coefficients `alpha`, `beta`). No refitting of any
   kind.
2. Spend the reserved alpha **0.025** (confidence **0.975**), debited to the alpha
   consumption ledger (P9). This is the sole remaining allocation.
3. Apply the **pre-registered M2 gate** (`specs/gates/probability-m2.yaml`) **EXACTLY as
   written** — deterministic evaluator (SPEC-093), no LLM decides the gate. Race/choice-set
   paired inference with block bootstrap clustered by the tennis correlation-cluster key
   (UTC calendar day; SPEC-090).
4. **Stop after the M2 return.** Record the outcome. There is nothing after M2 in this
   runbook.

---

## 5. HARD INVARIANTS (state explicitly)

- **H1 — No "adjust then re-open".** The SAME June outcomes may NOT trigger any model or
  calibration modification between Stage A and Stage B. Seeing the Stage A result must not
  cause a tweak that is then re-scored on June.
- **H2 — Nothing changes after opening.** No model, calibration, combination coefficient,
  threshold, feature, or gate parameter may change after June is opened, at any point in
  either stage. Everything is frozen before the single opening.
- **H3 — Underpowered is a valid, expected result.** June is expected UNDERPOWERED (only
  ~1027 eligible markets across 30 calendar-day clusters). Do **NOT** change `delta`,
  confidence (`0.975`), clustering key, or any endpoint to force a decision. An
  underpowered outcome is **CONTINUE / INCONCLUSIVE by design** — that is the system working
  honestly, not a failure to be tuned away (SPEC-096 spirit; CLAUDE.md "surprisingly good
  backtest is a suspected bug").
- **H4 — Probability-quality and information-gain only.** No CLV, ROI, P&L, staking, or
  selection/tip analysis is part of either stage.
- **H5 — One opening, no reuse.** Looking burns the lockbox (SPEC-092). A STOP at Stage A
  still burns it. Any subsequent evaluation of any model needs a new untouched period.
- **H6 — Deterministic gates only.** M1 and M2 are decided by the SPEC-093 deterministic
  evaluator bound to data and model manifests. An LLM never decides a gate, never estimates
  a probability, never prices or sizes anything (CLAUDE.md rule 3).
- **H7 — ADR 0015.** Live, real-money, and account activity remain blocked regardless of
  any outcome here. This runbook is offline evidence evaluation only.

---

## 6. Recording obligations (both paths)

- Log the single GATE-1 access (automatic on `LockboxRegistry.access`).
- Record in the experiment ledger: `experiment_id`, bound code/data/model manifests
  (digests), gate spec versions (`probability-m1`, `probability-m2`), and the Stage A
  outcome.
- Debit the alpha ledger: **only if Stage B runs** is the `0.025` M2 reservation consumed;
  if Stage A did not PASS, record that the reservation was **NOT** spent and M2 was **NOT**
  evaluated.
- Record that `lockbox-june-2026-tennis-v1` is burned.

---

**This runbook is NOT authorised for execution. Opening June requires a separate explicit founder authorisation recorded as lockbox-june-2026-tennis-v2.yaml. Looking at the lockbox burns it (SPEC-092).**
