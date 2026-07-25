# TE-0002 — The tennis models actually in use, how they are calculated, and what each measured

**Written:** 2026-07-25. This is the write-up that should have existed months ago. The
research was done and turned straight into `tennis_edge/`; it was never written down, so it
has been invisible. Every method below is a real, published, in-production model — not
something invented here.

**Bottom line up front:** all five are implemented, all five are measured walk-forward
against the same pinned benchmark, and none of them beats the closing price at a price you
can transact at. That is the same answer the published literature reports.

---

## 0. The benchmark everything is measured against

De-vigged Pinnacle closing price, **log loss 0.57539** over 113,547 ATP/WTA matches
(2000–2026 ATP, 2007–2026 WTA), pinned as a CI regression test.

Margin removal matters more than people expect. Four methods implemented in `devig.py`:

| method | formula |
|---|---|
| proportional | `p_i = (1/o_i) / Σ(1/o_j)` |
| multiplicative | same, applied to normalised inverse odds |
| **power** (default) | solve `k` such that `Σ (1/o_i)^k = 1`; `p_i = (1/o_i)^k` |
| Shin (1993) | solves for insider-trading fraction `z`, favourite–longshot aware |

**Power is the default** because it leaves the market at calibration slope **1.011** —
essentially perfectly calibrated. Proportional de-vigging leaves a visible favourite–longshot
distortion that a naive model then "discovers" and mistakes for edge. Getting this wrong
manufactures fake alpha, which is why it was the first thing built.

---

## 1. FiveThirtyEight Elo — Sackmann / Morris

**Who uses it:** FiveThirtyEight's published tennis ratings; Jeff Sackmann's Tennis Abstract.
The de facto public baseline.

**Calculation.** Standard Elo with a decaying, match-count-dependent K:

```
E_a  = 1 / (1 + 10^((R_b - R_a)/400))
K(m) = 250 / (m + 5)^0.4          # m = matches played by that player
R_a' = R_a + K(m_a) · (S_a - E_a)  # S = 1 win, 0 loss
```

- Grand Slam matches carry **K × 1.1**.
- Everyone starts at **1500**.
- The K decay is the whole point: a new player's rating moves fast, a veteran's barely
  moves. It is a crude but effective substitute for a proper uncertainty term.

**Surface Elo.** A parallel rating per surface, blended **50/50** with the global rating.
Surface ratings **cold-start at the player's global rating**, not at 1500 — otherwise a
top-20 player's first clay match says they are average, which is plainly false and injects
noise exactly where surface data is thinnest.

**Implementation:** `tennis_edge/ratings.py`. Day-batched: every match on a UTC date is
scored against start-of-day ratings and the deltas applied together, so a morning result
cannot inform an afternoon prediction.

**Measured: b₁ = −0.027.** Negative incremental weight over the closing price. The market
already contains everything this knows, and then some.

---

## 2. Angelini–De Angelis WElo — margin-weighted Elo

**Who uses it:** published in the tennis-forecasting literature as a strict improvement on
plain Elo; used by several public rating projects.

**Calculation.** Identical to Elo except the score `S` is not 1/0 but the share of games won:

```
f(G) = NG_winner / (NG_winner + NG_loser)
R_a' = R_a + K · (f(G) - E_a)
```

A 6-0 6-0 win moves the rating far more than 7-6 6-7 7-6. The intuition is sound — margin
carries information a binary result throws away.

**Implementation:** `tennis_edge/ratings.py` alongside the plain and surface variants.

**Measured:** folded into the rating layer's b₁ = −0.027. No separable improvement over
plain Elo against the closing price.

---

## 3. Barnett–Clarke serve model + O'Malley hierarchical Markov

**Who uses it:** this is *the* tennis pricing engine. It is what tennis traders and
quant desks actually price matches with, and what most commercial tennis models are
underneath.

**Calculation.** Two stages.

**(a) Barnett–Clarke — combine serve and return into a match-specific serve probability:**

```
f_ij = f_t + (f_i - f_av) - (g_j - g_av)
```
where `f_i` = player i's serve-points-won rate, `g_j` = opponent j's return-points-won rate,
`f_av`/`g_av` the tour averages, `f_t` the tournament average. It is additive in
*deviations from average* — a strong server against a strong returner nets out.

Serve rates are **shrunk toward the tour mean** in proportion to sample size, otherwise a
player with 40 recorded serve points gets a wild estimate.

**(b) O'Malley — propagate a point probability up to a match probability**, by exact
recursion rather than simulation:

```
game(p)      -> closed form from p
tiebreak(p,q)-> recursion over the 7-point race
set(p,q)     -> recursion over games + tiebreak
match(p,q)   -> best-of-3 or best-of-5 over sets
```

**Verification.** The implementation reproduces O'Malley's published values *exactly*:
best-of-3 at p=.6250/q=.6150 → **0.5506**; at .6450/.5950 → **0.7374**; best-of-5 → **0.7865**.
Serve-difference sensitivity **5.06**, matching the literature. That is how I know the
recursion is right and not merely plausible.

One correction worth recording: I initially asserted `p_serve_a + p_serve_b == 1`. That is
**wrong** — Barnett–Clarke guarantees consistency *within* a service game, not across the
two players' serve probabilities. Two of my own tests encoded that error.

**Implementation:** `tennis_edge/point_model.py` (memoised recursions),
`tennis_edge/serve_stats.py` (shrinkage, 8-day tournament lag because archive dates stamp
the Monday of the tournament week).

**Measured: b₁ = +0.056, Diebold–Mariano t = 1.89.** Positive but not significant. This is
the best of the five and it is still not enough. Notably it needs the Sackmann serve
archive, which main-tour-only price data does not carry — that is why the serve-stat gap was
worth closing.

---

## 4. Kaunitz et al. — cross-book consensus deviation

**Who uses it:** the only tennis-adjacent strategy in the literature with **verified
real-money results** (Kaunitz, Zhong, Kreiner — they bet real money and published the
account history, then had accounts limited, which is itself the finding).

**Calculation.** Not a model of tennis at all — a model of *bookmakers*:

```
consensus_i = mean over books ≠ target of logit(devig(price_i))
edge        = sigmoid(consensus) · decimal_odds_target - 1
bet if edge > threshold
```

The bet is that a book out of line with its peers is wrong, not informed.

**The trap, and the guard.** Measuring a book against a consensus **that includes it** is
circular: every variant shows positive CLV, including ones losing 12%. `consensus.py`
therefore *raises* if the CLV reference is inside the consensus set. A related trap: a
45-variant sweep was "won" by a 54-bet variant betting into `Avg` — a panel average, not a
book. Hence a bet floor and aggregate exclusion.

**Measured: CLV −1.59%, deflated Sharpe 0.048** on Tennis-Data closing prices.

**Caveat — untested at proper width.** Tennis-Data carries two real books plus two
aggregates, so that test was effectively two books wide. A ten-book test on a separate
corpus returned an implausible +33% and is recorded as a **suspected data defect, not an
edge** (see TE-0001 addendum). Testing this properly needs multi-book quotes with verified
provenance.

---

## 5. Residual gradient boosting on a market offset

**Who uses it:** standard practice wherever a strong baseline price exists — model the
*residual*, never the level.

**Calculation.** Feed `logit(p_market)` to LightGBM as `init_score`, so the tree ensemble
only ever learns what the market misses. Critically, `predict()` does **not** re-add the
offset — a classic and silent source of double-counting.

23 features (form, fatigue, rest days, head-to-head, surface history, rank deltas).
**Price columns are banned as features** and the ban is enforced structurally by
`features.py::assert_no_price_features`, not by convention.

**Measured: +0.00018 nats, DM t = 0.94.** Indistinguishable from zero.

---

## Scoreboard

| model | in-use by | measured |
|---|---|---|
| 538 Elo / surface / WElo | FiveThirtyEight, Tennis Abstract | b₁ = −0.027 |
| Barnett–Clarke + O'Malley | tennis trading desks | b₁ = +0.056, DM t = 1.89 |
| Kaunitz consensus | published real-money study | CLV −1.59%, DSR 0.048 |
| Residual GBM on market offset | standard practice | +0.00018 nats, DM t = 0.94 |
| Full-pyramid Elo vs real books | — | **−5.51% ROI**, 19,221 bets |

**Every one is flat against the closing price.** That is not a failure to find the right
model — these *are* the right models, implemented faithfully and verified against published
values where published values exist. It is what the efficient-market result looks like when
you check it honestly.

## What is genuinely untested

Not a model. A price. Every measurement above uses **bookmaker closing prices**, which carry
a 4.4% overround and are the hardest possible benchmark. The untested case is **exchange
prices** — Betfair, where there is no overround, only commission on net winnings, and where
the price is what someone will actually trade at rather than a displayed line.

That is the one open question, and it is blocked on data access, not on modelling
(ADR 0015; Betfair also geo-blocks this container). Nothing in the model layer is waiting on
more research.
