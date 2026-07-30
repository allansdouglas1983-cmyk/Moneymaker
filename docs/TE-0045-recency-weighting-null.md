# TE-0045 — recency-weighted training does not beat the stationary fit, anywhere

**Date:** 2026-07-30. **Type:** pre-registered experiment (declarations committed at
`857520f`, before the run). **Harness:** `tennis_edge/experiments/recency_weight.py`.
**Raw output:** `tennis-edge/docs/evidence/TE-0045-recency-weight-run.txt`.
**Answers:** TE-0041 open item 18.

## The question

Training weights 2003–2026 equally, yet three independent diagnostics mark a 2023/24
break (TE-0019, TE-0028, TE-0024/0029). TE-0033 showed the model's own edge held across
the break and exonerated composition; the untested implication was the FIT — should it
trust recent matches more? This was the cheapest offline test of the regime hypothesis.

Design: exponential recency weights, recomputed per fold from the fold boundary, under
the identical frozen walk-forward (same folds, same 22 features, same L2 = 25). Primary
half-life 3 years, fixed from the calendar before any result. Guard: the weighted fitter
reproduced the deployed fitter at uniform weights to 1.7e-16 before anything was read.

## The result — NULL on the declared question, and instructive in shape

96,366 rows, 63,780 out-of-sample paired predictions, day-clustered 95% CIs
(d = loss_stationary − loss_weighted; positive favours weighting):

| reading | n | d (nats) | CI95 | verdict |
|---|---|---|---|---|
| **Q1 pooled (PRIMARY, h=3y)** | 63,780 | **−0.000047** | [−0.000154, +0.000064] | **unresolved — spans zero** |
| Q2 post-2024 (secondary) | 12,160 | +0.000010 | [−0.000249, +0.000278] | unresolved |

Exploratory grid (descriptive only, no verdicts, as declared):

| half-life | pooled d | CI95 |
|---|---|---|
| 1y | **−0.000230** | [−0.000439, −0.000003] |
| 2y | −0.000090 | [−0.000233, +0.000062] |
| 3y (primary) | −0.000047 | [−0.000154, +0.000064] |
| 5y | −0.000020 | [−0.000089, +0.000051] |
| 8y | −0.000010 | [−0.000054, +0.000036] |

## Reading, per the declared rule

**Q1 spans zero → unresolved**, which under the declared vocabulary means: stationarity
is NOT shown wrong, and no era-weighted registration is motivated. But the shape of the
grid says more than the single verdict:

1. **The cost of forgetting is monotone in aggressiveness.** Every point estimate is
   negative pooled, and they order exactly by half-life: the harder you discount old
   matches, the worse you price new ones. At h=1y the harm is large enough that even
   this descriptive cell excludes zero. Old tennis matches still carry usable
   information about current players and the market's current errors.
2. **The help never appears where the hypothesis predicted it.** Post-2024 — the era the
   regime diagnostics point at — every half-life's difference is within ±0.0001 of zero.
   If the world had changed in a way the fit could exploit by forgetting, this is where
   it would show. It does not.
3. **Combined with TE-0033, the regime picture is now sharp**: the post-2023 anomaly
   lives in the ANCHOR relationship (the exchange price's lead over Bet365, directional
   only), not in the match-level structure the model fits. The model's coefficients
   transfer across the break; the equal-weighted training set stands vindicated on the
   available evidence.

## What remains of the regime question

The one channel still open is the anchor comparison (TE-0033 Q2, directional, never
cleared). That is not addressable by any refit — it resolves only with post-break data
accumulation: the live CLV monitor and the weekly forecast ledger. TE-0041 item 18 is
CLOSED by this run; the recheck trigger is stated below rather than left implicit.

**Recheck trigger:** if a future run of this identical harness on ≥2 more years of data
shows Q2 clearing zero in favour of weighting, the question reopens as a governed slice.
One run now, as declared; this document is the record.

## Ledger

No SPEC-ID changes. No serving change — the deployed equal-weighted fit is unchanged and
now positively supported rather than merely assumed. No gate evaluated. No spend.
