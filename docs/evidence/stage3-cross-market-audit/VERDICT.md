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

## Key figures

_(filled from AUDIT_REPORT.json)_

- Denominator B (committed June singles MO): __B__
- Identifying-sibling ceiling (event has TG and GH): __CEIL__ / __B__
- N_PRIMARY_IDENTIFYING: 15 s __/__ · 30 s __/__ · 60 s __/__ · 120 s __/__ · 300 s __/__
- Coverage at 300 s: STRICT __ / 1959 · PRIMARY_ONLY_TIER __ / 559
- Redundancy status distribution (§12): __
- Report digest: __
