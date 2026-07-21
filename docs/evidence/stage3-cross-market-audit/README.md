# STAGE3-0002 — Cross-market latent-model feasibility audit

**Zero-cost, outcome-blind, audit-only.** This directory holds the machine-readable
report (`AUDIT_REPORT.json`), the immutable per-match records (`PER_MATCH_RECORDS.jsonl`),
and the founder-facing verdict (`VERDICT.md`) for the question: *does the June Betfair
ADVANCED corpus contain enough live-synchronised, two-sided, independent derivative markets
(Total Games / Game Handicap) to make a two-parameter point→game→set→match latent model
**testable**?*

It answers **feasibility only**. No latent model is implemented or fitted; no serve
probability, residual, ROI, P&L, CLV, or EV is computed; no purchase, API call, bet,
account action, or spend occurs. The raw corpus is read-only.

## What is read (and what is never read)

Permitted (registration `specs/programme/cross-market-audit-v1.yaml`): market **definition**
identity (marketType, eventId, marketTime, runner id/name/hc), pre-off **book** state
(best back/lay, sizes, ladder depth, traded volume, publish times), and the frozen F0
decision timestamps. **Never read:** winners, sporting outcomes, settlement, BSP, ROI,
P&L, CLV, EV, tips, or any result-derived field. Betfair commits F0 pre-off, so every
reconstructed book is pre-settlement — there is no outcome in scope to leak.

## Method (mirrors the directive §3–§16)

1. **Inventory (§3)** — every Betfair tennis marketType, classified to an audit role from
   the corpus itself, not the research report. The two identifying types are
   `COMBINED_TOTAL` (Total Games) and `HANDICAP` (game handicap); both are
   `ASIAN_HANDICAP_DOUBLE_LINE`, singles, June-only.
2. **Parsers (§4)** — deterministic, versioned (`xmarket-parsers-v1`) selection parsers
   that refuse malformed/ambiguous structure. The HANDICAP parser handles the double-line
   packing (each magnitude packs two priceable lines) and refuses a set handicap
   (max |line| ≤ 3.0) as a game handicap — grounded in the observed data (real game
   handicaps only ever reach 11.5/15.5; no set-sized HANDICAP market exists).
3. **Linkage (§5)** — derivatives link to their Match-Odds sibling by **eventId only**,
   never by display name; multiple-MO-per-event, ambiguous same-role duplicates, unlinked
   events, and marketTime mismatches are all made visible, never silently resolved.
4. **As-of-F0 reconstruction (§6/§7)** — a derivative's book is rebuilt only from stream
   messages with `publish_time ≤ commit_pt_ms`; no later state; a later message can never
   backfill an earlier missing side. Quote age = anchor − latest pre-cutoff update, scored
   against 15/30/60/120/300 s cutoffs.
5. **Book quality + validity (§8)** — in-play / suspended / one-sided / crossed / empty
   books each refuse with their reason; two-sided line count, min spread (canonical-ladder
   ticks and bps), best sizes, depth, and traded volume are reported.
6. **Redundancy (§12)** — MO-vs-derivative book-change co-timing yields the four founder
   statuses (`OBSERVABLY_NON_REDUNDANT_UPDATES` / `OBSERVABLY_REDUNDANT_PATH` /
   `INDEPENDENCE_UNRESOLVED` / `INSUFFICIENT_UPDATES`). A timestamp difference alone never
   yields "non-redundant"; the feed cannot prove cross-matching, so ambiguity stays
   unresolved.
7. **Aggregation (§9–§15)** — `N_PRIMARY_IDENTIFYING` per cutoff × cohort × tour; line
   richness; auxiliary coverage; one-tick spread-sensitivity packet; UTC-day concentration;
   and a selection-bias coverage comparison on outcome-blind cohort/tour fields.
8. **Settlement semantics (§14)** — `specs/evidence/tennis-derivative-settlement-semantics-v1.yaml`,
   every type `UNRESOLVED` (no official rule source read, no June outcome read to infer a
   rule; §18 hard-stop honoured).

## Known limitations (surfaced, not hidden)

- **Tournament attribution is not available outcome-blind** in-repo: tennis marketDefinition
  carries no `competition` field, and joining tennis-data requires reading Winner/Loser.
  The report records `tournament_attribution: NOT_AVAILABLE_OUTCOME_BLIND`; only cohort,
  tour (ATP/WTA/`TOUR_UNRESOLVED`), and UTC day are broken out.
- **Tour resolves for only part of the universe** (the governed identity bridge leaves the
  rest `TOUR_UNRESOLVED`); those markets stay in the denominator, visibly.
- The quote-age staleness cutoff is a **reported sensitivity**, not a frozen policy.

## Reproducibility

`python -m research.xmarket.run_audit --corpus <ADVANCED_root> --out AUDIT_REPORT.json
--records-out PER_MATCH_RECORDS.jsonl`. The report carries a `report_digest`; two runs over
the same inputs produce the same digest (no wall-clock is embedded). Code:
`research/xmarket/`; tests: `tests/unit/xmarket/`.
