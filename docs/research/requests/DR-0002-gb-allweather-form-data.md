# DR-0002 — Cheapest lawful GB all-weather form data with knowledge-time support (BLOCKING)

**Status:** REQUESTED (BLOCKING) — no form-data source may be onboarded, scraped, or
purchased until this research is completed with dated citations and the founder approves
the rights/budget decision. Research findings inform decisions; they never prove a gate
(Amendment A §4).

**Requested:** 2026-07-16 (founder direction, Phase-2 acceptance conditions, item 7).
**Consumer decisions blocked on this:** fundamental-model feature sourcing (SPEC-030
runner features), `docs/licensed-sources.yaml` entries, EXP-0001's feature_set scope.

## Question

What is the cheapest LAWFUL source of GB all-weather horse-racing form data (runner,
trainer, jockey, going, distance, class, ratings, declarations) that provides GENUINE
knowledge-time support — i.e. for every field it must be possible to establish what was
publishable/known at a definite time BEFORE the race (declaration times, publication
times of ratings, non-runner announcement times), not merely a retrospective results
database?

## Evaluation criteria (all must be answered per candidate)

1. **Lawfulness:** licence explicitly permits offline research + model training
   (SPEC-044 internal vocabulary); scraping-only sources are quarantined by SPEC-100
   and cannot feed anything reachable from the decision layer — a candidate whose only
   access path is scraping must be marked accordingly.
2. **Knowledge-time (SPEC-020/023):** does the source carry true publication
   timestamps, or would backfill claim false historical validity? A source without
   provable pre-race publication times fails the criterion regardless of price.
3. **Cost:** price structure, minimum commitment, historical backfill cost.
4. **Coverage:** GB all-weather tracks (Lingfield, Kempton, Wolverhampton, Southwell,
   Newcastle, Chelmsford), depth of history, declaration-stage data availability.
5. **Candidates to assess at minimum:** Racing Post / RPTV data services, Timeform
   (Betfair-owned), Total Performance Data, Weatherbys/BHA racing admin data,
   Proform, Raceform Interactive, the BHA's own racing data feeds, and any official
   PRA/racecourse data suppliers. Note which offer machine-readable feeds vs displays.

## Constraints

As DR-0001: £499 is reserved for the Live App Key; any form-data spend is new,
founder-authorised money. Dated primary-source citations required.

## Routing

Handed off to the project owner for execution via ChatGPT Deep Research
(Cost-Aware Deep Research Routing Amendment, 2026-07-16). Claude Code's large-agent
research workflow is NOT to be used for this request.

**While unresolved:** work that may CONTINUE — offline platform code, EXP-0001
drafting (feature_set stays ⟨PENDING⟩), documentation. Work that must PAUSE — any
form-data source onboarding, purchase, scraping, licensed-sources entry, or feature
ingestion for the fundamental model.

## Copy-paste prompt for ChatGPT Deep Research

```
You are researching machine-readable horse-racing form data sources for a UK-based
research project modelling GB ALL-WEATHER racing. Current-as-of date required: state
what is true as of today's date and date every claim. Jurisdiction: Great Britain
(data about GB racing; buyer is a GB entity; UK licence law applies).

PERMITTED SOURCE HIERARCHY (label every citation's tier):
1. The provider's own official product, pricing and licence/terms pages.
2. Official governing-body sources (BHA, Weatherbys) for what data exists and who
   administers it.
3. Direct provider documentation (API docs, sample feeds, data dictionaries).
4. Reputable secondary reviews by known racing-data practitioners — corroboration only.

THE QUESTION: What is the CHEAPEST LAWFUL source of GB all-weather form data
(runners, trainers, jockeys, going, distance, class, official ratings, declarations,
non-runner announcements) with GENUINE KNOWLEDGE-TIME support — meaning for each field
it must be possible to establish what was published/known at a definite time BEFORE
the race (declaration publication times, ratings publication cycle, non-runner
announcement times), not merely a retrospective results database?

CANDIDATES TO ASSESS AT MINIMUM (add others you find): Racing Post data services,
Timeform (note: Betfair/Flutter-owned — flag any licensing synergy with Betfair data),
Total Performance Data, Weatherbys / BHA racing administration data services, Proform
Racing, Raceform Interactive, At The Races / Sky Sports Racing data feeds, and any
official racecourse/PRA data suppliers.

FOR EACH CANDIDATE ANSWER:
1. LAWFULNESS: does its licence explicitly permit offline research and model
   training? Quote the operative terms. Is machine-readable access an offered
   product, or would access require scraping a display product (flag scraping-only
   candidates prominently — they are quarantined in this project and cannot feed a
   betting decision path)?
2. KNOWLEDGE-TIME: does the feed/dataset carry true publication timestamps or a
   documented publication schedule precise enough to prove pre-race knowledge (e.g.
   declarations at 48h/24h stages with timestamps, ratings published on a known
   weekly cycle)? A source that only offers post-race form summaries FAILS this
   criterion regardless of price — say so explicitly per candidate.
3. COST: pricing structure, minimum commitment, historical backfill availability and
   cost, and any per-use restrictions.
4. COVERAGE: GB all-weather tracks (Lingfield, Kempton, Wolverhampton, Southwell,
   Newcastle, Chelmsford), years of history available, declaration-stage data depth.

EXPECTED DELIVERABLES:
- A candidate comparison table (lawfulness, knowledge-time support, cost, coverage,
  machine-readable access).
- A ranked recommendation of the cheapest lawful knowledge-time-capable option, with
  the evidence chain, plus the runner-up.
- Dated citations labelled by source-hierarchy tier.
- An explicit unresolved/uncertain section (do NOT guess; missing licence text is a
  finding, not a gap to paper over).

ACCEPTANCE CRITERIA: licence conclusions quote operative text; knowledge-time claims
cite documented publication schedules or timestamp fields; scraping-only access is
flagged per candidate; prices are dated.

CONSEQUENCE IF UNRESOLVED: the fundamental model (SPEC-030) has no lawful feature
source; EXP-0001's fundamental and combined arms stay blocked (the market-only
baseline work can proceed once DR-0001 resolves).
```

