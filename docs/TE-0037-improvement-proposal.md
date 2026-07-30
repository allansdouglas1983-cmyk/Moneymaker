# TE-0037 — where profit can and cannot come from: a system-wide proposal

Founder request, 2026-07-30: consider every area of the prediction system and propose
what would make it more profitable. This is the lead engineer's own audit; a parallel
multi-agent audit runs alongside and its surviving proposals will be merged in.

## The honest headline

Three things can raise realised profit, and only three: **a bigger edge**, **a smaller
cost of taking it**, or **more bets at the same edge**. Everything else — better
dashboards, cleverer staking, faster refreshes — either serves one of those or serves
*confidence about whether the edge exists at all*. Both are worth doing. They are not
the same thing, and this document keeps them apart.

The binding fact remains: forecast edge is proven (+0.0011 nats over the exchange price,
63,676 matches, calibrated on unseen data), money edge after execution costs is not
(+2.33% hypothetical, CI spanning zero, cost band half-width ~1.25%). **No item below
changes that. The realistic ceiling on "make it more profitable" today is to stop losing
edge we already have, and to find out faster whether the edge survives contact with
reality.**

---

## Done today

| what | which lever | evidence it worked |
|---|---|---|
| Price age served and displayed, amber past 2h | smaller cost | TE-0027 priced delay at ~0.2% ROI; the board previously showed a 5-hour-old quote identically to a fresh one |
| Closing-line-value monitor (`/clv`) | faster confidence | CLV converges far sooner than P&L; TE-0027 found the drift historically, this asks whether it persists live |
| All-venue price capture (~20/match/refresh) | smaller cost + confidence | raw material for line shopping and CLV; 156 observations on first run |
| Durable name aliases + unmapped queue | more bets | every unresolved name is a match with no opinion — evidence not collected |
| TE-0036 drawdown and ruin profile | survival | budget sizing had no measured basis; now it does |
| Schema in git | robustness | 18 tables existed only inside Supabase |

---

## Do next, ranked

### 1. Register the Betfair certificate (founder action, minutes)
Unblocks order-book depth capture, already written, tested and deployed dormant. This is
the **only** route to answering the fill question — whether a stake would actually have
been matched at the flagged price — which is the single largest unknown in the money
case and the reason the cost band spans zero. Nothing else on this list moves that.

### 2. Let CLV accumulate, then read it before anything else changes
Four to eight weeks of live CLV will say more about whether the edge is real than a year
of settled P&L, because TE-0036 shows P&L cannot resolve it at any budget a single person
would use. **Do not tune anything until this reads.** If CLV is reliably positive, the
edge is live and the remaining question is purely execution. If it is zero, no staking
scheme, filter or feature will save the system, and that is worth knowing cheaply.

**A caveat on item 2, recorded rather than glossed.** The board refreshes three times a
day (06:15 / 12:15 / 18:15 UTC), so for a match starting at 17:00 the last pre-off quote
is from 12:15 — nearly five hours early. That is a *pre-off* line, not a *closing* line,
and much of the informative drift happens in the final hour. So the CLV monitor as built
measures a weaker version of the quantity it names, and will understate the signal.

Two honest consequences: the endpoint's numbers should be read as "drift over the last
several hours before the off", not textbook CLV; and the fix is not more odds-API polling
(the free tier's 500 credits/month cannot fund hourly refreshes) but the **order-book
capture at 30-minute intervals**, which is dormant pending the certificate. This is a
third independent reason item 1 is ranked first.

### 3. Measure whether the model's edge varies by ROUND and TOURNAMENT TIER
A genuine gap found today: **all 22 features are differences between the two players.
None describe the match context.** `round_name` and `tier` are parsed from the corpus and
never reach the model.

The disciplined version of this is *not* to add them as features — the market knows the
round too, so a main effect would mostly be absorbed by the anchor. The question worth
asking is whether the **model's edge over the market** differs by context: first rounds
and lower tiers draw less attention and less liquidity, which is exactly where TE-0001
already found tier inefficiency.

Measure it on **log-score, not ROI.** Log-score per match has far better signal-to-noise
than realised return, so the strata may actually resolve where TE-0035's ROI slices all
spanned zero. Pre-register the strata before looking, record the alpha cost in the trial
ledger (SPEC-091), and treat any differential as evidence for a governed decision — never
as an immediate filter, which would be exactly the post-hoc threshold-fitting the frozen
policy forbids.

### 4. Keep the venue capture running and let it kill or confirm line shopping
First 8 captures: Betfair was the best exchange price **every time**, zero gain. That cuts
against the thesis that motivated the capture, which is why it is measured rather than
assumed. Give it a month. If the answer stays zero, line shopping is a dead end here and
we learned it for the price of a database table.

---

## Requires a governed change, with the evidence that would justify it

- **Any move off flat stakes.** TE-0036 gives the ruin arithmetic; the fractional-Kelly
  literature gives the failure mode (over-betting an *overestimated* edge destroys a
  bankroll faster than flat staking). Precondition: a live edge established by CLV **and**
  fill reality established by order-book data. Not before both.
- **Budget sizing.** TE-0036 says a 50-unit budget carries ~29% ruin if the edge is real
  and ~76% if it is not. The founder should choose the stake:budget ratio knowing that,
  and should expect roughly a one-in-three chance of the trial ending at the floor through
  variance alone even in the good case.
- **Any bet-selection filter** (outsiders-only, round-restricted, tier-restricted).
  Pre-registration first, always.

---

## Explicitly rejected, with reasons

| proposal | why not |
|---|---|
| Restrict betting to outsiders on TE-0035's +4.26% | Not selected in advance; CI spans zero; width ≈ the estimate. Adopting it is threshold-fitting. |
| Kelly or fractional Kelly now | Prohibited in v1, and the precondition (a *known* edge) is precisely what we lack. |
| Martingale / Fibonacci / d'Alembert progressions | Arithmetically incapable of turning a negative or zero expectation positive; they convert small frequent wins into rare catastrophic losses. Named here so they are never revisited. |
| Retrain more often / on live outcomes | Prohibited (no automatic live learning). Also pointless: ~500 new rows against 96,000 moves coefficients negligibly. |
| Add round/tier as plain model features | The market already knows them; a main effect is mostly absorbed by the anchor. The stratified *diagnostic* (item 3) is the version with information in it. |
| Line shopping across bookmakers | Bookmakers restrict consistent winners (`tennis_edge/venues.py`). A price only they offer has an expiry date it cannot control. |
| Pinnacle as an additional benchmark | Closed to UK customers, so never a return; and Betfair Exchange is already at least as sharp and is where a bet would actually go. Doubles credit usage for a diagnostic we effectively have. |
| Extending to football or racing now | Multiplies the multiple-testing problem before the tennis money question is settled. Racing additionally lacks free form data (see the session record of 2026-07-30). |

---

## The single highest-value thing

**Register the certificate, then leave the system alone for a month and read the CLV.**

Everything built today was aimed at making that month informative: prices captured across
venues and time, predictions minted automatically before every match, coverage gaps
logged rather than silently lost, both scorecards grading themselves. The system's job
now is not to be improved — it is to *run untouched and produce an honest read*. The
strongest temptation to resist is adjusting it while the evidence accumulates, because
every adjustment resets the clock on the only measurement that can settle the question.

## Status

PROPOSAL, non-gating. Nothing here changes a served number, a threshold, or a stake.
Items 3 and any filter require pre-registration and human approval before they run.
