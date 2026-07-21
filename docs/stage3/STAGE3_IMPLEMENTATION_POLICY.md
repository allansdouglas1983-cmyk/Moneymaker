# STAGE 3 IMPLEMENTATION POLICY — governance

Status: ACTIVE (founder directive STAGE3-0001). This document defines *how* Stage 3 is
governed. It authorises **no code, no new model families, and no code changes.** It binds
any future Stage 3 implementation, which begins only under a separate founder directive
naming the specific layer.

## 1. Governing principle

Stage 3 discovers **information independent of Frozen F2-v1**, or it honestly establishes
that there is none. The default and most likely finding is *no independent information*.
The programme's job is to establish that cheaply and honestly — never to manufacture a
pass. Every surprisingly good development result is a suspected artefact until a
pre-registered, post-freeze measurement says otherwise.

Frozen F2-v1 is the immutable active baseline. F3 (FAIL_HARM) and DP1 (STOP_DP1_HARM) are
closed programme history, reproducible but retired. No replacement sporting model is
implemented until a future founder directive authorises it.

## 2. Prohibited practices (hard)

The following are contamination events, not merely discouraged. Invoking any of them to
steer a Stage 3 decision burns the artefact it touched and stops work:

- **Historical optimisation** — tuning any parameter, threshold, feature set, formula,
  fold scheme, or model choice against development/backtest performance.
- **Cohort fishing** — searching cohorts (odds band, venue, surface, period, tour,
  round, …) for one where a layer looks good, then reporting that subgroup as the result.
  A cohort breakdown is diagnostic; a cohort is never a promotion basis, and no
  cherry-picked subgroup is labelled overall performance.
- **Feature fishing** — trying features until one appears to help; adding a feature
  because "it would have helped" after seeing outcomes.
- **ROI optimisation** — selecting, tuning, or promoting anything by betting return, P&L,
  CLV, or hypothetical profit. ROI is at most a clearly-secondary frozen-policy diagnostic
  and never a training target or selection criterion.
- **Threshold tuning** — inventing, relaxing, or altering any gate threshold, especially
  after seeing results. No threshold changes after result opening, ever.
- **Repeated retry until success** — re-running an evaluation, re-drawing a lockbox,
  re-registering a near-identical hypothesis, or "kicking it until it passes." Multiplicity
  is debited to the trial ledger; retries are counted against the alpha budget, not hidden.

Additional standing prohibitions carried from Stage 2 (non-exhaustive): no LLM estimates a
probability / price / stake / gate; no reconciled closing benchmark or post-event data in
a fundamental; no bookmaker odds in a fundamental; no actual-off time as a live feature;
no in-play, no lay/hedge, no passive execution pre-Gate-4; no spend without explicit
founder authorisation.

## 3. Identical gates to Stage 2

Every Stage 3 candidate passes **exactly the same governance gates** as Stage 2 — no
lighter path, no bespoke scoreboard:

1. **Gate zero (independence)** — the five questions answered in the hypothesis register
   before any code: exact new information; why F2 cannot represent it; knowable pre-off;
   lawful; prospectively validatable.
2. **Pre-registration** — a trial in `l8_evidence.trial_ledger` (SPEC-091) with
   pre-registered primary endpoint, minimum economically-meaningful effect, power
   assumptions, and stopping rule (SPEC-094); borrowed constants forbidden; multiplicity
   debited.
3. **Time-respecting OOF evaluation** — the model-independent `cross_fit` orchestrator
   (SPEC-031); paired, day-clustered proper scoring vs Frozen F2 (SPEC-090); calibration
   in-the-large + slope (SPEC-097); coverage-with-exclusions; frozen evidence roles
   (RAW_HONEST / IN_SAMPLE_CALIBRATION_DIAGNOSTIC / CALIBRATED_HONEST); determinism/replay.
4. **Uncertainty registration** — the exact uncertainty quantity, level, type, and
   empirical test frozen in advance (Stage 2G governance-gap closure); coverage is a gate
   only if a valid test was pre-frozen, else DIAGNOSTIC.
5. **Deterministic gate evaluation** — `gate evaluate` bound to data and model manifest
   hashes, returning PASS | CONTINUE | FAIL_* (SPEC-093); an LLM never decides a gate.
6. **Mutation gate** — every money-critical module introduced is 100%-non-equivalent-
   mutant-killed, or its residual survivors are per-ID founder-approved (fingerprint-bound,
   environment-tagged where identity-bound), exactly as the Stage 2 mutation adjudication.
7. **Lockbox / prospective confirmation** — development evidence never promotes; promotion
   requires post-freeze prospective confirmation on an unspent lockbox (SPEC-092), with no
   threshold changed after opening.
8. **Result-read barrier** — artefacts finalized and hashed (code/data/model/config
   digests) before any numerical value is opened; raw output reproduces byte-identically.

A candidate that fails any gate is recorded as `FAILED_*` permanent history, reproducible,
never quietly retried.

## 4. The independence bar (Stage-3-specific)

Beyond "not materially worse than F2" (Stage 2's non-harm boundary), a Stage 3 layer must
demonstrate **positive, independent** information:

- a pre-registered **orthogonality measurement** showing the layer's residual is not a
  deterministic or statistically-reconstructable function of F2's inputs;
- a paired proper-score **improvement** over Frozen F2 that survives day-clustered
  inference on post-freeze data — not development data;
- stable, not cohort-contingent: the gain may not depend on a fished subgroup.

No independent information ⇒ the honest result is retirement, exactly as DP1.

## 5. What Stage 3 may and may not do now

**May:** register hypotheses; write architecture and governance; prepare pre-registration
templates and evaluation-role definitions; preserve external Deep Research as
*hypothesis-generation-only* external inputs, awaiting a separate founder synthesis
directive after any relevant verdict.

**May not, until a future founder directive names the specific layer:** write
implementation code; register or build any model family; add features, formulas,
thresholds, or parameters; touch Frozen F2 / F3 / DP1; begin any replacement sporting
model; incur any spend.

## 6. Change control

This policy, the architecture, and the hypothesis register are human-owned governance
documents. The hypothesis register is append-only. Any change to a gate, threshold, or
prohibition is a governed specification change with a recorded rationale — never an
in-flight convenience, and never made after results are seen.
