# DR-TENNIS-MARKET-002B — Betfair Tennis ADVANCED pilot: purchase specification

**Status:** SPECIFICATION ONLY. **No purchase authorised or executed.** This is the
required pre-purchase deliverable (founder directive, 2026-07-16). Blocked on: (a)
ADR 0015 — founder's Betfair account exclusion/GAMSTOP restoration must resolve
first (the tennis pilot needs the same customer account as the paused racing pilot);
(b) ADR 0016 — the tennis pivot proposal itself is still PROPOSED, not approved; (c)
the founder's final confirmation of the selected month, per this document.

## 1. Exact package and filters

| Field | Value |
|---|---|
| Plan | **ADVANCED** (per Betfair's tier structure — same product line as DR-0001 established for horse racing: BASIC/ADVANCED/PRO, differing by update frequency and depth) |
| Sport | **Tennis** |
| Data month | See §2 below — recommendation pending founder confirmation |
| Download filter (post-purchase) | Market type = **MATCH_ODDS**; further filter to ATP/WTA main-tour singles by tournament/competition name post-download (Betfair's historical-data portal filters by Sport/Country/EventId/EventName/MarketType, not by "tour level" — ATP vs WTA vs Challenger is not a first-class portal filter, so the download is Tennis+MATCH_ODDS and tour-level classification happens in the pilot's own ingestion/analysis step against the known tournament calendar) |

## 2. Selected month and representativeness rationale

**No model performance or betting outcome was inspected in this selection** — the
choice rests entirely on tournament calendar composition (tour levels, surfaces,
event count), verified against official ATP/WTA sources.

Most recent complete calendar month as of 2026-07-16 is **June 2026**. Checking it
for anomaly (the same discipline applied to the racing pilot's month selection)
finds a genuine one: June 2026 straddles TWO different competitive contexts —
the final week of the **French Open** (clay, Slam, 24 May–7 June) and the start of
the **grass-court swing** (Queen's Club 15–21 June, Halle, Eastbourne, with
**Wimbledon starting 29 June** — almost entirely outside June). The ATP's own grass
season is short: only seven tour-level events across the whole June–July grass
swing. A June pilot would therefore measure a mixed, transitional, low-event-count
month — not representative of "steady state" tour liquidity.

**Recommended alternative: April 2026.** Verified from ATP/WTA official sources: a
full clay-swing month with no Grand Slam overlap and multiple concurrent tour
levels — ATP Masters 1000 (Monte-Carlo, 5–12 Apr), ATP 500s (Barcelona and Munich,
both 13–19 Apr), WTA 500 (Stuttgart, 13–19 Apr), plus Madrid (WTA 1000 / ATP
Masters 1000) starting 20–22 April and running into May. This is the most recent
month that is NOT dominated by a Slam or a short/transitional swing — a genuinely
"regular" cross-section of ATP+WTA main-tour Match Odds markets.

May 2026 was also checked and rejected as a default: Madrid continues, Rome
(ATP/WTA 1000) runs mid-May, but the back half of the month is dominated by French
Open qualifying (from 18 May) and the main draw (24 May onward) — a Slam-heavy
month, same concern as June.

**Recommendation to the founder: April 2026**, with June 2026 available as the
"most recent complete" alternative if recency is prioritised over representativeness
— flagged here as the founder's call, not assumed. **Final month selection requires
founder confirmation before any purchase**, per directive.

## 3. Event/tour/surface composition (April 2026 candidate)

| Tournament | Tour | Level | Surface | Dates |
|---|---|---|---|---|
| Houston (US Men's Clay Court Champs) | ATP | 250 | Clay | 30 Mar–5 Apr (tail into Apr) |
| Charleston | WTA | 500 | Clay | 30 Mar–5 Apr (tail into Apr) |
| Monte-Carlo Masters | ATP | Masters 1000 | Clay | 5–12 Apr |
| Barcelona Open | ATP | 500 | Clay | 13–19 Apr |
| Munich (BMW Open) | ATP | 500 | Clay | 13–19 Apr |
| Stuttgart | WTA | 500 | Clay (indoor) | 13–19 Apr |
| Madrid Open | ATP + WTA | Masters 1000 / WTA 1000 | Clay | 20/22 Apr–3 May (spans into May) |

All-clay month; no Challenger/qualifying counts established yet (Challenger
calendar wasn't part of this desk check — the pilot's own portal download and
downstream classification will establish actual Challenger/qualifying coverage,
per DR-TENNIS-MARKET-002B's own measurement scope).

## 4. Current portal price

**Not yet established.** Betfair's historical-data pricing page is JS-rendered and
did not surface tennis-specific pricing via search (the same limitation DR-0001 hit
for racing, resolved there only by ChatGPT Deep Research's page access). Also
unresolved: whether Tennis is priced as its own per-sport package (like Horse
Racing: Basic free/Advanced £69/Pro £230) or bundled into Betfair's "Other Sports"
package at a different price point — a genuine open question found during this
prep, folded into DR-TENNIS-MARKET-002A's desk research scope (in progress). **The
exact price must be confirmed on the portal (or from 002A's findings) before
purchase** — no purchase proceeds on an assumed price.

## 5. Known limitations (declared in advance, per the founder's methodology)

- **Challenger/qualifying/doubles coverage is unknown until measured** — this
  pilot's explicit job (per DR-TENNIS-MARKET-002B's measurement scope) is to
  establish it, not assume it.
- **BSP may not exist or may be unreliable for tennis** (flagged separately in
  DR-TENNIS-BENCHMARK-001 — closing-benchmark definition is NOT reused from
  racing and is pending that research thread).
- **One month cannot establish liquidity across surfaces** — April 2026 is
  entirely clay; a full-year or multi-surface assessment would need additional
  months, a decision deferred until this pilot's results are in.
- **Desk-research (002A) liquidity numbers are SECONDARY and inadmissible** as a
  substitute for this measurement, per the founder's explicit labelling
  requirement — this pilot is the sole primary evidence source for market counts,
  spreads, depth, and volume.
- **Retirement/walkover frequency this pilot measures is DESCRIPTIVE for one
  month/surface** — not a general-purpose base rate; DR-TENNIS-SETTLEMENT-001
  covers the deterministic settlement-treatment matrix separately.

## What this document does NOT authorise

No purchase, no download, no account action of any kind. Purchase proceeds only
after: ADR 0015 resolves, ADR 0016 is approved, the price is confirmed, and the
founder gives final month confirmation (this document's recommendation is a
proposal, not a decision).
