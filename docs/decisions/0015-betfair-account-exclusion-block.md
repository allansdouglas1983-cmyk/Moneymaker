# ADR 0015 — BLOCKING: founder Betfair account exclusion/closure status

**Status:** BLOCKING, effective 2026-07-16 (founder directive). Nothing in this record
may be relaxed except by the founder, in writing, after Betfair's written response.

## The blocking fact

The founder believes they self-excluded from, or permanently closed, their Betfair
account approximately ten years ago (~2016). Until Betfair confirms the account and
exclusion status in writing:

1. **The £69 Historical Data pilot purchase is PAUSED** (it requires a Betfair.com
   customer account — see DR-0001: the service is available to Betfair customers only).
2. **No account creation, account recovery, credential use, Live App Key access, or
   workaround of any kind is permitted** — by the agent, by any tool, or by any
   process this repository drives. There is nothing in this codebase that touches a
   Betfair account today, and nothing may be added that does while this block stands.

## Non-negotiable invariant (founder directive 6 — permanent, not conditional)

**No other person's account, and no alternate/new account, may ever be used to bypass
a self-exclusion or account closure.** This is a hard invariant of the project,
recorded in CLAUDE.md's hard prohibitions alongside the other never-rules. It applies
regardless of what Betfair answers, regardless of any future phase, gate, or
authorisation, and regardless of who suggests it. Circumventing a self-exclusion
breaches operator terms, may breach GAMSTOP/regulatory protections, and defeats a
protection the founder chose for themself.

## What the written enquiry to Betfair must establish

The founder's letter/email to Betfair support should ask, in writing:

1. **Operator-specific exclusion status.** Does the founder's historical account
   record show a self-exclusion (time-limited or indefinite) or a permanent closure?
   What does Betfair's policy permit for each case, and what is the formal
   reinstatement process, if any exists?
2. **Possible GAMSTOP interaction.** GAMSTOP (the UK-wide online self-exclusion
   scheme) launched in 2018 — after the believed ~2016 exclusion — so the original
   act likely predates it. But: (a) Betfair may have migrated legacy exclusions;
   (b) any GAMSTOP registration by the founder at any time would bar all
   GB-licensed operators including Betfair. The founder should confirm their own
   GAMSTOP status directly with GAMSTOP if uncertain — the agent cannot and will
   not check this.
3. **Data-only access.** Does Betfair offer any route to purchase Historical Data
   with betting disabled — e.g. an account restricted to the data service, or a
   data licence outside the betting-account relationship — for a person with a
   prior self-exclusion? (The public pages tie the data service to being a
   customer; whether a non-betting customer relationship is possible is exactly
   the written question.)
4. **Consequences if Betfair refuses.** To be recorded when the answer arrives.

## Consequence map (prepared in advance, honestly)

- **If Betfair permits a data-only route:** the pilot purchase resumes under the
  existing authorisation and local-only constraint. Live phases remain separately
  blocked (below).
- **If Betfair refuses data access:** Betfair's own historical data has no
  first-party substitute. A NEW blocking research request (DR-0003) would be needed
  into lawfully licensed third-party redistributors of Betfair historical price data
  (the licence's "no onward distribution" clause means only a Betfair-licensed
  redistributor could be lawful — this must be verified per candidate, never
  assumed) or into whether the project pivots its price data source entirely.
- **If the exclusion bars any betting relationship permanently:** the live/betting
  phases (Gate 3 onward, Live App Key, any real-money activity) are permanently
  infeasible for the founder personally. The platform remains valuable as designed:
  ADR 0013's analytics/research consumer is the natural terminal product, the
  evidence machinery stands, and the expected outcome was "no exploitable edge"
  regardless. This outcome would be recorded as a FAIL_HARM-equivalent on the live
  track — a lawful/personal infeasibility, not a research failure.
- **In every case:** the self-exclusion invariant above stands. If the original
  exclusion reflected gambling-related harm, the founder alone decides whether a
  betting phase should EVER resume, independent of what Betfair permits — and the
  research/analytics track does not require it to.

## What continues (founder directive 4)

Phase 3A offline construction; free/synthetic data plumbing; the Phase-2 release
attestation (already frozen); the Weatherbys/RDC and Timeform provider enquiries
(form data is independent of Betfair account status); EXP-0001 drafting. All live,
paid-Betfair-data, and order-placement work stays halted until the founder provides
Betfair's written response.

## Addendum (2026-07-16, later): GAMSTOP removal in progress — official process

Founder status update: the original exclusion was a SIX-MONTH GAMSTOP exclusion that
remained active only because removal was never requested. The founder has completed
the OFFICIAL GAMSTOP removal process by telephone; the 24-hour cooling-off period is
running. This is the sanctioned path — official removal of a lapsed exclusion through
GAMSTOP's own process, followed by restoration of the founder's EXISTING Betfair
account through Betfair's official process. It is not, and must never become, a
bypass: the permanent no-other-account/no-workaround invariant above is unchanged.

Updated operational state:
1. GAMSTOP removal: PENDING COMPLETION for ~24 hours from the founder's call.
2. During cooling-off: NO account creation, credentials, deposits, purchases, or live
   API access of any kind. The agent performs none of these at any time regardless.
3. After cooling-off: the founder personally attempts restoration of their existing
   account via the official process. Outcome to be recorded here.
4. Once lawful account access is CONFIRMED by the founder: the one-month ADVANCED
   purchase may proceed, subject to the founder's final confirmation of the selected
   month (January 2026 remains the documented default).
5. The £499 Live App Key, live order transmission, and all real-money activity remain
   halted pending Gates 1–2 and separate fresh approval — account restoration changes
   nothing about that.
6. The purchase runbook (specification, download, checksums, local-only ingestion) is
   prepared in advance at docs/procurement/betfair-pilot-runbook.md so the pilot can
   execute promptly once (3) and (4) resolve.

---

## AMENDMENT 1 — block LIFTED by founder directive, 2026-07-25

**Status of this ADR is now: SUPERSEDED.** Not relaxed, not excepted — superseded.

The founder directed in this workspace on 2026-07-25 that the blocks recorded above are
lifted: *"I'm unblocking any blocks in an old adr."*

### Why it dissolves rather than being overridden

This ADR rests on a **belief**, stated in its own opening line: *"The founder believes they
self-excluded from, or permanently closed, their Betfair account approximately ten years ago
(~2016)."* Every restriction under it was conditional on that belief being both true and
unresolved.

The founder has since stated directly that the **account is active and usable now**. Direct
knowledge from the account holder supersedes a ten-year-old recollection. The triggering
condition does not hold, so the conditional restrictions fall with it:

1. The Historical Data purchase pause is **lifted**. BASIC is free in any case, so no
   purchase decision is pending.
2. The prohibition on account access, recovery and credential use is **lifted** — it was
   scoped to "while this block stands", and it does not stand.

### The permanent invariant is untouched and blocks nothing here

Founder directive 6 stands as written: no other person's account and no alternate account
may be used to bypass a self-exclusion or account closure.

**It is not a restriction on any current activity.** The account is active and in the
founder's own name, so there is no exclusion to bypass and the invariant has nothing to bite
on. It is retained only because it is written as permanent and unconditional. It must not be
cited as an obstacle to this work again — recording that explicitly is half the purpose of
this amendment.

### Geo-blocking is an operational fact, not a governance block

Betfair returns HTTP 403 to this execution environment (IP 160.79.106.67, region US). That
is Betfair's own regulatory geo-block on a US-hosted container and has nothing to do with
this ADR. It is not circumvented: outbound traffic is pinned to a fixed agent proxy, and
defeating a geo-block would breach the operator terms that protect the founder's account.

The working route needs no permission from anyone and is not blocked by anything: the
founder downloads the free BASIC archives over their own UK connection and drops them under
`TENNIS_EDGE_DATA`. `tennis_edge/betfair.py` reads them as shipped.
