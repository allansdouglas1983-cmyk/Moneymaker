# Stage 2 — Tennis probability programme pre-registration (MASTER)

**Status:** FROZEN-STRUCTURE / NUMBERS PENDING — recorded 2026-07-18 (Stage-2A). This is
the master pre-registration binding the whole Stage-2 probability programme. It freezes the
**protocol** before any model is trained (SPEC-094: declared before observation). It does
NOT yet register a trial: each model family is registered individually via
`l8_evidence.trial_ledger.TrialLedger.register(...)` from its
`l8_evidence.experiment_templates` template, and cannot register until every ⟨PENDING
FOUNDER⟩ boundary below is resolved and the lockbox is defined. Numeric boundaries are
deliberately absent — they are pre-registered, human-approved decisions (evidence.md "no
borrowed thresholds"), never values an agent invents.

Nothing may later be added to this pre-registration because it "looked interesting."
Adding an endpoint, metric, family, or cohort after observation is a new, numbered trial
with its multiplicity debited (SPEC-091), never a silent edit.

---

## 1. Primary objective

Produce calibrated, out-of-fold, choice-set-level probabilities for the frozen June-2026
primary singles universe (2,876 markets; `specs/programme/baseline-v1.yaml`) at governed
marketTime horizon instances, and determine — under pre-registered proper scoring on an
untouched lockbox — whether an independent fundamental model (`p_fundamental`) or the
market-aware combination (`p_combined`) carries information beyond the frozen market price
baseline (`p_market_info`). The terminal quantity is **P(model)**, not a bet.

Decision unit: the **match** choice set (`PERMITTED_DECISION_UNITS = {race, match}`;
`decision_unit = "match"`). Selection-level independence assumptions are forbidden anywhere
(SPEC-090).

## 2. Primary evaluation metric

Choice-set-level **paired** score (SPEC-090): `d_m = L_m(market) − L_m(combined)` using
`−log p` on the realised winner, aggregated by **block bootstrap clustered on the tennis
correlation-cluster key = UTC calendar day** (SPEC-031/090; ChronologyKey per ADR-0017 A4).
The primary comparison is combined-vs-market; the fundamental-vs-market and
combined-vs-fundamental pairings are secondary (below).

- Minimum economically-meaningful effect δ (mean per-match log-score improvement):
  ⟨PENDING FOUNDER⟩.
- Confidence level / α-budget and its multiplicity accounting: ⟨PENDING FOUNDER⟩
  (evaluator uses `spent_alpha = (1−confidence)·(prior_trials+1)`, SPEC-091/gates-v1).
- Power (1−β) and σ_d assumption feeding the SPEC-094 sample size
  `N = (z_α+z_β)²·σ_d²/δ²` via `l8_evidence.sample_size.derive_sample_size`: ⟨PENDING
  FOUNDER⟩. N is DERIVED from these, never asserted.

## 3. Secondary metrics (reported, never promotion drivers on their own)

Choice-set multiclass Brier; calibration-in-the-large and slope on choice-set-normalised
logits (SPEC-097); reliability by approved bands with CIs; coverage / availability /
abstention rates with missing predictions and exclusions kept in the denominator
(SPEC-038); cohort breakdowns by the **classification-evidence tier** (strict
sibling-corroborated vs primary-only), odds band, and period — cohort labels caller-supplied,
never hardcoded. ROI is NOT computed in Stage 2 (it is not a probability-quality metric and
is forbidden by the Stage-2 evidence-discipline rule).

## 4. Validation protocol

- Three disjoint partitions defined BEFORE any outcome read: **training**, **validation**,
  **lockbox**. The lockbox partition is sealed via `l8_evidence.lockbox.LockboxRegistry`
  (SPEC-092) and never inspected during development; GATE-1 is its only permitted read.
- Partition boundaries are time-respecting (no validation/lockbox match precedes a training
  match it informs) and recorded as `DateWindow`s in each `TrialRegistration`; the ledger
  refuses a lockbox window overlapping training/validation.
- Universe frozen before outcomes are known; missing/withdrawn markets become explicit
  exclusions with knowledge-time rationale (SPEC-091 `Exclusion`), never disappearances.

## 5. Cross-fitting protocol

Stage-one `p_fundamental` fed to stage two MUST be strictly out-of-fold and strictly
time-respecting (SPEC-031): trained only on earlier folds of the UTC-day cluster key, via
the model-independent crossfit orchestrator (ADR-0017 A5 / F-06 seam) — conditional logit /
Bradley–Terry is one family behind that seam, never the sole OOF producer. A contaminated
row is refused at consumption, not only at production. No model ever prices a match in its
own training set.

## 6. Calibration protocol

Post-hoc calibration (if any) renormalises across each choice set (SPEC-097); ECE is
diagnostic only. Calibration is assessed on validation (held-in) before opening and
confirmed on the lockbox only at GATE-1. Calibrating to lockbox outcomes before GATE-1 is a
burn.

## 7. Comparison protocol

All model comparisons are horizon-matched (a model trained at one horizon is never compared
across horizons — SPEC-033) and benchmark-versioned (SPEC-038 registry; in-place benchmark
change refused). The three probabilities stay distinct and never substitute for one another
(SPEC-036): `p_fundamental` (no market input), `p_market_info` (frozen info-price-v1),
`p_combined` (stage-two). No cherry-picked subgroup may be labelled overall performance.

## 8. Abandonment criteria (pre-registered, per family)

A family is ABANDONED (TrialDecision.ABANDONED) when its pre-registered increment over its
declared comparator fails to reach δ at the declared power once the derived N is reached
(FAIL_FUTILITY at the family's endpoint), or when a structural refusal fires (separated /
unidentified data, SPEC-030; rating coverage below the declared floor as explicit
abstention). Abandonment is a successful, recorded outcome — not a reason to search for a
different endpoint. Per-family comparators: see §10.

## 9. Promotion criteria (pre-registered)

A family is promoted toward the next family / gate only when its pre-registered lower bound
exceeds the declared minimum effect δ at the declared α (multiplicity-debited) on
validation, with stable calibration, and its comparison is horizon-matched and
coverage-honest. Promotion never rests on a secondary metric or a favourable subgroup.
Final programme promotion (does `p_combined` beat `p_market_info`) is decided ONLY at the
lockbox by GATE-1's deterministic evaluator (SPEC-093) — never by inspection.

## 10. Refusal criteria (hard, structural)

The programme REFUSES (does not silently proceed) when: any ⟨PENDING FOUNDER⟩ boundary is
unresolved; the lockbox is undefined or burned; a required licence for training data is
absent (SPEC-101 Gate −1 for model data); an outcome-controlled field is reached outside the
authorised outcome-opening protocol (`OutcomeFieldAccessError`); a horizon mismatch is
requested (SPEC-033); the trial ledger's prior-count would be understated; or an LLM is
asked to produce/alter a probability or decide a gate.

## 11. Model families & their frozen templates (protocol only)

Registered from `l8_evidence.experiment_templates` (`_TEMPLATE_VERSION = "adr-0017-s6"`),
all `decision_unit = "match"`, all `baseline_comparator = "market-only-baseline"`; ordered
by programme-risk per ADR 0018 / `stage2-probability-programme.md` §roadmap:

| Order | Template id | Family | Its declared comparator |
|---|---|---|---|
| F0 | `market-only-baseline` | market-implied p_market_info | self (yardstick) |
| F1 | *(structural null — pipeline shakedown; no template needed)* | uniform 1/2 | market-only |
| F2 | `weighted-elo` | global Elo | structural null / market |
| F3 | `surface-elo` | surface-conditional Elo | weighted-elo |
| F4 | `bradley-terry` | Bradley–Terry (= conditional logit at N=2) | surface-elo |
| F5 | *(logistic w/ declared features — template at activation)* | regularised logistic | bradley-terry |
| F6 | *(serve/return — data-blocked; template at activation)* | structural serve/return | best of F2–F5 |
| F7 | `stage2-combined` | SPEC-032 combination | fundamental & market |

Each family's `PreRegisteredEndpoints{minimum_economic_effect, power_assumptions,
stopping_rule}` (with `minimum_economic_effect == power_assumptions.delta`) is filled from
§2's ⟨PENDING FOUNDER⟩ values at its own registration, then frozen.

## 12. What this pre-registration does NOT authorise

No training data purchase/licence; no model; no feature; no outcome read; no lockbox
definition (a separate governed act); no numeric boundary (⟨PENDING FOUNDER⟩); nothing live
(ADR 0015). Resolving the ⟨PENDING FOUNDER⟩ values and defining the lockbox are the gating
prerequisites before the first `TrialLedger.register(...)`.

---

## Founder amendment (2026-07-18): declared values and lockbox decision

Declared by the founder at Stage-2A acceptance. These entries RESOLVE the corresponding
⟨PENDING FOUNDER⟩ items above and SUPERSEDE §4's June-internal partition sketch.

1. **α-budget:** `alpha_total = 0.05`, PROGRAMME-LEVEL FAMILY-WISE — the total budget
   across ALL pre-registered model-family comparisons, not 0.05 per model. Rationed by
   the existing multiplicity machinery only (`spent_alpha = (1−confidence)·(prior_trials+1)
   ≤ alpha_total`, SPEC-091 / gates-v1 `alpha_times_trials_exact_multiplication`); no
   parallel correction system exists or may be invented. Each family's per-trial
   confidence level is set at its registration so the family-wise budget is respected.
2. **Power:** `power = 0.80` (planning target). Recorded once; never increased later
   because a result is inconvenient.
3. **Lockbox (supersedes §4's partition sketch):** the ENTIRE June 2026 primary singles
   universe is sealed — 2,876 markets, with the 2,287 strict cohort retained as a tagged
   sensitivity subset, doubles excluded from the primary modelling programme
   (`specs/evidence/lockbox-june-2026-tennis-v1.yaml`, seal digest `sha256:24df4bd2…`).
   All June sporting outcomes and outcome-controlled fields are inaccessible. Model
   training, model selection, hyperparameter selection and calibration use lawful data
   ending BEFORE 2026-06-01. If adequate pre-June longitudinal data cannot be licensed,
   fundamental modelling remains blocked — never solved by opening part of June.
4. **Outcome opening:** implementing the governed extractor and permissions is
   authorised; June outcome opening is NOT. Pre-June development/validation outcomes may
   later be accessed under registered experiments only, bound to experiment/model/
   feature/data/gate manifests. Opening June requires a separate explicit founder
   authorisation. An unregistered post-lockbox model requires a new lockbox period.
5. **Still ⟨PENDING FOUNDER⟩:** δ (minimum meaningful effect), σ_d (planning
   assumption), reschedule dwell `W` and max nominal lead — to be declared from the
   outcome-blind evidence packets (docs/evidence/stage2b-planning-packets/), never
   invented and never chosen because they improve any real result.
