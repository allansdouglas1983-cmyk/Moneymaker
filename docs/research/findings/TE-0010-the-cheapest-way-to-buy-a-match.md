# TE-0010 findings — the cheapest way to buy a whole tennis match

**Measured:** 2026-07-26, from `tennis_edge/experiments/cover_scan.py` over the June 2026
ADVANCED corpus.

**Question:** TE-0009 asked whether two markets agree and found they do. This asks the
strongest version of the same question, and one that **cannot be improved on by adding
another market pair**.

Match Odds, Set Betting and Number of Sets are all partitions of the same space — the final
set score. A best-of-three ends exactly one of four ways, and every runner in every one of
those markets pays out on some subset of the four:

| market | runner | pays out on |
|---|---|---|
| MATCH_ODDS | "A" | A 2-0, A 2-1 |
| SET_BETTING | "A 2-1" | A 2-1 |
| NUMBER_OF_SETS | "Three Sets" | A 2-1, B 2-1 |

So the question is not "do these two books agree" but **what is the cheapest way to buy every
outcome exactly once, using any runner from any of them**. If that costs under one unit, it
is a lock regardless of which market was wrong.

**Answer: it never costs under one unit. Zero locks in 5,799 covers. The best anywhere in
June costs 1.0031 — three tenths of a percent above free.**

---

## The result

2,281 matches with a usable market group (610 unusable: no Set Betting to read the format
from, or two players sharing a surname). Best-back prices, every leg carrying at least £10,
2% commission on winnings, exact covers only.

| horizon | covers found | no cover | best return | 99th pct | positive | median stake |
|---|---:|---:|---:|---:|---:|---:|
| T−6h | 1,811 | 470 | **−0.57%** | −1.21% | **0** | £123 |
| T−1h | 1,974 | 307 | **−0.60%** | −1.08% | **0** | £145 |
| T−10m | 2,014 | 267 | **−0.31%** | −1.03% | **0** | £150 |

**The exhaustive search matters here.** Over a four- or six-outcome space with a handful of
runners, every exact cover is enumerated. A negative best is therefore not "we did not find
one" — it is *there is not one*.

## The search does find cross-market improvements. They are just never enough.

The cheapest cover uses more than the two Match Odds runners in **1,091 of 5,799 cases**:

| legs in the cheapest cover | count |
|---:|---:|
| 2 (Match Odds alone) | 4,708 |
| 3 (mixed) | 879 |
| 4 (mixed) | 212 |

So roughly one match in five is cheaper to buy through a mix of markets than through Match
Odds alone. That is real cross-market structure and the search is picking it up. It closes
most of the gap TE-0009 measured — the best position improves from **−1.21%** there to
**−0.31%** here — and still never crosses zero.

That is the informative part. It is not that the markets are unrelated and the search found
nothing; it is that the search found genuine relative mispricings and they are consistently
just too small to cover the spread.

## What this closes, and how firmly

**Cross-market arbitrage in pre-off tennis on Betfair is closed.** Not "not found" — priced,
exhaustively, across every combination of the three markets that partition the outcome space,
on 2,281 matches at three horizons.

The remaining markets in the corpus (COMBINED_TOTAL, HANDICAP, SET_WINNER) are **not**
partitions of the final set score: total games and game handicaps depend on the games within
sets, and set-winner markets on which set. Bringing them in needs the repo's coherence engine
to solve serve parameters from Match Odds plus one Total Games line and project onto the
rest — a model-based coherence check rather than an identity, so a gap there would be
evidence that a *model* disagrees with a price, not that two prices disagree with each other.
That is a weaker claim, and after this result it starts from a much lower prior.

## Why the sequence matters more than this result

This is the fourth number this line produced. The first three were:

| run | best "return" | what was wrong |
|---|---:|---|
| 1 | **+639%** | prices used without the sizes behind them |
| 2 | **+384%** | markets paired by runner position instead of by name |
| 3 | −1.21% | correct, but only two markets |
| 4 | **−0.31%** | correct and exhaustive |

Runs 1 and 2 were internally consistent, produced by clean tested code, and completely wrong.
Neither was caught by a test — both were caught by refusing to believe a number that large.
The tests came afterwards, to hold the correction in place.

## Reproduction

`tennis_edge/experiments/cover_scan.py`; exact-cover search and the outcome-space mapping in
`tennis_edge/cover.py`; size and alignment rules in `tennis_edge/xmarket.py`. Data: Betfair
Historical ADVANCED, June 2026, outside the repository.
