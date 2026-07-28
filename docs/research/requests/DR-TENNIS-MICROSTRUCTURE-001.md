# DR-TENNIS-MICROSTRUCTURE-001 — Last-traded price versus the crossable price, pre-off (BLOCKING for money claims)

**Status:** REQUESTED / AWAITING FOUNDER EXTERNAL RESEARCH. Contains **no conclusions**.
Findings inform decisions and never prove a gate (Amendment A §4).

**Classification:** BLOCKING for any *money* claim derived from the BASIC archive. NOT
blocking for forecast-quality claims, which do not depend on transactability.

**Requested:** 2026-07-27.
**Related:** SPEC-040, SPEC-041, SPEC-042, SPEC-095; `tennis_edge/fill_evidence.py`,
`tennis_edge/exchange_prices.py`, `tennis_edge/betfair.py`.

## The problem, precisely

The founder has ruled out further data purchase. The exchange data we hold is **Betfair
Historical BASIC**: `EX_LTP` plus the market definition at roughly one-minute intervals. It
carries **no ladder and no traded volume**. From it we have built 27,209 corpus matches with
exchange prices spanning 2015-07-01 to 2022-03-14 — against 3,742 matches over eleven months
previously.

A last-traded price is a print of a trade **somebody else** got. It is not an offer that was
resting and available to us, at our size, at that moment. Settling a backtest at LTP and
reporting the return therefore embeds an assumption — that every claimed fill would have
happened — and that assumption is invisible in the output: it looks exactly like a return
that was earned.

We have implemented a falsification rather than an assumption. A claimed back at price P is
SUPPORTED if the market later trades at P or better before the off (somebody demonstrably was
matched there afterwards), UNSUPPORTED if later trades exist and all are worse, and
NO_EVIDENCE if nothing traded afterwards — three states, never collapsed to two, with the
no-evidence set kept in the denominator and reported separately.

**That is a binary survival test. The question is whether it can be made quantitative
without buying depth.**

## Questions (answers with sources and publication dates)

1. **LTP versus best-back, pre-off.** Is there published or well-evidenced practitioner work
   quantifying the relationship between a betting exchange's last-traded price and the
   simultaneously-available best back price in the pre-off period? Typical spread in ticks,
   how it varies with time to the off, liquidity, and price level. Tennis specifically if
   possible; any sport if not.
2. **Is LTP biased as an estimator of the takeable price?** Directionally, does settling at
   LTP overstate or understate what a backer would have got, and by how much? A published
   distribution or even a credible order of magnitude would let us report a corrected
   interval instead of an uncorrected point.
3. **Reconstructing depth from a trace.** Are there established methods for inferring
   available liquidity or fill probability from a last-trade series alone — trade arrival
   intensity, price-reversion after a print, time between prints? What are their documented
   limitations? We would rather adopt a known method with known failure modes than invent one.
4. **The traded-through test itself.** Is the survival test described above (later trade at
   the claimed price or better) a recognised technique, under any name, in market
   microstructure or backtesting literature? If it is known, what is known about its bias —
   we expect it to be *conservative* on markets that shorten and *permissive* on volatile
   ones, but we have not established that.
5. **Betfair-specific mechanics that change the reading.** Cross-matching between Match Odds
   and derivative markets, the effect of the pre-off inplay-suspension mechanic, market
   re-creation (we observe multiple markets per match — 45,115 exclusions under
   ALREADY_CLAIMED), and anything else that would make a naive reading of a BASIC trace
   misleading.
6. **Commission and charges, current.** Betfair Exchange commission on tennis for a UK
   customer as of 2026: the base rate, how market base rate and any discount or rewards
   scheme apply, and whether any charge applies beyond commission on net market winnings. We
   currently model a flat 2% on net winnings and want that confirmed or corrected.
7. **Minimum defensible standard.** Given BASIC only, what is the minimum standard a money
   claim should meet before it is stated as a return rather than as a hypothetical? We would
   rather adopt an external standard than set our own and mark our own homework.

## Constraints on the answer

- **Jurisdiction:** United Kingdom. The account is UK-resident; venues that do not accept UK
  customers are out of scope entirely (Pinnacle among them).
- **Current as of 2026-07**, sources dated. Commission structures change.
- **No paid data may be assumed available.** ADVANCED and PRO are out of scope by founder
  decision. Answers that require them should say so plainly and be listed as unavailable
  rather than recommended.
- **No betting advice, no staking systems.**

## Deliverables

1. A quantitative statement, if one exists, of the LTP-to-best-back relationship pre-off,
   with its source and its conditions.
2. A verdict on whether our traded-through test is a recognised method, and what is known
   about its bias.
3. Any adoptable method for turning a trace into a fill *probability* rather than a binary.
4. Confirmed current UK Betfair tennis commission mechanics.
5. A minimum standard for stating a money result from trace-only data.

## Acceptance criteria

Every claim sourced and dated. Where no published answer exists, say so explicitly — "not
established in the literature" is a usable answer and much better than a plausible guess.

## Work that continues regardless

Forecast-quality measurement against the exchange price (log score, calibration,
day-clustered) does not depend on any of this and proceeds.

## Work that pauses

No return computed from the BASIC archive is stated as a realised return until question 7 is
answered or a standard is set by the founder. Until then such numbers are reported as
hypothetical, with the supported / unsupported / no-evidence split shown alongside.
