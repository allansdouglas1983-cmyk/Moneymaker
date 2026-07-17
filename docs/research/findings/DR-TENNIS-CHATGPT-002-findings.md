# DR-TENNIS ChatGPT findings — provider contracts, Betfair tennis desk facts, pilot month

**Returned:** 2026-07-17, via founder's ChatGPT Deep Research (uploaded file).
**Assessed:** 2026-07-17 (assessment follows the verbatim report). `citeturn` markers
resolve only in the founder's ChatGPT session; load-bearing claims are SOURCE CLAIMS
pending founder spot-check, though several are portal-verifiable at purchase time.

---

## Verbatim report

# Tennis Pivot Research Update

## Bottom line

The research now points to a clearer structure for a tennis pivot. For **provider-side tennis data**, the strongest public evidence is mostly **negative or conditional**: Tennis Data Innovations’ public ATP results terms expressly forbid using its website data for betting settlement, odds feeds, statistical models, or AI training without a licence; Stats Perform’s public WTA terms and master licence language make use highly dependent on the signed work order and, in public form, prohibit machine-learning training, archival building, and betting-related use unless expressly authorized; and Sportradar’s public ATP addendum shows that official ATP data **can** be licensed for live odds and trading, but only inside a formal authorized-license framework with integrity conditions. That means the alleged blanket claim that “Sportradar forbids prediction/trading use” is **not** supported by the public ATP addendum; what the public documents do show is that unauthorized or unofficial trading use is restricted, while authorized official odds/trading use exists. citeturn15search3turn14search1turn48view0turn48view1turn47view0turn19search0

By contrast, **Betfair Historical Data** is already a clearly documented path for modeling and backtesting: official pricing is published, the ADVANCED package fields are published, filtering and download mechanics are published, excluded tennis markets are published, and the timestamp / market-state semantics are published. So the best evidential way to test a tennis pivot is still the route you specified: use **Betfair as the primary pilot evidence**, then treat third-party tennis feeds as a separate licensing track that still needs written contractual answers before any purchase decision. citeturn51search0turn43view0turn10search8turn10search9turn10search6turn41view0turn39search0

## Provider contract evidence

For **Tennis Data Innovations / official ATP data**, the public evidence is restrictive at the website level. TDI says it commercializes ATP Tour and ATP Challenger Tour data and manages betting live streaming from more than 14,500 matches each season, so it is plainly the official ATP-side commercial gatekeeper. But its public results-site terms say the content is for personal, domestic use only unless licensed, prohibit commercial products such as data feeds or live odds feeds, and expressly ban text/data mining or scraping for betting use, odds feeds, statistical models, and AI systems. Publicly, that means private model training for betting is **not expressly permitted** from the website terms; it would require a separate written licence. The public contact route is `contact@tennisdata.com`, plus the Wimbledon office address. No public page I found states pilot pricing, minimum term, historical backfill years, raw-retention rights, or whether derived models survive after termination. citeturn14search0turn15search3turn14search1turn15search0turn15search2

For **Stats Perform / official WTA data**, the public evidence is also conditional rather than permissive. Stats Perform publicly markets itself as the exclusive official WTA data and streaming partner, with official umpire-chair data, parallel low-latency shot-by-shot statistics, 50+ tournaments per year, and 5,500+ live video matches for licensed sportsbooks. But the public WTA terms say a licensee may not sublicense the data, may not mix WTA data with unofficial data, and may have use suspended around integrity concerns. More importantly, the public Master License Agreement says licensees may not use licensed materials to create, test, train, or support machine-learning or AI models, may not bulk-download or build archival files, and may not use the materials for betting activities or provide odds, models, or probabilities to third parties except where expressly allowed by the relevant work order. That does **not** tell us private model training is lawful for your use case; it tells us the answer has to come from explicit contract language, not implication. Stats Perform’s public contact route is its sales/contact form and London headquarters page. citeturn16search1turn16search4turn16search8turn48view0turn48view1turn49view0

For **Sportradar**, the public evidence is more nuanced and directly addresses the earlier allegation. Sportradar’s official ATP addendum says TDI official ATP data includes umpire-collected match data such as players, start and finish time, sets, games, breaks, points, tiebreaks, and right of service/ball changes, and it explicitly defines both “Live Data – ATP” and “Live Odds – ATP.” The same addendum then restricts licensees from using unofficial feeds, collating data from TV/internet/attendance, or creating markets from unauthorized third-party data. That public wording **refutes** a blanket “no prediction/trading use” claim; the public contract instead shows that **authorized** ATP live odds / trading use exists, while **unofficial** or unauthorized collection and trading routes are barred. Separately, Sportradar’s general terms say customers may not use Sportradar’s AI models or outputs to develop or train AI or competing services. Public contact routes include `info@sportradar.com` and developer/support channels. citeturn47view0turn19search1turn19search0turn20search7

For **Tennis-Data.co.uk**, the public language is the most permissive-looking of the non-official sources, but also the least formal. Its homepage says all data is free to use and accessible; its data pages describe computer-ready results and betting-odds data for spreadsheet use; and one public snippet explicitly invites questions about how the data can be used for “your own betting system.” At the same time, the site also disclaims correctness and is clearly an unofficial portal rather than an official rights-holder feed. So Tennis-Data is the strongest public signal for a low-cost unofficial data route, but its public materials still do **not** answer the legal questions that matter most here: raw retention, derived-model retention after subscription, local/private-cloud permission, or knowledge-time reconstruction of rankings. A public contact page exists, but the crawled evidence did not expose a complete contract answering those questions. citeturn33search0turn32search2turn28search6turn27search1turn32search7

For **API-Tennis**, the public package is commercially straightforward but legally lightweight. API-Tennis advertises historical information, records, standings, odds, and live odds, with monthly plans from $40 to $120 and a public contact email at `contact@api-tennis.com`. Its documentation shows ATP, WTA, Challenger, and ITF event types; fixtures with date/time, season, and qualification flags; standings for ATP/WTA; players with season stats; and odds/live odds endpoints. Its public terms allow monthly cancellation and say the company takes no responsibility for how you use the feed, but they do **not** publicly answer the crucial rights questions about raw retention, derived-model retention after cancellation, local/private-cloud processing, or whether private Betfair betting is contractually allowed. So API-Tennis looks operationally usable, but its public contract evidence is still incomplete for your standard. citeturn46search0turn46search1turn21view0

For **Goalserve**, the public product page says its tennis feed covers ATP, WTA, Challenger, and ITF, can be used for betting applications, includes pregame and in-play odds, and is priced at $150 per month. Goalserve also publishes a direct support email, `support@goalserve.com`. But the public terms page is a generic website/subscription terms page rather than a detailed downstream data-licence document, and it does not clearly answer whether raw historical backfill is licensed for long-term retention, whether derived models survive cancellation, or whether private betting model training is expressly permitted. As with API-Tennis, the public evidence is commercially encouraging but contractually incomplete. citeturn25search0turn25search4turn26view0

## Betfair desk facts established

The Betfair desk-research portion is much firmer. Official Betfair support pages publish tennis pricing at **£49.00 per month for ADVANCED** and **£499 per year**, with PRO at **£150.00 per month** and **£1,499 per year**. The portal search snippet also shows the same tennis pricing. Purchases are debited from the Betfair account balance, and previously purchased data remains available through the **My Data** page for later download. citeturn51search0turn50search0turn51search2turn51search4

Official Betfair documentation also establishes the **ADVANCED** package semantics. The historical-data feed specification says files are time-stamped JSON stream-format data; `pt` is the **published time in milliseconds since epoch**; and `marketDefinition` includes fields such as `turnInPlayEnabled`, `marketTime`, `suspendTime`, `inPlay`, `status`, and `betDelay`. The package table shows that ADVANCED includes runner changes, runner traded volume, last traded price, best available to back (`batb`), best available to lay (`batl`), and traded price-volume deltas. The equivalent-subscription table shows ADVANCED is **all changes rolled up into 1-second intervals** and maps to `EX_BEST_OFFERS`, `EX_TRADED_VOL`, `EX_TRADED`, `EX_LTP`, and `EX_MARKET_DEF`. That is enough to establish, at desk-research level, that pre-match versus in-play state is distinguishable in principle, that temporary suspensions are visible in principle, and that official publish-time semantics are defined in the feed. citeturn41view0turn43view0turn39search0

Filtering is also clear from official Betfair help pages. Custom download supports **Sport, Date range, EventId, Event Name, Market Type, Country, and File Type** filters. Betfair recommends filtering on the **My Data** page and downloading in smaller chunks. It also distinguishes **Event (`E`) files**, which interleave all market changes for an event in published-time order, from **Market (`M`) files**, which contain one file per market; downloading both doubles size without adding information. That means the pilot can be defined very cleanly around **Tennis / ADVANCED / one month / file type M / selected market type(s)**. citeturn10search9turn13search4turn9search0turn9search8

On market coverage, Betfair explicitly states that **tennis “Game betting” markets are not available** in historical data. So the desk-research candidate remains centered on **Match Odds**, not game-betting submarkets. Betfair also states its historical data is made available **5 days after event settlement**, and that markets for an event appear only once all markets for that event have settled. citeturn10search6turn13search5

One thing the public crawl did **not** cleanly expose is a complete, publicly readable retention/reuse clause for Betfair historical data beyond the portal snippet noting “as is” terms. So, while the package, fields, prices, exclusions, and timestamps are established, the final retention/licence wording should still be re-checked on the portal acceptance text immediately before purchase. citeturn13search0turn44search0

## Exact candidate pilot month

The cleanest candidate pilot month is **June 2026**. The reason is practical and evidence-based: as of **17 July 2026**, June 2026 is the **most recent fully completed calendar month** that is comfortably past Betfair’s published **five-day post-settlement availability lag**. That makes it the newest month likely to be fully present in the historical portal without the incompleteness risk that comes with the still-current July month. citeturn45time0turn13search5

June 2026 is also a credible tennis sample on sporting grounds. The official ATP calendar shows June ATP events in Stuttgart and ’s-Hertogenbosch, then Halle and London, then Mallorca and Eastbourne, with Wimbledon beginning on 29 June. On the WTA side, official tournament pages show the Berlin WTA 500 from **15–21 June 2026** and the Bad Homburg WTA 500 from **21–27 June 2026**. So June gives you a live month with meaningful ATP and WTA main-tour activity and a late-month Grand Slam transition, while still being fully historical and recent. On current published Betfair rates, the candidate purchase would therefore be **Betfair Tennis ADVANCED, June 2026, £49.00**. citeturn38view0turn36search10turn36search13turn51search0

## What the pilot alone can answer

The part labelled **DR-TENNIS-MARKET-003B** is still blocked until a month is actually purchased and inspected. The public documentation is enough to justify the pilot and define what the files will contain, but it is **not** enough to answer the empirical questions you care about: market counts by ATP/WTA/Challenger/qualifying, actual completeness rates, real top-of-book spreads, real depth at £2/£10/£25/£50/£100, matched-volume evolution, frozen-horizon availability, delayed-start behavior, temporary suspension patterns, retirement/void frequency, or whether a stable closing benchmark window truly exists in tennis Match Odds. Betfair’s own docs support that these states should be measurable, because the files expose publish time, in-play status, suspend time, market status, prices, and traded/available-volume structures; but the magnitude and quality of those measurements are inherently file-dependent and cannot be inferred honestly from marketing copy. citeturn41view0turn43view0turn39search0

The same is true for **DR-TENNIS-BENCHMARK-002**. The right benchmark is still a post-pilot choice, not a desk choice. The public docs show the components needed to test candidates such as a final normalized midpoint, WAP-based windows, or microprice-like constructions, but they do not tell us whether the last pre-suspension window is consistently populated enough in tennis to support one benchmark over another. That decision still has to be made only after examining real June 2026 files. citeturn41view0turn39search0

## Evidence gaps and blockers

The biggest unresolved issue is exactly the one you identified in **DR-TENNIS-DATA-003**: **written contractual answers**. In this environment I could do the provider-contact preparation and contract-evidence extraction from official pages, but I could not actually send outbound provider emails or submit contact forms on your behalf. So no provider has yet given written answers to the critical questions about personal betting model training, raw-data retention, derived-model survival after termination, private-cloud processing, or explicit permission for private Betfair betting outputs. Those answers still need to come directly from TDI, Stats Perform, Tennis-Data.co.uk, API-Tennis, Goalserve, and Sportradar in writing. citeturn15search3turn49view0turn32search7turn46search0turn26view0turn47view0

What the research **has** accomplished is narrowing the decision set. If the aim is to move immediately on the tennis pivot with the least legal ambiguity and the highest-quality primary market evidence, the best next evidence object is no longer “find another tennis data vendor.” It is: **Betfair Tennis ADVANCED for June 2026 at £49.00**, followed by the empirical 003B measurement pass and only then the benchmark selection. Provider-feed licensing should continue in parallel, but only once the written contractual answers are collected. citeturn51search0turn43view0turn10search6turn13search5
---

## Assessment (agent, 2026-07-17)

### Corrections to prior findings (DR-TENNIS-BATCH-001)

1. **The Sportradar "prediction-market prohibition" lead is REFUTED as a blanket
   claim.** The public ATP addendum shows authorised official live-odds/trading use
   EXISTS inside a formal licence framework; what is barred is unofficial/unauthorised
   collection and trading routes. The batch findings file's red flag is superseded by
   this more specific reading — the question becomes "can an individual get an
   authorised licence, at what price", not "is it forbidden".
2. **Two previously unreached providers are now characterised:** TDI (official ATP
   gatekeeper; website terms expressly ban betting/odds/statistical-model/AI-training
   use without a licence; contact@tennisdata.com) and Stats Perform (official WTA;
   public Master License bars ML training, archival building, and betting use except
   where the signed work order allows). Both are conditional-on-contract, not open.
3. **Tennis-Data.co.uk now characterised:** most permissive-looking public language
   ("free to use", invites betting-system questions) but informal, unofficial, and
   silent on retention/derived-model/knowledge-time questions.

### New Betfair desk facts (DR-TENNIS-MARKET-002A/003A — now substantially answered)

- **Tennis pricing: ADVANCED £49.00/month, £499/year; PRO £150/month, £1,499/year**
  (tennis is its own package, cheaper than horse racing's £69/£230).
- Tennis "Game betting" markets are NOT in historical data; Match Odds is available —
  consistent with the Match-Odds-only pilot universe.
- E-files vs M-files distinction confirmed; M-files (one per market) are the pilot
  choice; ADVANCED = 1s roll-up, EX_BEST_OFFERS/EX_TRADED_VOL/EX_TRADED/EX_LTP/
  EX_MARKET_DEF — same structure DR-0001 established for racing.
- `marketDefinition` exposes inPlay/suspendTime/status/betDelay — pre-match vs
  in-play distinguishable in principle; magnitude/quality still pilot-dependent.
- Retention/reuse licence wording NOT cleanly exposed publicly — re-check the portal
  acceptance text immediately before purchase (carried forward as a pre-purchase step).

### Pilot month: June 2026 recommended by this report (vs April 2026 previously)

The report recommends **June 2026** (most recent complete month past the 5-day lag;
credible ATP/WTA sample: Stuttgart, 's-Hertogenbosch, Halle, Queen's, Mallorca,
Eastbourne, Berlin, Bad Homburg, Wimbledon starting 29 June). The repo's earlier
tennis-pilot spec recommended **April 2026** (full clay swing, no Slam transition).
Both rationales are legitimate and documented; neither inspected model performance.
**This is the founder's call at purchase time** — the purchase spec now records both
candidates. Candidate purchase either way: **Betfair Tennis ADVANCED, one month,
£49.00** (subject to portal price confirmation at checkout).

### What remains unresolved (unchanged)

Written contractual answers from every provider (the report could not send outbound
email); the empirical pilot measurements (DR-TENNIS-MARKET-002B/003B); benchmark
selection (post-pilot, evidence-driven); ADR 0015 account restoration; ADR 0016/0017
execution decisions. Research authorises nothing: no purchase, no licence, no gate.
