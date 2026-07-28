# TE-0014 — The first Betfair result that rests on data: +1.87% [+0.05%, +3.80%], hypothetical

Every prior Betfair number in this project rested on 3,742 matches from one eleven-month
window — a sample TE-0012 showed could not distinguish a 3% edge from a 3% loss. The
founder-supplied Betfair Historical BASIC archive replaces it: **27,209 corpus matches with
exchange prices at T-600s, 2015-07-01 to 2022-03-14, 1,880 distinct days**, joined through
the governed identity bridge scoped per day and priced by `exchange_prices.py` with a
traded-through verdict attached to every side.

Same 22-feature model, same walk-forward (training years never see the scored year), flat 1
unit, no required-edge buffer, 2% commission on net winnings, intervals block-bootstrapped
over whole days. 25,268 of 63,676 out-of-sample matches carry an exchange price.

## The headline, with its label attached

**Nothing here is a realised return.** BASIC is a last-trade trace: no ladder, no traded
volume. A "fill" is a price somebody else was matched at. `DR-TENNIS-MICROSTRUCTURE-001`
(BLOCKING) asks what standard a trace-only money claim must meet; until it returns, these
are hypothetical returns with their evidence split shown.

| reading | bets | ROI | 95% CI | verdict |
|---|---|---|---|---|
| **model, all fills credited** | 21,568 | **+1.87%** | [+0.05%, +3.80%] | clears zero |
| control (market's own probability), all fills | 20,113 | −1.64% | [−3.20%, +0.02%] | spans zero |
| **model, supported fills only** | 13,526 | **+2.33%** | [−0.11%, +4.83%] | spans zero |
| control, supported only | 13,016 | −1.97% | [−3.93%, +0.28%] | spans zero |

## What changed from every previous reading

**The control no longer beats the model — it loses money.** On the 2,760-bet sample the
control (+2.43%) sat above the model (−0.00%), and TE-0013 flagged the possibility that any
exchange edge was really a Bet365-versus-Betfair disagreement play. On 21,568 bets the
ordering reverses decisively: model +1.87%, control −1.64%, a spread of 3.5 points. Betting
the bookmaker's own de-vigged opinion into the exchange loses at commission, as it should if
the exchange price is efficient against the bookmaker. Whatever the model's edge is, it is
**not** price shopping. The small-sample reversal was noise, which is what TE-0012 said
eleven-month samples produce.

**The point estimate survives the fill falsification.** Restricted to fills the record
supports — the market later traded at the claimed price or better — the ROI *rises* to
+2.33% while the interval widens (fewer bets) to span zero by 0.11%. The edge is not
concentrated in phantom fills. It is, however, one hair short of clearing zero on the
strictest reading, and that is the honest headline: **suggestive on 13,526 supported bets,
not established.**

## What the falsification caught

| fill class | bets | ROI | 95% CI |
|---|---|---|---|
| unsupported (price only shortened after) | 4,525 | +3.99% | [+0.01%, +7.91%] |
| no evidence (market went silent) | 3,517 | −2.60% | [−6.93%, +1.74%] |

The **unsupported** fills are the best-looking rows in the table — +3.99% — and that is
exactly the adverse-selection signature: when the model bets and the price then only ever
shortens, the claimed price was steam the trace cannot confirm was still available. A
conventional backtest banks those 4,525 bets at full value. The **silent** markets lose
money outright. Both classes are excluded from the supported reading, and both are why the
supported reading is the one that governs.

By liquidity stratum (prints after the horizon): silent −2.60%; thin (1–4) +2.23%
[−0.24%, +4.74%]; **moderate (5–19) +4.33% [+0.68%, +8.00%], clearing zero**. The edge
concentrates where the market demonstrably kept trading — the one place a fill claim means
most. No market in the sample reached the active (20+) stratum at this horizon; BASIC's
one-minute cadence caps how many prints a ten-minute window can contain, so the upper strata
are unreachable by construction at T-600s, not merely unpopulated.

## Sample arithmetic, updated

TE-0012's requirement was n\* ≈ 31,000 bets for a 2% effect at 5%/80%. This run produced
21,568 all-fills bets (70% of n\*) and 13,526 supported bets (44%). The intervals behave
accordingly: ±1.9pp around the all-fills estimate against ±4.2pp on the old 2,760-bet
sample. One more tranche of comparable size — the truncated 2022–2026 tail of the archive,
if the source file can be re-downloaded whole — would put the supported reading over the
line one way or the other.

## Caveats that stand

1. **Hypothetical, pending DR-TENNIS-MICROSTRUCTURE-001.** No ladder, no volume, no size.
2. **The lower bound is +0.05%** on the permissive reading and −0.11% on the strict one.
   This is an edge measured in single percentage points with intervals to match.
3. **T-600s LTP is stale relative to a closing price — measured, and it cuts the other
   way.** TE-0015 found the bare exchange price at T-600s *beats* the Bet365 close by
   +0.000781 nats [+0.000116, +0.001472] despite the timing handicap. The model's offset
   therefore knows *less* than the price it out-performed here, so the gap over the control
   cannot be a timing artefact; it has to come from the features.
4. **2015–2022 only.** The archive is truncated at 94%; 2022-03 onward is missing.

## What this run used

`exchange_prices_600s.jsonl` — 27,209 rows, horizon 600s, corpus `vintage-2026-07-26`,
source digest `sha256:df6a1211…` (truncated archive, declared in its header). Feature cache
`residual-v4`, 96,052 rows, provenance printed at build. Fill evidence over the fired bets:
SUPPORTED 62.7% / UNSUPPORTED 21.0% / NO_EVIDENCE 16.3%.
