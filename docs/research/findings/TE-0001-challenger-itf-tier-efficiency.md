# TE-0001 findings — Challenger/ITF tier efficiency

**Measured:** 2026-07-25, in-workspace (not a Deep Research request — this is a direct
measurement over an acquired corpus, so every number below is reproducible from the script
and the pinned dataset hash rather than being a source claim).

**Question:** task #72 — the Challenger/ITF thesis. Published operator figures put the
achievable yield at roughly **9% in Challenger/ITF against about 2.4% on the main ATP
tour**, which would mean the tiers we never tested are the ones that matter. The thesis had
been blocked since the beginning for one reason: no Challenger or ITF prices.

**Answer: the thesis cannot be tested on free data, and the one positive number it
produces is measured against a price nobody quotes.** Detail below.

---

## The corpus

`kaggle-hallmar-atp-itf-betting` (registered in `docs/licensed-sources.yaml` as
**candidate / rights unverified**), zip sha256
`8a075d87bf55cd99ac165c8fbb8354c256c4bc6821e55014c1ae28cf5b25c3c0`, retrieved 2026-07-25.

- 1,689,433 deduped singles matches, 2008–2018, including Challenger and ITF **with full
  serve/return statistics** — genuinely richer than anything we had at those tiers.
- 217,599 moneyline quotes across 11 books.

## Finding 1 — the lower tiers have no real prices

This is the decisive result. Counting quotes by book:

| tier | quote rows | OddsPortal aggregate | real-book rows |
|---|---:|---:|---:|
| main | 159,815 | 27,794 (17.4%) | **132,021** |
| challenger | 33,845 | 31,884 (94.2%) | **1,961** |
| itf | 23,841 | 23,841 (100.0%) | **0** |

At match level, requiring two or more *real* books: main tour has 17,652 such matches,
Challenger has **152**, ITF has **zero**.

OddsPortal is an aggregator, not a bookmaker. Its number is an average across books and
across time; no one quotes it and no one can transact at it. So:

- **The cross-book consensus strategy cannot be tested at Challenger or ITF.** That
  strategy — deviation of one book from the consensus of others — is the only tennis method
  in the literature with real-money verification behind it, and it needs several books
  quoting the same match. The data has 152 such Challenger matches and no ITF ones.
- **Any model-vs-market result at those tiers is measured against an unbettable price.**

## Finding 2 — the overround is nearly double

| tier | overround | market log loss |
|---|---:|---:|
| main | 1.0436 | 0.56165 |
| challenger | 1.0728 | 0.58839 |
| itf | 1.0796 | 0.53723 |

Lower tiers are **7.3–8.0% overround against 4.4% on main tour**. Before any question of
skill, the cost of doing business at Challenger/ITF is roughly twice main tour. That cuts
directly against the 9%-yield thesis rather than supporting it: the tier is not cheap to
trade, it is expensive.

(ITF log loss is *lower* — those matches are more predictable, larger skill gaps — but that
is predictability, not profit. The market prices it too.)

## Finding 3 — information without money

Walk-forward Elo (FiveThirtyEight K, blocked by tournament start and round so no result
informs a prediction made in the same block), trained on the full 1.69M-match pyramid,
scored only where both players have ≥10 prior matches. `b1` is the incremental weight on
the model beyond the market — the same measure reported for the four architectures already
tested, so it is directly comparable. ROI is flat stakes at the **actual quoted price**
with a 5% required edge.

| tier | scored | b1 | t | bets | ROI |
|---|---:|---:|---:|---:|---:|
| main | 31,006 | 0.1604 | 6.69 | 19,221 | **−5.51%** |
| challenger | 31,005 | 0.1704 | 5.61 | 13,523 | **−7.44%** |
| itf | 22,510 | 0.5278 | 19.09 | 10,471 | **+1.24%** |

`b1` is positive and statistically significant at every tier — the model carries real
information the displayed price does not. **It converts to money at none of them.** The
overround eats it. Main tour and Challenger lose 5.5% and 7.4%.

The ITF +1.24% is not an edge:

1. It is priced **100% against the OddsPortal aggregate** — see Finding 1. There is no
   book behind it. This is precisely the failure the programme rules name: *historical
   displayed prices are not actual executions*, and *prove EV at crossable prices*.
2. It is not significant. Per-bet standard error is ≈0.98% at these odds, so +1.24% is
   about 1.3 standard errors from zero — and that understates the variance, because
   longshot bets have per-bet variance above 1.
3. It is gross. No commission, no slippage, no stake-size constraint. ITF markets could not
   absorb meaningful stakes even if the price were real.

### Why b1 here (+0.16) contradicts b1 on Tennis-Data (−0.027)

Both are honest; they measure against different things.

- The Elo here is trained on the **whole pyramid** including ITF and Challenger, so it knows
  about lower-ranked players and qualifiers that a main-tour-only rating has never seen.
  That is a genuine information advantage and probably explains part of the gap.
- The price here is an **aggregate, frequently stale**: 192,350 of 217,599 quote rows carry
  a `betting_date` on or after the tournament start date, so for many matches the recorded
  number is not a pre-match closing price. Beating a stale average is not an edge.

The Tennis-Data measurement is against a genuine Pinnacle closing price and remains the one
to trust. This corpus does not overturn it.

## Verdict on task #72

**Closed as untestable on free data, thesis unsupported by what could be measured.**

The tiers where the published edge is claimed are exactly the tiers where free data has no
transactable prices. Testing it properly needs real-book Challenger/ITF quotes — which means
either exchange historical data (Betfair returns 403 to this container; geo-blocked) or a
paid odds feed. Neither is reachable at £0.

Where real prices *do* exist — main tour — the same method loses 5.51% over 19,221 bets.

## Reproduction

`tennis_edge/experiments/tier_efficiency.py`, against the pinned dataset hash above.
The corpus stays outside the repository and is research-quarantined (SPEC-100): it must not
acquire an import path into anything reachable from `l5_decision`, `l5b_risk` or
`l6_broker`, and its unverified rights make it unusable for any commercial output
(SPEC-044, SPEC-101).
