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

## Amendment 2 — 2026-07-30, founder directive: the trial staking rule is the per-bet allocator, not flat

The founder has explicitly and repeatedly rejected flat staking for the trial. By
founder directive the trial's staking clause is superseded: suggested stakes follow the
registered conservative per-bet allocator (`tennis_edge.staking.rules.conservative_kelly`
— f_i = 0.355 × Kelly(p_model_i, O_i, c) of the live bank, HB-capped; the 0.355 is the
TE-0043 measured conservative-bound/point ratio, provenance-pinned, never a default).

Unchanged and still binding: placement is manual and human ALWAYS; the recording flow
refuses without a pre-set loss budget and when the budget is exhausted; back-only,
pre-off-only, one selection per market; honest recording; directive 6. The site displays
a suggested stake; it places nothing and authorises nothing — the founder decides at the
point of placement, every time.

## Amendment 3 — 2026-07-30, correction: Amendment 2's rule is withdrawn as policy

Amendment 2 registered `conservative_kelly` (f = 0.355 × Kelly of the live bank,
HB-capped) as the trial staking rule. The founder rejected it on sight, and on
re-reading the research documents the rejection is substantively correct — the rule was
mis-derived, in three specific ways:

1. **The shrink construction is not from the research.** The 0.355 is a real
   measurement (TE-0043's conservative-bound/central-edge ratio), but "Kelly × pooled
   ratio" as a *construction* appears nowhere in DR-TENNIS-STAKING-006. The matrix
   (§5.7) prescribes the opposite: a fractional rule's fraction is "derived the RCK way
   (λ from pre-registered (α,β)) rather than by folklore k". This was a folklore k.
2. **The research's registered edge-consuming forms were not used.** D7 (stake at the
   per-bet conservative quantile of p — the SPEC-034-shaped rule) and D13/RCK
   (fraction from a pre-registered drawdown tolerance) are the honest forms; D2 with an
   invented multiplier is the configuration the matrix warns against.
3. **Per-bet sizing of a same-day card violates matrix §4**: "per-bet Kelly-type rules
   silently overstake a correlated card… stake must be computed jointly or divided by a
   declared same-day cap." Day-level feasibility reservation is not the joint
   computation the research requires.

**Withdrawn as policy.** The catalogue entry and its tests remain as a measured object
(the six-month frontier numbers in TE-0046 Addendum 2 stay archived, labelled
exploratory); nothing derived from it may be served or used to size a real stake. The
trial staking clause reverts to UNSET pending a correctly derived rule.

**The replacement path, from the research's own gating logic:** the matrix froze the
edge-consuming family out while "the day-clustered edge CI currently spans zero" — the
5%-era reading TE-0044 corrected. At the founder-attested 2% the interval clears zero,
so the matrix's own operability condition for those arms is met. The candidates the
matrix registers for the founder's stated objective (maximum profit inside the horizon,
per-bet stakes varying with bank, odds and win chance, jointly sized day cards, hard
protection against ruin) are **E2 CVAR-LP-EV** (max EV subject to a day-card CVaR
budget, π_k-weighted per the verified correction — a native multi-bet formulation, not
Kelly in any form) and **D19 JOINT-HARA** (joint same-day allocation), both under the
**B5 HB-CAP** probability-one drawdown bound and the STK-HARNESS-V1 day mechanics.
Constants (the drawdown tolerance pair (α, β) and the day CVaR budget) are
founder-declared and frozen in the config commit before any replay output, per
protocol. Adoption requires the frozen head-to-head, Bonferroni-corrected at the true
trial count, and founder sign-off. Placement remains manual and human, always.

## Amendment 4 — 2026-07-30, founder directive: trial stakes follow the TE-0047 registered rule

Founder directive ("Accept proposals build it properly no shortcuts"), accepting the
DR-007 → D7 sequence. The trial's staking clause, UNSET since Amendment 3, is now:
suggested stakes follow the **TE-0047 registered D7 conservative-bound allocator** —
Kelly evaluated at the lower bound of the measured day-clustered edge interval
(Δe = 0.0249, TE-0043 provenance), divided by the day's full selected card size
(matrix §4 correlation charge), under the multi-bet B5 HB-CAP day budget at
d_max = 0.30 (founder drawdown tolerance, probability-one bound), with the £1
skip-never-round-up floor. The rule refuses by construction whenever the conservative
bound is non-positive, which is DR-003's protection carried inside the formula.

Basis, honestly stated: DR-007 discharged DR-003's spans-zero condition on the
supported-fills reading at the attested 2%; the realised-fill (after real execution)
edge remains UNMEASURED and is exactly what this trial exists to measure; superiority
over flat staking is NOT claimed and was pre-declared unlikely to be establishable
(TE-0047 registration). The adoption basis is risk-shape evidence plus founder
directive, not a proven reward ranking.

Serving: the site displays the rule's suggested stakes for the founder-entered bank,
computed by `docs/staking.js` — an exact-BigInt port held to the registered Python
rules by 300 golden vectors at exact integer-pence equality. Unchanged and still
binding: placement is manual and human ALWAYS; the recording flow refuses without a
pre-set loss budget and when the budget is exhausted; back-only, pre-off-only, one
selection per market; honest recording; directive 6. The site places nothing and
authorises nothing — the founder decides at the point of placement, every time.

## Amendment 5 — 2026-07-30, founder directive: the loss budget derives from the live bank

"It should calculate from the bank at any time not a static number I give you now and
should be entered and edited on the app." So ordered, so built:

- **The bank is the app-entered value** — editable on the board and the ledger card,
  stored server-side (`tennis.config: bank_pence`) so every device shares one bank; the
  high-water mark ratchets with it and an explicit reset re-bases it.
- **The loss budget is DERIVED, never set**: budget = d_max × current bank (d_max = 0.30,
  the TE-0047 registered cap), floored to the penny — so the recording guard and the
  staking policy agree about the worst case by construction, at every bank value, at all
  times. The static `real_loss_budget` and the `/budget` endpoint are superseded.
- **SPEC-060 spirit preserved**: settled losses decrement against the derived budget and
  wins never restore it; no code path changes the budget without a human act — editing
  the bank in the app IS the deliberate act. No bank set means recording refuses.

Unchanged: placement manual and human always; back-only, pre-off-only, one selection
per market; honest recording; directive 6. Nothing places, cancels or amends an order.
