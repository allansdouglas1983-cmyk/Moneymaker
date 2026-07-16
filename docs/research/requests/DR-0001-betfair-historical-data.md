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

## Routing

Handed off to the project owner for execution via ChatGPT Deep Research
(Cost-Aware Deep Research Routing Amendment, 2026-07-16). Claude Code's large-agent
research workflow is NOT to be used for this request.

**While unresolved:** work that may CONTINUE — all offline platform code, EXP-0001
drafting, DR-0002 preparation, documentation, verifier passes. Work that must PAUSE —
any data purchase, licence acceptance, `docs/licensed-sources.yaml` entry for Betfair
Historical Data, Gate −1 evaluation of that source, data ingestion, lockbox definition,
EXP-0001 registration.

## Copy-paste prompt for ChatGPT Deep Research

```
You are researching Betfair Historical Data packages for a UK-based horse-racing
research project. Current-as-of date required: state explicitly what is true as of
today's date, and date every claim. Jurisdiction: Great Britain (data covers GB and
IRE horse racing; the buyer is a GB consumer of Betfair's historical data service).

PERMITTED SOURCE HIERARCHY (strongest first — prefer higher tiers, label the tier of
every citation):
1. Official Betfair pages: historicdata.betfair.com (including its FAQ, sample files,
   API docs and terms), developer.betfair.com, Betfair legal/licence pages.
2. Official Betfair developer forum answers from Betfair staff accounts.
3. Sample data files or schema documentation downloadable from the official site.
4. Reputable secondary sources (published books/blogs by known Betfair API developers)
   — ONLY for corroboration, never as the sole basis of a claim.
Marketing copy is not evidence of message granularity; schema/sample files are.

QUESTIONS (answer every one, separately, with citations):
1. For the BASIC, ADVANCED and PRO historical-data tiers, what exactly does each
   contain for GB/IRE horse-racing WIN markets: message types, ladder/price depth
   (full depth? best 3? traded only?), traded-volume updates, market-definition
   changes (non-runners, suspensions), BSP fields, timestamp fields and resolution,
   and any conflation/throttling applied to the recorded stream?
2. Current prices per tier (per month of data, per sport, currency), how purchases
   are billed, and any bulk/backfill pricing. Estimate total cost for 12, 24 and 36
   months of GB+IRE horse-racing data at each tier.
3. What purchase filtering exists (by country, sport, market type, month)? Can a
   buyer purchase only GB+IRE WIN horse-racing markets?
4. The licence terms attached to purchased historical data, mapped to these specific
   uses: offline research; model training; retention of the raw data; retention of
   models derived from it; processing on cloud/third-party CI infrastructure;
   publication or redistribution of derived probabilities/odds; commercial use of
   derived outputs. Quote the operative licence language.
5. Which is the CHEAPEST tier that genuinely supports each of these two needs, and
   what does each tier provably lack:
   (a) GATE 1 need: pre-off market prices sufficient to compute a defined
       market-information probability at fixed decision horizons (e.g. T-10m, T-2m)
       plus reconciled BSP for post-race grading;
   (b) GATE 2 need: latency-adjusted, size-aware executable-price scenario analysis —
       requires order-book depth and traded-volume evolution over time, not just
       last-traded prices.

EXPECTED DELIVERABLES:
- A tier-by-tier factual table (contents, price, filtering, licence highlights).
- A direct recommendation of minimum tier for Gate 1 and for Gate 2, each with the
  evidence that the tier suffices, and an explicit list of what it lacks.
- A dated citation list, each entry labelled with its source-hierarchy tier.
- An explicit "unresolved/uncertain" section for anything that could not be
  established from permitted sources (do NOT guess).

ACCEPTANCE CRITERIA: every numeric claim (price, depth levels, timestamp resolution)
carries a dated citation; licence conclusions quote operative text; the Gate-2
depth question is answered from schema/sample evidence, not marketing; uncertainty
is declared, never smoothed over.

CONSEQUENCE IF UNRESOLVED: the project cannot lawfully or economically select a
historical-data purchase; Gates 1-2 experimentation stays blocked.
```

