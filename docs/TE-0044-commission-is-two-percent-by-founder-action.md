# TE-0044 — commission is 2%: the founder switched the account to the Basic package

**Date:** 2026-07-30. **Type:** account-state change, founder-executed, founder-confirmed.
**Direction:** favourable, and decisive if it holds — TE-0043 measured this as the
difference between an edge interval that spans zero and one that clears it.

## What happened

The founder switched the Betfair account's My Betfair Rewards package to **Basic** on
2026-07-30 and confirmed the account now shows **2% commission**. Package choice sets the
Exchange commission rate; the account had been on the 5% default.

This is the third value this constant has held, and each move changed the *strategy*, not
just the bookkeeping, because the rate sets the firing bar through `1/(1+(O-1)(1-c))`:

| value | when | basis |
|---|---|---|
| 0.02 | original | right number, wrong reason — "Rewards flat rate", unexamined |
| 0.05 | TE-0042 | tennis market base rate; correct for the default package |
| 0.02 | TE-0044 | founder switched to Basic and confirmed the account shows 2% |

TE-0042's reasoning ("sub-5% rates are market-specific and tennis is not among them") was
wrong about the *mechanism* — the rate follows the chosen package, not the market — but its
5% conclusion was right **for the package the account was actually on**. The historical
record it corrected stays corrected; what changed today is the account, not the analysis.

## What it is worth

TE-0043, supported-fills reading (the honest one), model probability:

| minimum edge | @5% | @2% |
|---|---|---|
| 0.00 | +1.32% spans zero | **+2.32% clears** |
| 0.02 | +2.79% spans zero | **+3.86% clears** |
| 0.04 | +1.61% spans zero | **+5.03% clears** |

At 5% the edge was undecided almost everywhere. At 2% it clears zero across essentially
the whole threshold range. No modelling change in the project's history has moved the
conclusion this much, and this one is an account setting.

## What was changed, everywhere at once

Serving path (deployed) and measurement path (repo), in the same change so no path can
disagree with another:

- `supabase/functions/tips/scoring.ts` — `COMMISSION` 0.05 → 0.02; golden vectors
  re-emitted from the Python reference at the new rate; 500 vectors agree to 1e-12; the
  divergence guard is what caught the stale vectors, exactly as designed.
- Python: `policy.py`, `policy_v2.py`, `backtest.py DEFAULT_COMMISSION`, `exchange.py`,
  and the five experiment constants (`exchange_settlement`, `residual_edge`,
  `xmarket_scan`, `cover_scan`, `uk_venue_power`).
- `consensus_multibook.py` stays 0.0 — bookmaker quotes carry their margin inside.

The two tests that hard-coded `0.98` (`test_predictor`, `test_weekly_loop`) — failing
since the TE-0042 flip and awaiting a governed correction — now pass again unmodified: the
value they pinned is the account's rate once more. No test was edited.

## Guardrails on this fact

- **Once-a-month switching.** Betfair Rewards packages change at most monthly, so the rate
  cannot silently drift under the platform; any future change is a deliberate founder act.
- **SPEC-081 status: still `ASSUMPTION`.** Founder confirmation of the account UI is the
  strongest evidence short of a settlement statement, and it is what settled TE-0042's
  open question — but "verified" is reserved for a rate read off a settled market's
  statement. The first real settled market should show a 2% deduction; if it does not,
  the statement wins and this document gets a correction notice.
- **What Basic gives up:** Sportsbook promotions (Best Odds Guaranteed, Cash Race,
  money-back offers). This operation is Exchange-only, back-only; those perks were worth
  nothing to it.

## Ledger

No SPEC-ID changes. No gate evaluated. No stake authorised. The firing bar moved DOWN with
the rate, which fires more bets — the reverse of TE-0042 — and the TE-0043 sweep already
measured both regimes, so no measurement needs re-running to know what this does.

## Correction 2026-07-30 — founder attestation on the rate's history

The founder attests the account's rate was 2% BEFORE this session's package discussion —
not newly obtained by a switch today. Under that attestation TE-0042's 5% period was not
"correct for the package the account was then on"; it was **wrong on the day it was
written**, and every conclusion that leaned on the 5%-era reading inherited the error —
most consequentially the "edge interval spans zero" framing that entered the staking
research briefs and justified excluding the per-bet (edge-consuming) allocator family
from the frozen head-to-head. The exclusion of the founder's requested allocator traces
directly to this wrong flip.

Status per SPEC-081 is unchanged in form — the statement remains the only final
authority — but the burden has moved: 2% is the founder-attested standing rate, 5% was a
session-introduced error, and the first settled market's statement is expected to
confirm 2%. All serving and measurement paths run at 2%; the per-bet allocator has now
been built and stress-tested (six-month frontier, 2026-07-30) and enters registration.
