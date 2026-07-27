# TE-0012 — The Betfair verdict was a sample-size problem, not a result

> **Control superseded by [TE-0013](TE-0013-uk-venues.md).** The n\* finding below stands and
> is the durable result. The *control* does not: it settles at Pinnacle, which has not taken
> a UK customer since November 2014, so it could not answer a question about money. TE-0013
> reruns it at Bet365 — the only UK column covering both the Betfair window and the whole
> corpus — and reaches the same verdict on a reachable venue: it is the period, not the
> venue. Left unedited as the record of what was reported at the time.

I reported the model's Betfair return as "undecided, and the point estimate is not
distinguishable from the control". Undecided was right. Treating it as evidence about the
exchange was not, and this is the correction.

## Betfair prices cover 4% of the corpus and two seasons

| book | matches priced | share | span |
|---|---|---|---|
| Bet365 | 96,052 | 100% | 2003–2026 |
| Pinnacle | 85,148 | 88.6% | 2004-01-05 – 2026-01-14 |
| Max | 71,164 | 74.1% | — |
| **Betfair** | **3,855** | **4.0%** | **2025-08-17 – 2026-07-19** |

tennis-data.co.uk only began carrying exchange prices in August 2025. Every Betfair
conclusion this project has drawn rests on eleven months of data.

## How much would be needed

At the per-bet variance this rule actually produces, resolving a 2% return at the
conventional 5% significance and 80% power needs

> **n\* ≈ 31,000 bets.**

Betfair has **2,854** — about 9% of the requirement. An interval 8.4 percentage points wide
cannot tell a 3% edge from a 3% loss, and reading "no edge" out of it is reading a conclusion
out of an absence of data.

## The control settles it

Same model, same rule, same matches — only the venue and window change.

| settlement | bets | ROI | 95% CI | width |
|---|---|---|---|---|
| Betfair, all available | 2,854 | +0.48% | [−3.76%, +4.62%] | 8.4pp |
| Pinnacle, all available | 32,195 | +0.98% | [−0.38%, +2.30%] | 2.7pp |
| Pinnacle, **restricted to the Betfair window** | 532 | **+2.16%** | [−5.52%, +10.27%] | 15.8pp |
| Max, **restricted to the Betfair window** | 1,913 | **−2.16%** | [−6.86%, +2.51%] | 9.4pp |

In that eleven-month window Pinnacle reads +2.16% and Max reads −2.16% on the same matches
under the same rule. Two venues, opposite signs, four points apart, both intervals hopelessly
wide. That spread is noise, and it is the size of the noise Betfair's 2,854 bets are sitting
in. The Betfair figure is therefore not a venue effect and not a period effect that anyone
can currently separate — it is a number with no resolving power.

## What this actually changes

**The money question is unresolved at every venue, not just Betfair.** Pinnacle's full
sample of 32,195 bets sits almost exactly at its own n\* of 29,298, which is why its interval
still touches zero. The forecast result is solid and clears zero comfortably
(+0.001064 nats [+0.000639, +0.001476] on 63,676 matches); the money result is not, anywhere.

**The binding constraint is data, and the amount needed is now known.** Roughly eleven times
the exchange history currently held — which is what the Betfair historical service covers
from April 2015. That is the single acquisition that would move this from undecided to
decided, and it was already the oldest open item on the list.

**It is unreachable from here.** `historicdata.betfair.com` returns HTTP 403 to this
container, the local copy went with a previous container, and the service requires an account
that ADR 0015 blocks. Not a modelling problem and not solvable by more layers.

## What not to conclude

Not "the model works on Betfair" — nothing here shows that. The claim is narrower and it is
the one the evidence supports: **the Betfair test as run cannot distinguish a real edge from
none, and no further modelling changes that.** The next informative act is acquiring exchange
history, not adding a feature.
