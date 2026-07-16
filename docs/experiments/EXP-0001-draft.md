# EXP-0001 (DRAFT — NOT REGISTERED, NOT EXECUTED)

**Status:** DRAFT. This document is a pre-registration *draft* only. It is NOT an entry
in the SPEC-091 trial ledger, defines NO lockbox, inspects NO data, and authorises NO
purchase. Registration happens only after: DR-0001/DR-0002 findings are filed, the
founder approves data rights + budget, the data is ingested through l0–l3, and a pilot
cohort (outside the future lockbox) yields the σ_d estimate. Every ⟨PENDING⟩ below must
be resolved to a concrete pre-registered value before `TrialLedger.register()` is called.

## Registration fields (SPECIFICATION §9.7)

| Field | Draft value |
|---|---|
| `experiment_id` | `EXP-0001` (final id minted at registration) |
| `hypothesis` | The cross-fitted combined model (SPEC-032) achieves a lower race-level log score than the frozen market-information baseline on GB all-weather WIN markets at the approved decision horizon; the fundamental-only model (SPEC-030) is a secondary comparison. Expected outcome per CLAUDE.md: no exploitable edge — failure is informative. |
| `decision_unit` | `race` |
| `primary_endpoint` | Mean race-level paired difference `d_r = ln(p_combined_winner) − ln(p_market_winner)` (SPEC-090), anytime-valid lower bound compared against `minimum_economic_effect` by the SPEC-093 evaluator (GATE-1, `anytime_valid_bounds_v1`). |
| `secondary_endpoints` | (a) `d_r` for fundamental vs market (is there any independent signal at all); (b) race-level multiclass Brier difference; (c) calibration-in-the-large and slope for the combined model (SPEC-038); (d) signal CLV distribution vs BSP (SPEC-095, diagnostic only). |
| `minimum_economic_effect` | ⟨PENDING founder⟩ — must be derived from Gate −1B payback arithmetic (the smallest log-score edge that could plausibly clear commission + the live-key fee at the intended stake/frequency), not a borrowed constant. |
| `training_window` | ⟨PENDING data purchase⟩ — earliest purchased month → T_split. |
| `validation_window` | ⟨PENDING⟩ — T_split → T_val_end; strictly after training; meeting-day expanding-window cross-fit inside it (SPEC-031). |
| `lockbox_window` | ⟨PENDING⟩ — the most recent purchased period, defined via SPEC-092 `LockboxRegistry.define()` at registration time; never overlapping training/validation (SPEC-091 enforces); read once, by Gate 1 only. |
| `exclusions` | Drafted rules, each with knowledge-time rationale at registration: non-GB-all-weather markets; races voided/abandoned; races with in-play-only data; races where the market-information price definition (specs/prices/info-v1.yaml) is uncomputable at the horizon — every exclusion enters the frozen-universe funnel, never a disappearance. |
| `feature_set_hash` | ⟨PENDING⟩ — sha256 of the approved feature build (SPEC-024) once DR-0002's source is licensed and ingested. |
| `model_hash` | ⟨PENDING⟩ — SPEC-030/031/032 model manifest digests (§6.12). |
| `execution_policy_hash` | Not applicable to Gate 1 (no orders); recorded as the sha256 of the literal string `no-execution-gate-1` unless the founder prefers a null-policy manifest. ⟨PENDING confirmation⟩ |
| `number_of_prior_trials` | Ledger-derived at registration (`TrialLedger.prior_trial_count()`); expected 0. |
| `stopping_rule` | Anytime-valid confidence sequence on the mean `d_r` at pre-registered `confidence_level`; stop at PASS/FAIL_HARM/FAIL_FUTILITY per `specs/gates/v1.yaml` GATE-1 precedence; hard cap `max_n` from the SPEC-094 plan below. The SampleSizePlan content digest is quoted here at registration. |
| `alpha_budget` | ⟨PENDING founder⟩ — draft proposal: 0.05 total across the experiment family, exact-multiplication multiplicity per SPEC-091/093. |
| `result` / `confidence_interval` / `decision` / `reviewer` | Empty at registration; completed only after Gate 1 evaluation, attested (reviewer + UTC timestamp). |

## Sample size (SPEC-094 — derivation, not assertion)

`N = ⌈(z_α + z_β)² · σ_d² / δ²⌉` via `l8_evidence.sample_size.derive_sample_size`.
- α: from `alpha_budget` after multiplicity adjustment; two-sided ⟨PENDING founder — draft: two-sided⟩.
- power: ⟨PENDING founder — draft: 0.8⟩.
- σ_d: ⟨PENDING pilot⟩ — estimated from a pre-registered pilot cohort strictly outside
  the lockbox; the pilot's cohort definition and dates are themselves recorded before
  σ_d is computed.
- δ = `minimum_economic_effect`.
The resulting `SampleSizePlan.content_digest()` is quoted in `stopping_rule` at
registration so pre-observation derivation is verifiable.

## Model arms

1. **Market-only baseline:** `p_market_info` per specs/prices/info-v1.yaml (frozen
   definition, versioned) — the benchmark, never altered mid-experiment.
2. **Fundamental conditional logit:** SPEC-030, features from the DR-0002 source only,
   no market input.
3. **Cross-fitted combined:** SPEC-032 on strictly out-of-fold fundamentals (SPEC-031)
   + `p_market_info`.

All three persist SPEC-036 probability outputs and SPEC-037 snapshots (INITIAL vintage
at the approved horizon); evaluation joins after settlement through SPEC-038's versioned
benchmark registry (benchmark pinned to FINAL_APPROVED_HORIZON_ONLY ⟨PENDING founder —
or INITIAL_ONLY⟩ before any outcome is seen).

## What this draft does NOT authorise

No lockbox definition, no ledger registration, no data inspection, no purchase, no
live credential, no order of any kind. Blocked on: DR-0001, DR-0002, founder budget +
rights approval, and every ⟨PENDING⟩ above.
