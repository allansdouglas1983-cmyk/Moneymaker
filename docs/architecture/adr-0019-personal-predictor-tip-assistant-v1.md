# ADR 0019 — Personal Tennis Predictor & Tip Assistant V1 (Stage 2G)

Status: accepted (founder directive, 2026-07-20). Budget: £0 (freeze in force).

## Preserved, immutable prior findings
- F2-v1 (global Elo) is CLOSED: predictive vs the uninformed null, but its calibration did not
  transfer to June (M1 **FAIL_HARM**, unchanged forever).
- F3 surface Elo is permanently closed (FAIL_HARM). Surface is **not** reintroduced into DP1.
- Rolling calibration did not rescue F2-v1; the June F2/market combination showed no stable
  incremental information; no economic edge was established; no betting/Live-Key/expenditure was
  justified. Stage 2F's termination applied to the **registered F2-v1 betting hypothesis** — not
  to every possible personal prediction model.
- June is development evidence forever; it can never again be called an untouched confirmation
  block. No old alpha or significance claim transfers into Stage 2G. No historical result may be
  represented as proof of future profitability.

## Decision
Create a NEW programme with two products: (1) a PERSONAL PREDICTOR (match win probabilities +
explicit uncertainty) and (2) a PERSONAL TIPPING ASSISTANT (is a quoted Betfair back price
attractive after uncertainty, commission, market and data quality). Private, single-user,
pre-match Match Odds singles, back-only, manual-only; **no automated execution ever in scope**;
`BET_CANDIDATE` structurally unreachable until gates P1+P2+T1 pass and the founder activates T2.

## Components and SPEC-IDs (new; manifest previously ended at SPEC-104)
| ID | component | content |
|---|---|---|
| SPEC-105 | dp1_model | DYNAMIC_GLICKO2_V1 fundamental family (money) |
| SPEC-106 | dp1_model | WinProbabilityDistribution output + analytic uncertainty (money) |
| SPEC-107 | dp1_model | AFFINE_LOGIT_CALIBRATION_FOR_DP1 (money) |
| SPEC-108 | mp1 | MARKET_ANCHORED_RESIDUAL_V1, pooled λ∈[0,1] (money) |
| SPEC-109 | tp1 | tipping-policy status contract; BET_CANDIDATE token-gated (money) |
| SPEC-110 | tp1 | commission-aware break-even + EV in Decimal (money) |
| SPEC-111 | ps1 | personal prediction snapshot, append-only, outcome-free (evidence) |
| SPEC-112 | ps1 | prospective shadow capture: manual entry / delayed-key observe (evidence) |
| SPEC-113 | ps1 | prospective grading + gates P0/P1/P2/T1/T2 (evidence, planned) |
| SPEC-114 | ui1 | private local single-user interface, no execution path (support) |
| SPEC-115 | governance | deterministic reason-code registry (evidence) |

## Key design choices
- **DP1 = Glicko-2** (canonical Glickman equations; constants founder-frozen: 1500/350/0.06,
  τ=0.5, ε=1e-6, UTC-day periods, separate tours, same-day batch; inactivity inflates RD each
  empty period and can never shrink it). Full registration:
  `specs/programme/dp1-glicko2-registration-v1.yaml`.
- **Uncertainty is analytic**, not invented: the pairwise logit difference is Normal(δ, s²) under
  the rating posteriors, so the interval is the exact sigmoid image of δ±z·s (z=1.644854 frozen);
  the central probability is a frozen 20-node Gauss–Hermite posterior mean.
- **Reliability ≠ picking winners** (founder §2): sum-to-1 coherence, calibration, explicit
  uncertainty, visible unsupported players, measured temporal transfer, abstention, model/market
  separation, price-dependent recommendations, pre-match frozen predictions, append-only audit;
  most matches may correctly be NO BET.
- **Data boundary** frozen before any scoring: `specs/programme/stage2g-data-boundary-v1.yaml`
  (July 1–2 development; STAGE2G-HOLDOUT-JULY-V1 = July 3–12, predictor-only, frozen by date
  range so enumeration cannot read outcomes).
- **Market anchor**: single pooled λ on the June F0∩DP1 intersection via expanding UTC-day folds,
  frozen thereafter; λ=0 preserved honestly if that is the answer.
- **Evaluation** reuses the model-independent chronological crossfit (`l4_pricing/crossfit.py`),
  with frozen F2-v1 and the structural null as baselines; June is development-labelled.
- Build order = founder §21 slices 1–7, red tests first, one commit series per slice,
  independent verifier after each; STOP conditions = founder §22 verbatim.

## Consequences
Old F2/F3/M1 identifiers are never reused. A new trial ledger entry registers DP1
(`specs/programme/stage2g-trial-ledger-registration-v1.yaml`). Prospective confirmation uses only
observations after the full freeze (model, calibration, λ, snapshot, policy). The Delayed App
Key, if lawfully available, is observation-only (SPEC-102 already makes real money impossible on
it by construction); otherwise manual price entry. No stake-sizing model exists in Stage 2G.
