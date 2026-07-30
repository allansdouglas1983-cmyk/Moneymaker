# TE-0036 — the shape of the ride: drawdown, ruin, and what a small budget can prove

Harness `tools/drawdown_profile.py`. The frozen TE-0019 rule's 13,526 SUPPORTED bets at
flat 1 unit, 2% commission, in date order; then a day-block bootstrap (2,000 resampled
histories, days kept intact to preserve within-card correlation) for the *distribution*
of worst case; then the same variance structure with the mean shifted to each edge
hypothesis our own confidence interval permits.

## The observed history

| quantity | value |
|---|---|
| bets / days | 13,526 over 1,823 |
| terminal P&L | **+314.9 units** (+2.33% ROI) |
| longest losing run | 17 bets |
| worst single day | −13.7 units |
| max drawdown | **127.6 units** |
| deepest level reached | −6.0 units |

To earn 315 units you must sit through a 128-unit hole. That is the honest price of the
edge, and it is 40% of everything the edge produced in eleven years.

## The observed path was lucky

| | observed | bootstrap median | p10 / p90 | p1 / p99 | worst |
|---|---|---|---|---|---|
| max drawdown | 127.6 | 107.1 | — / 167.0 | — / 248.1 | 329.2 |
| deepest level | **−6.0** | **−28.8** | −95.1 / — | −191.8 / — | −313.9 |

The real sequence never went more than 6 units underwater; the median re-ordering of the
*same bets* goes to −29, and one in ten goes below −95. The historical path flatters the
experience of running this strategy. **Anyone starting today faces the distribution, not
the path.**

## The stress test that matters

Everything above assumes +2.33% is the true edge. Our own 95% interval is
[−0.11%, +4.83%] — zero is permitted. Shifting every bet by a constant preserves the
variance exactly while moving the mean to a hypothesised truth:

| hypothesis | median max DD | P(ruin \| 50u) | P(ruin \| 100u) | P(ruin \| 200u) |
|---|---|---|---|---|
| as measured +2.33% | 107 | 28.9% | 8.8% | 1.0% |
| CI lower −0.11% | 198 | 78.0% | 57.4% | 25.4% |
| no edge 0.00% | 191 | 76.2% | 54.1% | 22.8% |
| cost-eaten −1.00% | 264 | 91.8% | 78.8% | 51.1% |

## What this changes

1. **A small real-money trial cannot settle whether the edge exists.** At a 50-unit
   budget, ruin is 29% if the edge is real and 76% if it is not. Both outcomes happen
   often under both hypotheses, so hitting the floor is weak evidence against the edge
   and surviving is weak evidence for it. This is not a defect in the trial — it is why
   ADR 0020 states the trial's purpose is **fill evidence**, not income and not proof.
   TE-0036 supplies the numbers behind that sentence.
2. **The budget should be set to survive, not to test.** At £2 flat, £100 is 50 units
   and carries a ~29% chance of exhaustion *even if the edge is exactly as measured*.
   Expect roughly a one-in-three chance the trial ends at the floor through variance
   alone. Sizing the stake relative to the budget is the single most consequential
   operational parameter and until now had no measured basis.
3. **Seventeen consecutive losers is normal.** Any stopping rule that reacts to a losing
   run shorter than that is reacting to noise. Recorded here so that a run of losses is
   not later mistaken for a broken model.
4. **The evidence route must be CLV, not P&L.** Given ruin probabilities of this size at
   any budget a single person would use, settled P&L cannot resolve the question on a
   human timescale. That is the argument for the closing-line-value monitor shipped
   alongside this finding.

## Status

DIAGNOSTIC, non-gating. Hypothetical trade-through returns (TE-0019 SUPPORTED class), so
the drawdowns are hypothetical too; real execution can only make them worse. Sizes no
stake, moves no threshold, authorises no spend. Staking remains flat minimum stake under
a hard budget (ADR 0020) and any change to that is a governed specification change with
human approval.
