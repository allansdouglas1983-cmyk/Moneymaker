# DR-0001 findings — Betfair Historical Data packages

**Returned:** 2026-07-16, via founder's ChatGPT Deep Research (per the Cost-Aware Deep
Research Routing Amendment). **Assessed:** 2026-07-16 (assessment follows the verbatim
report). Citation markers (`citeturn...`) are artifacts of the source tool preserved
verbatim; they resolve only inside the founder's ChatGPT session, so every load-bearing
claim is classified below as a SOURCE CLAIM pending the founder's spot-check of the
underlying pages — not as an independently verified fact.

**Founder status clarification (2026-07-16):** the founder is an INDIVIDUAL and this
project is for PERSONAL USE — recorded because the licence terms turn on exactly this
distinction (see assessment).

---

## Verbatim report

# Betfair Historical Data Packages for GB and IRE Horse Racing

## Executive conclusion

As of **2026-07-16 (Europe/London)**, Betfair’s official historical-data materials support this practical conclusion for a GB-based horse-racing research project:

**ADVANCED is the cheapest tier that genuinely supports Gate 1**, because it gives you **1-second** rolled-up pre-off market data with **best-3 back and lay quotes**, traded-price deltas, last-traded price, market-definition changes, and the all-plan BSP reconciliation fields. **BASIC does not genuinely support Gate 1** unless you deliberately define market information using only stale-or-absent last-traded price, because BASIC is only **EX_LTP + EX_MARKET_DEF**, at **1-minute intervals**, and its `ltp` is **only sent when it changes**. **PRO is the cheapest tier that genuinely supports Gate 2**, because Gate 2 explicitly needs **full order-book depth** and traded-volume evolution, and only PRO gives **all-ladder `atb`/`atl`** on a **tick-by-tick** basis. citeturn3view3turn13view2turn3view2turn13view1

You **can** filter downloads to **GB + IE + WIN** markets through Betfair’s Historical Data API and My Data filtering, but you **cannot** buy only that subset at a reduced subset price. Betfair’s public support documentation says the custom download can filter by **sport, date range, eventId, event name, market type, country and file type**, and its API example explicitly shows **`marketTypesCollection: ["WIN"]`-style filtering and `countriesCollection: ["GB","IE"]`-style filtering**. But Betfair also says **“All data is sold ‘as is’ and is only available for purchase via the packages provided.”** citeturn13view3turn35view1turn35view2turn13view4

On licensing, the public Betfair historical-data terms surfaced from the official historical-data portal are clear on the big points: the purchased historical data is for **“personal, internal use only,”** it **“may not be used for any business purpose without a licence,”** and **“No onward distribution”** of the Historical Betfair Data is allowed. Betfair’s vendor-program materials also say that where data is needed for **“testing, analysis, training or simulation modes,”** the **historical data services** should be used, and a separate Betfair vendor-licence document says you must not provide access to **“Historical Betfair Data, Historical Betfair Data related products”** without a Historical Data License. What the public sources do **not** cleanly resolve is whether **purely derived probabilities/odds** can be **published or commercialized** without extra clearance, or whether private cloud/CI processing is permitted under the purchase terms alone. citeturn39search0turn38search0turn37search0turn15view0turn16view0

## Package contents and granularity

Betfair’s official historical-data feed specification says that **all pricing plans** use the same broad message family: `op`, `mcm`, `pt`, `mc`, `id`, and `marketDefinition`. The same all-plan schema also carries the market- and runner-status information you care about for horse-racing WIN markets: `status` values such as **OPEN / SUSPENDED / CLOSED**, runner statuses such as **ACTIVE / REMOVED / WINNER / LOSER**, plus `bspReconciled`, runner `bsp`, `removalDate`, and `adjustmentFactor`. The key timestamp field `pt` is explicitly defined as **“Published Time (in millis since epoch)”**. citeturn1view0turn2view0

Betfair’s downloadable specification then distinguishes the tiers by both **content** and **frequency/conflation model**. The subscription-equivalence table is the clearest evidence for how much book you really get: **PRO = tick by tick + all changes as per API stream format + `EX_ALL_OFFERS`**, **ADVANCED = 1 second intervals + rolled up + `EX_BEST_OFFERS`**, **BASIC = 1 minute intervals + `EX_LTP` plus `EX_MARKET_DEF`**. citeturn3view3

### Tier-by-tier factual table

| Tier | What it contains for GB/IRE horse-racing WIN markets | Price depth and traded data | Timestamp / update cadence | What it provably lacks |
|---|---|---|---|---|
| **BASIC** | All-plan fields, including `marketDefinition`, market status, runner status, `bspReconciled`, runner `bsp`, and `ltp`. Betfair’s subscription-equivalence table maps BASIC to **`EX_LTP` + `EX_MARKET_DEF`** only. citeturn1view0turn2view0turn3view3 | No `rc`, no runner-level book deltas, no `batb`, no `batl`, no `trd`, no market total `tv`, no runner total `tv`. BASIC therefore does **not** carry quoted back/lay ladders or traded-price evolution. Betfair also says BASIC `ltp` is **only sent when it changes**, not repeated in every 1-minute message. citeturn3view2turn3view3turn13view2 | `pt` is milliseconds since epoch across all plans; BASIC itself is delivered at **1-minute intervals**. citeturn1view0turn3view3 | Anything needed for depth-aware execution or reliable quoted-price snapshots: no best quotes, no full ladder, no traded deltas. citeturn3view2turn3view3 |
| **ADVANCED** | All-plan fields plus `rc`, market total `tv`, runner total `tv`, `ltp`, `batb`, `batl`, and `trd`. Betfair’s table maps ADVANCED to **`EX_BEST_OFFERS`**, **`EX_TRADED_VOL`**, **`EX_TRADED`**, **`EX_LTP`**, **`EX_MARKET_DEF`**. citeturn3view2turn3view3 | `batb`/`batl` are **best-available** offers only, and Betfair’s support example explicitly states each update is `[Level (0-2), Price, Volume Available]`, i.e. **best 3 levels only**. ADVANCED also carries traded-price deltas and both market-total and runner-total traded-volume fields. citeturn14view0turn14view3turn3view2 | `pt` is milliseconds since epoch across all plans; ADVANCED is **“all changes as per API stream format rolled up by frequency”** at **1 second intervals**. citeturn1view0turn3view3 | No **all-ladder** `atb`/`atl`, no `spb`/`spl`, no projected SP `spn`/`spf`. So it lacks full-depth queue information. citeturn3view2turn3view3 |
| **PRO** | All-plan fields plus `rc`, market total `tv`, `ltp`, `trd`, `spb`, `spl`, `spn`, `spf`, and **all-ladder** `atb`/`atl`. Betfair maps PRO to **`EX_ALL_OFFERS`**, **`EX_TRADED_VOL`**, **`EX_TRADED`**, **`EX_LTP`**, **`EX_MARKET_DEF`**, **`SP_TRADED`**, **`SP_PROJECTED`**. citeturn3view2turn3view3 | Full depth: the spec explicitly says `atb` / `atl` are **“All ladder levels”**. Betfair’s PRO FAQ says `atb/atl` volumes are **absolute** at each price, a `0` volume removes the point, and `trd` is cumulative **at each price point**. Betfair also says PRO does **not** contain the total cumulative traded volume per runner, only cumulative traded amount **at each traded price**. citeturn3view2turn13view1 | `pt` is milliseconds since epoch across all plans; PRO is **tick by tick** with no stated roll-up/conflation. citeturn1view0turn3view3 | It does not give ADVANCED’s separate runner-total `tv`; instead you reconstruct runner trading via the price-point `trd` stream. citeturn3view2turn13view1 |

### Message types, market-definition changes, BSP, and resolution

For **message types**, the official feed specification says every plan uses `mcm` market-change messages carrying initial images and updates; `mc` is the market-change object; `marketDefinition` is republished when any listed market-definition field changes. That same all-plan schema includes the fields that record non-runner and suspension type changes: market `status`, runner `status`, `removalDate`, `adjustmentFactor`, and `bspReconciled`. citeturn1view0turn2view0

For **BSP**, the all-plan schema includes runner `bsp` and market `bspReconciled`, so all tiers carry the reconciled BSP/result-state information needed for post-race grading. Only **PRO** adds the pre-reconciliation or projected SP-side fields `spb`, `spl`, `spn`, and `spf`. citeturn2view0turn3view2

For **timestamp resolution**, the only field with an explicit precision statement in the public spec is `pt`, which is in **milliseconds since epoch**. Other date-time fields such as `marketTime`, `suspendTime`, `openDate`, and `removalDate` are typed as strings in the schema; examples are ISO-like timestamps ending in `Z`, but the public spec does not separately state their guaranteed sub-second resolution. citeturn1view0turn14view0

## Pricing, billing and filtering

Betfair’s current official historical-data portal snippet, crawled on **2026-07-16**, shows the horse-racing price row as **“Sport, Basic, Advanced, Pro; Horse Racing, free, £69.00, £230.00.”** Betfair’s support FAQ independently confirms the **Horse Racing ADVANCED** price at **£69.00 per month** and the **Horse Racing PRO** price at **£230.00 per month**, with annual bulk prices of **£699** and **£2,299** respectively for **any 12 months of data for an individual sport**. citeturn33search0turn1view3

Betfair says historical-data purchases are **debited directly from your Betfair account** and appear on your statement in the format **`[Plan Type] [Sport] [Month Year] / [Month Year Range]`**, which shows that billing is organized by purchased sport-plan-month or month-range items. Betfair’s Historical Data API example reinforces this by showing `GetMyData` responses with `plan`, `sport`, and `forDate`, where `forDate` is explicitly **“The Month that this item covers.”** citeturn13view6turn35view0

Betfair’s public support also says bulk discounts are available for **“any 12 months of data for an individual sport”** if you contact Developer Support. No separate official backfill schedule beyond that 12-month discount is publicly listed in the support FAQ I found. The historical-data homepage snippet also says **“All data from May 2015 – April 2016 is free to purchase,”** but because that statement is only visible to me as a search snippet from a JS-rendered page, I have not used it in the standard 12/24/36 month cost estimates below. citeturn1view3turn10search0

### Price and cost table

| Tier | Current horse-racing price as of 2026-07-16 | Published 12-month bulk price | Estimated cost for 12 months | Estimated cost for 24 months | Estimated cost for 36 months |
|---|---|---:|---:|---:|---:|
| **BASIC** | Free. citeturn33search0 | No separate bulk schedule published; free row shown on official portal snippet. citeturn33search0 | **£0** | **£0** | **£0** |
| **ADVANCED** | **£69.00/month**. citeturn33search0turn1view3 | **£699/year** for any 12 months of one sport. citeturn1view3 | **£699** estimated minimum using the published annual discount, versus **£828** at straight monthly pricing. citeturn1view3 | **£1,398** estimated if the published 12-month discount is applied to two 12-month blocks, versus **£1,656** straight monthly. citeturn1view3 | **£2,097** estimated if the published 12-month discount is applied to three 12-month blocks, versus **£2,484** straight monthly. citeturn1view3 |
| **PRO** | **£230.00/month**. citeturn33search0turn1view3 | **£2,299/year** for any 12 months of one sport. citeturn1view3 | **£2,299** estimated minimum using the published annual discount, versus **£2,760** straight monthly. citeturn1view3 | **£4,598** estimated if the published 12-month discount is applied to two 12-month blocks, versus **£5,520** straight monthly. citeturn1view3 | **£6,897** estimated if the published 12-month discount is applied to three 12-month blocks, versus **£8,280** straight monthly. citeturn1view3 |

### What filtering exists, and whether you can buy only GB and IRE WIN markets

Betfair’s public support states that the **Custom Download** can filter by **Sport, Date range, EventId, Event Name, Market Type, Country, and File Type** before download. Betfair’s own Historical Data API example is even more explicit: it shows `GetCollectionOptions` returning market types including **`WIN`** and countries including **`GB`** and **`IE`**, and then shows a filtered request using `marketTypesCollection: [ "WIN", "PLACE" ]`, `countriesCollection: [ "GB", "IE" ]`, and `fileTypeCollection: [ "M" ]`. citeturn13view3turn35view1turn35view2

So the precise answer is:

- **Yes, you can download only GB+IRE WIN horse-racing markets** after purchase, because the official filter vocabulary supports **Country** and **Market Type**, and Betfair’s own API example shows both `WIN` and `GB`/`IE`. citeturn35view1turn35view2
- **No, you cannot buy only that subset at subset pricing**, because Betfair says **“All data is sold ‘as is’ and is only available for purchase via the packages provided.”** In practice, you buy the **Horse Racing** package month(s), then filter what you download. citeturn13view4turn13view6

## Licence mapping

The public official Betfair historical-data terms that surface from the historical-data portal are strong enough to establish the baseline rule set. The portal snippet states: **“Personal Use Only: All historical data is provided for personal, internal use only.”** A related snippet adds: **“It may not be used for any business purpose without a licence.”** Another states: **“No onward distribution: The resale or distribution to, or the use of the Historical Betfair Data by, another organization or individual is strictly prohibited.”** A further official developer page says that where data is required for **“testing, analysis, training or simulation modes,”** the delayed key or the **historical data services** must be used. citeturn39search0turn38search0turn37search0turn15view0

Betfair’s vendor licence PDF adds two important official definitions and restrictions that are relevant to commercial or published downstream use, even though it is a vendor-program document rather than the retail historical-data purchase page. It defines **“Historical Betfair Data”** as **“any data or service relating to a Betfair market after that market has been settled”**, and it prohibits providing access to **“Historical Betfair Data, Historical Betfair Data related products”** without a Historical Data License. That is the strongest official public evidence I found that Betfair treats post-settlement data-related downstream products as licensable, not automatically free to commercialize. citeturn16view0

### Use-by-use mapping

| Use case | What the official public sources support | Working conclusion |
|---|---|---|
| **Offline research** | Official Betfair product pages say the service is for **analysis**, **back test**, and experimenting with strategies; vendor product requirements say historical data services must be used for **testing** and **analysis** modes. citeturn1view4turn15view0 | **Yes, supported** for personal/internal research. |
| **Model training** | Vendor product requirements explicitly say that where data is required for **“training”**, the delayed key or **historical data services** must be used. citeturn15view0 | **Yes, supported** for personal/internal model training. |
| **Retention of raw purchased data** | I found no public historical-data term that expressly grants or limits local retention duration. Betfair does say previously purchased data can be re-downloaded from **My Data**. citeturn4search15turn13view7 | **Unresolved in public terms.** Practical re-download exists; explicit retention grant not found. |
| **Retention of models derived from the data** | No public clause expressly addresses internally retained derived models. The historical-data portal does, however, limit use to **personal/internal** use and says business use needs a licence. citeturn39search0turn38search0 | **Internally likely compatible**, but **not expressly stated**. Commercial exploitation remains licence-sensitive. |
| **Processing on cloud / third-party CI infrastructure** | I found no public historical-data purchase term directly addressing cloud processing. The vendor licence bans bureau/timeshare/outsourcing use of the **API**, but that is not clearly the same thing as private processing of purchased offline files. citeturn16view1 | **Unresolved.** Needs direct Betfair clarification before using third-party hosted pipelines. |
| **Publication or redistribution of derived probabilities / odds** | Official portal terms say **personal/internal use only**, **no business purpose without a licence**, and **no onward distribution** of Historical Betfair Data. Vendor licence also restricts providing **Historical Betfair Data related products** without a Historical Data License. None of the public sources I found cleanly state whether **purely derived** probabilities, with no raw data exposed, are treated as “Historical Betfair Data related products.” citeturn39search0turn38search0turn37search0turn16view0 | **Not clearly permitted from public sources.** Conservative reading: obtain commercial / historical-data licence clearance first. |
| **Commercial use of derived outputs** | Official portal term: the data **“may not be used for any business purpose without a licence.”** Vendor materials show Betfair operates separate commercial licensing paths. citeturn38search0turn8search0 | **No, not under the personal/internal purchase posture alone.** Commercial licence appears required. |

## Minimum tier recommendations for Gate 1 and Gate 2

For **Gate 1**, the cheapest tier that **genuinely** supports the stated need is **ADVANCED**. The evidence is straightforward. Gate 1 asks for **pre-off market prices** at **fixed horizons** like **T-10m** and **T-2m**, plus reconciled BSP for grading. ADVANCED gives you **1-second** rolled-up snapshots, **best-3 quoted back and lay prices** via `batb`/`batl`, traded-price deltas via `trd`, `ltp`, market/runner trading totals, and the all-plan BSP/BSP-reconciled fields. BASIC only gives `ltp` and market-definition changes, at **1-minute intervals**, and Betfair explicitly says BASIC `ltp` is **only sent when it changes**. That means BASIC does **not** provide a dependable quoted pre-off market state at a defined horizon; it only gives a sparse last-trade trace. citeturn3view3turn14view0turn3view2turn13view2

What ADVANCED still lacks for Gate 1 is **full depth** and **tick-by-tick** all-offers history, but Gate 1 does not require that. What BASIC provably lacks is far more important: there is **no quote ladder at all**, no best back/lay levels, no traded-price ladder deltas, and no guarantee that `ltp` is present at the exact decision horizon. So the minimum-tier recommendation for Gate 1 is **ADVANCED**, not BASIC. citeturn3view3turn3view2turn13view2

For **Gate 2**, the cheapest tier that genuinely supports the stated need is **PRO**. Your Gate 2 requirement expressly says **“requires order-book depth and traded-volume evolution over time, not just last-traded prices.”** ADVANCED gives only **best 3** back/lay levels and is **rolled up to 1-second intervals**. PRO gives **`EX_ALL_OFFERS`** with **all ladder levels** in `atb`/`atl`, **tick-by-tick** updates, `trd` traded-price evolution, and projected and traded SP fields. That is the first tier whose official schema matches the stated need for **latency-adjusted, size-aware executable-price scenario analysis**. citeturn3view3turn3view2turn13view1

What PRO still provably lacks is the separate **runner-total traded-volume field** that ADVANCED has; Betfair’s PRO FAQ says PRO does not contain the **total cumulative traded volume per runner**, only the cumulative traded volume **at each price point**. But that does not undermine the Gate 2 recommendation, because the decisive requirement in your question is **full depth over time**, and only PRO provides that. citeturn13view1

## Unresolved points and dated citation list

The main unresolved issues are legal, not technical. I could not establish from public permitted sources whether the standard historical-data purchase alone permits **private cloud / third-party CI processing**, or whether **purely derived probabilities/odds** may be **published or sold** without extra commercial clearance. The public sources clearly say **personal/internal use only**, **no business purpose without a licence**, and **no onward distribution** of Historical Betfair Data, but they do not publicly draw a sharp line around every possible derived-output scenario. citeturn39search0turn38search0turn37search0turn16view0

A smaller unresolved point is pricing nuance for very old months. The official historical-data homepage snippet says **“All data from May 2015 – April 2016 is free to purchase,”** but because the full JS-rendered price page is not inspectable in the same clean way as the support FAQ pages, I have treated that as a special-case note rather than building it into the standard 12/24/36-month cost estimates above. citeturn10search0

### Dated citation list

- **Tier 1 — official Betfair historical-data portal**, crawled **2026-07-16**: current horse-racing pricing row showing **Basic / Advanced / Pro = free / £69 / £230**. citeturn33search0
- **Tier 1 — official Betfair historical-data portal**, crawled **2026-07-16**: public historical-data terms snippets including **personal/internal use only**, **commercial licence**, **no business purpose without a licence**, and **no onward distribution**. citeturn39search0turn38search0turn37search0turn40search0turn25search0
- **Tier 1 — Betfair Developer Support FAQ**, updated **2026-06-15**: bulk pricing for ADVANCED and PRO by sport, including **Horse Racing £69 / £699 / £230 / £2,299**. citeturn1view3
- **Tier 1 — Betfair Developer Support FAQ**, updated **2026-06-15**: historical data delivered via file download; filters by **Sport, Date range, EventId, Event Name, Market Type, Country, File Type**. citeturn13view3
- **Tier 1 — Betfair Developer Support FAQ**, updated **2026-06-15**: Historical Data API example showing **`WIN`**, **`GB`**, **`IE`**, month-based purchased items, and filterable requests. citeturn35view0turn35view1turn35view2
- **Tier 1 — Betfair Developer Support FAQ**, updated **2026-06-15**: BASIC `ltp` only sent when it changes. citeturn13view2
- **Tier 1 — Betfair Developer Support FAQ**, updated **2026-06-15**: ADVANCED `batb/batl` tuples are **levels 0–2**. citeturn14view0turn14view3
- **Tier 1 — Betfair Developer Support FAQ**, updated **2026-06-15**: PRO `atb/atl` absolute by price, `0` deletes, `trd` cumulative by price point, and no total cumulative traded volume per runner. citeturn13view1
- **Tier 1 — Betfair Developer Support FAQ**, updated **2026-06-15**: all data available **5 days after event settlement**; purchased mid-month data can be re-downloaded from My Data. citeturn13view7
- **Tier 1 — Betfair Developer Support FAQ**, updated **2026-06-15**: **“All data is sold ‘as is’ and is only available for purchase via the packages provided.”** citeturn13view4
- **Tier 1 — Betfair Developer Program vendor product requirements**, current page crawled **2026-07-16**: for **testing, analysis, training or simulation modes**, use delayed data or **historical data services**. citeturn15view0
- **Tier 1 — official Betfair vendor licence PDF hosted on developer.betfair.com**, crawled **2026-07-16**: definition of **Historical Betfair Data** and restriction on providing **Historical Betfair Data / related products** without Historical Data License. citeturn16view0
- **Tier 3 — official downloadable Betfair Historical Data Feed Specification PDF**, crawled **2026-07-16**: all-plan fields, plan-specific fields, and frequency/subscription-equivalence tables. citeturn1view0turn2view0turn3view2turn3view3

---

## Assessment (agent, 2026-07-16)

### Validation against the request

All five DR-0001 questions are answered and the acceptance criteria are substantially
met: tier-by-tier factual table, prices dated 2026-07-16, filtering answered precisely
(download-filtering yes, subset-pricing no), licence conclusions quoting operative
language, per-gate minimum-tier recommendations with what each tier provably lacks, and
an explicit unresolved section. One criterion is only partially met: the Gate-2 depth
answer rests on the feed specification's subscription-equivalence table rather than
sample-file inspection — acceptable evidence, but since the citation markers resolve
only in the founder's ChatGPT session, the founder should spot-check the two decisive
pages (the feed-spec equivalence table and the pricing FAQ) before any money moves.

### Classification

**Facts (repository-local, independently verified in this session):**

- Our frozen `specs/prices/info-price-v1.yaml` defines p_market_info as the implied-
  probability midpoint of BEST back and BEST lay — level 0 of `batb`/`batl` suffices.
  ADVANCED therefore covers Gate 1's price definition exactly as frozen; BASIC cannot
  compute it at all (no quoted prices). This independently confirms the report's
  Gate-1 conclusion.
- Our frozen `specs/prices/exec-price-v1.yaml` (taker-v1) sets the worst acceptable
  price to the decision-time BEST-BACK tick with zero adverse slippage and requires
  the full stake within that band — it consumes best-back price AND size, both present
  in ADVANCED (level-0 tuple carries volume). See inference 1 for the Gate-2
  consequence.

**Source claims (credible, tier-1 cited, pending founder spot-check):** tier contents
and cadences (BASIC 1-min LTP-only and sparse; ADVANCED 1s best-3 + traded deltas +
totals; PRO tick-by-tick all-ladder + SP fields); prices (£0 / £69 / £230 monthly;
£699 / £2,299 annual per sport); download filtering by country/market-type but
packages-only purchasing; data available 5 days after settlement; re-download via My
Data; licence: personal/internal use only, no business purpose without a licence, no
onward distribution; May-2015–Apr-2016 possibly free (low-confidence snippet, correctly
excluded from the estimates).

**Inferences (the assessor's, not the report's):**

1. **Gate 2 may be satisfiable on ADVANCED under our frozen execution policy.** The
   report answered the request as phrased (full depth ⇒ PRO). But taker-v1
   (exec-price-v1, pre-registered) never rests an order and never accepts a worse tick
   than decision-time best back, so its executable-price scenarios need best-back
   price+size evolution — which ADVANCED carries at 1-second cadence. The limits are
   real and must be DECLARED in the Gate-2 pre-registered scenario set rather than
   discovered: 1s roll-up hides sub-second book changes (latency scenarios coarser
   than reality), and adverse-size scenarios beyond levels 0–2 are unobservable. PRO
   remains genuinely necessary for Phase-5 fill modelling (SPEC-040–043 queue/depth
   envelopes) and any passive execution — both unauthorised.
2. **The cloud/CI unresolved point bites this repository immediately:** CI runs on
   GitHub-hosted runners. Under SPEC-044's fail-closed posture, `cloud_processing` and
   `third_party_ci_processing` cannot be marked permitted for a Betfair historical
   source until Betfair clarifies in writing — until then the plan must assume raw
   purchased data is processed locally only and never enters CI fixtures.
3. **The founder's individual/personal-use status (recorded above) fits the licence's
   permitted core exactly** — personal, internal research and model training by one
   individual, no distribution. Two boundaries remain even for an individual: (a) the
   future analytics/predictor product (Gate P1) would be a "business purpose" and
   needs a commercial licence — already how SPEC-044/046 treat it (publication
   ineligible, gate blocked); (b) private automated betting with models trained on
   this data is not expressly addressed in the public terms — likely within personal
   use, but worth including in the written questions to Betfair.
4. Derived-output publication being licence-sensitive changes nothing operationally
   today: publication is already forbidden until Gate P1 and would fail SPEC-044
   closed for this source regardless.

**Recommendations (decision menu — research authorises nothing):**

- **Option A (recommended):** ADVANCED, 12 months of Horse Racing, GB+IE WIN download
  filter — £699 (annual discount; £828 straight monthly). Fully covers Gate 1 as
  frozen; covers Gate 2 under taker-v1 IF the scenario set pre-registers the 1s/best-3
  limits explicitly. PRO deferred until Phase 5 is ever authorised.
- **Option B:** PRO, 12 months — £2,299 (~3.3× A). Covers everything including future
  fill modelling; buys depth data the current phase cannot yet use.
- **Option C:** A now, plus a short PRO window (2–3 months, £460–£690) later, only if
  Gate 1 passes and the declared-limits Gate-2 scenarios prove insufficient.
- **Before ANY purchase:** (a) founder sends Betfair developer support two written
  questions — is private cloud/third-party-CI processing of purchased files permitted
  for a personal-use buyer, and is private automated betting using models trained on
  the data within personal use; (b) founder spot-checks the equivalence table and
  pricing FAQ; (c) decide test-correction-0001 so the source enters the registry with
  `reviewed_at`/`recheck_by` discipline from day one.
- All options are NEW spend above the £499 live-key reserve (SPEC-103): explicit
  budget authorisation required.

**Unresolved (carried forward in the ledger):** cloud/CI processing rights;
derived-output publication status; raw-data retention terms; private automated betting
under personal use; the free-2015/16 window; sub-second resolution of non-`pt`
timestamp fields.

### Impact on repository artifacts

- `docs/licensed-sources.yaml`: NO entry yet — blocked on the founder's Betfair
  written clarifications and the budget decision.
- `EXP-0001-draft`: window fields become draftable against month-granular purchases
  once a tier is chosen; the 5-days-post-settlement availability lag bounds the
  lockbox end date; the Gate-2 scenario-limit declarations (if Option A) belong in
  the pre-registration text, before observation.
- Gate −1B payback arithmetic gains real `c_fixed` candidates: £699 / £2,299 alongside
  the £499 live-key fee.
- No spec, manifest, or code change is required by these findings.
