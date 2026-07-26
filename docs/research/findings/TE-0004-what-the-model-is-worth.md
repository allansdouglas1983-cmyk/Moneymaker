# TE-0004 — What the model is actually worth: α ≈ 0, seventeen years running

**Measured:** 2026-07-25. **72,669 out-of-sample matches, 2010–2026.** This is the largest
and cleanest measurement in the project, and it closes the modelling question.

---

## The method

Every prior test asked "is the model better than the market?" and got a flat answer. This
asks the sharper question: **given free rein, how much weight does maximum likelihood
actually give the model?**

```
score = α·logit(p_model) + β·logit(p_market)
```

α and β fitted by MLE on the winner, **refitted each year on strictly earlier years only**,
each year scored with weights that never saw it. Out-of-sample at three levels: day-batched
ratings and serve estimates, per-year expanding-window refit, and the market price as an
input never a target. No intercept — an intercept would absorb a base-rate error a
well-formed choice set cannot have, masking a miscalibrated input instead of exposing it.

The method is built so it **can** return "the model adds nothing", and unit tests pin that:
a market-only generator must recover α ≈ 0, a model-only generator β ≈ 0.

## The answer

| year | n | α | t(α) | β | t(β) |
|---|---:|---:|---:|---:|---:|
| 2010 | 4,548 | −0.021 | — | 0.974 | — |
| 2018 | 4,573 | −0.005 | −0.3 | 0.948 | 55.0 |
| 2021 | 4,345 | +0.001 | 0.1 | 0.949 | 59.7 |
| 2024 | 4,684 | −0.001 | −0.1 | 0.955 | 65.3 |
| 2026 | 2,814 | −0.007 | −0.4 | 0.959 | 68.8 |

**α is indistinguishable from zero in every single year — t between −0.4 and +0.3 — and is
negative more often than positive.** β is overwhelming, t between 55 and 69.

## The control that settles it

A pooled gain of +0.00017 nats with a day-clustered CI excluding zero could look like a
finding. The control separates where it comes from: **β alone, α forced to zero**, on
identical rows.

| | pooled log loss |
|---|---:|
| market | 0.58234 |
| **shrink-only** (β only, α = 0) | **0.58219** |
| full combination | 0.58217 |

- gain from shrinking the market alone: **+0.00015 nats**
- gain the **model** adds on top: **+0.00001 nats**

**The model contributes 6% of a 0.03% improvement.** Rounded honestly: nothing. Without this
control the combination would have looked like a model improvement when it is a
recalibration of the price.

## What *is* real

**The de-vigged market is very slightly overconfident, and shrinking its logit by ~5% is a
genuine, highly significant improvement.** β ≈ 0.95 with t ≈ 60, stable across all 17 years
and every cohort. It is worth +0.00015 nats — statistically overwhelming, economically
trivial, and free.

That is the best available predictor: **the price, recalibrated.**

## Cohorts

| cohort | n | advantage (nats) | t |
|---|---:|---:|---:|
| best_of=3 | 65,254 | +0.00023 | +2.95 |
| **best_of=5** | 7,415 | **−0.00039** | −1.43 |
| market 0.3–0.7 | 40,448 | +0.00019 | +3.24 |
| market fav>0.7 | 15,558 | +0.00007 | +0.32 |
| ATP | 37,717 | +0.00022 | +2.06 |
| WTA | 34,952 | +0.00011 | +1.03 |

The shrink helps mid-range prices and best-of-3, and **hurts best-of-5** — Grand Slam
matches, where the market is sharpest and most heavily traded. Consistent with the reading
that this is a small calibration artefact of thinner markets, not information.

## Consequence for the product

`tennis_edge/predictor.py` is built on this rather than around it. Its answer is the
recalibrated market; the model view is computed and reported as a **labelled diagnostic**;
and every prediction carries `model_weight` so the insignificance is visible at the point of
use rather than buried here. `recommendation` is hard-pinned to `NOT_EVALUATED` and a test
asserts no input can produce anything else.

A tool that presented this number as a proprietary model would be lying about where it comes
from.

## Why this is the end of the modelling line, not a to-do

Six architectures have now been measured against the price: Elo family, Barnett–Clarke point
model, cross-book consensus, residual GBM, full-pyramid Elo, and now an MLE-weighted
combination that was *free to choose* how much model to use and chose none. The failure is
not of implementation — the O'Malley recursion reproduces published values exactly, and the
combination recovers known synthetic weights.

More model work on this data has no expected value. What would change the answer is
different **information** — not a different way of arranging the information we have.

Reproduce: `uv run python -m tennis_edge.experiments.combination_walk_forward`
