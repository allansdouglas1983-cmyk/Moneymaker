# Stage 2A readiness review (Task 6) + Stage 2B plan (Task 7)

**Status:** 2026-07-18. Concludes the Stage-2A validity-protection slice and defines the
first modelling stage. No model, feature, parameter or outcome read is produced here.

---

## Task 6 — Stage-2 readiness review

**Question:** *Is the programme now scientifically safe to begin probability modelling?*

### Answer: **YES WITH BLOCKERS.**

The environment is now scientifically safe for the parts of modelling that read **no
outcome** (the F0 market baseline, the F1 structural null, all feature construction), and it
is *structurally* safe against accidental contamination for everything else. The structural
protections that make this true are in place and CI-green:

- complete outcome-field classification, fail-closed, human-owned
  (`specs/evidence/outcome-field-classification-v1.yaml`);
- the pre-lockbox access guard + replay-provable recorder (`l8_evidence.outcome_fields`);
- the outcome-extraction quarantine (`l8_evidence.tennis_outcomes`, import-forbidden from
  `l3_features`/`l4_pricing`);
- the evidence-discipline rule and the master pre-registration (structure frozen);
- the existing lockbox registry (SPEC-092), trial ledger (SPEC-091), sample-size
  derivation (SPEC-094) and gate evaluator (SPEC-093), unchanged and unweakened.

But **full modelling that reads outcomes may not begin** until the following blockers clear.
They are listed in strict dependency order — each depends on those above it.

1. **Founder resolves the ⟨PENDING FOUNDER⟩ pre-registration numbers** — minimum economic
   effect δ, α-budget/confidence, power (1−β), σ_d — and the reschedule dwell constant `W`.
   Nothing can register as a trial without them (SPEC-094; the ledger refuses an incomplete
   registration). *Blocks everything below.*
2. **Define and seal the tennis lockbox partition** (SPEC-092) — a disjoint, time-respecting
   holdout of the frozen universe, sealed via `LockboxRegistry.define(...)` **before any
   outcome is read**. *Blocks any outcome read.*
3. **Authorise and implement the outcome-opening protocol** — fill in
   `l8_evidence.tennis_outcomes` (currently refusing) under founder sign-off, reading only
   the `OUTCOME_CONTROLLED`/`POST_SETTLEMENT_ONLY` fields, only on the training/validation
   partition, at grading time. *Blocks reading the winner on any partition.*
4. **License longitudinal training-results data** (SPEC-101, Gate −1 for model data), with
   SPEC-023 backfill provenance. *Blocks the fundamental strength families F2–F6; does NOT
   block F0/F1, which need no external data.*
5. **Competitor-identity resolution quality report** (runner names ↔ results-corpus
   identities; F-07 CompetitorId). *Blocks F2–F6 (a mis-joined player is a silent label
   error).*
6. **Stage-2B engineering slices** (below) — buildable once 1–2 are set; the outcome-reading
   ones also need 3–5.

Nothing about profitability, returns or CLV is a prerequisite here, and none was consulted.
The answer is YES for the non-outcome harness now, and gated on 1–5 for outcome modelling.

---

## Task 7 — Stage 2B implementation plan (no implementation here)

Stage 2B builds the first probability model **and** the evaluation harness around it. It is
sequenced so the harness is proven on models that cannot leak before any outcome-reading,
licence-dependent family is touched.

### First model family: **F0 market-implied baseline + F1 structural null** (then F2 weighted Elo)

- **F0 — market-implied `p_market_info`:** the frozen info-price-v1 midpoint, normalised
  across the two selections at each stability-selected horizon instance. It is the yardstick
  every later family is measured against (M2 is *defined* relative to it).
- **F1 — structural null:** uniform 1/2 within each match choice set.
- **F2 — weighted Elo:** the first genuine fundamental family, begun only after blockers 4–5
  clear.

### Why this family is first

- **It needs no outcome and no licence.** F0 reads only `SAFE_BEFORE_LOCKBOX` prices; F1
  reads nothing. Both run today under the access guard, with the recorder proving zero
  outcome access. This de-risks the entire harness (snapshots SPEC-037, predictor ledger
  SPEC-038, cross-fit folds, lockbox discipline, the access recorder, determinism/replay)
  before a single result is read.
- **F1 is the leak detector.** A correctly built pipeline CANNOT let the null beat the market
  baseline; if it appears to, the harness has a bug — that is the null's entire purpose.
- **F0 is the measuring stick.** No fundamental result means anything except relative to it,
  so it must exist and be calibrated first.

### Expected outputs

- `p_market_info` and null probabilities at each market's stability-selected horizon
  instance, as immutable SPEC-037 snapshots (horizon-tagged, abstention-explicit);
- predictor-ledger scaffolding (SPEC-038) with fundamental/market/combined kept distinct;
- for every produced artefact, a `PreLockboxAccessRecorder` manifest digest.

### Expected evidence

- pipeline determinism / bit-exact replay of features, prices and snapshots;
- the null's proper scores match their analytic values; the market baseline's own
  calibration is characterised on validation (held-in), **not** the lockbox;
- **zero outcome reads**, proven by the access manifests (not asserted by prose).

### Stopping conditions

- STOP and fix if the harness shows any leak signature (null competitive with market;
  non-reproducible digest; any `OutcomeFieldAccessError` in a pre-lockbox path).
- STOP before F2 until blockers 1–5 clear (numbers, lockbox, outcome-opening, licence,
  identity). F0/F1 do not wait on these; F2+ do.
- No parameter is tuned on any outcome at any point in Stage 2B.

### Completion gate

Stage 2B's completion is a **harness-readiness** checkpoint (pre-statistical): the
evaluation pipeline is deterministic, leak-free on F1, F0 is calibrated on validation, and
snapshots/ledger/recorder are wired — *not* a probability-quality claim. The first
**statistical** gate is **M1 (probability adequacy)**, evaluated on the sealed lockbox by the
SPEC-093 evaluator only after fundamental families (F2+) exist and the pre-registration
numbers are frozen. Stage 2B does not touch the lockbox and makes no M1 claim.
