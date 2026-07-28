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
| **deployment row: exchange+features (24k train) over b365+features (90k train)** | **+0.000812** | [+0.000042, +0.001570] | **clears zero** |

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

## The deployment row

The decision row held training data constant to isolate the anchor. Deployment faces the
real trade: the re-anchored fit can train only on the 24k covered rows, while the deployed
architecture trains on ~90k. Measured head to head on the same out-of-sample matches, the
re-anchored fit still wins — **+0.000812 nats [+0.000042, +0.001570]** — so the sharper,
serve-matched anchor outweighs a 3.7× training-data disadvantage. The lower bound is a
whisker above zero and is reported as such.

## What deployment requires (not done in this slice)

The artifact refit on exchange offsets, golden vectors re-emitted, the 1e-12 port check,
and the database push are their own slice. One caveat gates it and cannot be measured away
with current data: **the covered rows end at 2022-03** (the archive is truncated), so a
re-anchored fit's coefficients are verified through 2022 and assumed stable to 2026 —
untestable without post-2022 exchange prices. The cheapest cure is the missing tail of the
archive itself: a complete re-download would both roughly double the settlement sample and
make the deployment verifiable on recent seasons. Until one or the other lands, the site
continues to serve the Bet365-anchored fit, mismatch and all, as it has since launch.

Run: `tennis_edge/experiments/exchange_anchor.py`, MIN_TRAIN=3000 (chosen before results),
feature cache `residual-v4` / `vintage-2026-07-26`, prices `exchange_prices_600s.jsonl`.
