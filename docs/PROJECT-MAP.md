# The project map — everything that exists, in one page hierarchy

**Purpose.** The companion to `docs/EVIDENCE-STATE.md`. That page says what is *proven*;
this one says what is *built*. A session that has not read both is building blind — it
will rebuild capabilities that exist, contradict decisions that were made, or miss open
items that were already found. Compiled 2026-07-30 from a four-agent sweep of the entire
repository; sources are the files themselves, which remain the authority.

**How to use it.** Before building anything, check §3 (capabilities — 58 of them) and §6
(open items). Before deciding anything, check §2 (binding obligations digest) and the ADR
index. Update this page when the structure changes, in the same commit.

---

## 1. What this repository is: TWO platforms sharing one repo

**A. The racing research platform** (repo root: `l0_raw/` … `l8_evidence/`,
`governance/`, `analytics_contracts/`, `assistant_v0/`, `xmarket_contracts/`).
Spec-driven (SPEC-001…115 in `docs/spec-manifest.yaml`), CI-gated (`make verify`,
`make mutants`, `make replay`), mutation-tested money modules, 21 ADRs. Layer status:
l0/l1/l3/l4/l5/l7-core/l8 **implemented and active**; l6 partially (orders/retry);
l2_state, l4b_fill, l5b_risk, replay are **README-only scaffolds** (planned phases —
documented, not a defect). Tennis settlement (SPEC-084) **refuses everything** via typed
error until a founder-approved policy matrix lands. `make build` is a deliberate
always-fail stub (Phase 0).

**B. The tennis-edge platform** (`tennis-edge/` + `supabase/` + `docs/index.html` +
`artifacts/`). The live system: a market-anchored ridge-logistic residual model (22
features over a de-vigged price logit, `residual-model-v3.json`) served through a
Supabase Edge Function to a GitHub Pages site, with a weekly self-refreshing state
pipeline and an append-only prediction ledger. 49 modules, 37 experiments, 13 tools,
~90 test files. `sport_tennis/coherence/` holds a complete, mutation-tested,
SYNTHETIC-ONLY cross-market solver (Match Odds + one Total Games line → latent serve
parameters) that is deliberately NOT wired to real prices (`BLOCKED_BY_MATH_SPEC`,
EXT-XMARKET-003) — the market-parsing half lives separately in root `xmarket_contracts/`.

The two trees VENDOR some packages under the same names (`sport_tennis`, `sport_core`,
`price_contracts`) with different contents. Do not conflate them.

## 2. The binding constraints, in one breath

Full list: the 40-item STANDING OBLIGATIONS digest in the ADR/rules sweep (and
`.claude/rules/`). The ones that shape day-to-day work: the three rules (no stubbed money
modules; no test edited alongside an implementation; no LLM-produced number in any money
path) · pre-off, back-only, one selection per market · no Kelly in v1; flat stake + hard
loss budget; ADR 0020 real-stake protocol is founder-manual only and nothing in the repo
ever places/cancels/amends an order · directive 6 (no alternate account, ever) survives
everything · commission on net market result only · exact Decimal/integer money, never
float · universe frozen before outcomes; day-clustered inference; CLV never a training
target · `BET_CANDIDATE` structurally unreachable; `recommendation` pinned NOT_EVALUATED
· racing behaviour byte-identical under the sport-adapter transition · CODEOWNERS-owned
paths (workflows, specs, tests, money modules) are human-owned.

## 3. What already exists — do not rebuild

The full 58-item capabilities inventory is in the codebase sweep; the headline groups:

- **Data acquisition, immutably versioned**: Tennis-Data vintages (`refresh.py`),
  Sackmann via Software Heritage pinned snapshots (`archive.py`), 4GB Betfair tar
  streaming with complete member accounting (`betfair_archive.py`), Kaggle ITF.
- **Price handling**: five de-vig methods measured against each other (`devig.py`), the
  exact non-linear tick ladder with integer indices (`price_contracts/ladder.py`), three
  structurally distinct price types, frozen exchange price tables v1–v4 + mayjul with
  per-side fill evidence attached (`exchange_prices.py`).
- **Fill honesty**: trade-through falsification (SUPPORTED/UNSUPPORTED/NO_EVIDENCE,
  `fill_evidence.py`), Roll effective-spread estimation that refuses rather than
  zero-fills (`execution_cost.py`), the frozen display-band table (`display_band.py`).
- **Ratings & features**: Elo/surface/weighted (`ratings.py`), the 1.69M-match
  Challenger/ITF pyramid (`pyramid.py`), Barnett–Clarke point→match Markov model
  (`point_model.py`), opponent-adjusted serve/return with shrinkage (`serve_stats.py`,
  `serve_detail.py`), durability/H2H/workload (`durability.py`), network features
  (`network.py`), one shared cached residual feature builder (`residual_features.py`,
  `feature_cache.py`, FEATURE_SET_VERSION=residual-v4) with a static price-token
  leakage guard.
- **Models**: the deployable Newton-fitted residual model (`residual_model.py`, L2=25),
  stage-two α/β combination (`combine.py`), the frozen policies v1/v2.
- **Measurement**: log score/Brier/calibration/day-clustered bootstrap/deflated Sharpe
  (`metrics.py`), append-only ledgers with commit-hash lineage (`ledger.py`,
  `forecast_ledger.py`), idempotent weekly loop (`weekly.py`), self-grading scorecard.
- **Staking study apparatus** (new, 2026-07-30): integer-pence replay engine with
  day-open sizing and skip-not-round-up (`staking/engine.py`), the parameterised firing
  rule (`staking/selection.py`), the opportunity-set loader (`staking/sequence.py`), the
  exporter and the selection sweep (`tools/export_bet_sequence.py`,
  `tools/sweep_selection.py`). STK-HARNESS-V1 (`staking/harness.py`): stress haircuts,
  paired stationary-bootstrap draws, absorbing ruin states, and `reserve_day` — the §1.6
  day-reservation semantics as ONE shared pure function (replay and any future serving
  path consume the same implementation). The rule catalogue (`staking/rules.py`)
  includes `conservative_kelly` as a measured object only — withdrawn as policy by
  ADR 0020 Amendment 3; the open follow-up is pre-registering E2 CVAR-LP-EV +
  D19 JOINT-HARA under B5 HB-CAP with founder-declared (α, β).
- **Coherence mathematics** (synthetic-only): DP scoring engine validated against an
  independent oracle, 2-D root solver with canonical dedup and discretisation-stability
  contracts, holdout projection (`sport_tennis/coherence/*`).
- **Cross-language guarantee**: 500 golden vectors hold the TypeScript serving port to
  the Python reference at 1e-12 (`tools/emit_golden_vectors.py`, `scoring.test.ts`).

## 4. The live system and its automation

Site: GitHub Pages (`docs/index.html`, "RESEARCH / SHADOW ONLY" banner) → Supabase Edge
Function `tips` (v15, byte-verified against the repo). Routes: open `/health`,
self-throttled open `/board-refresh` (6h) and `/book-capture` (20min); owner-only board,
`/ledger`, `/scorecard`, `/clv`, `POST /price|/bet|/budget`. Auth = live Supabase session
+ allowlist of one email. `recordBet` refuses without a pre-set loss budget and when the
budget is exhausted (ADR 0020).

Automation (all UTC): Tuesday 06:00 GitHub Actions weekly refresh (corpus → grade last
week BEFORE rebuild → rebuild state → re-emit golden vectors → commit artifacts → verify
served digest). DB-side pg_cron: `pull_state` Tue 06:00, `pull_results` 07:30 (grades
both ledgers), `pull_forecasts` 07:45, `board-refresh` pokes 06:15/12:15/18:15 daily,
`tennis-book-capture` every 30min — armed, failing on `CERT_AUTH_REQUIRED` until the
founder registers the client certificate (the one manual step; capture self-starts after
it). Deploys of the function are gated on the golden vectors passing.

Data at rest (this container): `/home/user/tennis_edge_data/` — 15GB Betfair BASIC
archives + price tables, Sackmann, Tennis-Data vintages, feature caches, bet-sequence
exports. `artifacts/` (repo root): `residual-model-v3.json` (SERVED), `residual-model.json`
(stale v1 — a known trap: `weekly.py`'s default still points at it), `live-state.json`,
`forecasts.json`, `results.json`.

## 5. The graveyard — tested and killed, do not resurrect without new evidence

Network/intransitivity layer (harmful, TE-0016) · GBM/neural/GNN model classes
(DR-FORECAST-LIT + TE-0007) · Wikipedia/crowd-attention buzz (collapsed under one-row
correction) · cross-market arbitrage locks (5,799 covers, zero locks, TE-0010) · the
coherence layer as a pricing feature (TE-0030: −0.0015, died; solver survives as
synthetic math only) · cross-market derivative prices as an independent signal
(NO_GO_UNPROVEN_INFORMATION_ORIGIN, permanent) · Challenger/ITF tier at reachable data
(TE-0001) · bookmaker venues as money (restrict winners; Pinnacle unreachable since
2014) · surface Elo for DP1 (F3 FAIL_HARM, permanent) · martingale in every form ·
Kelly-family staking while the costed reading is unresolved (DR-STAKING-003/004/005) ·
anchor temperature (TE-0028 FAIL) · round/tier stratification (TE-0039 NULL under
selection-adjusted bar).

## 6. Open items that matter (the working list)

The full 19-item list with sources is in the findings sweep; the load-bearing ones:

1. **Register the Betfair certificate** (founder, minutes) — unlocks 30-min order-book
   depth capture, the only route to a real fill/execution answer (TE-0037 #1).
2. **The post-2023 regime question** — three independent diagnostics; TE-0033 exonerated
   composition with precision; what weakened is the exchange price's lead over Bet365.
   The one open scientific question (TE-0031).
3. **2022–2026 BASIC tail provenance** — `data2.tar` was not the tail; the v4 table's
   2023–2026 coverage came from founder-supplied archives; any future tail data must
   arrive the same way (TE-0018).
4. **Commission verification against a settled statement** (SPEC-081) — 2% Basic is
   founder-confirmed in the UI, still `ASSUMPTION` (TE-0044).
5. **Retirement target-mismatch** — training and settlement both drop retirements while
   Betfair settles them; ~3.6% of bets invisible; money half gated on SPEC-084
   (TE-0041 #16).
6. **Execution-cost measurement upgrade** — replace the Roll proxy with directly measured
   LTP-to-crossable gaps once captured books exist; prior estimate moves the band to
   roughly [+0.8%, +1.8%] (TE-0041 #8), which would settle TE-0020's open caveat.
7. **Display band double-charges the crossing spread** (TE-0041 #9) and lacks odds-band
   stratification (#12).
8. **CLV accumulation** — 4–8 weeks of live observations before touching anything else
   (TE-0037 #2); the capture cadence upgrade depends on item 1.
9. ~~Stationarity~~ — CLOSED by TE-0045 (pre-registered): recency weighting never beats
   the equal-weighted fit and aggressive forgetting demonstrably harms; the anomaly is
   localised to the anchor relationship, which only live-data accumulation resolves.
10. **Staking study** (this session, tasks #87/#88): research workflow → verified
    candidate set → head-to-head over the real 89,998-row sequence under the
    pre-registered protocol.

## 7. Where to read more

- Evidence: `docs/EVIDENCE-STATE.md` → the TE documents it cites.
- Decisions: `docs/decisions/` (ADR 0001–0020; 0015 superseded by 0020, directive 6
  survives; 0016 superseded by 0017).
- Rules that bind edits: `CLAUDE.md`, `.claude/rules/*.md`, `docs/CI-AND-TRUST.md`.
- Operations: `docs/OPERATING.md`, `docs/OPERATING-betfair-capture.md`,
  `supabase/schema/objects.md`.
- Research ledger: `docs/research/ledger.yaml` + `docs/research/findings/`.
- Programme history: `docs/TE-0017` (the programme), `docs/TE-0031` (its closure),
  `docs/PROGRESS.md` (racing platform; stale after mid-Stage-2E — trust ADRs beyond it).
