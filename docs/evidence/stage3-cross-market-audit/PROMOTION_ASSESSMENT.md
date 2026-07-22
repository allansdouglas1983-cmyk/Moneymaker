# STAGE3-0004 §10 — audit-code promotion assessment

`research/xmarket/` remains **research-only**. This assessment classifies which components
may later need production promotion for `CROSS_MARKET_COHERENCE_V1`. Promotion means
**re-homing** the logic into a governed production package (`xmarket_contracts/`) behind
neutral contracts with the **advice-critical** test bar — it does **not** import
`research.xmarket` into production, and it does **not** expose anything to pricing or tipping
modules. The 56.3% advisory mutation score for the research audit modules does **not**
transfer; every promoted behavioural mutant must be killed or founder-approved equivalent.

| # | Component (research/xmarket) | Classification | Notes |
|---|---|---|---|
| 1 | raw market-type parser (`market_role`) | **PROMOTE_AFTER_HARDENING** | preserve raw marketType; fail-closed on unknown |
| 2 | Total Games parser (`parse_total_games`) | **PROMOTE_AFTER_HARDENING** | Over/Under + exact line; refuse malformed |
| 3 | Game Handicap parser (`parse_game_handicap`) | **PROMOTE_AFTER_HARDENING** | double-line; Set-vs-Game boundary must hold |
| 4 | event linkage (`linkage`) | **PROMOTE_AFTER_HARDENING** | by eventId; cancelled/relisted separate |
| 5 | as-of-F0 synchronizer (`reconstruct_as_of`) | **PROMOTE_AFTER_HARDENING** | no post-F0 message; no backfill |
| 6 | two-sided-book validator (`book_exclusion_reason`) | **PROMOTE_AFTER_HARDENING** | one-sided/crossed/suspended/in-play refuse |
| 7 | quote-age calculation (`quote_age_seconds`) | **PROMOTE_AFTER_HARDENING** | age at F0; sensitivities only |
| 8 | immutable provenance / observation record | **PROMOTE_AFTER_HARDENING** | neutral contract; no outcome/prob/tip field |
| 9 | market-quality arithmetic (`book_quality`: spread bps, ladder-tick, sizes) | **KEEP_RESEARCH_ONLY** | diagnostic-only; the survivor-heavy arithmetic; the coherence layer will re-derive book-quality features under EXT-XMARKET-003 |
| 10 | redundancy co-timing (`redundancy.classify`) | **KEEP_RESEARCH_ONLY** | superseded by the governed cross-matching evidence policy; origin-unresolved by design |
| 11 | audit orchestrator / run_audit / aggregations | **DELETE_AFTER_EVIDENCE_FREEZE** | one-shot audit driver; its output artifact is frozen and preserved, the driver is not production |
| 12 | coherence numerical layer (projection / expected-total-games / handicap distributions / objective) | **BLOCKED_BY_MATH_SPEC** | not implemented; EXT-XMARKET-003 must resolve first |

## What is promoted in THIS slice (STAGE3-0004)

Components 1–8 are promoted into `xmarket_contracts/` behind neutral contracts, with red +
property + mutation tests proving:

- exact raw `marketType` preservation (never renamed);
- deterministic, type-specific selection parsing;
- Set Handicap cannot become Game Handicap;
- Total Games line extraction;
- event linkage by governed identifiers; cancelled/relisted remain separate;
- no post-F0 message can enter; a derivative later than the cutoff refuses;
- one-sided / crossed / suspended / in-play refuses;
- unknown semantics / unsupported cohort refuses;
- immutable observation record; no outcome / probability-adjustment / tip field;
- deterministic serialization; no import path to execution.

Components 9–12 are **not** promoted now (diagnostic-only, superseded, one-shot, or
math-blocked). They remain research-only or are retired after the evidence freeze; none is
exposed to pricing or tipping.
