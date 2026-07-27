# TE-0011 — Two layers measured, one blocked, and Betfair still undecided

> **Superseded in part by [TE-0013](TE-0013-uk-venues.md).** The money table below is led by
> Pinnacle and by the panel maximum. Neither can be bet from the UK — Pinnacle closed to UK
> customers in November 2014 and the panel maximum is arithmetic over twenty books, not a
> venue. The layer measurements and the forecast result are unaffected; the settlement table
> is redone at Bet365, Ladbrokes and Betfair in TE-0013. Left unedited as the record of what
> was reported at the time.

Three layers were added to the residual model and measured against the frozen benchmark.
Each was compared paired: same rows, same walk-forward, same ridge penalty, same
day-clustered interval, one feature set difference. The only thing that varies is the layer.

## Results

| layer | gain over the model without it | verdict |
|---|---|---|
| serve detail (7 features) | **+0.000047 nats** [+0.000013, +0.000081] | KEEP |
| durability (5 features) | **+0.000150 nats** [+0.000004, +0.000293] | KEEP, marginally |

Durability's lower bound is +0.000004. That interval clears zero by a hair, and a hair is
what it is: this is a small effect held up by a large sample, not a discovery.

The model against the closing price, out-of-sample on 63,676 matches:

| feature set | gain over the closing price |
|---|---|
| 10 features (deployed) | +0.000862 [+0.000471, +0.001228] |
| 17 features (+ serve detail) | +0.000914 [+0.000516, +0.001276] |
| 22 features (+ durability) | **+0.001064** [+0.000639, +0.001476] |

Placebo, the identical procedure with features detached from their matches:
**−0.000172** [−0.000278, −0.000061]. Negative, as it must be.

## The money, and the part that matters

Flat 1 unit, settled at the actual quoted price, no required-edge buffer. The control is the
identical rule driven by the market's own probability, so its return is price selection
rather than skill.

| venue | model | control | bets |
|---|---|---|---|
| Pinnacle | +1.48% [+0.23%, +2.69%] | −2.08% | 38,078 |
| Max | +3.41% [+2.40%, +4.43%] | +0.41% | 60,817 |
| Bet365 | +2.26% [−0.15%, +4.59%] | fires too rarely | 9,549 |
| **Betfair Exchange** | **+0.48%** [−3.76%, +4.62%] | **+1.80%** | **2,854** |

**Betfair is the only venue that counts** — it is the one that cannot limit a winning
account, and Pinnacle has not taken UK customers since 2016. There the model returned
+0.48% against a control of +1.80%, on 2,854 bets, with an interval four percentage points
wide either side of zero.

So the layers improved the forecast and did not move the Betfair interval off zero. On the
venue that matters the result is undecided, and the point estimate is not distinguishable
from betting the market's own opinion. That is the honest reading and it is the one that
governs.

## What is not measured

**Cross-market coherence is blocked, not flat.** The solver in `sport_tennis/coherence/`
inverts the Set Betting / Number of Sets / Combined Total complex back to per-point serve
probabilities, which is an estimate the Match Odds price does not contain. It needs the
Betfair historical tick corpus, and that corpus is not reachable from this environment:
`historicdata.betfair.com` returns HTTP 403 and the previously downloaded copy is gone with
the container it lived in. The wiring is not written and the layer is not measured. Saying
it is flat would be inventing a result.

## Why the new model is not deployed

`artifacts/residual-model-v3.json` holds the 22-feature fit. The site still serves the
10-feature model, deliberately.

The site computes features from a per-player state snapshot, and that snapshot does not yet
carry head-to-head records, retirement rates or workload. Deploying the 22-coefficient model
against a 10-feature input would apply coefficients that were fitted *in the presence of* the
other twelve to a prediction that does not have them. Those are different numbers, and the
result would be neither the old model nor the new one. Extending the state snapshot and the
TypeScript port is the work that unlocks it.
