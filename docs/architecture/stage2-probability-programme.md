# Stage 2 — Probability-Engine Programme (definition only; no implementation)

**Status:** DEFINED 2026-07-18 as part of the Stage-1 closure package (ADR 0018;
Gate M0 PASS; baseline `specs/programme/baseline-v1.yaml`). Slice activation is
human-controlled, as ever. This document defines objectives, inputs, outputs,
evidence, blocked work, dependencies, completion criteria and the exit gate — it
authorises **no code**, **no features**, **no parameters**, **no model runs**.

**Terminal deliverable:** calibrated, out-of-fold, choice-set-level **P(model)** —
the three probabilities of SPEC-036 (p_fundamental, p_market_info, p_combined) for
the frozen June-2026 universe at governed horizon instances, with a complete
predictor evidence ledger. **Not betting.** Stage 2 contains no stake, no order, no
EV consumption, no execution modelling.

---

## 1. Objectives

1. Open outcome data under governance for the first time — protocol first, data second.
2. Produce `p_market_info` at governed horizon instances from the reconstructed books
   (the frozen info-price contract applied to tennis), because every later claim of
   model value is *relative to this yardstick*.
3. Produce `p_fundamental` from market-blind model families (roadmap, §5) via the
   model-independent crossfit orchestrator (A5 seam; UTC-day clusters per SPEC-031/090).
4. Produce `p_combined` via the SPEC-032 stage-two combiner.
5. Evaluate everything at choice-set level (SPEC-090 paired inference, SPEC-097
   calibration, SPEC-038 ledger) under pre-registered endpoints (SPEC-094) with the
   trial ledger current (SPEC-091).
6. Exit through Gate M1 (probability adequacy), then Gate M2 (market comparison).

## 2. Inputs

- Frozen canonical replay manifest + universe manifest (digests in baseline-v1).
- Horizon instances from the governed marketTime protocol (pilot `recon.py` method,
  productionised as a governed slice — the pilot script itself stays archival).
- **Outcomes** — from the corpus's own post-`CLOSED` runner status, read by a NEW
  outcome-extraction reducer that is structurally incapable of reading pre-off
  content (mirror-image of the pilot's stop-at-CLOSED discipline), OR from a
  licensed external results source; either way joined only at grading time
  (SPEC-021/037 discipline).
- **Longitudinal results history** (multi-year, pre-June-2026) for player-strength
  families — REQUIRES its own licensing decision (SPEC-101/044, Gate −1 for model
  data) and SPEC-023 backfill provenance (true publication times, not
  first-seen-at-backfill).
- Competitor identity: namespaced string CompetitorId (F-07 seam) with an explicit
  name-resolution quality report (runner names ↔ results-corpus identities).

## 3. Outputs

- Immutable SPEC-037 prediction snapshots (vintage-linked, horizon-tagged) for every
  (market, horizon-instance) in scope; abstentions explicit (SPEC-047 semantics,
  no forced predictions).
- SPEC-038 predictor performance ledger entries per family, fundamental vs market
  vs combined always distinguished; missing predictions stay in the denominator.
- Versioned model artefacts with immutable version ids; every retrain is a new
  version + new evaluation (no live learning — there is no "live" in Stage 2 at all).
- The Stage-2 evidence pack: calibration reports, paired-inference results,
  coverage/abstention accounting, per-tier (strict vs primary-only) breakdowns.

## 4. Evidence required (before the first model result may be looked at)

In strict order — each is a separate governed slice:

1. **Outcome-opening protocol** — written, reviewed, frozen: who/what may read
   post-CLOSED data, through which module, with which structural guards.
2. **Tennis lockbox frozen (SPEC-092)** — a holdout partition of the June universe
   (and of any future month) defined and sealed BEFORE any outcome is read; Gate M1/M2
   evaluation is its only permitted read; any other access burns it.
3. **Pre-registration (SPEC-094)** — endpoints (choice-set log-score improvement),
   minimum meaningful effect, power arithmetic, stopping rule, cohort definitions,
   abstention policy — declared per family BEFORE that family sees an outcome.
4. **Trial ledger entries (SPEC-091)** — every family evaluation is a numbered trial
   with the multiplicity budget debited.

## 5. Blocked work (hard, for all of Stage 2)

- Anything in §"Live activity" of baseline-v1 (ADR 0015 stands).
- EV computation, stake sizing, order construction, execution/fill modelling
  (that is Stage 3 / M3 territory; l4b_fill stays untouched and `planned`).
- Benchmark selection (separate founder decision; CLV diagnostics wait for it).
- Feature construction from anything failing the F-01 knowability boundary or
  carrying adapter-undeclared taints (SPEC-020/021/022).
- Any comparison of vintages or families on outcomes outside the pre-registered
  endpoints (no metric shopping; SPEC-038 "no cherry-picked subgroup").
- Doubles beyond descriptive reporting.

## 6. Dependencies

- Licensing: longitudinal results corpus rights (blocking for Elo/BT/logistic
  families; the null and market baselines do not need it — they can proceed first).
- The reschedule operational policy decision (outcome-blind, from pilot evidence)
  before any horizon consumer is built.
- Engineering slices (each red-first, human-activated): outcome reducer;
  horizon-instance producer; tennis feature-registry entries; StageOneFamily
  implementations per roadmap family; snapshot/ledger wiring for tennis decision
  units (already sport-agnostic post-ADR 0017, expected to be thin).

## 7. Completion criteria

Stage 2 is complete when: the evidence pack exists for every roadmap family carried
to its pre-registered endpoint (or documented abandonment); every claim in it is
reproducible from immutable manifests; the lockbox remains unburned except for gate
evaluation; and Gates M1 and M2 have been evaluated by the SPEC-093 deterministic
evaluator with recorded outcomes — **whatever those outcomes are**. A Stage 2 that
ends in FAIL_FUTILITY at M2 is a *successful* Stage 2: the question was answered.

## 8. Gate at completion

**M1 — Probability adequacy** (defined below), then **M2 — Market comparison**.
M1/M2 are the tennis instantiation of SPECIFICATION §9's Gate-1 machinery (lockbox
evaluation, pre-registered, SPEC-093-evaluated); the M-naming is the programme
milestone view, not a parallel gate system. Gate specs are authored as
`specs/gates/probability-m1.yaml` / `market-comparison-m2.yaml` when their
pre-registrations exist — structure-only, no numeric leaves, boundaries from the
pre-registration records.

---

# Model-family roadmap (Task 5 — design only, nothing built)

Ordering principle: **minimise programme risk per pound** — each family exists to
kill a specific risk or to be the yardstick a later family must beat; a family is
promoted only by pre-registered evidence, abandoned by pre-registered futility, and
never chosen by opinion. All families are evaluated identically: out-of-fold via the
crossfit orchestrator (UTC-day clusters), choice-set log score + multiclass Brier,
calibration-in-the-large + slope (SPEC-097), SPEC-090 paired inference vs the
baselines, strict/primary-only tier breakdown always reported.

**F0 — Market-implied baseline (p_market_info).** Exists because M2 is *defined*
against it: no fundamental family means anything except relative to the market's own
information. Incremental information: none (it IS the yardstick). Evaluated for:
constructibility at horizon instances, overround-normalisation behaviour,
calibration (the market's own). Abandoned: never (it is infrastructure, not a
candidate).

**F1 — Structural null (uniform 1/2 within choice set).** Exists to shake down the
entire evaluation pipeline (snapshots, ledger, folds, lockbox discipline) with a
model that CANNOT leak and whose scores are analytically known. Incremental
information: zero by construction — any pipeline showing the null beating F0 has a
bug, which is precisely the point. Abandoned: retired automatically once the
pipeline validates; never appears in M2.

**F2 — Global Elo (WeightedElo seam, longitudinal history).** Exists because it is
the cheapest genuine player-strength signal and the canonical public-information
model — if it adds nothing beyond F0 (the expected result), that is the cleanest
possible measurement of "public form is priced in". Incremental information:
longitudinal player strength. Evaluated: as above, plus rating-coverage accounting
(players unseen in history → explicit abstention, in the denominator). Abandoned if:
licensing for longitudinal results fails (blocks F2–F5 entirely), or its
pre-registered improvement-over-F1 endpoint fails (which would indicate identity
resolution or data problems, not "tennis is unpredictable").

**F3 — Surface-conditional Elo.** Exists because surface specificity is tennis's
best-documented public heterogeneity and June's grass regime makes it maximally
measurable. Incremental information: surface adjustment ON TOP of F2 — evaluated as
F3 vs F2 paired at choice-set level, never F3 vs F0 alone. Abandoned if the
pre-registered increment over F2 fails futility.

**F4 — Bradley–Terry (time-decayed, regularised, batch MLE).** Exists because BT on
pairs IS the platform's conditional logit (SPEC-030) at N=2 — it drops into the
StageOneFamily seam, carries principled uncertainty, and validates the entire
SPEC-030/031 machinery on tennis. Incremental information: batch-consistent strength
estimates with uncertainty vs Elo's online approximation. Evaluated: increment over
F3; refusal behaviour on separated/unidentified data must trigger (SPEC-030
metamorphic property), not regularise silently. Abandoned on futility vs F3.

**F5 — Regularised logistic with declared features.** Exists to test whether ANY
knowability-clean public covariates (ranking points, age, recent schedule/fatigue,
head-to-head) add information beyond latent strength. Every feature enters through
the feature-declaration registry with knowledge-time stamps; F-01-unsafe features are
structurally unbuildable. Incremental information: covariate signal beyond F4.
Abandoned on futility vs F4 — with the explicit expectation recorded now that this
is the most likely first family to fail cleanly.

**F6 — Serve/return structural model.** Exists because it is the only family whose
information is not a repackaging of results history: it models the scoring structure
(serve-hold/break probabilities propagated deterministically through game/set/match
recursion). Incremental information: within-match structure invisible to
results-only models. Requires point/serve-level data — a NEW licensing decision;
this family is defined but data-blocked at Stage-2 start. Abandoned if: licensing
fails, or its pre-registered increment over the best of F2–F5 fails.

**F7 — Stage-two combination (SPEC-032).** Exists because it is the deployable
output shape: c = softmax(α·log p_fund + β·log p_market). Incremental information:
none of its own — it measures how much fundamental signal SURVIVES in the presence
of the market price (α's fitted weight and the combined model's M2 result are the
programme's central numbers). Never abandoned; its result is the Stage-2 verdict.

Explicitly deferred (not in Stage 2): in-match/point-process live models (no
in-play, ever, in this programme), neural/boosting families (SPEC-035 constraints
apply if ever proposed; only after F2–F7 evidence exists), and any family whose data
cannot clear licensing.

---

# Gate ladder after Stage 2 (Task 6 — one question per gate, no mixing)

Each gate: single question, SPEC-093-evaluated when activated, pre-registered
boundaries, structure-only YAML authored at activation. Technical correctness and
profitability are NEVER in the same gate. The ladder maps onto SPECIFICATION §9's
existing gate machinery (M1/M2 ≈ Gate 1 lockbox evaluation; M3 ≈ Gate 2; M4 ≈
Gate 3's economic half; canary/production ≈ Gate 3 live-readiness and beyond) — a
milestone view, not a second governance system.

| Gate | The single question | Outcome licenses | Never considers |
|---|---|---|---|
| **M0 — Market adequacy** (PASS, 2026-07-18) | Is the market technically suitable for an evidence-led probability project? | Stage-2 definition and start | profitability, model quality |
| **M1 — Probability adequacy** | Are the out-of-fold probabilities statistically sound in absolute terms (calibration + proper score vs the structural null) on the untouched lockbox? | Naming a model version "adequate"; proceeding to M2 | the market, EV, execution |
| **M2 — Market comparison** | Does p_combined contain information not already in p_market_info (SPEC-090 paired, clustered, pre-registered)? | Stage-3 (execution study) definition | profitability, stakes, fills |
| **M3 — Execution viability** | Can intended taker-v1 orders be executed at prices preserving the modelled quantity (size-aware, latency-adjusted, crossable-price scenarios; three-envelope discipline when fills are modelled)? | Defining M4's economic evaluation | whether the edge is profitable |
| **M4 — Economic viability** | Is conservative-lower-bound net EV positive after commission and execution costs, at pre-registered power with multiplicity accounted? | Requesting founder consideration of a live canary | nothing technical — this is the ONLY profitability gate |
| **Live canary** | Does minimal-stake live behaviour match offline predictions within pre-registered tolerances and the absolute loss budget? | Production consideration | — **cannot even be scheduled while ADR 0015 stands** |
| **Production** | Is there sustained canary evidence plus full operational readiness (kill switch SPEC-063, external watchdog SPEC-064, reconciliation SPEC-083, DEBT-MUT-L6-LEGACY killed, budgets separated)? | Unattended operation | new statistical claims |

Failure semantics at every step: CONTINUE means measure more (within pre-registered
sample bounds), FAIL_FUTILITY means the question answered "no" honestly, FAIL_HARM
means stop for integrity/legal/budget reasons. A FAIL at any gate is a valid,
successful programme terminal state — the analytics-only terminal state of ADR 0015
remains available throughout.
