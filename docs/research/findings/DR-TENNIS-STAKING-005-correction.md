# DR-TENNIS-STAKING-005 — CORRECTION: the minimum stake is £1, not £2

**Date:** 2026-07-30. **Type:** correction of a fabricated input that propagated into two
research runs and three findings documents.

## What went wrong

I asserted early, without checking, that Betfair's minimum stake is **£2**. It was never
verified. Worse, I then wrote it into the brief for the bank-allocation research as a given —
the resulting report tags it `[BRIEF]`, meaning the agents correctly treated it as a fact
supplied by me and reasoned from it rather than checking it.

**The entire conclusion of DR-TENNIS-STAKING-004 pivots on that number.** Its decisive line
was "full Kelly is £1.96, below the £2 chip, therefore no staking rule is expressible". That
argument dies if the chip is £1.

## The verified fact

Betfair reduced the Exchange minimum stake **from £2 to £1 on 7 February 2022**, applying to
**both back and lay** and across **all products**. Announced on Betfair's own Developer
Program forum and their own announcements page.

- <https://forum.developer.betfair.com/forum/developer-program/announcements/35781-betfair-exchange-change-of-minimum-stake-to-%C2%A31-from-7th-february-2022>
- <https://betting.betfair.com/betfair-announcements/whats-new-on-betfair/betfair-exchange-minimum-stake-were-lowering-it-to-1-020222-6.html>

The competing "£2" figure traces to a betting-affiliate page — precisely the source class
DR-TENNIS-STAKING-003 found dominates this space and which the research briefs were
explicitly told to distrust. I took the affiliate number and skipped the primary source.

Betfair's own pages return HTTP 403 to automated fetches, so this rests on their developer
forum announcement plus consistent secondary reporting of it. **Still not a live check of the
account**, and it should be confirmed against the account or a live API response before any
money moves.

## What changes: full Kelly becomes expressible

Full Kelly by price, from the same arithmetic chain as 004 (KL → δ → commission → `EV/b`):

| odds | ROI @5% | full Kelly | on £100 | expressible from bank |
|---|---|---|---|---|
| 1.30 | +1.24% | 4.36% | £4.36 | £22.91 |
| 1.50 | +1.43% | 3.00% | £3.00 | £33.31 |
| 2.00 | +1.86% | 1.96% | £1.96 | **£51.09** |
| 3.00 | +2.81% | 1.48% | £1.48 | £67.58 |
| 5.00 | +4.68% | 1.23% | £1.23 | £81.19 |

At the £1 floor, **full Kelly is placeable at every price on a £100 bank**, and has been since
about £51. The fractions are not:

| rule | stake on £100 | expressible from |
|---|---|---|
| full Kelly | £1.96 | £51.09 |
| half Kelly | £0.98 | £102.17 |
| quarter Kelly | £0.49 | £204.34 |
| tenth Kelly | £0.20 | £510.86 |

Half-Kelly misses the floor by two pence at £100 and becomes available at £103.

## What does NOT change

Everything that did not depend on the floor still stands, and it is most of the substance:

- **Adopt no Kelly rule while the edge interval spans zero** (DR-TENNIS-STAKING-003). A
  mis-signed f* scaled by any fraction is still a negative-expectation bet. This was never a
  granularity argument.
- **Plug-in Kelly systematically over-bets**, worsening with estimate variance, plus a
  winner's-curse effect because bets are filtered on estimated edge.
- **A bettor whose true edge is half the measured one is betting exactly 2× Kelly** — the
  zero-growth point — while believing they are at full Kelly.
- **Full Kelly gave 100% ruin** on 7,200 basketball and 14,400 football games under realistic
  imperfect estimates. Now that full Kelly is the *only* expressible variant on this bank,
  that finding gets worse, not better: the one rule the lattice can express is the one the
  evidence most condemns.
- **You cannot buy a statistically meaningful P&L result with £100** — best reachable t is
  0.513 against a needed 1.96. Unaffected by the floor.
- **P(wipe-out) = 0 by construction** under the floor guard. Unaffected.

## The honest net effect

The £2 error made the conclusion look cleaner than it is. The true position is not "no rule
is expressible" but something more awkward: **at £100 the only expressible Kelly variant is
full Kelly, and full Kelly is the variant the evidence most strongly warns against.** The
shrunk versions that the literature actually supports need £102 (half), £204 (quarter) or
£511 (tenth).

That still points at the same operational answer — flat minimum stakes, floor, variance
budget — but for a different and more uncomfortable reason than the one I gave.

## Process failure worth recording

An unverified number became load-bearing across two workflows and three documents because I
stated it once and then cited myself. The research could not catch it: it was handed to the
agents as a premise. The guard that would have caught it is the one this repository already
applies to data — a fact used in a money path needs a source, and "I said so earlier" is not
one.
