# TE-0042 — the commission rate is 5%, not 2%, and it costs 1.97 points of ROI

**Date:** 2026-07-30. **Type:** correction of a labelled assumption to a published fact.
**Direction:** unfavourable. Every displayed edge gets worse.

## The finding

The platform hard-codes commission at **2%**, described in `scoring.ts` as the "Betfair
Rewards flat rate". For **tennis on a standard UK Betfair Exchange account that is the
wrong number.** The market base rate is **5%**.

The 2% reductions that exist are market-specific — major football (Premier League,
Champions League) and UK horse racing — and **tennis is not among them**. Going below the
base rate otherwise requires actively accumulating Betfair Points through the rewards
programme. The founder confirmed directly (2026-07-30) that this is a standard account
with no plan, no tier and nothing extra.

That single fact is what settles it, and it did not need account access to establish. The
rate is published; the only unknown was which plan applied, and the answer was "none".

Sources, all consistent on 5% for tennis and on commission being charged on **net winnings
per market** rather than per bet:
- <https://support.betfair.com/app/answers/detail/412-exchange-what-is-the-market-base-rate/>
- <https://www.betting.co.uk/reviews/betfair/commission/>
- <https://betfairsquare.com/sports/tennis>
- <https://betfair-datascientists.github.io/wagering/commission/>

Betfair's own support pages return HTTP 403 to automated fetches, so the rate above rests
on secondary sources that agree with each other and with the base-rate structure. **An
account statement remains the only true confirmation** (SPEC-081: the statement is truth),
and this document should be revisited when the first real settled market produces one.

## What it costs, measured

Bet set **frozen at the 2% rule** so the commission effect is isolated from the selection
effect. 6,546 markets, 1,597 days, exchange prices, MIN_EDGE = 0.02:

```
ROI @ 2% commission   +8.315%
ROI @ 5% commission   +6.345%
COST OF THE ERROR     -1.970 percentage points of ROI
                      day-clustered CI95 [-2.056, -1.887]
```

This lands exactly where theory says it should. With `dROI/dc = -G`, where G is mean gross
winnings per unit stake, the measured G = 0.6566 predicts `-0.6566 x 0.03 = -1.970` pp. The
measurement and the closed form agree to three decimals, which is the check that the number
is real rather than an artefact of the harness.

The ROI levels above are uncosted and in-sample; **only the difference is the finding.**

## Two separate consequences, and the second is worse

**1. Returns fall by ~1.97 points.** Applied to TE-0019's supported reading of +2.63%, the
honest figure becomes **≈ +0.66%** — and TE-0020 already showed that reading spans zero once
declared execution costs are applied. At 5% there is no surviving claim of an edge.

**2. The FIRING RULE was wrong, which is the more serious error.** Break-even is
`1/(1+(O-1)(1-c))`, so a wrong `c` moves the bar itself:

| odds | break-even @2% | @5% | shift |
|---|---|---|---|
| 1.50 | 0.6711 | 0.6780 | +0.68 pp |
| 2.00 | 0.5051 | 0.5128 | +0.78 pp |
| 3.00 | 0.3378 | 0.3448 | +0.70 pp |
| 5.00 | 0.2033 | 0.2083 | +0.51 pp |

Every bet whose edge sat inside that strip was fired on a bar that was too low, and was
negative-EV at settlement. At MIN_EDGE = 0.02 over the exchange-priced corpus:

```
markets firing @2%   6,546
markets firing @5%   4,153   (63.4%)
fired at 2%, not at 5%   2,393
```

**Over a third of everything the rule ever fired should not have fired.** That is not a
restatement of returns; it is a different strategy.

## Why this was invisible

The error was made *consistently*, in the backtest and in the serving path alike. A
backtest that applies the same wrong commission everywhere produces internally coherent
numbers — the bias is in the level, and nothing inside the measurement contradicts it. This
is precisely the failure mode `breakEvenProbability`'s own docstring warns about: "the error
is invisible in a backtest that makes it consistently."

Eleven years of measurement did not catch it because nothing in the data could.

## What changes

Corrected to 0.05 in the served path and the measurement path. Every prior money figure
computed at 2% is **restated, not deleted** — the old numbers were arithmetically correct
given a false input, and the record of the error is worth more than a tidy history.

`predictions.commission_source` stays **`ASSUMPTION`**, not `VERIFIED_STATEMENT`. A published
base rate is a much better assumption than the previous one, but SPEC-081 reserves "verified"
for a rate read off an account statement, and that standard is not met by a web page.

## What this does NOT change

No model coefficients, no features, no de-vig method, no execution-cost band. The commission
enters only through `breakEvenProbability`, and this is a correction to an input, not a
refit. The model's probabilistic claims are untouched; what changes is the price at which
acting on them is worthwhile.

## Ledger

No SPEC-ID changes. No gate evaluated. The correction is applied regardless of direction, as
a defect fix — and the direction is unfavourable, which is the reason it must be applied
rather than deferred.
