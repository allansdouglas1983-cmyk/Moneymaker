# STAGE3-0002 — Cross-market feasibility audit — VERDICT

> Numbers below are filled from `AUDIT_REPORT.json` (report digest recorded there). This
> file is the founder-facing summary; the JSON is authoritative.

## Verdict

**LIMITED_DATA_AUDIT_INCONCLUSIVE**

The June corpus contains a real but bounded and selection-biased population of
live-synchronised, two-sided identifying derivative markets (Total Games / Game Handicap).
That population is large enough to be *interesting* but two feasibility preconditions are
**unresolved in this zero-cost audit**, so the audit cannot green-light implementation:

1. **Derivative settlement semantics are UNVERIFIED (§14).** No official Betfair Exchange
   tennis rule source was read (that is external research, not authorised here), and June
   outcomes were not read to infer a rule. Every market type is `UNRESOLVED`. Per §18 this
   is an explicit hard-stop for building on these markets.
2. **Genuine independence is OBSERVABLE-ONLY / UNRESOLVED (§12).** The historical feed does
   not expose internal order origin, so non-redundancy cannot be proven from it. Derivatives
   do carry their own updates and traded volume, but that is not proof of an independent
   information dimension.

Additional scope limits that keep this short of a GO: identifying-market coverage is a
minority of the committed universe and is **strongly concentrated in the STRICT cohort**
(≈0% in `PRIMARY_ONLY_TIER`); tour attribution is partial; tournament attribution is not
available outcome-blind; and the two-sided books are frequently wide.

This matches the founder's already-accepted external-research posture
(`LIMITED_DATA_AUDIT_FIRST`) and the standing discipline that a surprisingly-usable result
is a suspected artefact until a governed, post-freeze measurement says otherwise.

## If the preconditions were resolved — the candidate cohort (§27, conditional)

Were settlement semantics verified and an independence test passed, the objectively-defined
eligible cohort implied by this audit would be: **committed MO markets in the `STRICT`
cohort whose event has a Total Games and/or Game Handicap sibling that at F0 is OPEN,
pre-match, two-sided, uncrossed, structurally parseable, carries an identifiable line, and
whose quote age is within the chosen sensitivity cutoff.** This is stated as the *shape* of
a future bounded step, not an authorisation — no implementation follows from this audit.

## What is NOT concluded

- No latent model was implemented or fitted.
- No serve probability or residual was fit.
- No ROI, P&L, CLV, EV, tip, or selection analysis occurred.
- No purchase, API call, bet, deposit, or execution occurred; £0 spend.
- F2-v1 / F3 / DP1 and all their evidence are untouched; June remains development data.

## Key figures (authoritative — `AUDIT_REPORT.json`, digest below)

- Denominator A (June singles MO universe): **2876**. Denominator B (F0-committed June
  singles MO, the cross-market sync denominator): **2518** (STRICT 1959 · PRIMARY_ONLY_TIER
  559). All 2518 matched in the corpus.
- Identifying-sibling **ceiling** (committed-MO event has a Total Games AND a Game Handicap
  sibling): **635 / 2518 ≈ 25.2%** — before any synchronization/liquidity filter.
- 210 identifying derivatives exist whose event has **no** committed MO
  (`NOT_LINKED_TO_MATCH_ODDS_EVENT`); linkage anomalies (multiple-MO / ambiguous) = **0**
  among committed MO (each committed event is unique).
- **N_PRIMARY_IDENTIFYING** (open, pre-match, two-sided, uncrossed, parseable, lined,
  observed with no later messages), by max quote age:
  15 s **150** · 30 s **211** · 60 s **294** · 120 s **382** · 300 s **494**.
  At 300 s: both markets 434 · Game-Handicap-only 35 · Total-Games-only 25.
- **Coverage at 300 s**: overall 494 / 2518 (19.6%); STRICT **494 / 1959 (25.2%)**;
  **PRIMARY_ONLY_TIER 0 / 559 (0%)**; ATP 163/479 · WTA 259/544 · TOUR_UNRESOLVED 71/1491.
- **Book width** (of the 294 usable at 60 s): min spread ≤1 tick only **5**, ≤2t 21, ≤3t
  60, ≤5t 152, ≤10t 265 — most usable books are several ticks wide.
- **Line richness** (1252 usable identifying derivatives): min 17 · median 32 · max 95 lines.
- **Redundancy (§12)**: `OBSERVABLY_NON_REDUNDANT_UPDATES` **56** · `INDEPENDENCE_UNRESOLVED`
  **1196** (no `OBSERVABLY_REDUNDANT_PATH`, no `INSUFFICIENT_UPDATES`). Only ≈4.5% show
  observably independent movement; independence is **not established** for the rest.
- Auxiliary coverage: 1957 / 2518 committed MO have ≥1 auxiliary set-structure market.
- UTC-day concentration (300 s): 29 distinct days, largest single day 65 markets.
- Tournament attribution: **NOT_AVAILABLE_OUTCOME_BLIND** (no `competition` field; joining
  tennis-data needs Winner/Loser).
- **Report digest**: `sha256:f220722588b25363fe9e764aa69077839dca6fd1cf2bfe6a0e326c6cdf014ee6`
  (byte-identical across two independent runs — §17 determinism).
