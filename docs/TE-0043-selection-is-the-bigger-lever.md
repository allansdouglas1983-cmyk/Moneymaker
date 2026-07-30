# TE-0043 — selection moves the edge sevenfold; staking can only rescale it. And the commission package may be the single most valuable free action available.

**Date:** 2026-07-30. **Type:** measurement. **Scope:** 89,998 side-prices, 3,255 days,
2015-05-01 to 2026-05-12, real Betfair exchange prices with per-side fill evidence.
**Raw output:** `tennis-edge/docs/evidence/staking/TE-0043-selection-sweep.txt`.

## Why this was measured before choosing a staking rule

Expected profit over a sequence of bets is

```
E[W_N] = W_0 + sum_i E[S_i * ev_i]
```

where `S_i` is the stake and `ev_i` the per-unit expected value. A staking rule chooses
the weights `S_i`. **It cannot change any `ev_i`.** Selection chooses which `ev_i` enter
the sum at all, so it is the only lever that moves per-bet expectation; sizing decides
whether the programme survives long enough to collect whatever selection earns.

That ordering is not a preference, it is arithmetic, and it says the firing rule should be
measured first. So this sweep switches sizing off entirely: flat GBP 1 stakes on a bank
large enough that the floor, the minimum stake and ruin can never bind. Everything that
moves between rows below is selection, uncontaminated by compounding.

Intervals are day-clustered bootstrap, 2,000 draws, resampling whole UTC days. Several
matches settle on the same day and share a market state; resampling individual bets treats
them as independent evidence and is the easiest available way to manufacture a confident
wrong answer.

## Finding 1 — the model beats its own market control, decisively

The control is the identical rule fired off the **market's own de-vigged probability**
instead of the model's. It answers whether the edge belongs to the forecast or merely to a
disagreement between two venues' prices. At a zero threshold, where the largest and least
selected sample sits:

| commission | source | bets | ROI | CI95 |
|---|---|---|---|---|
| 5% | model | 30,221 | **+1.08%** | [−0.51, +2.72] spans zero |
| 5% | market control | 25,372 | **−2.69%** | [−4.04, −1.31] **below zero** |
| 2% | model | 38,212 | **+2.12%** | [+0.78, +3.62] **clears zero** |
| 2% | market control | 35,479 | **−1.59%** | [−2.73, −0.37] **below zero** |

The control is not merely worse. It is **significantly negative** in both commission
regimes, on 25,000-35,000 bets, while the model is positive in both. The gap is roughly
3.7 percentage points of ROI.

This matters more than any number in the table, because the standing worry about this
platform has been that its apparent edge was a Bet365-versus-Betfair price-disagreement
artefact wearing a model's clothes. On this evidence it is not. **The forecast is doing
work the de-vigged market price does not do.**

## Finding 2 — the commission package, not the model, decides whether the edge is establishable

The supported-fills reading is the honest one: a bet counts only where the market later
traded at that price or better, so the record shows somebody was demonstrably matched
there. Model probability, supported fills only:

| minimum edge | @5% commission | @2% commission |
|---|---|---|
| 0.00 | +1.32% spans zero | **+2.32% clears** |
| 0.01 | +1.91% spans zero | **+3.22% clears** |
| 0.02 | +2.79% spans zero | **+3.86% clears** |
| 0.03 | +4.10% clears | **+4.10% clears** |
| 0.04 | +1.61% spans zero | **+5.03% clears** |

At 5% the reading is undecided almost everywhere — exactly the position TE-0020 reported.
**At 2% it clears zero across essentially the whole threshold range**, on 9,793 bets and
2,763 days at the current threshold.

Commission is not a model parameter. It is an account setting. If a 2% rate is genuinely
available on this account, obtaining it is worth more than any modelling work currently on
the roadmap, and it costs nothing.

**THIS REQUIRES VERIFICATION BEFORE IT IS ACTED ON, AND IT CONTRADICTS TE-0042'S
REASONING.** TE-0042 concluded 5% on the grounds that sub-5% rates are *market-specific*
reductions (major football, UK horse racing) which tennis does not receive. A separate
finding in the same session recorded that under the Betfair Rewards scheme the rate is set
by **package choice** — Basic 2%, Rewards 5% (the default when no choice is made),
Rewards+ 8% — rather than by market. Those two accounts cannot both be right. Until the
rate is read off an account statement, `predictions.commission_source` stays `ASSUMPTION`
per SPEC-081, and the 2% column above is a conditional result, not a claim.

## Finding 3 — one odds band is dead weight, and it replicates four times

Minimum edge 0.02, every configuration:

| band | 5% all fills | 5% supported | 2% all fills | 2% supported |
|---|---|---|---|---|
| 1.01–1.50 | +2.92% clears | +2.25% spans | +3.95% clears | +3.28% clears |
| **1.50–2.00** | **+0.54%** spans | **+0.87%** spans | **+0.13%** spans | **+0.54%** spans |
| 2.00–3.00 | +2.10% spans | +2.97% spans | +4.39% clears | +4.60% spans |
| **3.00–6.00** | **+7.51%** clears | +5.99% spans | **+9.77%** clears | **+9.46%** clears |
| 6.00+ | −1.97% spans | −2.12% spans | +2.22% spans | −1.69% spans |

The **1.50–2.00 band returns essentially zero in all four**, and 3.00–6.00 is the
strongest in all four. Two of those columns use a different commission and two use a
different fill-crediting standard, so they are materially different bet sets — this is
four-way replication, not one lucky cell. **6.00+ is bad or unmeasurable everywhere.**

## What this does NOT establish

- **The table has 384 cells scored on one realised path.** Some clear zero by chance. The
  single-cell results above are diagnostics; only the four-way replications should be
  treated as candidate findings, and even those need a pre-registered selection rule and a
  multiplicity correction before any threshold or band is adopted.
- **This is not a clean holdout.** The walk-forward fits on prior years only, so each
  prediction is out-of-sample against its own fit — but the feature set and model form
  were chosen with knowledge of the corpus. Selection effects at the design level are not
  removed by an honest walk-forward.
- **No fill is proven.** Betfair Historical BASIC is a last-trade trace with no ladder and
  no traded volume. SUPPORTED means the market later traded there or better, not that this
  order would have been matched.
- **Nothing here is a realised return**, and nothing here authorises a stake.

## What changes

`MIN_EDGE = 0.02` is revealed as an inherited constant that has never been tested. It is
now a swept parameter with a measured response surface rather than an assumption. No
threshold is adopted in this document.

The staking study proceeds as planned, but its ordering is now evidenced rather than
asserted: selection first, sizing second, and the joint policy last, because the optimal
threshold depends on the sizing rule and vice versa.

## Ledger

No SPEC-ID changes. No gate evaluated. No spend authorised. No parameter adopted.
