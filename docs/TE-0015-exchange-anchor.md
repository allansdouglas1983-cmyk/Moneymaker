# TE-0015 — The exchange price is the better anchor, and the features survive it

Paired four-way comparison on 25,268 covered matches (19,957 scored out-of-sample,
2017–2022): identical rows, identical walk-forward, identical 22 features; the one
difference is the offset the corrections are added to. Day-clustered bootstrap, 2,000 draws.

| comparison | gain (nats) | 95% CI | verdict |
|---|---|---|---|
| bare exchange T-600s over bare Bet365 closing | +0.000781 | [+0.000116, +0.001472] | clears zero |
| features over bare Bet365 | +0.001270 | [+0.000392, +0.002188] | clears zero |
| features over bare exchange | +0.001262 | [+0.000434, +0.002074] | clears zero |
| **exchange+features over b365+features** | **+0.000773** | [+0.000184, +0.001350] | **clears zero** |

## Three findings, each independently useful

**1. The exchange at T-600s beats the bookmaker's close — despite a timing handicap.** The
Bet365 price is captured *after* the exchange price and still forecasts worse by +0.000781
nats. The de-vig assumption (a power-law share of a 4.4% overround) evidently costs more
than ten minutes of information is worth. This retires the concern recorded in TE-0014
caveat 3: the settlement model's edge over the exchange cannot be explained by its offset
knowing more — its offset knows *less* than the price it beat, so the edge must come from
the features.

**2. The features are not a re-derivation of the exchange price.** Their paired gain is
+0.001270 on the Bet365 anchor and +0.001262 on the exchange anchor — essentially
unchanged. If the corrections had merely been recovering information the exchange already
prices, their value would have collapsed on the sharper anchor. It did not move.

**3. Re-anchoring wins end to end.** The decision row clears zero. And it carries a
structural bonus the experiment did not have to assume: **the live site's offset already is
an exchange price** — the user enters Betfair back prices, which are normalised into the
model's offset. The deployed coefficients were fitted against Bet365-closing offsets and
applied to exchange offsets, a train/serve mismatch that has existed since the site went
live. Fitting on exchange offsets does not just score better; it makes training match what
serving actually does.

## Why this is conservative

The exchange anchor ran at an information disadvantage (T-600s vs a later close) and on a
quarter of the training data the deployed model enjoys (both refits train only on covered
rows — per-year sizes printed in the run log). Both handicaps argue the true re-anchored
gain is at least what was measured.

## What deployment requires (not done in this slice)

The deployed artifact trains on 96,052 rows; exchange offsets exist for 27,209. Options —
train on covered rows only with matched semantics, or a mixed-offset scheme — differ
materially, and coefficients fitted one way are not comparable to the other. That choice,
the artifact refit, re-emitted golden vectors and the 1e-12 port check are their own slice.
Until it lands, the site continues to serve the Bet365-anchored fit, mismatch and all, as it
has since launch.

Run: `tennis_edge/experiments/exchange_anchor.py`, MIN_TRAIN=3000 (chosen before results),
feature cache `residual-v4` / `vintage-2026-07-26`, prices `exchange_prices_600s.jsonl`.
