# TE-0008 findings — what the frozen v2 policy actually does

**Measured:** 2026-07-26, in-workspace, from
`tennis_edge/experiments/policy_v2_backtest.py` over the cached feature matrix.

**Question:** `residual_edge` measures the *model* with a parameter-free rule — bet whenever
the probability clears the quoted break-even, no buffer — because a model has no knob to
tune. A **policy** does. v2 adds `MIN_EDGE`, and the honest order of operations is to declare
it first and only then find out what it does.

`MIN_EDGE = 0.02` was committed in `policy_v2.py`, inside the policy digest, before this was
run. That ordering is the only thing that makes the numbers below interpretable, and it is
checkable from the commit graph rather than asserted here.

---

## The result at the frozen threshold

63,576 out-of-sample matches, 2012-01-01 to 2026-07-12. Flat 1u. "Control" is the identical
rule driven by the **market's own** de-vigged probability, so its return is what shopping
between books earns with no model involved.

| venue | bets | ROI | 95% CI (day-clustered) | control | model − control |
|---|---:|---:|---|---:|---:|
| **Pinnacle** | 12,355 | **+3.55%** | **[+1.45%, +5.68%]** | −1.01% | **+4.56 pts** |
| Max (best of ~20) | 24,413 | +5.71% | [+4.05%, +7.70%] | +1.85% | +3.86 pts |
| Betfair | 864 | +6.94% | [−0.85%, +14.80%] | +4.15% | +2.79 pts |
| B365 (pricing book) | 1,523 | −0.01% | [−5.61%, +5.50%] | n/a | — |

**The Pinnacle row is the significant one and the one that matters.** Pinnacle is sharp,
always available, and does not close winning accounts — the only bookmaker where a small edge
could actually be run. Its interval excludes zero, and its control is *negative*: betting
whenever the pricing book disagrees with Pinnacle loses 1.01%, and the model turns that into
+3.55%. The B365 row returning −0.01% is a sanity check passing — betting into the book you
priced from should return exactly nothing.

## The thing that would normally condemn this, and why it does not

ROI rises monotonically with the threshold. TE-0001's addendum flagged exactly that pattern
as "the signature of an artefact rather than an edge", and it was right to.

The full curve, with the control beside it, shows what is happening:

| threshold | Pinnacle model | Pinnacle control | Max model | Max control |
|---:|---:|---:|---:|---:|
| 0.000 | +0.98% | −2.08% | +3.05% | +0.39% |
| 0.010 | +1.75% | −1.58% | +4.03% | +0.94% |
| **0.020** | **+3.55%** | **−1.01%** | **+5.71%** | **+1.85%** |
| 0.030 | +3.60% | +0.52% | +6.39% | +2.79% |
| 0.050 | +5.04% | +3.11% | +10.72% | **+11.41%** |
| 0.100 | +24.04% | n/a | +40.39% | **+65.79%** |

**The control rises too.** Most of the climb is the selection mechanism, not the model: a
higher threshold selects bigger price disagreements, which are longer-priced and
higher-variance, and that lifts a naive rule as readily as a modelled one. At Max the control
*overtakes* the model above 0.05 and doubles it at 0.10.

The model's own contribution — the difference — behaves quite differently:

| threshold | Pinnacle | Max | Betfair |
|---:|---:|---:|---:|
| 0.000 | +3.06 | +2.66 | −4.24 |
| 0.010 | +3.33 | +3.09 | +0.94 |
| **0.020** | **+4.56** | **+3.86** | **+2.79** |
| 0.030 | +3.08 | +3.60 | −2.57 |
| 0.050 | +1.93 | −0.69 | — |
| 0.100 | — | −25.40 | — |

It peaks near the frozen threshold and **collapses above 0.05**. A pure artefact would keep
climbing; this does not. That is evidence the effect is real, but it is *not* evidence that
0.02 is optimal — it was declared in advance, and a value chosen off this table would be a
fitted parameter with no out-of-sample record at all.

## The exchange, again, still undecided

Betfair at the frozen threshold is **+6.94%**, which is the first positive exchange number in
the programme. It is also on 864 bets with an interval spanning zero and a control of
+4.15%, so the model's contribution there is +2.79 points with no significance behind it.

That is consistent with TE-0007's corrected position and does not move it: **the exchange is
untested at usable power.** A positive point estimate is not a result, and three exchange
measurements now exist that disagree with each other precisely because none of them has the
sample to disagree meaningfully.

## What this licenses

**It licenses running the policy into a ledger**, which is what it was built for: a
frozen rule, committed before the matches it will be judged on, accumulating a forward record
that would detect the edge decaying — or failing to appear live at all.

**It does not license a stake.** The venue where the result is significant is a bookmaker;
the venue a personal bettor can actually run indefinitely is the exchange; and those are not
the same venue. `upcoming.py` pins its recommendation field to `NOT_EVALUATED` regardless of
anything in this document.

**It specifically does not license re-reading the threshold table.** If a different
`MIN_EDGE` is ever wanted it is a new policy vintage with its own digest and its own
out-of-sample record, not a better reading of a table produced after the fact.

## Reproduction

`tennis_edge/experiments/policy_v2_backtest.py`; policy constants and digest in
`tennis_edge/policy_v2.py`; model artefact in `artifacts/residual-model.json`.
