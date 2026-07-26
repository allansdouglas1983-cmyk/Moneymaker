# TE-0007 findings — a real forecasting edge, and the venue where it disappears

**Measured:** 2026-07-26, in-workspace. Reproducible from
`tennis_edge/experiments/residual_edge.py` against the pinned Tennis-Data vintage.

**Question:** TE-0005 established that the closing price has a measurable defect and that
the largest single-feature correction was two orders of magnitude too small to trade. It
also explained why six architectures had failed: the market's errors point in *different
directions*, so bundling them into one composite probability cancels them. That left an
obvious next move — fit them jointly, each free to take its own sign, and add the one input
the main-tour market plausibly has not absorbed: a rating that knows the lower tiers.

**Answer, in one line: the model genuinely beats the closing price, it converts to money
against bookmakers, and it does not convert at the exchange — which is the only venue that
matters for a personal bettor.**

---

## The model

Ten features, each a correction to the de-vigged B365 closing logit, which enters as an
unpenalised offset. Ridge penalty fixed a priori at 25. Full Newton with a backtracking line
search. Walk-forward by year, fit on every prior year, scored on the next; 96,162 priceable
matches, 63,576 scored out-of-sample from 2012.

Five of the ten are new here: pyramid Elo, pyramid surface Elo, pyramid tier share, pyramid
workload and pyramid rest, all built from the whole professional circuit — Grand Slam down to
Futures — rather than the priced main-tour corpus.

| feature | coefficient | reading |
|---|---:|---|
| **pyramid_elo_gap** | **+0.1114** | market under-weights |
| **pyramid_surface_gap** | **+0.0853** | market under-weights |
| **point_model_residual** | **+0.0820** | market under-weights |
| pyramid_rest_gap | −0.0771 | market over-weights |
| rank_gap | −0.0625 | market over-weights |
| pyramid_tier_gap | +0.0521 | market under-weights |
| surface_elo_gap | −0.0421 | market over-weights |
| pyramid_workload_gap | +0.0299 | market under-weights |
| elo_residual | −0.0230 | market over-weights |
| weighted_elo_gap | +0.0092 | market under-weights |

The three largest are pyramid ratings and the serve model. That is the hypothesis this
session was built to test, and it is what the fit found: **the main-tour closing price
under-weights information from below the main tour.**

Individual coefficients should not be over-read. These features are strongly correlated —
ranking, Elo and surface Elo all measure roughly the same thing — so the split between them
is unstable even though their joint effect is not. The signs of the *largest* terms are the
interpretable part.

## Finding 1 — it beats the closing price, and the procedure cannot fake it

| | log-score gain vs the market | 95% CI (day-clustered) |
|---|---:|---|
| **the model** | **+0.000862 nats** | **[+0.000471, +0.001228]** |
| the placebo | −0.000114 nats | [−0.000210, −0.000014] |

The placebo re-runs the *entire* procedure with each row keeping its price, its odds and its
result but holding another row's feature vector from the same season. Sample size, feature
correlations, penalty, walk-forward and interval are identical; only the link between a
feature and the match it describes is destroyed. It returns a small **negative** number, as
a penalised fit on noise should. The real gain is not something this procedure can
manufacture.

(Features are shuffled, not outcomes. TE-0001 recorded that shuffling outcomes is invalid —
it breaks the price–outcome coupling and asymmetric payoffs inflate returns mechanically.
That test was run once, proved nothing, and is not repeated.)

+0.000862 nats is **3.5× the best single feature** in TE-0005. Fitting the corrections
jointly, with signs free, recovers what bundling them destroyed.

## Finding 2 — against bookmakers it converts; the control proves it is the model

Flat 1u, no required-edge buffer, bet whenever the probability clears the quoted break-even.
Each book reports the model's rule and then the **identical rule driven by the market's own
de-vigged probability**. The control's return is attributable to shopping between books;
only the difference can be credited to the model.

| venue | model ROI | 95% CI | control ROI | model − control |
|---|---:|---|---:|---:|
| Pinnacle | +0.98% | [−0.36%, +2.23%] | −2.08% | **+3.06 pts** |
| Max (best of ~20 books) | +3.05% | [+2.09%, +4.06%] | +0.42% | **+2.63 pts** |
| B365 (the pricing book) | −0.01% | [−2.93%, +2.77%] | (fires 4 times) | — |
| **Betfair exchange** | **−1.81%** | [−6.12%, +2.21%] | **+2.43%** | **−4.24 pts** |

The control is what makes the bookmaker rows readable. At Max the naive rule earns +0.42%
and the model earns +3.05%, so the result is not price selection. At Pinnacle the naive rule
*loses* 2.08% — betting whenever B365 disagrees with Pinnacle is a losing cross-book bet —
and the model turns it into +0.98%. The two books agree on the model's contribution to
within half a point, which is the consistency you would want and did not have to get.

B365 is the pricing book, so betting into it correctly returns exactly zero. That is a
sanity check passing, not a result.

## Finding 3 — and at the exchange it disappears

**This is the finding that decides whether any of it is usable.**

At Betfair the model returns **−1.81%** and its control returns **+2.43%**: the model is
*worse* than doing nothing. Neither is significant on 2,722 bets from 2025–26 — exchange
coverage in this corpus is thin — but nothing here supports an exchange edge, and the sign
is wrong.

The explanation is not mysterious. Tennis-Data's Betfair column is the exchange **closing**
price, which is the sharpest number in the sport. The bookmaker edge is most likely the
model exploiting *softness* — quotes that are stale, or shaded, or slow — and the exchange
has none to exploit. TE-0003 already measured that the exchange and the bookmaker are
indistinguishable as forecasts while the exchange costs 1.12% against 4.4%; the natural
reading of all three results together is that the model's money comes from bookmaker margin
structure, not from out-forecasting a live two-sided book.

## What this means for a personal bettor

Stated plainly, because the arithmetic and the venue constraint point the same way:

- **There is a real forecasting edge.** It is measured, out-of-sample, day-clustered,
  placebo-controlled and replicated across two independent settlement books. That is a
  genuine change from where this programme stood a day ago, when six architectures had
  returned nothing.
- **It is not usable at the exchange**, which is the only venue that cannot limit or close
  a winning account. The one exchange measurement available is negative.
- **At bookmakers it is worth about +1% at Pinnacle** — and that number's confidence
  interval includes zero. It would take roughly 62,000 bets to distinguish it from zero at
  95%. The +3.05% at Max is significant but Max is not a venue: it is the best of twenty
  books, requiring twenty accounts, each of which limits winners.

So: a real edge, in the wrong place, of a size that cannot be verified in a personal
lifetime of betting at the one book that would tolerate it.

## What would change the answer

Only one thing, and it is a data problem rather than a modelling one: **a long exchange
price history**. Every measurement here prices against a bookmaker close because that is
what the corpus carries; the exchange column covers 2025–26 only, and one June of tick data
covers 3,521 markets. If the model's bookmaker edge is really an exploitation of softness,
a long exchange series would show it collapsing — and if it is not, the same series would
show the edge surviving at 1.12% round-trip cost, which is the only configuration in which
any of this is worth acting on.

That is the single question worth spending on next, and it is answerable with a purchase
rather than a discovery.

## Reproduction

`tennis_edge/experiments/residual_edge.py` — model, control, placebo and all four venues in
one run. `tennis_edge/pyramid.py` supplies the pyramid features.

Data: Tennis-Data (pinned vintage) for prices and results; Jeff Sackmann's archive
(CC BY-NC-SA 4.0, non-commercial) for the pyramid. Both stay outside the repository.
