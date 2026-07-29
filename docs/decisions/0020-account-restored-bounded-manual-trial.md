# ADR 0020 — Account status updated; bounded manual real-stake trial protocol

**Status:** ACCEPTED, 2026-07-29. Supersedes the BLOCKING state of ADR 0015. Recorded
from the founder's written statement in the working session of 2026-07-29.

## The facts (founder statement, corroborated)

- The self-exclusion ADR 0015 described was set **approximately eight years ago** and
  ran for **six months**. It expired long ago.
- The account remained closed until the founder **contacted Betfair and had the
  exclusion removed through Betfair's own process**, several weeks before this record.
  No new account, no third-party account, no workaround — the founder's own account,
  restored by the operator.
- Corroboration: the Betfair Historical Data archives this project has ingested
  (May 2015 – July 2026) were downloaded by the founder from Betfair's historical-data
  service, which requires a logged-in customer account. Those downloads succeeded weeks
  before this record — consistent with, and only with, a restored account.

ADR 0015's own relaxation clause — "nothing in this record may be relaxed except by
the founder, in writing" — is satisfied by the founder's statement above.

## What is now permitted

1. **Account-dependent data access** (historical archives): already exercised;
   legitimate.
2. **Delayed App Key observation** (SPEC-112): the founder may create a Delayed App
   Key; the platform may consume its data for shadow observation. SPEC-102 stands
   unchanged: real-money placement on a delayed key is impossible by construction.
3. **A bounded, founder-manual, real-stake trial** under the protocol below. Its
   purpose is evidence — actual fills at actual prices, the one thing no historical
   archive can contain — not income.

## The trial protocol (governed; the recording flow enforces what code can enforce)

- **Flat stakes only.** One fixed stake per bet, chosen by the founder at or near the
  exchange minimum. No Kelly, no scaling with confidence, no increase after losses.
- **A hard loss budget, set before the first bet.** Stored in `tennis.config`
  (`real_loss_budget`). The recording flow REFUSES to record a bet when no budget is
  set, and REFUSES when settled losses have consumed it (SPEC-060 semantics: losses
  decrement; wins do not restore). The budget is money the founder can afford to lose
  entirely, separate from all other funds (SPEC-103 spirit).
- **Back only, pre-off only, one selection per market** — the platform's standing
  rules apply to the human exactly as they would to any executor.
- **Every bet is recorded** at placement time with the actual matched price, via the
  site's recording flow, and graded from results. Retirements/walkovers are marked
  CHECK_STATEMENT, never auto-graded: for real money, **the account statement is
  truth** (SPEC-081 spirit) and the local grade is a hypothesis.
- **Placement itself is manual and human, always.** Founder directive 2026-07-29:
  everything is automated except the placing of bets. Nothing in this repository
  places, cancels, or amends an order, and nothing may be added that does under this
  ADR.

## What remains permanently in force

- **Founder directive 6 (ADR 0015):** no other person's account and no alternate/new
  account may ever be used to bypass any exclusion or closure. Permanent, regardless
  of account status.
- The three rules (CLAUDE.md): in particular, no LLM ever prices a bet or sizes a
  stake — the flat-stake protocol is deterministic and founder-chosen.
- Evidence discipline: the trial's P&L is recorded honestly, wins and losses alike;
  losing records are never deleted; the measured edge (+2.3% pooled, interval spanning
  zero after costs) is the stated expectation, meaning the trial is expected to
  roughly break even and its value is the fill evidence.

## Honest context carried forward

The forecast edge is proven; the money edge after real execution costs is undecided —
that is exactly what this trial exists to measure. Nothing in this ADR asserts the
trial will profit, and no result of the trial may be cherry-picked into a claim it
does not support.
