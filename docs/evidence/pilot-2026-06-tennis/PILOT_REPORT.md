# Betfair Tennis June-2026 Market-Feasibility Pilot — Report

*Generated deterministically from hashed artefacts. Market-feasibility measurement only: no winners, settlement, P&L, betting returns, profitable subsets, selection rules, CLV, or model performance were computed or inspected. No live key, real order, or real-money activity (ADR 0015). Prices are canonical integer tick indices (price_contracts.ladder, SPEC-053); sizes are integer minor units.*

## 1. Corpus and manifest identities

| Artefact | Value |
|---|---|
| Purchased corpus | 20,482 files, immutable; re-checked against SHA256SUMS.txt (all pass) |
| Corpus SHA256SUMS digest | `d6d2f44b318aea425f3904ac83b8eb4a4bd067b7fe777c0375f107519162f9cc` |
| Canonical unique-market count | **16,981** (16,955 standalone + 26 combined-only) |
| MATCH_ODDS analytical markets | 3,521 |
| Packaging-audit digest | `b8d3470e9d3f86da0e5e1a884cd629eb13e43ccdee613f6c291d699508876564` |
| Universe-manifest digest | `ce9a147e64df0db5865dade4d78f0ae02cb93532c2f81518e9da313115029049` |
| Canonical replay manifest digest | `be2ae21a938fdc0ba2b4a9dfb21f6d4c8dcde699fab2f245383f19ed844bc617` |
| Reconstruction (replay) output digest | `3c1b64ab8d5c08f1bc654d690ac593ecb34dc073eb099f3d9abc7d4486a5d793` |

Frozen cohorts (universe manifest): primary singles **2,876**, strict sibling-corroborated sensitivity **2,287**, doubles descriptive **613**; excluded out-of-window 32, unknown-format 0.

## 2. Deterministic replay result

The reconstruction is a pure function of each market's canonical file bytes and the governed horizon protocol. Two independent full runs of all 3,489 markets produced **byte-identical** output (`3c1b64ab8d5c08f1bc654d690ac593ecb34dc073eb099f3d9abc7d4486a5d793`); per-market re-runs are identical. Errors: **0**. This satisfies the SPEC-010/011 reducer-determinism / bit-exact-replay discipline for the measurement pipeline.

## 3. Horizon completeness (as-of-published-marketTime state machine)

Primary protocol per the founder's governed correction: at each publish time `t`, using only the marketTime known at `t`, an **immutable** horizon instance is minted when `remaining = marketTime − t` crosses from `> H` to `<= H` while OPEN and pre-match; a later schedule revision that lifts remaining back above `H` re-arms the horizon and a subsequent crossing mints a new, lineage-linked instance. Instances are never rewritten or retrospectively selected. `first inPlay` is used only post-hoc for timing description.

### Primary singles (2,876) — total 2,876, never observed in-play 124

| Horizon | ≥1 instance | exactly 1 | multiple (reschedule) | no instance | first-instance min before in-play (p10/med/p90) |
|---|--:|--:|--:|--:|--:|
| T-30m | 2,646 | 2,252 | 394 | 230 | 37.72 / 73.397 / 182.508 |
| T-10m | 2,367 | 1,110 | 1,257 | 509 | 17.693 / 57.75 / 159.848 |
| T-5m | 2,353 | 1,228 | 1,125 | 523 | 9.591 / 31.594 / 149.222 |
| T-2m | 2,386 | 1,074 | 1,312 | 490 | 7.836 / 26.033 / 136.762 |
| T-60s | 2,385 | 1,079 | 1,306 | 491 | 7.071 / 25.107 / 135.741 |

*No-instance reasons at T-5m:* HORIZON_NEVER_REACHED_PRE_MATCH=497, CROSSING_DURING_PRE_MATCH_SUSPENSION=15, FIRST_OPEN_STATE_ALREADY_WITHIN_H=11.

### Strict sensitivity (2,287) — total 2,287, never observed in-play 118

| Horizon | ≥1 instance | exactly 1 | multiple (reschedule) | no instance | first-instance min before in-play (p10/med/p90) |
|---|--:|--:|--:|--:|--:|
| T-30m | 2,076 | 1,740 | 336 | 211 | 37.62 / 75.277 / 193.222 |
| T-10m | 2,010 | 817 | 1,193 | 277 | 18.207 / 57.639 / 161.112 |
| T-5m | 1,856 | 1,095 | 761 | 431 | 9.3 / 26.892 / 154.88 |
| T-2m | 1,831 | 958 | 873 | 456 | 7.477 / 21.478 / 143.088 |
| T-60s | 1,818 | 949 | 869 | 469 | 6.556 / 20.303 / 142.088 |

*No-instance reasons at T-5m:* HORIZON_NEVER_REACHED_PRE_MATCH=410, CROSSING_DURING_PRE_MATCH_SUSPENSION=13, FIRST_OPEN_STATE_ALREADY_WITHIN_H=8.

### Doubles (613) — total 613, never observed in-play 78

| Horizon | ≥1 instance | exactly 1 | multiple (reschedule) | no instance | first-instance min before in-play (p10/med/p90) |
|---|--:|--:|--:|--:|--:|
| T-30m | 530 | 414 | 116 | 83 | 38.9 / 70.747 / 200.827 |
| T-10m | 542 | 225 | 317 | 71 | 18.53 / 45.971 / 157.303 |
| T-5m | 508 | 313 | 195 | 105 | 8.456 / 17.746 / 149.38 |
| T-2m | 484 | 256 | 228 | 129 | 7.605 / 15.288 / 149.303 |
| T-60s | 473 | 250 | 223 | 140 | 6.733 / 14.288 / 154.183 |

*No-instance reasons at T-5m:* HORIZON_NEVER_REACHED_PRE_MATCH=98, FIRST_OPEN_STATE_ALREADY_WITHIN_H=3, CROSSING_DURING_PRE_MATCH_SUSPENSION=4.

## 4–6. Spread, depth & matched-volume distributions (first-instance)

*Primary per (market, horizon) = FIRST live-knowable crossing. FINAL-instance figures are reported in §9 as a labelled comparison; neither is selected for being preferable.*

### Primary singles (2,876)

| Horizon | markets w/ state | complete 2-sided | one-sided | crossed | spread ticks (med/p90) | spread bp (med/p90) | best-back £ (p10/med) | cum back £ (med) | matched/sel £ (med/p90) |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| T-30m | 2,646 | 2,620 | 26 | 13 | 3.0 / 17.0 | 136.366 / 568.182 | 2.0 / 38.88 | 229.47 | 339.35 / 5044.77 |
| T-10m | 2,367 | 2,344 | 23 | 7 | 3.0 / 14.0 | 132.275 / 495.495 | 2.04 / 55.46 | 267.12 | 469.59 / 6258.96 |
| T-5m | 2,353 | 2,336 | 17 | 4 | 3.0 / 15.0 | 138.244 / 530.303 | 2.69 / 56.94 | 255.4 | 501.92 / 6768.53 |
| T-2m | 2,386 | 2,366 | 20 | 7 | 3.0 / 15.0 | 134.953 / 525.716 | 3.17 / 57.87 | 260.4 | 518.0 / 7084.19 |
| T-60s | 2,385 | 2,365 | 20 | 7 | 3.0 / 15.0 | 135.227 / 529.412 | 3.22 / 60.52 | 253.75 | 513.62 / 7030.12 |

### Strict sensitivity (2,287)

| Horizon | markets w/ state | complete 2-sided | one-sided | crossed | spread ticks (med/p90) | spread bp (med/p90) | best-back £ (p10/med) | cum back £ (med) | matched/sel £ (med/p90) |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| T-30m | 2,076 | 2,060 | 16 | 7 | 3.0 / 9.0 | 106.293 / 336.7 | 2.19 / 56.62 | 309.86 | 624.04 / 6667.16 |
| T-10m | 2,010 | 1,995 | 15 | 3 | 3.0 / 9.0 | 113.619 / 334.411 | 3.0 / 66.82 | 310.54 | 695.08 / 7837.35 |
| T-5m | 1,856 | 1,843 | 13 | 2 | 3.0 / 9.0 | 110.873 / 317.604 | 3.58 / 76.08 | 325.46 | 840.26 / 8921.13 |
| T-2m | 1,831 | 1,820 | 11 | 2 | 3.0 / 9.0 | 106.838 / 318.979 | 4.0 / 77.15 | 332.51 | 916.41 / 9521.77 |
| T-60s | 1,818 | 1,806 | 12 | 2 | 3.0 / 9.0 | 106.564 / 315.126 | 4.0 / 79.47 | 328.76 | 922.57 / 9502.88 |

### Doubles (613)

| Horizon | markets w/ state | complete 2-sided | one-sided | crossed | spread ticks (med/p90) | spread bp (med/p90) | best-back £ (p10/med) | cum back £ (med) | matched/sel £ (med/p90) |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| T-30m | 530 | 517 | 13 | 2 | 29.0 / 220.0 | 1047.056 / 4989.899 | 1.58 / 8.19 | 171.54 | 2.25 / 498.0 |
| T-10m | 542 | 525 | 17 | 1 | 23.0 / 224.0 | 845.166 / 4706.88 | 1.54 / 12.97 | 167.24 | 12.76 / 585.71 |
| T-5m | 508 | 489 | 19 | 1 | 21.0 / 237.0 | 798.991 / 5015.025 | 1.67 / 13.63 | 141.07 | 30.01 / 633.19 |
| T-2m | 484 | 466 | 18 | 1 | 21.0 / 237.0 | 778.388 / 5008.333 | 1.6 / 16.11 | 146.27 | 37.65 / 661.64 |
| T-60s | 473 | 457 | 16 | 1 | 21.0 / 236.0 | 779.874 / 5008.333 | 1.54 / 15.62 | 129.79 | 35.25 / 613.87 |

## 5b. Fixed-stake executable-capacity (displayed liquidity; not a claim of actual fill)

Backing either selection; % over (market, selection) back-book opportunities at the first-instance snapshot. `within 3 levels` = the three delivered ladder levels.

### Primary singles — T-5m first-instance

| Stake | fill @ best | within 1 tick | within 3 levels | non-fill (3 levels) | VWAP odds med (where fillable) |
|---|--:|--:|--:|--:|--:|
| £2 | 96.2% | 98.3% | 99.9% | 0.1% | 1.93 |
| £10 | 72.6% | 84.4% | 98.3% | 1.7% | 1.91 |
| £25 | 63.0% | 77.1% | 93.6% | 6.4% | 1.86 |
| £50 | 52.5% | 68.4% | 85.9% | 14.1% | 1.82 |
| £100 | 35.0% | 53.8% | 75.2% | 24.8% | 1.747 |

### Strict sensitivity — T-5m first-instance

| Stake | fill @ best | within 1 tick | within 3 levels | non-fill (3 levels) | VWAP odds med (where fillable) |
|---|--:|--:|--:|--:|--:|
| £2 | 97.0% | 98.9% | 100.0% | 0.0% | 1.95 |
| £10 | 79.5% | 90.8% | 99.0% | 1.0% | 1.93 |
| £25 | 72.3% | 86.6% | 96.2% | 3.8% | 1.89 |
| £50 | 61.2% | 78.6% | 91.4% | 8.6% | 1.86 |
| £100 | 40.7% | 62.3% | 83.3% | 16.7% | 1.8 |

### Doubles — T-5m first-instance

| Stake | fill @ best | within 1 tick | within 3 levels | non-fill (3 levels) | VWAP odds med (where fillable) |
|---|--:|--:|--:|--:|--:|
| £2 | 88.0% | 91.1% | 100.0% | 0.0% | 1.76 |
| £10 | 55.0% | 68.1% | 96.2% | 3.8% | 1.707 |
| £25 | 39.0% | 54.6% | 90.0% | 10.0% | 1.66 |
| £50 | 34.0% | 47.0% | 77.3% | 22.7% | 1.607 |
| £100 | 25.9% | 37.2% | 61.1% | 38.9% | 1.55 |

## 7. Start and suspension analysis

| Metric | Primary singles | Doubles |
|---|--:|--:|
| Total markets | 2,876 | 613 |
| Never observed in-play | 124 | 78 |
| Delayed starts (vs final scheduled) | 2,274 | 486 |
| Early starts (vs final scheduled) | 125 | 32 |
| Off − final scheduled mt, min (med/p90) | 5.681 / 17.671 | 6.662 / 14.789 |
| Off − EARLIEST mt, min (med/p90) [sensitivity] | 104.97 / 1552.983 | 299.094 / 3390.916 |
| Schedule revisions/market (med/p90) | 6.0 / 18.0 | 7.0 / 23.0 |
| Markets with ≥1 pre-in-play suspension | 880 | 105 |
| Pre-in-play suspension duration s (med/p90) | 6.013 / 7.015 | 10.035 / 13.03 |
| Off-ladder price-event markets | 0 | 0 |

**Headline:** the earliest marketTime is a session/order-of-play placeholder (off is a median ~105 min later for singles); even the *final* published marketTime under-predicts the off by a median ~6 min (p90 ~18 min). Tennis starts are overwhelmingly **late and repeatedly rescheduled** (median 6 revisions/market) — the concrete, measured form of conceptual-audit F-01.

## 8. Closing-benchmark candidate feasibility (no benchmark selected)

Feasibility only — no candidate is selected or activated (`sport_core.benchmarks.selected_benchmark()` still refuses). Window = final 60 s of valid pre-in-play states before first observed in-play; in-play messages are structurally excluded.

| Candidate | Primary singles avail % | Doubles avail % |
|---|--:|--:|
| 1. Final valid normalized midpoint | 99.5% | 98.1% |
| 2. Time-weighted midpoint (60 s) | 96.7% | 46.9% |
| 3. Normalized microprice (60 s) | 96.7% | 46.9% |
| 4. Traded-volume-weighted price (60 s) | 40.4% | 6.7% |
| 5. Last traded price (secondary) | 99.2% | 89.7% |

Primary singles: final-60 s window available 97.2% of in-play markets (median 9.0 observations); 7.5% of windows overlap a suspension. Doubles window available only 47.5% (median 2.0 observations).

*Field sufficiency:* ADVANCED files carry best back/lay price+size (`batb`/`batl`), traded ladder (`trd`), total matched (`tv`), last traded (`ltp`) and suspension markers — sufficient to construct candidates 1, 2, 3 and 5 honestly and with in-play exclusion. Candidate 4 (traded WAP) is only ~40% constructible for singles / ~7% for doubles because matched volume frequently does not grow in the final 60 s. No BSP/`sp*` field was read (tennis has no Starting-Price mechanism; SPEC-021 taint discipline preserved).

## 9. Primary-vs-strict sensitivity comparison

| Metric (T-5m first-instance) | Primary singles | Strict sensitivity | First vs FINAL-instance (primary) |
|---|--:|--:|--:|
| Complete two-sided books | 2,336/2,353 | 1,843/1,856 | 2,343/2,353 |
| Spread ticks (median) | 3.0 | 3.0 | 3.0 |
| Best-back £ (median) | 56.94 | 76.08 | 61.25 |
| Matched/sel £ (median) | 501.92 | 840.26 | 663.51 |
| £50 fill @ best | 52.5% | 61.2% | 54.2% |
| £100 non-fill (3 levels) | 24.8% | 16.7% | 23.6% |

**Material, directional difference (kept, not discarded):** the 589 primary-only singles (SINGLES resolved from their own MATCH_ODDS runners but without sibling markets) are systematically **thinner and wider** than the sibling-corroborated strict cohort — median best-back roughly £57 vs £76, matched roughly £502 vs £840, £50 fill-at-best ~53% vs ~61%. Sibling-market presence is a proxy for event tier/liquidity. This is reported as a market-tier / classification-evidence covariate, not a reason to drop primary-only markets.

## 10. Doubles descriptive appendix

Doubles (613) are far thinner: median spread **21.0 ticks** (vs 3 for singles), median best-back £13.63, median matched £30.01/selection; 78/613 never observed in-play; final-60 s benchmark window available only 47.5%. Doubles are unsuitable as a trading-feasibility candidate and are retained for description only.

## 11. Data-quality defects

- **Clean price data:** 0 reconstruction errors, 0 off-ladder price events across all 3,489 markets; crossed/structurally-invalid books are negligible (≤8 markets per horizon).
- **Schedule instability is the dominant regime feature** (not a parse defect): non-monotone marketTime revisions, median 6/market, off late even vs the final schedule. It forces the multi-instance horizon behaviour and means fixed-clock horizons are only meaningful through the as-of state machine.
- **Never-in-play in captured stream:** 124 singles / 78 doubles have no observed in-play transition (no benchmark window, no off). Reported as a data fact; cause not inferred (would be outcome-adjacent).
- **Horizon-construction edge cases:** small numbers of `CROSSING_DURING_PRE_MATCH_SUSPENSION` and `FIRST_OPEN_STATE_ALREADY_WITHIN_H` misses per horizon, recorded with explicit reasons.
- **First-crossing ≠ near-off at short horizons:** because of reschedules, the *first* T-60s crossing is a median ~25 min before the real off; the state machine exposes this rather than hiding it.

## 12. Proposed initial market universe

Adopt the frozen **2,876 primary June singles MATCH_ODDS** universe as the feasibility universe, carrying **classification-evidence tier (strict vs primary-only)** forward as a liquidity covariate rather than excluding the thinner primary-only markets. Exclude **doubles** from any trading-feasibility universe (descriptive only). MATCH_ODDS remains the sole analytical market unit; other market kinds stay metadata-only corroboration.

## 13. Proposed decision horizon

Liquidity is roughly **horizon-invariant** from T-30m to T-60s (median spread ~3 ticks and median best-back depth ~£57–70 at every horizon), so there is little liquidity to be gained by acting closer to the off — while short horizons suffer the worst schedule churn. Recommendation: operate at a **moderate horizon (T-10m to T-5m) via the as-of state machine**, taking the first live-knowable crossing, where completeness is high (~2.35k/2.88k markets carry a clean two-sided instance) and the final-minute suspension/reschedule churn is avoided. The **operational policy** governing reschedules (act on first crossing vs invalidate-and-refresh vs a stability condition) is a separate governed decision, to be frozen from the revision-behaviour evidence above and **not** from profitability/outcomes; the data favour invalidate-and-refresh with a short post-revision stability window, because the first crossing is frequently far from the true off.

## 14. Whether another historical month is needed

**Not required to conclude the June-2026 feasibility picture.** One month gives clean, zero-error data and large singles samples (2,752 in-play markets); the market-quality, capacity, start/suspension and benchmark-feasibility questions are answered with stable distributions. A second month is warranted **only** to close one specific measured gap, not to add volume.

## 15. The specific evidence gap a second month would close

June 2026 is a **single tennis regime** — the grass-court run-up to Wimbledon. Every measured property (liquidity tier split, ~3-tick spreads, £50/£100 capacity cliffs, 6-revision schedule instability, ~+6 min late starts, 40% traded-WAP constructibility) could be grass-season / tournament-tier specific. The single gap a second month would close is **cross-regime stability**: does the T-5m completeness, spread, fixed-stake capacity, schedule-revision and benchmark-availability profile **replicate on a different surface / tournament tier** (e.g. a hard-court or clay month, or a month containing a Grand Slam main draw)? A second month is justified iff cross-regime stability is decision-relevant now; it would be pre-registered to test replication of those exact metrics, and — per ADR 0015 — never to enlarge the sample for its own sake, and never chosen on profitability or outcomes.

---
*Discipline attestation: no winners, settlement, P&L, returns, profitable subsets, selection rules, CLV, or model performance were computed or inspected at any point. The raw 20,482-file corpus is unmodified (re-verified against SHA256SUMS.txt). Classifier, dedup policy, and primary universe manifest were frozen and hashed before any price was opened.*
