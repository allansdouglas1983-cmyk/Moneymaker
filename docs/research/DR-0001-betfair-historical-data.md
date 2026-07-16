# DR-0001 — Betfair Historical Data packages (BLOCKING)

**Status:** REQUESTED (BLOCKING) — no data purchase, licence acceptance, or Gate −1
evaluation for a Betfair historical source may proceed until this research is completed,
its findings dated and filed here with citations, and the founder approves the resulting
budget/rights decision. Research findings inform decisions; they never prove a gate
(Amendment A §4).

**Requested:** 2026-07-16 (founder direction, Phase-2 acceptance conditions, item 7).
**Consumer decisions blocked on this:** historical data purchase for Gates 1–2;
`docs/licensed-sources.yaml` entry for Betfair Historical Data; EXP-0001 execution.

## Questions

1. **Package contents.** What exactly do the current Betfair Historical Data
   BASIC, ADVANCED and PRO tiers contain for GB/IRE horse racing WIN markets —
   message granularity (market definition changes, ladder depth levels, traded volume
   deltas, conflation), timestamps and their resolution, BSP fields, and whether
   pre-off order-book depth (not just last-traded price) is present per tier?
2. **Prices.** Current per-month/per-sport pricing for each tier, currency, and any
   bulk/backfill discounts. Total cost estimates for 12/24/36 months of GB/IRE WIN
   horse-racing data per tier.
3. **Filtering.** Can purchases be filtered (country, sport, market type) so only the
   needed markets are bought? At what granularity?
4. **Rights.** The licence terms attached to purchased historical data: internal
   research/model training permission, retention, derived-model retention, cloud/CI
   processing, and any publication/redistribution restrictions — mapped onto the
   SPEC-044 permitted-uses vocabulary.
5. **Minimum tier for Gates 1 and 2.** Gate 1 needs pre-off prices adequate for
   p_market_info at defined decision horizons plus BSP for grading. Gate 2 needs
   latency-adjusted, size-aware executable-price scenarios — i.e. ladder depth and
   traded-volume evolution, not just last-traded. Which is the CHEAPEST tier that
   genuinely supports each gate, and what does the data provably lack at each tier
   (so the gap is declared rather than discovered)?

## Constraints

- Total external budget remains £499, reserved for the Live App Key — any historical
  data cost is NEW spend requiring explicit founder authorisation (SPEC-103 budget
  separation; Gate −1B payback arithmetic).
- Every claim in the findings must carry a dated citation to a primary source
  (betfair developer/historicdata pages, official pricing pages, licence text).
  Marketing claims are not evidence of message granularity — sample-file schemas are.

## Findings

*(empty — to be completed by the deep-research execution and dated on filing)*
