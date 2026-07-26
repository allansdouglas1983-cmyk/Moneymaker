# TE-0009 findings — do Betfair's own tennis markets agree with each other?

**Measured:** 2026-07-26, in-workspace, from `tennis_edge/experiments/xmarket_scan.py` over
the June 2026 ADVANCED corpus.

**Question:** every other finding here asks whether a model can out-forecast the market, and
they say that is hard and worth little. This asks something the market can get wrong without
anybody being right about tennis. Match Odds and Set Betting on the same match are related by
**identity**: for a best-of-three, P(A wins the match) is exactly P(A 2-0) + P(A 2-1). If the
two markets disagree, one of them is wrong, and which one does not matter to someone taking
both sides.

**Answer: they agree, to within the cost of trading them. Zero transactable positions in
6,305 fillable candidates.** The best cross-market position available anywhere in June 2026
*loses* 1.2%.

---

## The sample

2,891 singles Match Odds markets. 2,159 had a Set Betting partner; 592 did not; 140 could not
be reconciled by name and were refused rather than guessed at.

## Finding 1 — the markets disagree early and converge

Median absolute gap between the two markets' de-vigged views of who wins:

| horizon | markets | median gap | 90th percentile | share > 5 points |
|---|---:|---:|---:|---:|
| T−6h | 2,062 | **5.21 pts** | 26.3 pts | 50.7% |
| T−1h | 2,086 | 1.29 pts | 23.3 pts | 32.2% |
| T−10m | 2,099 | **1.04 pts** | 22.7 pts | 24.7% |

Six hours out the two markets disagree by 5 points at the median; by ten minutes out that
falls to 1 point. Set Betting is the thinner and slower of the two and spends most of the day
catching up. The disagreement is real and it is large early.

## Finding 2 — and none of it is transactable

The position: back A on Match Odds, back every one of B's scorelines, stake in proportion so
every outcome pays the same. Best-back prices only, every leg required to have at least £10
behind it, 2% commission on winnings.

| horizon | fillable | unfillable | best return | 99th pct | positive |
|---|---:|---:|---:|---:|---:|
| T−6h | 1,904 | 2,220 | **−1.62%** | −3.36% | **0** |
| T−1h | 2,102 | 2,070 | **−1.21%** | −2.65% | **0** |
| T−10m | 2,299 | 1,899 | **−1.56%** | −2.50% | **0** |

**Not one positive position out of 6,305.** The best available anywhere in the month loses
1.2%, which is approximately the combined round-trip cost of the two books. The markets
disagree by less than it costs to trade the disagreement — which is precisely what an
efficient pair of markets looks like, and is a much stronger statement than "the median gap
is small".

About half the candidate positions are **unfillable** at £10 a leg. Set Betting is thin
enough that a nominal best-back price frequently has nothing behind it.

## The two bugs this took, and why they matter more than the result

The first run reported a **+639% guaranteed return**. The second, **+384%**. Both were mine,
and both were caught only by refusing to believe the number.

**Bug 1: prices without sizes.** A Set Betting leg routinely shows a nominal best back with a
couple of pounds against it. A leg quoted at 1000.0 contributes 0.001 to the implied total —
on its own enough to manufacture a six-hundred-percent lock out of a book nobody could trade.
The programme's own rule says historical displayed prices are not executions; I had not
applied it to this market.

**Bug 2: pairing the markets by position instead of by name.** Betfair orders Match Odds
runners its own way and names players inside the Set Betting runner strings. Grouping set
scores alphabetically and pairing them positionally backs one player on Match Odds *together
with that same player's set scores* — covering one outcome twice and leaving the other
uncovered. That is an unhedged double, not a dutch, and an unhedged double can report any
number at all.

Fixing bug 2 revealed a third: strict name matching refused 2,296 of 2,299 pairs, because the
two markets do not spell players the same way. Match Odds carries "Dane Sweeny", "Felix
Gill", "Yunchaokete Bu"; Set Betting carries "Sweeny", "Fe Gill", "Yu Bu". The surname is the
only part both agree on.

The sequence 639% → 384% → 0 is the useful record here. Each intermediate number was
internally consistent, produced by clean code, and completely wrong.

## What this closes

**Cross-market arbitrage between Match Odds and Set Betting is closed.** It was the most
promising remaining idea precisely because it needed no forecasting skill — an incoherence
either locks or it does not, with no argument about whether the model beats the market. It
does not lock.

**What it does not close:** other market pairs exist in the corpus — NUMBER_OF_SETS,
COMBINED_TOTAL (total games), HANDICAP, SET_WINNER. The identity linking Match Odds to Set
Betting is the tightest and most abundant of them, so it was the right one to test first, and
its failure makes the others less promising rather than untested. The repo's coherence engine
(`sport_tennis/coherence/`) solves serve parameters from Match Odds plus one Total Games line
and projects onto the rest; connecting it to this corpus is the natural next step and now has
a realistic prior attached to it.

## Reproduction

`tennis_edge/experiments/xmarket_scan.py`; the arithmetic and its refusals in
`tennis_edge/xmarket.py`. Data: Betfair Historical ADVANCED, June 2026, outside the repo.
