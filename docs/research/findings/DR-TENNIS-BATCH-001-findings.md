# DR-TENNIS batch findings — Priorities 1–7 (2026-07-16)

**Returned:** 2026-07-16, via Claude Code's own deep-research workflow (founder's
explicit `/deep-research` invocation, not the ChatGPT handoff). 104 agents, ~6.0M
subagent tokens, 22 sources fetched, 76 claims extracted, 25 verified (15 confirmed,
10 refuted), 0 unverified-and-reported.

**Filing note — read before anything else:** the harness decomposed the founder's
seven distinct priorities into only **five** generic search angles (data licensing,
provider technical coverage, Betfair market/settlement, feature literature, CLV
literature). Two priorities (data licensing, feature/CLV literature) got real
coverage. **Four priorities got essentially nothing**: 002A, SETTLEMENT-001,
BENCHMARK-001, and FITNESS-001 produced no surviving verified claims at all. This
is reported honestly as a coverage failure of this research pass, not as evidence
those questions have no answer — they remain open and need dedicated, narrower
follow-up passes (one priority per call), not another single mega-request.

---

## DR-TENNIS-DATA-002 — lawful data procurement (Priority 1)

**Status:** UNRESOLVED on the decisive question; partial provider facts established.

**Facts (source claims, primary-page-fetched, high confidence):**
- **API-Tennis**: ToS disclaim provider responsibility for customer use, but contain
  no clause on betting/wagering/model-training, permitted or prohibited. [api-tennis.com/terms-of-use]
- **Goalserve**: subscription only ($150/mo, $1,200/yr annual), no one-off historical
  package, no licensing language anywhere on the pricing page. [goalserve.com]
- **Sportradar**: 7-tier coverage system confirmed verbatim — Tier 1 (Slams) and
  Tier 2 (ATP incl. Challenger) get full Round-1 point-by-point + corrections; Tier 6
  (WTA International/250/125k) only gets point-by-point from the semis onward — a
  real ATP/WTA coverage asymmetry. Historical depth capped: ~3 seasons of
  competition data, match stats/timelines purged after 3 months, only competitor
  bio data reaches back to 2007. [developer.sportradar.com, 3 pages]

**The critical unresolved fact, flagged for your direct attention:** Sportradar's
terms (found second-hand, NOT independently fetched from the primary ToS/Free-Trial
document — treat as a strong lead, not a confirmed fact) reportedly **bar use of its
data/outputs for "any prediction market, trading platform, financial product or
similar offering" without prior written consent**. If accurate, this is an explicit
prohibition, not silence — the opposite of what you need. Requires direct written
confirmation from Sportradar before any further consideration.

**No provider — none — has a publicly visible explicit grant of rights for private
profit-seeking betting-model training.** This was true across every page reached.
Per your own framing of the request, silence is not permission; only a signed
contract settles this.

**Refuted / unreliable:** Enetpulse's "full ATP/WTA point-by-point" coverage claim
was refuted (0-3) — the page actually only advertises live scores/results/rankings,
not the depth Priority 1 needs. **Tennis Data Innovations, Stats Perform (WTA), and
Tennis-Data.co.uk — three of the seven named priority targets — produced zero
surviving findings.** Tennis-Data.co.uk's terms page and a related "Tennis Results"
terms page were fetched but yielded no usable claims (marked unreliable source
quality, 0 claims each) despite a promising early search snippet suggesting personal-
use-only licensing language existed there — worth a direct re-fetch.

**Recommendation:** treat this priority as still open. Direct written outreach to
Sportradar (confirm/deny the prediction-market prohibition) and to Tennis Data
Innovations / Stats Perform / Tennis-Data.co.uk (none were reached) is the actual
next step — not further web search.

---

## DR-TENNIS-MARKET-002A — Betfair tennis market desk research (Priority 2A)

**Status:** Essentially UNRESOLVED. No official Betfair tennis package/market facts,
no external liquidity estimates, and no settlement rules were established for the
Exchange product this project actually needs.

**What was found instead (misattributed under this search angle):** the research
correctly identified that Betfair publishes **two separate tennis rules pages** — a
Sportsbook (fixed-odds) rules page and a separate "Exchange - Tennis Rules" page —
and that **the Sportsbook page is the wrong product** for this project (back-only,
pre-match Exchange Match Odds). The Sportsbook page itself returned HTTP 403 on
direct fetch (bot-blocked); specific claims about its retirement/walkover treatment
were explicitly REFUTED (0-3 votes) after being checked. **The correct Exchange
rules page was never successfully reached at all.**

**No external liquidity/opportunity estimates surfaced.** Per your own labelling
requirement, this means there is currently nothing to even label SECONDARY — the
desk-research half of Priority 2 is not done, not merely inconclusive.

**Recommendation:** re-run as its own narrow research call: fetch
`support.betfair.com/.../exchange-tennis-rules/` directly (not via search snippet),
and separately search for published liquidity/volume commentary on Betfair tennis
exchange markets specifically. Do not treat this batch as having answered 002A.

---

## DR-TENNIS-MODEL-002 — feature value beyond the market (Priority 3)

**Status:** Partial evidence on one feature family (serve-strength/Elo); most of the
requested feature list (surface transitions, rest days, workload, travel, altitude,
indoor/outdoor, age trajectory, qualifying-vs-main-draw, intransitivity, fitness
proxies) was **not covered** — no surviving claims for any of them.

**Confirmed:** Gollub (2021), *Journal of Sports Analytics* — Elo-informed serve-
forecasting methods (Efron-Morris shrinkage, opponent/schedule-adjusted ratings,
Klaassen-Magnus Elo-synthesis) outperform the classical Barnett-Clarke baseline serve
model on a real 7,622-match ATP dataset (2014–2016): 69.7% vs 64.6% accuracy for the
best Elo-synthesis variant. Elo used as a serve-strength *input*, not a standalone
match predictor. Peer-reviewed, but the dataset is a decade old — directional
support only, not current state-of-the-art.

**Refuted (worth knowing what did NOT hold up):** a claim that betting-odds
benchmarks plateau prediction accuracy near 70.4% regardless of method was refuted
(0-3); a claim that Logistic Regression/ADTree ML models beat Elo by ~2-2.3% on a
2005–2020 ATP dataset was refuted (0-3); a claim about gender-asymmetric Elo
performance (standard Elo better for WTA, surface Elo better for ATP) was refuted
(1-2). None of these should be treated as established.

**Recommendation:** the serve/Elo angle has genuine literature support and is a
reasonable starting feature family. Everything else on your feature list is
genuinely unresearched, not merely unsupported — needs its own pass.

---

## DR-TENNIS-SETTLEMENT-001 — withdrawal/walkover/retirement matrix (Priority 4)

**Status:** UNRESOLVED. Blocking. The deterministic settlement matrix cannot be
built from this research — the only Betfair page reached is the Sportsbook
product's rules page, not the Exchange page, and even Sportsbook-specific claims
about retirement/walkover were refuted rather than confirmed. **Zero rows of the
requested matrix are established.**

**Recommendation:** this must be re-run as its own dedicated, narrow research call
(or a direct fetch attempt against the Exchange-specific URL, bypassing search
snippets) before any tennis settlement code is designed. Per the founder's own
directive elsewhere in this project, this must be settled before creating the
tennis outcome table — it is not settled yet.

---

## DR-TENNIS-BENCHMARK-001 — tennis closing-line definition (Priority 5)

**Status:** UNRESOLVED. No surviving claims at all — the primary closing benchmark,
WAP/microprice window, suspension/delayed-start treatment, and staleness rules for
tennis remain completely open. Needs a dedicated follow-up pass; nothing here should
be read as "BSP works the same as racing" or any other assumption — the question is
simply unanswered.

---

## DR-TENNIS-FITNESS-001 — lawful injury/fitness signals (Priority 6)

**Status:** UNRESOLVED. No surviving claims. As specified, this was framed as a
research track rather than a v1 requirement — remains exactly that: untouched,
deferred, no action needed now.

---

## DR-TENNIS-CLV-001 — closing-line value and profitability evidence (Priority 7)

**Status:** Partial, and the confirmed finding is a caution, not encouragement.

**Confirmed:** Lyócsa & Výrost (2018), *Applied Economics* — tested 40 tennis
betting rules; individual (uncorrected) tests showed some rules with positive
returns, but this evidence **mostly disappeared once data-snooping/multiple-testing
correction was applied**, leading the authors to conclude tennis betting markets are
more efficient than earlier uncorrected studies suggested. This is bookmaker-market
literature from 2018 — **not exchange-specific, not Betfair-specific, not CLV-metric
specific** — but it is directly relevant as a caution against trusting any single
promising backtest, which is exactly the caution CLAUDE.md already embeds
("treat every surprisingly good backtest as a suspected bug").

**Refuted:** a Grand-Slam-only study (Vaughan Williams et al., 5 events, 2018–2020,
bookmaker-not-exchange odds) had two of its methodological claims refuted on
verification — its finding that bookmaker odds outperformed both ML and Elo models
should not be relied on as stated.

**Gap found but not chased:** two additional sources were fetched with claims
extracted (a favourite-longshot-bias-in-tennis-exchanges paper, and a Brazilian
journal article) but neither survived to the verified/reported findings — the
raw material exists (visible in the source list) but wasn't synthesized. A cheap,
targeted follow-up re-reading just those two URLs could close this gap without
another full multi-agent pass.

**Recommendation:** treat "does beating the tennis close predict profit" as still
essentially open, exchange-specific evidence-wise, per the research brief's own
expectation that peer-reviewed evidence would be thin here. It was.

---

## Overall impact assessment

- **Nothing here authorises a purchase, a licensed-sources entry, or any ADR 0016
  code change.** Per protocol, research informs decisions; it never proves a gate.
- **DR-TENNIS-DATA-002's core question is UNRESOLVED and now carries a specific red
  flag** (the Sportradar prohibition lead) requiring direct written follow-up before
  any tennis fundamental-data relationship is pursued — mirrors the racing project's
  own DR-0002 experience (no priced, rights-clear source found by web research
  alone).
- **DR-TENNIS-SETTLEMENT-001 remains a hard blocker** for any tennis outcome-table
  design — explicitly required to be settled first, and it isn't.
- **Recommendation on process, not just content:** future DR batches this broad
  should be split into one research call per priority, or at most two-to-three
  closely related priorities per call — this run's five-angle decomposition of
  seven priorities is the direct cause of the four blank priorities above.
