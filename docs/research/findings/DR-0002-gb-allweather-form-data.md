# DR-0002 findings — GB all-weather form data with knowledge-time support

**Returned:** 2026-07-16, via founder's ChatGPT Deep Research (per the Cost-Aware Deep
Research Routing Amendment). **Assessed:** 2026-07-16 (assessment follows the verbatim
report). Citation markers (`citeturn...`) are artifacts of the source tool preserved
verbatim; they resolve only inside the founder's ChatGPT session — load-bearing claims
are classified as SOURCE CLAIMS pending the founder's spot-check. The report also
partially overlaps DR-0001 (Betfair tiers); divergences are addressed in the assessment.

---

## Verbatim report

# Betfair Historical Data and GB All-Weather Form Data Procurement Review

## Scope and current status

All findings below are current as of **16 July 2026** in **Europe/London**. For the Betfair portion, I relied primarily on Betfair’s own historical-data support pages, the official package-specification PDF, and related Betfair developer materials. For the GB all-weather form-data portion, I relied primarily on each provider’s official product, pricing, and terms pages, then on BHA / Weatherbys / RDC materials for the official publication and administration chain. Where a point could not be established from those permitted sources, I have marked it **unresolved** rather than guessing. citeturn10search0turn2view0turn44search0turn30search1

## Betfair historical data for GB and IRE WIN markets

Betfair’s historical-data service is available to **Betfair.com customers only**, and Betfair says the service provides **market, price and settlement information** from **April 2015 onward** in this format. It also says the files are **time-stamped** and use the **same format as the Exchange Stream API**. Data is made available **5 days after event settlement**, once all markets in the event have settled. citeturn15search0turn15search2turn47search0turn47search3

### Tier-by-tier factual table

| Tier | What it contains for horse-racing WIN markets | Depth / traded / BSP / timing | Current public price and billing |
|---|---|---|---|
| **BASIC** | Market-definition changes plus runner changes containing **`ltp`** and **`tv`** only. Betfair’s spec describes BASIC as “**Traded Price Updates by Selection and Frequency, Market Definition Changes**.” citeturn2view0turn13search1 | **1-minute frequency**. No best-back / best-lay ladder. Runner changes are limited to **`id ltp tv`**. Market-definition payload includes fields such as status, suspend / settle times, runners, removal date, and runner **`bsp`** in the runner definition. The event timestamp field is **`pt`**; examples show it in **milliseconds since epoch**, while schedule times such as `marketTime` are ISO-8601 timestamps with milliseconds. citeturn2view0turn14view0 | Public Betfair price card shows **Horse Racing BASIC = Free**. Purchases are billed directly to the Betfair account statement. citeturn1search0turn15search1 |
| **ADVANCED** | Market-definition changes plus runner changes with **`batb`**, **`batl`**, **`ltp`**, and **`tv`**. Betfair’s support article explains `batb/batl` tuples as **[level, price, volume]**. citeturn2view0turn14view0 | **1-second frequency**. Depth is **best 3** on each side because levels are documented as **0–2**. Traded volume is present via **`tv`**. Market-definition changes include non-runner / suspension-relevant status fields as above. BSP is still present through market / runner definition fields, but the runner-change-only SP fields are not part of ADVANCED. citeturn2view0turn14view0 | Public Betfair price card shows **Horse Racing ADVANCED = £69.00 per month**. Betfair also publishes a **12-month bulk price of £699** for any 12 months of Horse Racing ADVANCED. Billing is via the Betfair account. citeturn1search0turn11view0turn15search1 |
| **PRO** | Tick-by-tick stream format with market-definition changes and runner changes including **full-book-style `atb` / `atl`**, traded-price updates **`trd`**, and SP-related fields **`spb` `spl` `spf` `spn`**, plus `batb/batl` and display-delta helpers. Betfair explicitly says PRO is the **Exchange Stream API tick-by-tick** package. citeturn2view0turn14view1 | **Tick by tick**, with no published conflation layer. `atb/atl` are absolute available volumes at price points; `trd` is cumulative traded volume by price point. Betfair also notes that `trd` may move both up and down because of cross-currency effects. This is the only tier that publicly proves full book evolution over time. citeturn2view0turn14view1turn13search5 | Public Betfair price card shows **Horse Racing PRO = £230.00 per month**. Betfair also publishes a **12-month bulk price of £2,299** for any 12 months of Horse Racing PRO. Billing is via the Betfair account. citeturn1search0turn11view0turn15search1 |

### Filtering and whether you can buy only GB and IRE WIN markets

Betfair’s official specification shows request filters for **event type / sport**, **country**, **market type**, **plan**, and date range fields. Betfair also says purchasers can **custom filter data prior to download**. However, Betfair separately says that the data is sold only via the packages provided and that you **cannot buy a cheaper subset** of a package. In practical terms, that means a buyer **can download only GB and IRE WIN horse-racing markets after purchase**, but **cannot buy a GB+IRE-WIN-only commercial subset at a reduced price**. citeturn2view0turn15search2turn12search0

### Cost estimates for 12, 24, and 36 months of GB and IRE horse racing

Because Betfair prices horse racing as one **Horse Racing** sport package rather than separate GB and IRE charges, the public cost basis is the same whether your downstream filter later keeps only GB / IRE WIN markets or all horse-racing markets. The only public discount schedule I found is the published **any-12-months** bulk price for an individual sport. On that basis:

| Tier | 12 months at list | 12 months at published bulk rate | 24 months estimated using two 12-month bulk blocks | 36 months estimated using three 12-month bulk blocks |
|---|---:|---:|---:|---:|
| BASIC | £0 | £0 | £0 | £0 |
| ADVANCED | £828 | **£699** | **£1,398** | **£2,097** |
| PRO | £2,760 | **£2,299** | **£4,598** | **£6,897** |

These are arithmetic estimates from Betfair’s current public monthly and bulk schedules. I did **not** find a separate public backfill schedule beyond the 12-month sport discount table. The public price pages I found display prices in **GBP**; I did **not** find a public multi-currency price schedule from permitted sources. citeturn1search0turn11view0

## Betfair licence position and the Gate recommendations

### What the public Betfair pages do and do not prove

Betfair’s own historical-data FAQ expressly frames the service as suitable for research and testing by saying you can **“Backtest your strategy before going ‘live’”** and **“Experiment with new sport/market types.”** That is strong support for **offline research / backtesting** as an intended use. Betfair also recommends historical-data tools and software for backtesting. citeturn15search2

I did **not** find, in the permitted official Betfair sources, a public historical-data licence text that explicitly answers all of the following: **model training**, **retention of raw purchased files**, **retention of models derived from those files**, **cloud or third-party CI processing**, **publication / redistribution of derived probabilities or odds**, or **commercial sale / operation of derived outputs**. Betfair’s public pages link out to general Terms & Conditions and Privacy Policy, but the specific historical-data-rights wording needed for those questions was not publicly visible in the materials I could lawfully cite here. Accordingly, those points should be treated as **unresolved / fail-closed** until you obtain the actual contractual language from Betfair. citeturn10search0turn15search1turn47search7

### Direct recommendation for Gate 1

For **Gate 1**, the cheapest tier that **can** support a pre-registered market-only probability arm is **BASIC**, **if** you define your market-information probability as a **last-traded-price-at-or-before-horizon** measure and accept BASIC’s structural limits: no best-back / best-lay quotes, no executable ladder, only **1-minute** frequency, and `ltp` only when it changes. BASIC also carries market-definition changes and final runner-definition BSP fields needed for post-race reconciliation. citeturn2view0turn13search1turn14view0

However, if your Gate-1 market-information probability needs a **quote-based** market view rather than last-traded, or anything finer than BASIC’s 1-minute structure, then **ADVANCED** is the true minimum because BASIC provably lacks `batb/batl`. ADVANCED adds best-3 prices and volumes at **1-second** frequency, which is a much cleaner foundation for horizon snapshots. My operational recommendation is therefore:

- **Cheapest defensible Gate-1 tier:** **BASIC**, only for an **LTP-defined** market arm. citeturn2view0turn13search1
- **Safer Gate-1 tier:** **ADVANCED**, if you want an actual pre-off quote snapshot rather than a potentially stale last-traded price. citeturn2view0turn14view0

### Direct recommendation for Gate 2

For **Gate 2**, the minimum tier is unambiguously **PRO**. Your requirement is **latency-adjusted, size-aware executable-price scenario analysis**, which needs book depth and traded-volume evolution over time. Betfair’s own materials show that:

- **ADVANCED** only provides **best-3** `batb/batl` ladders at **1-second** frequency. citeturn2view0turn14view0
- **PRO** provides **tick-by-tick** `atb/atl` depth, `trd` by price point, and SP-specific fields, with explicit documentation on how available and traded volume are represented. citeturn2view0turn14view1

Therefore:

- **Gate 2 minimum tier: PRO.** citeturn2view0turn14view1
- What lower tiers lack: BASIC lacks any ladder; ADVANCED lacks full-depth order-book history and is conflated to 1 second. citeturn2view0turn14view0

## GB all-weather form-data candidates

The strict requirement here is tougher than “has racecards.” You need a source that is **lawful**, **machine-readable**, and has **genuine knowledge-time support** for what was known before the race. That means not only current APIs, but either field-level timestamps or official publication schedules precise enough to reconstruct prior knowledge.

### Candidate comparison table

| Candidate | Machine-readable access offered? | Lawfulness from public terms | Knowledge-time support for pre-race fields | Public price visibility | Coverage notes | Verdict |
|---|---|---|---|---|---|---|
| **Weatherbys / RDC / BHA-origin pre-race data** | **Yes, in principle.** Weatherbys advertises tailored data files and API services; RDC licenses official British pre-race data; Weatherbys continues to provide PRD services. citeturn30search1turn44search0turn44search3 | **Exact licence text unresolved publicly.** I found no public contract terms spelling out offline research / model training / redistribution rights, so I cannot quote them. What is public is that this is an official commercial data-supply route, not scraping. citeturn30search1turn44search0 | **Strongest official knowledge-time evidence.** NRAS is the administration system for entries, declarations, jockey bookings, and non-runners; BHA says provisional declarations can be tracked live before **10:00**; Weatherbys overnight declarations are released at **10:30am** the day before; BHA ratings are updated every **Tuesday morning**. citeturn30search2turn32search4turn32search10turn31search0turn31search2turn31search18 | **No public price found.** citeturn30search1turn44search0 | Official British route, so GB all-weather coverage is the best-supported inference, but public history depth by year was not stated in the pages I found. citeturn44search0turn30search2 | **Best evidence chain for genuine knowledge-time. Cheapest cannot be proven publicly.** |
| **Timeform API** | **Yes.** Betfair’s developer page says the API is available to Betfair customers for **“private or commercial use”**; Timeform’s older API article says users can plug it into **“your own calculations and algorithms.”** citeturn19view1turn43view0 | **Mostly supportable, but not fully.** The public API positioning supports licensed private / commercial use. Timeform’s own site also says website data “may not be used … without a license,” so the licensed API is the lawful route. I did not find a public API contract that specifically enumerates model-training or redistribution rights. citeturn19view1turn43view1 | **Promising but not fully proved for historical KT.** Timeform is appointed by RDC as an onward supplier of official British pre-race data, and the API is “intended to deliver pre-race data to commercial customers,” but I did not find public documentation proving field-level publication timestamps or historical snapshot semantics for declarations / non-runners. citeturn43view1turn19view0 | **No current public API price found.** A 2014 article quoted £500–£1,500 per month for individual users, but that is not current enough to use as a 2026 price. citeturn43view0 | Timeform says API coverage matches its website, which covers Britain since the early 1990s; that would include GB all-weather racing, but explicit AW-track lists are not published on the commercial pricing page. Timeform is also a **Flutter** company, which may help operationally when paired with Betfair, but that is a corporate relationship, not a licence shortcut. citeturn19view0turn19view2turn43view1 | **Runner-up. Best public machine-readable candidate after the official admin-data route.** |
| **Racing Post B2B API** | **Yes, for B2B.** Spotlight Sports Group’s official announcement describes a JSON API with racecards, form, results, stats, pedigree, and more. citeturn21search1 | **Public B2B licence text not found.** For consumer-facing Racing Post services, official terms say the site / interactive services are for **“personal and non-commercial use only.”** That means consumer-site use or scraping is not acceptable for this project. citeturn21search1turn29search2 | **Not proven.** The B2B announcement says data is up to date when queried, but I found no public documentation of publication timestamps or historical snapshot rules for declarations, ratings, or non-runners. citeturn21search1 | **No public B2B price found.** Consumer-facing products exist, but those are not machine-readable licensing answers. citeturn21search1turn27search7 | Broad GB racing coverage is strongly implied, but years of historical machine-readable backfill are not publicly specified in official B2B materials I found. citeturn21search1 | **Commercial API exists, but public KT and public licence granularity are insufficiently documented.** |
| **Raceform Interactive** | **No public API found.** The official product is PC software / subscription tooling, not an openly documented machine-readable feed. citeturn27search7turn28view0 | Consumer terms are subscription / shop terms, and Racing Post’s general service terms restrict use to **personal, non-commercial** use. That is not a safe basis for a GB research entity building a model pipeline. citeturn28view0turn29search2 | **Not proven.** No public timestamped feed or documented publication schedule for historical snapshots was found. citeturn28view0 | Public consumer prices are **£47/month** for Flat only and **£72/month** for Flat & Jumps. citeturn27search0turn27search7 | Official BHA results are included, but that does not solve the machine-readable or KT problem. citeturn27search7 | **Fail for this project: display / software product, not a publicly evidenced lawful machine-readable KT source.** |
| **Proform Racing** | **No public API found.** The official product is a subscription research platform. citeturn24view0turn25view0 | Terms allow printing / downloading for **personal use** and say you **“must not”** use site content for commercial purposes without a licence. The site also says it provides analytical tools and historical data only. citeturn26view0turn26view1turn25view0 | **Not proven.** I found no public field-level publication timestamps or official knowledge-time schedule documentation for declarations / ratings / non-runners. citeturn24view0turn25view0 | Public monthly prices shown are **£37.50** for Standard and **£97.50** for Premium. citeturn25view0 | Proform says it covers UK & Irish Flat and Jumps and back-testing history since **1997**. That strongly implies AW coverage, but it does not solve licence or KT. citeturn24view0 | **Fail for this project: consumer research platform, not a publicly evidenced KT-capable machine-readable feed.** |
| **Total Performance Data** | **Yes**, but for live/websocket/JSON GPS and race-metric feeds. citeturn33search0turn33search4turn37search8 | Public terms shown in docs say stream data is for display and **“must not be used to store and save racing data”**; historical commercial use is via a separate licence. citeturn35search1 | **Fails the fundamental-data requirement.** TPD’s public offering is live, in-race, and post-race tracking / pace / stride data. It is not the primary official source for declarations, official ratings, or non-runner publication times. citeturn23search8turn33search1turn37search8 | Public TPD Zone prices are **£10 / £36 / £70 / £120 / £240 per month** depending on race allowance. Historical / stride data is by contact. citeturn34search0turn35search3 | Track coverage depends on racetrack rights. TPD itself says coverage grows as rights are sold to it, which is not a safe basis for assuming complete six-track GB AW coverage from public sources alone. citeturn34search3turn33search1 | **Useful for in-running research, not the cheapest lawful source of pre-race form with KT.** |
| **At The Races / Sky Sports Racing** | I found **no official public API / feed documentation** in permitted official sources. I found only consumer / media site materials and FAQs. citeturn37search2turn37search4 | Because no official public machine-readable product / terms were located, any attempt to extract data from the consumer site would be a scraping route and should be treated as quarantined. citeturn37search2turn37search4 | **Not proven.** No public machine-readable KT evidence found. citeturn37search2turn37search4 | **No public feed price found.** citeturn37search2turn37search4 | Consumer racecards clearly cover GB racing, but that is not the same as a licensed machine-readable source. citeturn37search4 | **Fail: no public official feed evidence found.** |
| **The Racing API** | **Yes.** Public REST API, docs, pricing and terms are available. citeturn38search0turn42search0turn39search4 | Public terms explicitly allow use in the creation of **applications, websites, and data analysis**, and the product page expressly includes **statistical analysis**, **research**, and **betting models, strategies and automated trading programs**. But it also states it is **not an official provider** and that data is compiled from public sources. citeturn38search0turn42search2 | **Fails strict KT.** The service updates today’s racecards every **3 minutes**, tomorrow’s every **15 minutes**, future racecards daily, and it does not claim official source-of-record timestamps for field publication. Since it is not an official provider, it does not satisfy your genuine historical knowledge-time bar. citeturn38search0turn42search2 | Public prices are **Free / £27.99 / £59.99 / £99.99** per month. citeturn42search0 | It advertises UK / Irish coverage, but the issue is provenance, not nominal field coverage. citeturn38search0turn42search2 | **Cheapest lawful public API I found, but it does not meet the KT requirement.** |

## Recommendation

The strict answer is that **the cheapest publicly provable lawful source that also genuinely supports pre-race knowledge-time could not be established from public official sources**. The reason is simple: the sources with the best knowledge-time evidence — the **official British pre-race/admin chain** through **Weatherbys / RDC / BHA-origin data** — do **not** publish the pricing and licence detail needed to prove “cheapest” from the open web. citeturn30search1turn44search0turn32search4turn31search0

So the best-supported recommendation is:

**Recommended route:** pursue the **official pre-race data route via Weatherbys / RDC / BHA-origin supply**, because it has the strongest evidence for real publication-time support: entries and declarations administered in the official system, live provisional declaration tracking before 10:00, overnight declaration release at 10:30 the day before racing, and official ratings on a documented Tuesday-morning cycle. That is the cleanest provenance chain for declarations, official ratings, and non-runner timing. Before purchase, require written contractual answers on: offline research, model training, raw-data retention, model retention, cloud processing, and redistribution / publication of derived outputs. citeturn30search2turn32search4turn32search10turn31search0turn31search2turn44search0

**Runner-up:** **Timeform API**. It is the strongest public machine-readable commercial option I found because it is explicitly for **private or commercial use**, is designed to plug into **calculations and algorithms**, and is appointed by RDC as an onward supplier of official British pre-race data. It also has a clear corporate synergy with Betfair because Timeform is a Flutter business. What stops it from being the primary recommendation is not general quality, but the lack of public proof that historical declarations / non-runners / ratings are preserved with the exact knowledge-time semantics your project requires. Ask for sample payloads and documentation showing publication timestamps or immutable snapshots before relying on it for EXP-0001’s fundamental arm. citeturn19view1turn43view0turn43view1

**Cheapest lawful public API, but not acceptable for this requirement:** **The Racing API**. It is the lowest-cost machine-readable source I found with explicit research / modelling permission, but it also explicitly says it is **not an official provider**, uses public sources, and only documents interval-based updates, not true administrative publication provenance. That makes it unsuitable for your strict KT bar even though it may be economically attractive for exploratory or editorial tools. citeturn42search0turn42search2turn38search0

## Dated source list with hierarchy labels

### Betfair historical-data sources

- **Betfair Historical Data support article: “What data packages are available?”** — updated **16 Jul 2026**. **Hierarchy tier: 1**. Confirms the three package names and points buyers to the data specification. citeturn10search0
- **Betfair Historical Data specification PDF** — published **11 Jun 2025**. **Hierarchy tier: 1**. The load-bearing source for fields, message types, frequency, and filters. citeturn2view0
- **Betfair support article: “Are bulk purchase discounts available?”** — updated **15 Jun 2026**. **Hierarchy tier: 1**. Current 12-month bulk pricing for Horse Racing ADVANCED and PRO. citeturn11view0
- **Betfair support article: “How do I pay for the data bought through the Historical Data site?”** — updated **15 Jun 2026**. **Hierarchy tier: 1**. Billing method. citeturn15search1
- **Betfair support article: “How frequently is the historical data updated?”** — updated **15 Jun 2026**. **Hierarchy tier: 1**. Five-day post-settlement release rule. citeturn47search0
- **Betfair support article: “How do I download and view Betfair Historical Data?”** — updated **15 Jun 2026**. **Hierarchy tier: 1**. Confirms time-stamped data and Exchange Stream API format. citeturn47search3
- **Betfair support article: “What data is provided by the Historical Data service?”** — updated **15 Jun 2026**. **Hierarchy tier: 1**. Research / backtesting positioning and April 2015 start. citeturn15search2
- **Betfair support article: “Advanced Historical Data - How do I interpret updates?”** — updated **15 Jun 2026**. **Hierarchy tier: 1**. Best-3 ladder semantics in ADVANCED and timestamp examples. citeturn14view0
- **Betfair support article: “How is traded & available volume represented within the PRO Historical Data files?”** — updated **15 Jun 2026**. **Hierarchy tier: 1**. Full-depth / traded-volume semantics in PRO. citeturn14view1

### GB all-weather form-data sources

- **Weatherbys “Data Supply”** — crawled **16 Jul 2026**. **Hierarchy tier: 1**. Evidence of official data supply and API / bespoke-feed route. citeturn30search1
- **Weatherbys “Racing / NRAS”** — crawled **16 Jul 2026**. **Hierarchy tier: 1 / 2 hybrid** because Weatherbys is both provider and racing administrator. Shows entries, declarations, and non-runner functions in the official admin system. citeturn30search2
- **Racecourse Data Company / RMG pre-race data pages** — crawled **16 Jul 2026**. **Hierarchy tier: 2**. Official British pre-race data licensing structure and Weatherbys’ continuing PRD-service role. citeturn44search0turn44search3
- **BHA “Ratings database”** — crawled **16 Jul 2026**. **Hierarchy tier: 2**. Tuesday-morning official ratings publication. citeturn31search0
- **BHA “Transparent declaration tracking available on BHA Website”** — published **10 Mar 2023**, crawled **16 Jul 2026**. **Hierarchy tier: 2**. Live provisional declaration tracking before 10:00. citeturn32search4
- **BHA / Weatherbys declaration timing evidence** — BHA press material stating overnight declarations are released by Weatherbys at **10:30am** the day before. **Hierarchy tier: 2**. citeturn32search10
- **Betfair Developers “Guide to the Timeform API”** — crawled **16 Jul 2026**. **Hierarchy tier: 1**. Current public statement that Timeform API is for “private or commercial use.” citeturn19view1
- **Timeform commercial / products pages** — crawled **16 Jul 2026**. **Hierarchy tier: 1**. Current commercial-only wording, official-British-pre-race-data lineage via RDC, and current lack of public API pricing. citeturn19view0turn43view1
- **Spotlight Sports Group “Announcing the Racing Post API”** — crawled **16 Jul 2026**. **Hierarchy tier: 1**. Evidence that a B2B Racing Post API exists and is query-current, but without public KT semantics or pricing. citeturn21search1
- **Racing Post general terms** — crawled **16 Jul 2026**. **Hierarchy tier: 1**. “personal and non-commercial use only” for site / interactive-services use. citeturn29search2
- **Proform pricing and terms pages** — crawled **16 Jul 2026**. **Hierarchy tier: 1**. Consumer pricing and personal-use / no-commercial-use-without-licence position. citeturn25view0turn26view0turn26view1
- **TPD Zone pricing, websocket docs, and live/post-race API pages** — crawled **16 Jul 2026**. **Hierarchy tier: 1**. Consumer GPS pricing and storage / historical-licence restrictions. citeturn34search0turn35search1turn37search8
- **The Racing API pricing and terms** — crawled **16 Jul 2026**. **Hierarchy tier: 1**. Cheapest publicly priced lawful API found, but explicitly non-official and therefore insufficient on KT provenance. citeturn42search0turn42search2

## Unresolved and uncertain items

I did **not** find a public Betfair historical-data licence text from the permitted official sources that expressly settles **model training**, **raw-data retention**, **derived-model retention**, **cloud / third-party CI use**, **publication of derived probabilities**, or **commercial sale of derived outputs**. Betfair’s public pages strongly support backtesting and experimentation, but those narrower rights remain contract questions. citeturn15search2turn10search0

I did **not** find public current API pricing for **Timeform** or public B2B pricing / licence detail for the **Racing Post API**. I also did **not** find a public Weatherbys / RDC rate card or public model-training licence text for the official British pre-race-data route. That is why I cannot prove the **cheapest** knowledge-time-capable source from open sources alone. citeturn43view1turn21search1turn30search1turn44search0

For **Timeform** and **Racing Post B2B**, I found strong evidence that the products carry rich pre-race data, but I did **not** find public documentation proving historical **field-level publication timestamps** or immutable snapshot semantics for declarations / non-runners / ratings. Those products may still be sufficient in practice, but that cannot be proven from the permitted public sources I found. citeturn43view1turn21search1

For **At The Races / Sky Sports Racing**, I found consumer-site and media materials but **no** official public machine-readable feed documentation or pricing in permitted official sources. I therefore treat this route as **not established** rather than assuming an API exists. citeturn37search2turn37search4

For **TPD**, public GPS subscription pricing is clear, but history / stride-data commercial pricing is **contact-only**, and racecourse coverage depends on rights held, so complete six-track GB all-weather coverage could not be proved from public official pages alone. citeturn35search3turn34search3

---

## Assessment (agent, 2026-07-16)

### Validation against the request

The DR-0002 question is answered honestly: no candidate can be publicly proven both
cheapest AND knowledge-time-capable, because the best-KT sources (the official
Weatherbys/RDC/BHA chain, Timeform, Racing Post B2B) do not publish prices or licence
granularity. All five evaluation criteria are covered per candidate, scraping-only
routes are flagged, and the unresolved section is explicit. The report meets the
acceptance criteria within what public sources allow. Citation markers again resolve
only in the founder's session.

### Divergences from DR-0001 (same underlying facts, different question phrasing)

- This report says BASIC could support a "cheapest defensible" LTP-defined Gate-1 arm.
  **For this repository that option does not exist:** our pre-registered
  `specs/prices/info-price-v1.yaml` defines p_market_info as the best-back/best-lay
  implied-probability midpoint, which BASIC structurally cannot compute (no quotes).
  Changing the definition to LTP would be info-price-v2 — a new pre-registration —
  and would trade a £69/month saving for a stale, one-sided market measure. Not
  recommended. ADVANCED remains our Gate-1 minimum (consistent with DR-0001).
- Gate-2 = PRO is repeated as phrased; the DR-0001 assessment's inference stands:
  under our frozen taker-v1 policy, Gate 2 may be satisfiable on ADVANCED with
  pre-registered 1s/best-3 scenario limits.
- New source claims not in DR-0001: history starts April 2015; service is for
  Betfair.com customers only; BASIC runner changes carry `tv` as well as `ltp`
  (DR-0001 said no `tv` in BASIC — a direct conflict between the two reports; the
  founder's spot-check of the spec PDF should settle it; nothing in our plans turns
  on it).

### Classification

**Facts (repository-relevant, verified locally):** our scraping quarantine (SPEC-100)
already structurally handles the report's "quarantined" verdicts — a scraped source
can never feed anything reachable from the decision layer, so Racing Post consumer
pages, ATR, and similar are unusable for the live path regardless of their content.
Our knowledge-time machinery (SPEC-020/023) is exactly what the report's KT bar maps
onto: a source without provable publication times produces features that fail the
feature build, by construction.

**Source claims (tier-1/2 cited, pending spot-check):** the candidate table's terms,
prices and KT evidence as written — notably: official chain (NRAS declarations,
10:30am overnight decs, Tuesday ratings cycle) has the strongest KT evidence and no
public price; Timeform API is Betfair-customer-accessible for "private or commercial
use" with no current public price (2014 quote £500–£1,500/month, stale); The Racing
API is £27.99–£99.99/month, research/model use permitted, but explicitly non-official
with interval-based updates (fails strict KT).

**Inferences (the assessor's):**

1. **The fundamental arm is now the project's cost and schedule risk, not the Betfair
   data.** The Betfair side has firm prices (£69/month pilot path). The form-data side
   has NO usable public price for any KT-capable source, and the one stale datapoint
   (Timeform 2014: £500–£1,500/month) is far above this project's spend posture. If
   KT-capable form data costs anything like that, the founder faces a real decision:
   fund it, or descope EXP-0001.
2. **EXP-0001 as drafted is blocked on form data** — the combined arm needs
   p_fundamental, and σ_d (the sample-size pilot input) is the spread of d_r between
   the combined and market arms, so even the pilot needs some fundamental features.
   A descoped EXP-0001a is available if form data stalls: market-only vs a
   fundamentals-from-market-history model is NOT valid (that's market info by another
   name) — but a minimal fundamental feature set from officially published free BHA
   ratings pages exists only via scraping, which is quarantined from the live path.
   Honest options: (a) wait for provider quotes; (b) fund Timeform/official-chain if
   quotes are acceptable; (c) run a scraped-ratings RESEARCH-ONLY pilot (SPEC-100
   quarantine respected — results can never authorise a live path and would need
   re-running on licensed data). Option (c) burns no lockbox and buys σ_d
   methodology practice, but its numbers are provisional by construction.
3. **The two provider contacts are founder actions** (money/identity): Weatherbys/RDC
   and Timeform, asking for: personal-use research licence terms (offline research,
   model training, retention, cloud processing, no publication needed pre-Gate-P1),
   pricing for GB all-weather pre-race data with historical backfill, and — decisive
   for KT — sample payloads or documentation showing field-level publication
   timestamps or immutable declaration/ratings snapshots.
4. The report's Betfair-licence caution (couldn't surface the operative licence text
   at all) is STRONGER than DR-0001's (which quoted portal snippets). Combined
   posture stays the same: fail closed, get written answers before purchase.

**Recommendations (decision menu — research authorises nothing):**

- Founder contacts Weatherbys/RDC and Timeform for quotes + KT evidence (I can draft
  both emails on request).
- Betfair £69 pilot month proceeds independently of form data (pipeline validation +
  p_market_info infrastructure) once authorised — the market side of EXP-0001 is
  buildable while form-data quotes are awaited.
- Decide whether a quarantined scraped-ratings research pilot (option c) is wanted in
  the meantime; it is lawful-risk-adjacent and must be explicitly authorised, never
  assumed.
- The Racing API is recorded as unsuitable for the strict KT bar (kept on file for
  possible non-evidence exploratory tooling only, and only if ever needed).

**Unresolved (carried to ledger):** all KT-capable source prices; Timeform/official
chain licence granularity; Racing Post B2B terms; BASIC `tv` discrepancy between the
two reports; Betfair operative licence text (now flagged by both reports).

### Impact on repository artifacts

- `docs/licensed-sources.yaml`: still no entries — both sources await written terms.
- `EXP-0001-draft`: feature_set remains ⟨PENDING⟩; registration blocked on form-data
  resolution; the market-side infrastructure is buildable against the Betfair pilot.
- No spec, manifest, or code change required by these findings.
