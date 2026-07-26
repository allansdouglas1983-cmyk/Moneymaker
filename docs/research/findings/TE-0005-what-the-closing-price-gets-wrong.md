# TE-0005 findings — what the closing price gets wrong

**Measured:** 2026-07-26, in-workspace. Every number below is reproducible from the named
script against the pinned Tennis-Data vintage; none of it is a source claim.

**Question:** six architectures had failed to beat the closing price and the fitted
market-combination gave the model a weight indistinguishable from zero in every one of
seventeen years (TE-0004). That result is consistent with two very different worlds:

1. the closing price has absorbed everything our inputs contain, or
2. our inputs contain something, and every architecture so far combined them in a way that
   destroyed it.

Nothing measured before this could tell those apart, and they call for opposite responses.

**Answer: world 2 is real, and it does not pay.** There is residual structure in the closing
price — it is detectable, it replicates out-of-sample, and its direction is the opposite of
what every model built here assumed. It is also about two orders of magnitude too small to
cross the cost of transacting.

---

## The diagnostic that separated them

`tennis_edge/experiments/serve_features.py`. Take the de-vigged closing logit as a **fixed
offset** and fit each feature *singly* against the residual, out-of-sample by year. This
asks whether a feature explains what the price missed, independently of whether any model
happened to use it well. Testing features singly rather than jointly is deliberate: a joint
fit lets a genuinely informative feature hide behind a correlated useless one, and the
question at this stage is existence, not attribution.

Significance is the **out-of-sample log-score gain with a day-clustered 95% interval**, not
the coefficient's t. The coefficient's t is an in-sample quantity — it says how precisely the
training set pinned the coefficient down, not whether it helped on data it never saw. Matches
on the same day share tournament conditions, so an unclustered interval is how noise acquires
a significant-looking statistic.

96,162 priceable matches; 68,121 scored out-of-sample (2010 onward), B365 closing, power
de-vig.

| feature | n | coef | t(fit) | OOS gain (nats) | 95% CI (day-clustered) |
|---|---:|---:|---:|---:|---|
| **rank_gap** | 68,121 | **−0.0510** | −4.11 | **+0.000249** | [+0.000044, +0.000453] |
| **point_model_residual** | 56,379 | **+0.0802** | +3.73 | **+0.000229** | [+0.000015, +0.000435] |
| **experience_gap** | 68,121 | −0.0176 | −1.69 | +0.000100 | [+0.000015, +0.000187] |
| weighted_elo_gap | 68,121 | −0.1208 | −3.65 | +0.000169 | [−0.000001, +0.000343] |
| surface_elo_gap | 68,121 | −0.0980 | −3.10 | +0.000127 | [−0.000015, +0.000286] |
| workload_gap | 68,121 | +0.0185 | +1.12 | +0.000030 | [−0.000029, +0.000089] |
| elo_residual | 68,121 | +0.0075 | +0.29 | −0.000011 | [−0.000047, +0.000022] |
| h2h_gap | 68,121 | −0.0633 | −1.32 | −0.000050 | [−0.000129, +0.000028] |
| **rest_gap** | 68,121 | −0.0041 | −0.66 | **−0.000057** | [−0.000112, −0.000003] |

**Four of nine intervals exclude zero against 0.5 expected by chance** — eight times the
false-positive rate. One of the four (`rest_gap`) is *negative*: it made the forecast
measurably worse. That matters as a control. A procedure that only ever produces positive
survivors is one that cannot fail; this one can, and did.

## Finding 1 — the market's errors do not all point the same way

This is the result, and it explains every failure before it.

`rank_gap` is `log1p(rank_b) − log1p(rank_a)`, positive when A is the better-ranked player.
Its coefficient is **negative**. So when A is much better ranked than B, the closing price
puts A **too high**. The same sign appears on `weighted_elo_gap` (−0.121) and
`surface_elo_gap` (−0.098): the price **over-extrapolates rating and ranking gaps**. This is
the favourite–longshot bias, the oldest and most replicated regularity in betting markets,
showing up in a modern tennis closing line — as a signal to **fade**, not to follow.

`point_model_residual` — the Barnett–Clarke serve model's disagreement with the price — has
the **opposite** sign, +0.080. Serve-and-return information is genuinely under-weighted.

Every architecture tested before this bundled these into one composite probability and added
it to the market in a single direction. A fade and a follow of similar size **cancel**. That
is not a metaphor for the α ≈ 0 in TE-0004; it is a mechanical explanation of it. The models
were not failing to find anything. They were averaging two real effects into nothing.

## Finding 2 — it is far too small to pay

The honest arithmetic, and it is not close.

The largest single-feature gain is **+0.00025 nats per match**. A log-score gain is, for a
full-Kelly bettor at zero cost, the expected log-growth per bet — so this is roughly **0.025%
per match before any cost**, at a staking aggressiveness nobody should use on tennis singles.

Against that:

- **B365 closing overround is 4.4%**, about 2.2% per side.
- **Betfair** is far cheaper — TE-0003 measured ~1.12% round-trip against 4.4% — but 2%
  commission on net winnings still costs roughly 1% of stake on an even-money bet.

The cheapest venue available costs about **forty times** the largest per-match gain measured.
There is no staking rule, no threshold, and no bet-selection scheme that closes a gap of that
size, because selecting a subset does not create edge — it only concentrates whatever is
there, and what is there is 0.00025 nats.

## What this does and does not license

**It does license** dropping the assumption that the inputs are worthless. They are not. The
closing price has a measurable, replicable, correctly-signed defect and this programme can
now detect it. Any future work that acquires a genuinely cheaper price, or a market with less
attention on it, starts from a real finding rather than a hunch.

**It does not license** a bet. Not a small one, not a trial one, not "to see". The measured
effect is two orders of magnitude below the cost of acting on it, and that gap is not the
kind of thing that closes with better engineering.

**It specifically does not license** the reading that a fade-the-favourite strategy is
available. The coefficient is a *conditional* correction of about 0.05 logits per unit of
log-rank gap, applied on top of the price. It is not a claim that backing outsiders wins —
TE-0001 measured that directly and it loses.

## Reproduction

- `tennis_edge/experiments/serve_features.py` — the single-feature residual diagnostic above.
- `tennis_edge/experiments/residual_edge.py` — the joint model, with money settled at
  Pinnacle, B365 and Max.
- `tennis_edge/pyramid.py` — ratings over the full professional pyramid, which the priced
  main-tour corpus cannot express.

Data: Tennis-Data (pinned vintage) for prices; Jeff Sackmann's archive (CC BY-NC-SA 4.0,
non-commercial) for results and serve statistics. Both stay outside the repository.
