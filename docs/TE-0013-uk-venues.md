# TE-0013 — Which of these prices could actually have been taken

TE-0011 and TE-0012 both led their money tables with Pinnacle and with the panel maximum.
Neither is a place a person in the UK can bet. Pinnacle closed to UK customers on
1 November 2014 ahead of the point-of-consumption tax and withdrew its 2016 licence
application; the panel maximum is the best of about twenty books on each match, which is
arithmetic over the table rather than a counter anyone stands at. Reporting either as a
return describes money nobody here could have collected. This is the correction, the UK
venues that replace them, and the guard that stops it recurring.

## What Tennis-Data actually publishes

Fourteen price columns. Eleven are venues; three of those eleven are reachable with useful
coverage.

| column | venue | reachable from the UK | matches priced | span |
|---|---|---|---|---|
| BFE | **Betfair Exchange** | yes — and cannot limit a winner | 3,855 (4.0%) | 2025-08-17 – 2026-07-19 |
| B365 | **Bet365** | yes — restricts winners | 96,052 (100%) | 2002-06-10 – 2026-07-19 |
| LB | **Ladbrokes** | yes — restricts winners | 48,126 (50.1%) | 2007-12-31 – 2018-10-21 |
| UB | Unibet | yes, but the column stops in 2009 | 14,946 (15.6%) | 2005-11-05 – 2009-11-29 |
| PS | Pinnacle | **no** — closed to UK since Nov 2014 | 85,148 (88.6%) | 2004-01-05 – 2026-01-14 |
| Max | best of panel | **not a venue** | 71,164 (74.1%) | 2010-04-19 – 2026-07-19 |
| Avg | panel average | **not a venue** | 71,165 (74.1%) | 2010-04-19 – 2026-07-19 |
| EX, SJ, CB, IW, SB, GB, B&W | Expekt, Stan James, Centrebet, Interwetten, Sportingbet, Gamebookers, bwin | not UK-facing, or one season only | — | all end 2018 or earlier |

Two questions decide whether a column may carry a conclusion, and they are independent.

**Can the bet be placed?** A UK resident bets at a firm licensed by the Gambling Commission.
Bet365, Ladbrokes, Unibet and Betfair are; Pinnacle is not, and the panel statistics are not
firms at all.

**Can it keep being placed?** A traditional bookmaker prices to a margin and manages risk by
restricting accounts that win. Bet365 and Ladbrokes both will. Betfair Exchange charges 2%
commission on net winnings instead of burying a margin in the quote and does not close
accounts for winning — which is why it decides this project, and why its two seasons of
coverage are the binding constraint rather than an inconvenience.

## The measurement

Flat 1 unit, no required-edge buffer, bet whenever the model clears the commission-aware
break-even at the quoted price. Same walk-forward, same 22-feature model, day-clustered
intervals, 63,676 out-of-sample matches. Only the settlement venue changes. `n*` is the
sample a 2% return would need to be resolved at 5% significance and 80% power, given the
per-bet variance this rule actually produces.

Every venue is reported twice. The **control** is the identical rule driven by the market's
own de-vigged probability with no model correction at all; whatever it earns is price
selection between books, and only the difference between the two rows can be credited to the
model.

### Bettable from the UK

| venue | bets | model ROI | 95% CI | control ROI | n\* |
|---|---|---|---|---|---|
| Betfair Exchange | 2,854 | +0.48% | [−3.76%, +4.62%] | **+1.80%** (2,469 bets) | 31,127 |
| Bet365 | 9,549 | +2.26% | [−0.15%, +4.59%] | no control possible | 26,288 |
| Ladbrokes | 8,757 | +0.07% | [−1.89%, +1.98%] | −0.45% (7,132 bets) | 18,056 |
| Unibet | 0 | — | — | — | column ends 2009, before scoring starts in 2012 |

**No UK venue clears zero.** Bet365 comes closest and misses: +2.26% with a lower bound of
−0.15%. Ladbrokes, a decade of a second UK bookmaker, is flat at +0.07%. Betfair returns
+0.48% while its control returns +1.80%.

### Not bettable from here — diagnostics, not returns

| column | bets | model ROI | 95% CI | control ROI | n\* |
|---|---|---|---|---|---|
| Pinnacle (closed to UK) | 38,078 | +1.48% | [+0.23%, +2.69%] | −2.08% | 29,818 |
| Best of panel (not a venue) | 60,817 | +3.41% | [+2.40%, +4.43%] | +0.41% | 35,575 |
| Panel average (not a venue) | 15,105 | −0.28% | [−2.59%, +2.76%] | −0.92% | 54,990 |

**Both of the numbers that clear zero are in this table, and neither is money.** The best
result in the whole exercise, +3.41% on 60,817 bets, is the panel maximum — and it fires six
times as often as Bet365 precisely because it is the most generous price available anywhere
that day. Its own control earns +0.41% doing nothing but shopping. The gap between the panel
maximum and the panel average, +3.41% against −0.28%, is 3.7 points of pure price selection
with no forecasting in it at all.

Pinnacle's +1.48% against a control of −2.08% is the strongest *sharpness* evidence here: a
low-margin book that does not limit winners, beaten by 3.6 points over the market's own
opinion on 38,078 bets. It says the forecast is good. It does not say anyone in the UK could
have collected, because they could not.

## The control, redone at a venue that exists

TE-0012 asked whether Betfair's flat result was a venue effect or a period effect, and
answered with Pinnacle. That control was unreachable, so it could not settle a question about
money. Bet365 is the only UK column covering both the Betfair window and the whole corpus, so
it is the only one that can.

| settlement | bets | ROI | 95% CI |
|---|---|---|---|
| Bet365, all available | 9,549 | +2.26% | [−0.15%, +4.59%] |
| **Bet365, restricted to the Betfair window** | 733 | **−2.82%** | [−11.04%, +5.14%] |
| Betfair, all available (same window) | 2,854 | +0.48% | [−3.76%, +4.62%] |
| Pinnacle, restricted to the Betfair window | 631 | +0.52% | [−6.56%, +7.47%] |

**It is the period, not the venue.** Over its full history Bet365 reads +2.26%; restricted to
2025-08 to 2026-07 it reads −2.82%. In that same window Betfair reads +0.48% and Pinnacle
+0.52%. Three venues, a 3.3-point spread, every interval more than fourteen points wide.
Nothing here says the exchange is worse than a bookmaker — it says eleven months cannot
distinguish anything from anything, and that the venue Betfair is being compared against is
having a bad eleven months too.

## What the UK picture actually is

**The money question is undecided at every venue a UK resident can reach.** Three reachable
columns, three intervals containing zero. That is the finding, and it is not the same finding
as "there is no edge" — the forecast result is solid and clears zero comfortably. It is that
no settlement test currently run has the power to convert a forecasting improvement into a
demonstrated return.

**On Betfair the control beats the model, for the second measurement running.** Betting the
de-vigged Bet365 probability into Betfair's price returns +1.80% on 2,469 bets; adding the
model's twenty-two corrections gives +0.48% on 2,854. Both intervals are four points wide
either side of zero and neither clears it, so nothing is established. But the ordering is the
wrong way round, it is the same direction TE-0011 reported, and it is what an exchange-side
edge would look like if the edge were *Bet365 disagreeing with Betfair* rather than the model
knowing anything. This data cannot separate those, and that is the second reason — after
sample size — no Betfair claim is made.

**Bet365 has no control, and that is structural rather than an omission.** The model's offset
*is* the de-vigged Bet365 price, and a bookmaker's overround puts its own de-vigged
probability permanently below its own break-even, so the market's rule fires four times in
fourteen years. Every one of those 9,549 bets exists because the twenty-two corrections
overcame Bet365's margin outright, with no price shopping available to help. That makes it
the most demanding test in the table and the one with no baseline to subtract — and it still
does not clear zero.

## Two data roots, and why the numbers above are the second set

This machine held two corpus roots with different Tennis-Data vintages *and* different
Sackmann archives, selected silently by `TENNIS_EDGE_DATA`. The first run of this analysis
used the stale one and produced a coherent, plausible table in which Bet365 returned +2.84%
[+0.42%, +5.38%] — clearing zero. On the canonical corpus it returns +2.26% [−0.15%, +4.59%]
and does not. One venue's headline verdict flipped on the choice of root.

The feature cache key already covers vintage and archive digest, so a *stale cache* is a miss
rather than a silent wrong answer. Nothing caught the *wrong root*, because both roots were
internally consistent — each produced a cache that legitimately matched its own inputs.
`build_residual_features` now prints the root, the vintage id and the manifest digest on every
build. The numbers above reproduce the deployed model's own record exactly (96,052 rows,
trained through 2026-07-19, +0.001064 nats), which is the check that says the right corpus was
used.

## What is guarded now

`tennis_edge/venues.py` is a registry: every price column, whether it is a bookmaker, an
exchange or a statistic, whether a UK resident can reach it, whether it restricts winners,
and why. `uk_settlement_keys()` and `benchmark_keys()` partition it, the money reports iterate
those rather than a hand-written tuple, and `tests/unit/tennis_edge/test_venues.py` asserts
that nothing synthetic and nothing closed to the UK can appear in the settlement list. A
future table cannot be led by Pinnacle without deleting a test.

`FEATURE_SET_VERSION` moves to `residual-v4`. No feature changed — the fitted model carries
over untouched — but the Ladbrokes and Unibet quotes are now part of each cached row, and a
stale v3 cache would have answered with the old venue list.

## The Betfair BASIC archive is the exchange dataset. There is no other.

The exchange sample is the binding constraint on every money conclusion here, and the free
Betfair Historical BASIC product covers April 2015 onward — roughly ten times the coverage
the Tennis-Data `BFE` column gives. **It is the dataset. No further data purchase is in
scope, and no conclusion in this project may be written so as to require one.** A previously
purchased ADVANCED corpus was lost with the container it lived on; that is a real loss and it
does not create an entitlement to replace it.

**BASIC is a last-trade trace, not a quoted book.** It carries `EX_LTP` and the market
definition at one-minute intervals, with no ladder and no traded volume. A last-traded price
is a price *somebody else* transacted at — possibly for two pounds, possibly minutes earlier.
Treating it as a price you could have taken is the same error as treating a displayed
bookmaker price as an execution, and `tennis_edge/betfair.py` refuses to blur the two.

So the archive substantially settles **whether the model beats the exchange's own price** —
a different and better question than every number above, all of which are anchored to a
bookmaker's closing line. It cannot, on its own, prove a stake of a given size would have
been matched.

**What BASIC can be made to say about execution, without paying for depth.** A last-trade
trace is weak evidence about availability, but it is not *no* evidence, and the honest use of
it is a falsification test rather than an assumption:

- **Traded-through.** If the price the rule claims to have taken subsequently trades at that
  price or better before the off, then somebody was matched there and the claim survives. If
  the market never trades at or through it again, the fill is unsupported and the bet is
  excluded with a reason rather than credited.
- **Trade frequency as a liquidity stratum.** A price that appears in many one-minute
  observations sat in the market; one that appears once may have been a single small trade.
  Returns reported by stratum make the fragile subset visible instead of averaging it away.
- **The excluded set is reported, never dropped.** Universe in equals filled plus excluded,
  with the exclusion reason attached — the same discipline `exchange_link.py` already applies
  to the name join.

None of that recovers depth. It converts an unstated assumption into a stated, falsifiable
one, which is the most BASIC can honestly support and is worth considerably more than an
unqualified return.

**The settlement horizon stays at 600 seconds before the scheduled off, and the reason is
recorded rather than tuned.** The one experiment that could compare horizons
(`experiments/exchange_horizons.py`, against the ADVANCED corpus that did not survive) found
the spread tightening 44.9 → 3.5 ticks approaching the off while log loss stayed flat: no
information arrives late, but execution gets much cheaper late. That argues for pricing close
to the off. With BASIC the execution half of that is unobservable, so the horizon is held at
the existing default and not fitted — a horizon chosen against observed returns is a
parameter, and the best one is always found afterwards.

## What this does not change

The forecast result stands: **+0.001064 nats** over the closing price, 95% CI
[+0.000639, +0.001476], 63,676 out-of-sample matches. That was never a claim about a venue.

TE-0012's central finding also stands and is why none of the money numbers above are
conclusions: the exchange has a tenth of the sample its own variance demands, and the only
act that changes that is more exchange history.
