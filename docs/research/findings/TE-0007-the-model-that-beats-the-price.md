# TE-0007 findings — a real forecasting edge, and the venue it has not been tested at

**Measured:** 2026-07-26, in-workspace. Reproducible from
`tennis_edge/experiments/residual_edge.py` against the pinned Tennis-Data vintage.

> **Read the addendum before Finding 3.** Finding 3 below concluded that the edge fails at
> the exchange. A second, independent exchange measurement arrived the same day with the
> opposite sign, and both are too small to decide anything. The corrected position — the
> exchange is *untested at usable power*, not shown to fail — is in the addendum, with the
> body left standing as the record of what was concluded when.

**Question:** TE-0005 established that the closing price has a measurable defect and that
the largest single-feature correction was two orders of magnitude too small to trade. It
also explained why six architectures had failed: the market's errors point in *different
directions*, so bundling them into one composite probability cancels them. That left an
obvious next move — fit them jointly, each free to take its own sign, and add the one input
the main-tour market plausibly has not absorbed: a rating that knows the lower tiers.

**Answer, in one line: the model genuinely beats the closing price and converts to money
against bookmakers; at the exchange — the only venue that matters for a personal bettor —
the two available measurements disagree in sign and neither has the power to settle it.**

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
- **It is unproven at the exchange**, which is the only venue that cannot limit or close a
  winning account. Two measurements exist and they disagree in sign; see the addendum. What
  is certain is that it has not been *shown* to work there.
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

---

# Addendum — two corrections and the strata, same day

Two further runs landed after the above was written. One of them changes a conclusion.

## Correction: the exchange question is undecided, not negative

Finding 3 above says "nothing here supports an exchange edge, and the sign is wrong". That
was written on a single exchange measurement. There is now a second, independent one, and it
has the opposite sign.

`exchange_horizons.py` scores the same model against the **June 2026 tick corpus** — real
two-sided books, 388 markets paired to a model view, the model trained only on data before
2026-06-01, and both sides of every comparison read at the same horizon:

| horizon | market log loss | model gain | 95% CI (day-clustered) |
|---|---:|---:|---|
| T−24h | 0.59243 | −0.000714 | [−0.007381, +0.004951] |
| T−12h | 0.60330 | +0.000575 | [−0.003827, +0.005036] |
| T−6h | 0.59741 | +0.000405 | [−0.003850, +0.004514] |
| T−1h | 0.60092 | **+0.000932** | [−0.003536, +0.005378] |
| T−30m | 0.60113 | **+0.000970** | [−0.003472, +0.005377] |
| T−10m | 0.60121 | **+0.000966** | [−0.003541, +0.005381] |
| T−2m | 0.60151 | +0.000882 | [−0.003628, +0.005307] |

Positive at seven of eight horizons, and from T−1h onwards clustered at **+0.00093 — the
same magnitude as the +0.000862 measured against the bookmaker close.** Every interval
includes zero, because 388 markets buys an interval roughly ten times wider than 63,576 do.

So the two exchange measurements are: −1.81% ROI on 2,722 Tennis-Data closing quotes (CI
[−6.12%, +2.21%]), and +0.0009 nats at seven of eight horizons on 388 tick markets (all CIs
spanning zero). **Neither decides anything.** The correct statement is that the exchange is
untested at usable power, not that the edge fails there. Finding 3's wording overstated one
noisy measurement and is corrected here rather than edited away.

What it would take is now calculable rather than hand-waved. Matching the bookmaker
interval's half-width (0.00038) at the exchange needs about **49,000 markets** — roughly two
years of Betfair ADVANCED tick data at the ~2,200 usable markets per month this corpus
yields. That is the purchase referred to under "what would change the answer", now with a
number attached.

## The pre-declared strata, and the check that matters most

`attention_strata.py` partitions the out-of-sample set four ways, all fixed and committed
before the run. 13 cells scored, 8 exclude zero against 0.7 expected by chance.

| partition | stratum | n | gain | 95% CI |
|---|---|---:|---:|---|
| workload | **mismatch (>1 match in 14d)** | 14,496 | **+0.001819** | [+0.000847, +0.002866] |
| pyramid background | **mismatched (tour vs circuit)** | 20,415 | **+0.001399** | [+0.000707, +0.002109] |
| one-sidedness | clear favourite (0.60–0.80) | 33,276 | +0.000982 | [+0.000469, +0.001523] |
| pyramid background | similar backgrounds | 32,952 | +0.000796 | [+0.000264, +0.001342] |
| workload | similar workload | 38,871 | +0.000731 | [+0.000251, +0.001206] |
| — | **no pyramid record** | 10,209 | **+0.000000** | [−0.000835, +0.000841] |

Three things, in order of how much they matter.

**First, the strongest evidence in this whole line of work: where the pyramid features are
absent, the model adds exactly zero.** The 10,209 matches with no pyramid record score
+0.000000, interval symmetric about zero. The gain is not spread thinly across everything —
it lives entirely in the matches where the new information exists. A spurious effect would
have no reason to respect that boundary; a real one has no choice but to.

**Second, both pre-declared hypotheses fire in the predicted direction and by a wide
margin.** Fatigue mismatch scores 2.5× the matched cell; a tour-player-versus-circuit-player
mismatch scores 1.8× the matched cell. Those were written down before the numbers, in a file
committed before the run, precisely so this sentence could be written honestly.

**Third, the season control is not doing the job it was designed for, and that is itself
informative.** Two of its four cells clear zero. Season was included as a null partition
whose hits would reveal the false-positive rate — but a null partition only measures noise
when the underlying effect is absent, and here it is not. Splitting a real, temporally
uniform effect by season gives real cells. What the control actually establishes is that the
edge is **not concentrated in one period**, which is a different reassurance from the one
intended and a more useful one.

None of this changes the economics in Finding 3, which remain the binding constraint.

---

# Addendum 2 — is it still there? (2026-07-26)

A pooled result over fifteen years is the wrong summary if the thing being averaged is
dying, and the pooled number looks identical either way. This matters more here than it
usually would, because the *reason* the model works is that the closing price under-weights
information from below the main tour — and lower-tier data has become far more available
across exactly the period being measured. If anything in this programme was going to decay,
it is this.

`edge_decay.py`, three views of the same walk-forward, no refit.

**Early versus recent** — the two halves of the out-of-sample period:

| period | n | gain | 95% CI (day-clustered) |
|---|---:|---:|---|
| 2012–2018 | 31,704 | +0.000828 | [+0.000333, +0.001347] |
| 2019–2026 | 31,872 | +0.000895 | [+0.000330, +0.001448] |

Indistinguishable, and **both halves independently exclude zero**. That second point is
worth as much as the first: the finding does not rest on one lucky stretch, it replicates
on each half of the sample separately.

**Trend** — per-match gain regressed on year, day-clustered:

    gain per additional year  -0.00003940  [-0.00013020, +0.00004455]
    -> no detectable trend either way at this power

**Year by year**, only 2019 clears zero on its own (+0.002145, [+0.000669, +0.003626]) —
which is what fifteen noisy annual estimates of a small persistent effect should look like.
Two years are negative (2018, 2026), neither significantly. Nothing here suggests the effect
is concentrated in a period.

**The honest limit on this.** A flat slope is not proof of durability; it is a failure to
detect decay on fifteen annual points, which is a weak test by construction. What it does
rule out is the specific worry that prompted it — that the pooled number is an average over
a large early effect and nothing recent. It is not: the recent half is, if anything,
fractionally larger.
