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

**Two documented candidates now stand** (updated 2026-07-17): this spec's original
recommendation of **April 2026** (full clay swing, no Slam transition, maximum
"steady-state" representativeness) and the founder's ChatGPT report's recommendation
of **June 2026** (most recent complete month past the 5-day availability lag;
credible ATP/WTA sample across Stuttgart, 's-Hertogenbosch, Halle, Queen's, Mallorca,
Eastbourne, Berlin, Bad Homburg, with Wimbledon starting 29 June — grass-swing +
Slam-transition composition). Neither selection inspected model performance. **The
founder decides between them at purchase time**; both rationales are preserved here.

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

**Established by the founder's ChatGPT Deep Research (2026-07-17, source claims
pending portal confirmation at checkout):** Tennis is its own package — **ADVANCED
£49.00/month** (£499/year bulk), PRO £150/month (£1,499/year). Also established:
tennis "Game betting" markets are NOT included in historical data (Match Odds is);
M-files are the correct file type; the retention/reuse licence wording is not
publicly exposed and MUST be read on the portal acceptance text immediately before
purchase. Candidate purchase: **Tennis ADVANCED, one month, £49.00.**

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

---

## Founder confirmation (2026-07-17, F-13 acceptance message)

The next programme step is empirical data acquisition, still governed by ADR 0015 and
explicit human approval. Parameters CONFIRMED as the standing proposal:

- **one month only** — no bulk package, no multi-month assumption;
- **proposed month: June 2026** (the earlier April-vs-June candidacy is resolved:
  June 2026 is the proposed first pilot month);
- **package: Tennis ADVANCED**;
- **local immutable storage and checksums** (l0 append-only + SHA-256 per the
  ingestion runbook; processed locally only, no third-party CI/cloud upload);
- **additional months considered solely after the pilot identifies a specific,
  measured evidence gap** — never speculatively.

No live key, real order, or real-money activity is authorised by that acceptance.
Purchase execution still requires: ADR 0015 resolution (lawful account access
confirmed) + the founder's explicit final go.

---

## Founder amendment (2026-07-18): storage rule updated for the founder's actual workflow

SUPERSEDES the "processed locally only / no cloud upload" precaution above, by explicit
founder decision (in-session, 2026-07-18). The founder operates entirely through the
remote workspace and runs nothing locally; a local-only rule is unworkable in fact.

**Amended rule:** the purchased raw data is stored in PRIVATE, access-controlled
storage under the founder's own control (e.g. a private Google Drive/Dropbox folder),
and pulled into the project workspace only while running analysis, for the founder's
own research exclusively. It is never made public, never shared, never published,
never committed to GitHub, and never redistributed in raw form. Betfair's portal
re-download of purchased months serves as the ultimate source of record.

**Unchanged:** checksum discipline (the first workspace pull computes and pins the
SHA-256 manifest in the repo; every later pull must match it); derived outputs and
manifests in the repo, raw data never; the rights questions to Betfair remain open and
any written answer from Betfair that contradicts this posture reopens the decision.
