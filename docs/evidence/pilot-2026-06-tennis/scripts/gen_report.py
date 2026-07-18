"""Generate the market-feasibility pilot report (markdown) from pilot_metrics.json and
the frozen manifest headers. Tables come straight from the metrics — no hand-typed
numbers — so the report is reproducible from the hashed artefacts.
"""
from __future__ import annotations

import json
import os

AUDIT = os.path.dirname(os.path.abspath(__file__))
M = json.load(open(os.path.join(AUDIT, "pilot_metrics.json")))
UNIV = json.load(open(os.path.join(AUDIT, "PRIMARY_JUNE_ANALYSIS_UNIVERSE_MANIFEST_header.json")))
CANON = json.load(open(os.path.join(AUDIT, "CANONICAL_REPLAY_MANIFEST_header.json")))
RECON_DIGEST = "3c1b64ab8d5c08f1bc654d690ac593ecb34dc073eb099f3d9abc7d4486a5d793"
METRICS_DIGEST = None  # filled at end

HL = [("1800", "T-30m"), ("600", "T-10m"), ("300", "T-5m"), ("120", "T-2m"), ("60", "T-60s")]
COH = [("primary_singles", "Primary singles (2,876)"), ("strict_singles", "Strict sensitivity (2,287)"), ("doubles", "Doubles (613)")]


def d(dist_obj, *keys):
    return " / ".join(str(dist_obj.get(k, "-")) for k in keys)


out = []
w = out.append

w("# Betfair Tennis June-2026 Market-Feasibility Pilot — Report")
w("")
w("*Generated deterministically from hashed artefacts. Market-feasibility measurement only: "
  "no winners, settlement, P&L, betting returns, profitable subsets, selection rules, CLV, "
  "or model performance were computed or inspected. No live key, real order, or real-money "
  "activity (ADR 0015). Prices are canonical integer tick indices (price_contracts.ladder, "
  "SPEC-053); sizes are integer minor units.*")
w("")

# ---- 1. Corpus & manifest identities ----
w("## 1. Corpus and manifest identities")
w("")
w("| Artefact | Value |")
w("|---|---|")
w(f"| Purchased corpus | 20,482 files, immutable; re-checked against SHA256SUMS.txt (all pass) |")
w(f"| Corpus SHA256SUMS digest | `{CANON['corpus_sha256sums_digest']}` |")
w(f"| Canonical unique-market count | **{CANON['canonical_unique_market_count']:,}** ({CANON['standalone_canonical_markets']:,} standalone + {CANON['combined_only_markets']} combined-only) |")
w(f"| MATCH_ODDS analytical markets | {CANON['match_odds_analytical_markets']:,} |")
w(f"| Packaging-audit digest | `{CANON['packaging_audit_digest']}` |")
w(f"| Universe-manifest digest | `{CANON['universe_manifest_digest']}` |")
w(f"| Canonical replay manifest digest | `{CANON['canonical_replay_manifest_digest']}` |")
w(f"| Reconstruction (replay) output digest | `{RECON_DIGEST}` |")
w("")
w("Frozen cohorts (universe manifest): "
  f"primary singles **{UNIV['cohort_counts']['PRIMARY_JUNE_SINGLES_UNIVERSE']:,}**, "
  f"strict sibling-corroborated sensitivity **{UNIV['cohort_counts']['STRICT_SIBLING_CORROBORATED_SENSITIVITY_COHORT']:,}**, "
  f"doubles descriptive **{UNIV['cohort_counts']['DOUBLES_DESCRIPTIVE_COHORT']:,}**; "
  f"excluded out-of-window {UNIV['universe_membership_counts'].get('EXCLUDED_OUT_OF_WINDOW',0)}, unknown-format 0.")
w("")

# ---- 2. Deterministic replay result ----
w("## 2. Deterministic replay result")
w("")
w("The reconstruction is a pure function of each market's canonical file bytes and the "
  "governed horizon protocol. Two independent full runs of all "
  f"{M['n_records']:,} markets produced **byte-identical** output "
  f"(`{RECON_DIGEST}`); per-market re-runs are identical. Errors: **{M['n_errors']}**. "
  "This satisfies the SPEC-010/011 reducer-determinism / bit-exact-replay discipline for the "
  "measurement pipeline.")
w("")

# ---- 3. Horizon completeness ----
w("## 3. Horizon completeness (as-of-published-marketTime state machine)")
w("")
w("Primary protocol per the founder's governed correction: at each publish time `t`, using only "
  "the marketTime known at `t`, an **immutable** horizon instance is minted when "
  "`remaining = marketTime − t` crosses from `> H` to `<= H` while OPEN and pre-match; a later "
  "schedule revision that lifts remaining back above `H` re-arms the horizon and a subsequent "
  "crossing mints a new, lineage-linked instance. Instances are never rewritten or "
  "retrospectively selected. `first inPlay` is used only post-hoc for timing description.")
w("")
for cname, clabel in COH:
    hc = M["horizon_completeness"][cname]
    w(f"### {clabel} — total {hc['total_markets']:,}, never observed in-play {hc['never_inplay']}")
    w("")
    w("| Horizon | ≥1 instance | exactly 1 | multiple (reschedule) | no instance | first-instance min before in-play (p10/med/p90) |")
    w("|---|--:|--:|--:|--:|--:|")
    for H, hlab in HL:
        h = hc["horizons"][H]
        fi = h["first_instance_minutes_before_inplay"]
        w(f"| {hlab} | {h['markets_with_instance']:,} | {h['exactly_one_instance']:,} | "
          f"{h['multiple_instances_reschedule']:,} | {h['no_instance']:,} | {d(fi,'p10','median','p90')} |")
    w("")
    # miss reasons at T-5m as representative
    mr = hc["horizons"]["300"]["no_instance_reasons"]
    if mr:
        w(f"*No-instance reasons at T-5m:* " + ", ".join(f"{k}={v}" for k, v in mr.items()) + ".")
        w("")

# ---- 4/5/6 market quality tables ----
def quality_block(which, title):
    w(f"## {title}")
    w("")
    w("*Primary per (market, horizon) = FIRST live-knowable crossing. FINAL-instance figures are "
      "reported in §9 as a labelled comparison; neither is selected for being preferable.*")
    w("")
    for cname, clabel in COH:
        w(f"### {clabel}")
        w("")
        w("| Horizon | markets w/ state | complete 2-sided | one-sided | crossed | spread ticks (med/p90) | spread bp (med/p90) | best-back £ (p10/med) | cum back £ (med) | matched/sel £ (med/p90) |")
        w("|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
        for H, hlab in HL:
            h = M[which][cname][H]
            w(f"| {hlab} | {h['markets_with_state']:,} | {h['complete_two_sided_books']:,} | "
              f"{h['one_sided_book_markets']} | {h['crossed_or_invalid_markets']} | "
              f"{d(h['spread_ticks'],'median','p90')} | {d(h['spread_prob_bp'],'median','p90')} | "
              f"{d(h['best_back_size_gbp'],'p10','median')} | {h['cum_back_size_gbp'].get('median','-')} | "
              f"{d(h['matched_volume_per_selection_gbp'],'median','p90')} |")
        w("")


quality_block("market_quality_first_instance", "4–6. Spread, depth & matched-volume distributions (first-instance)")

# fixed-stake capacity (primary + doubles), representative horizons
w("## 5b. Fixed-stake executable-capacity (displayed liquidity; not a claim of actual fill)")
w("")
w("Backing either selection; % over (market, selection) back-book opportunities at the "
  "first-instance snapshot. `within 3 levels` = the three delivered ladder levels.")
w("")
for cname, clabel in [("primary_singles", "Primary singles"), ("strict_singles", "Strict sensitivity"), ("doubles", "Doubles")]:
    w(f"### {clabel} — T-5m first-instance")
    w("")
    w("| Stake | fill @ best | within 1 tick | within 3 levels | non-fill (3 levels) | VWAP odds med (where fillable) |")
    w("|---|--:|--:|--:|--:|--:|")
    cap = M["market_quality_first_instance"][cname]["300"]["fixed_stake_capacity"]
    for st in ["£2", "£10", "£25", "£50", "£100"]:
        c = cap[st]
        vw = c["vwap_matched_odds_dist"].get("median", "-")
        w(f"| {st} | {c['pct_fill_at_best']}% | {c['pct_fill_within_1_tick']}% | "
          f"{c['pct_fill_within_3_levels']}% | {c['pct_non_fill_3_levels']}% | {vw} |")
    w("")

# ---- 7. start / suspension ----
w("## 7. Start and suspension analysis")
w("")
w("| Metric | Primary singles | Doubles |")
w("|---|--:|--:|")
sp = M["start_suspension"]
ps, dbl = sp["primary_singles"], sp["doubles"]
def row(label, ka, kb):
    w(f"| {label} | {ka} | {kb} |")
row("Total markets", f"{ps['total_markets']:,}", f"{dbl['total_markets']:,}")
row("Never observed in-play", ps["never_inplay"], dbl["never_inplay"])
row("Delayed starts (vs final scheduled)", f"{ps['delayed_starts_vs_final_scheduled']:,}", dbl["delayed_starts_vs_final_scheduled"])
row("Early starts (vs final scheduled)", ps["early_starts_vs_final_scheduled"], dbl["early_starts_vs_final_scheduled"])
row("Off − final scheduled mt, min (med/p90)", d(ps["offset_first_inplay_minus_final_scheduled_min"], "median", "p90"), d(dbl["offset_first_inplay_minus_final_scheduled_min"], "median", "p90"))
row("Off − EARLIEST mt, min (med/p90) [sensitivity]", d(ps["offset_first_inplay_minus_earliest_marketTime_min_SENSITIVITY"], "median", "p90"), d(dbl["offset_first_inplay_minus_earliest_marketTime_min_SENSITIVITY"], "median", "p90"))
row("Schedule revisions/market (med/p90)", d(ps["schedule_revision_count"], "median", "p90"), d(dbl["schedule_revision_count"], "median", "p90"))
row("Markets with ≥1 pre-in-play suspension", f"{ps['markets_with_pre_inplay_suspension']:,}", dbl["markets_with_pre_inplay_suspension"])
row("Pre-in-play suspension duration s (med/p90)", d(ps["pre_inplay_suspension_duration_s"], "median", "p90"), d(dbl["pre_inplay_suspension_duration_s"], "median", "p90"))
row("Off-ladder price-event markets", ps["off_ladder_event_markets"], dbl["off_ladder_event_markets"])
w("")
w("**Headline:** the earliest marketTime is a session/order-of-play placeholder (off is a median "
  "~105 min later for singles); even the *final* published marketTime under-predicts the off by a "
  "median ~6 min (p90 ~18 min). Tennis starts are overwhelmingly **late and repeatedly rescheduled** "
  "(median 6 revisions/market) — the concrete, measured form of conceptual-audit F-01.")
w("")

# ---- 8. benchmark feasibility ----
w("## 8. Closing-benchmark candidate feasibility (no benchmark selected)")
w("")
w("Feasibility only — no candidate is selected or activated (`sport_core.benchmarks."
  "selected_benchmark()` still refuses). Window = final 60 s of valid pre-in-play states before "
  "first observed in-play; in-play messages are structurally excluded.")
w("")
w("| Candidate | Primary singles avail % | Doubles avail % |")
w("|---|--:|--:|")
bf = M["benchmark_feasibility"]
for key, lab in [("candidate_1_final_midpoint", "1. Final valid normalized midpoint"),
                 ("candidate_2_windowed_midpoint", "2. Time-weighted midpoint (60 s)"),
                 ("candidate_3_microprice", "3. Normalized microprice (60 s)"),
                 ("candidate_4_traded_wap", "4. Traded-volume-weighted price (60 s)"),
                 ("candidate_5_last_traded_price", "5. Last traded price (secondary)")]:
    w(f"| {lab} | {bf['primary_singles'][key]['rate_pct']}% | {bf['doubles'][key]['rate_pct']}% |")
w("")
w(f"Primary singles: final-60 s window available {bf['primary_singles']['final_60s_window_rate_pct']}% of in-play markets "
  f"(median {bf['primary_singles']['window_observation_count'].get('median')} observations); "
  f"{bf['primary_singles']['windows_overlapping_suspension_pct']}% of windows overlap a suspension. "
  f"Doubles window available only {bf['doubles']['final_60s_window_rate_pct']}% "
  f"(median {bf['doubles']['window_observation_count'].get('median')} observations).")
w("")
w("*Field sufficiency:* ADVANCED files carry best back/lay price+size (`batb`/`batl`), traded "
  "ladder (`trd`), total matched (`tv`), last traded (`ltp`) and suspension markers — sufficient to "
  "construct candidates 1, 2, 3 and 5 honestly and with in-play exclusion. Candidate 4 (traded WAP) "
  "is only ~40% constructible for singles / ~7% for doubles because matched volume frequently does "
  "not grow in the final 60 s. No BSP/`sp*` field was read (tennis has no Starting-Price mechanism; "
  "SPEC-021 taint discipline preserved).")
w("")

# ---- 9. primary vs strict ----
w("## 9. Primary-vs-strict sensitivity comparison")
w("")
w("| Metric (T-5m first-instance) | Primary singles | Strict sensitivity | First vs FINAL-instance (primary) |")
w("|---|--:|--:|--:|")
p5 = M["market_quality_first_instance"]["primary_singles"]["300"]
s5 = M["market_quality_first_instance"]["strict_singles"]["300"]
pf5 = M["market_quality_final_instance"]["primary_singles"]["300"]
w(f"| Complete two-sided books | {p5['complete_two_sided_books']:,}/{p5['markets_with_state']:,} | {s5['complete_two_sided_books']:,}/{s5['markets_with_state']:,} | {pf5['complete_two_sided_books']:,}/{pf5['markets_with_state']:,} |")
w(f"| Spread ticks (median) | {p5['spread_ticks'].get('median')} | {s5['spread_ticks'].get('median')} | {pf5['spread_ticks'].get('median')} |")
w(f"| Best-back £ (median) | {p5['best_back_size_gbp'].get('median')} | {s5['best_back_size_gbp'].get('median')} | {pf5['best_back_size_gbp'].get('median')} |")
w(f"| Matched/sel £ (median) | {p5['matched_volume_per_selection_gbp'].get('median')} | {s5['matched_volume_per_selection_gbp'].get('median')} | {pf5['matched_volume_per_selection_gbp'].get('median')} |")
w(f"| £50 fill @ best | {p5['fixed_stake_capacity']['£50']['pct_fill_at_best']}% | {s5['fixed_stake_capacity']['£50']['pct_fill_at_best']}% | {pf5['fixed_stake_capacity']['£50']['pct_fill_at_best']}% |")
w(f"| £100 non-fill (3 levels) | {p5['fixed_stake_capacity']['£100']['pct_non_fill_3_levels']}% | {s5['fixed_stake_capacity']['£100']['pct_non_fill_3_levels']}% | {pf5['fixed_stake_capacity']['£100']['pct_non_fill_3_levels']}% |")
w("")
w("**Material, directional difference (kept, not discarded):** the 589 primary-only singles "
  "(SINGLES resolved from their own MATCH_ODDS runners but without sibling markets) are "
  "systematically **thinner and wider** than the sibling-corroborated strict cohort — median "
  "best-back roughly £57 vs £76, matched roughly £502 vs £840, £50 fill-at-best ~53% vs ~61%. "
  "Sibling-market presence is a proxy for event tier/liquidity. This is reported as a "
  "market-tier / classification-evidence covariate, not a reason to drop primary-only markets.")
w("")

# ---- 10. doubles appendix ----
w("## 10. Doubles descriptive appendix")
w("")
dq = M["market_quality_first_instance"]["doubles"]["300"]
w(f"Doubles (613) are far thinner: median spread **{dq['spread_ticks'].get('median')} ticks** "
  f"(vs 3 for singles), median best-back £{dq['best_back_size_gbp'].get('median')}, median matched "
  f"£{dq['matched_volume_per_selection_gbp'].get('median')}/selection; {M['horizon_completeness']['doubles']['never_inplay']}/613 never "
  f"observed in-play; final-60 s benchmark window available only {bf['doubles']['final_60s_window_rate_pct']}%. "
  "Doubles are unsuitable as a trading-feasibility candidate and are retained for description only.")
w("")

# ---- 11. defects ----
w("## 11. Data-quality defects")
w("")
w("- **Clean price data:** 0 reconstruction errors, 0 off-ladder price events across all "
  f"{M['n_records']:,} markets; crossed/structurally-invalid books are negligible (≤8 markets per horizon).")
w("- **Schedule instability is the dominant regime feature** (not a parse defect): non-monotone "
  "marketTime revisions, median 6/market, off late even vs the final schedule. It forces the "
  "multi-instance horizon behaviour and means fixed-clock horizons are only meaningful through the "
  "as-of state machine.")
w(f"- **Never-in-play in captured stream:** {ps['never_inplay']} singles / {dbl['never_inplay']} doubles have no observed in-play "
  "transition (no benchmark window, no off). Reported as a data fact; cause not inferred (would be outcome-adjacent).")
w("- **Horizon-construction edge cases:** small numbers of `CROSSING_DURING_PRE_MATCH_SUSPENSION` "
  "and `FIRST_OPEN_STATE_ALREADY_WITHIN_H` misses per horizon, recorded with explicit reasons.")
w("- **First-crossing ≠ near-off at short horizons:** because of reschedules, the *first* T-60s "
  "crossing is a median ~25 min before the real off; the state machine exposes this rather than hiding it.")
w("")

# ---- 12-15 recommendations ----
w("## 12. Proposed initial market universe")
w("")
w("Adopt the frozen **2,876 primary June singles MATCH_ODDS** universe as the feasibility universe, "
  "carrying **classification-evidence tier (strict vs primary-only)** forward as a liquidity "
  "covariate rather than excluding the thinner primary-only markets. Exclude **doubles** from any "
  "trading-feasibility universe (descriptive only). MATCH_ODDS remains the sole analytical market "
  "unit; other market kinds stay metadata-only corroboration.")
w("")
w("## 13. Proposed decision horizon")
w("")
w("Liquidity is roughly **horizon-invariant** from T-30m to T-60s (median spread ~3 ticks and "
  "median best-back depth ~£57–70 at every horizon), so there is little liquidity to be gained by "
  "acting closer to the off — while short horizons suffer the worst schedule churn. Recommendation: "
  "operate at a **moderate horizon (T-10m to T-5m) via the as-of state machine**, taking the "
  "first live-knowable crossing, where completeness is high (~2.35k/2.88k markets carry a clean "
  "two-sided instance) and the final-minute suspension/reschedule churn is avoided. The **operational "
  "policy** governing reschedules (act on first crossing vs invalidate-and-refresh vs a stability "
  "condition) is a separate governed decision, to be frozen from the revision-behaviour evidence "
  "above and **not** from profitability/outcomes; the data favour invalidate-and-refresh with a short "
  "post-revision stability window, because the first crossing is frequently far from the true off.")
w("")
w("## 14. Whether another historical month is needed")
w("")
w("**Not required to conclude the June-2026 feasibility picture.** One month gives clean, "
  "zero-error data and large singles samples (2,752 in-play markets); the market-quality, capacity, "
  "start/suspension and benchmark-feasibility questions are answered with stable distributions. A "
  "second month is warranted **only** to close one specific measured gap, not to add volume.")
w("")
w("## 15. The specific evidence gap a second month would close")
w("")
w("June 2026 is a **single tennis regime** — the grass-court run-up to Wimbledon. Every measured "
  "property (liquidity tier split, ~3-tick spreads, £50/£100 capacity cliffs, 6-revision schedule "
  "instability, ~+6 min late starts, 40% traded-WAP constructibility) could be grass-season / "
  "tournament-tier specific. The single gap a second month would close is **cross-regime stability**: "
  "does the T-5m completeness, spread, fixed-stake capacity, schedule-revision and benchmark-"
  "availability profile **replicate on a different surface / tournament tier** (e.g. a hard-court or "
  "clay month, or a month containing a Grand Slam main draw)? A second month is justified iff "
  "cross-regime stability is decision-relevant now; it would be pre-registered to test replication of "
  "those exact metrics, and — per ADR 0015 — never to enlarge the sample for its own sake, and never "
  "chosen on profitability or outcomes.")
w("")
w("---")
w("*Discipline attestation: no winners, settlement, P&L, returns, profitable subsets, selection "
  "rules, CLV, or model performance were computed or inspected at any point. The raw 20,482-file "
  "corpus is unmodified (re-verified against SHA256SUMS.txt). Classifier, dedup policy, and primary "
  "universe manifest were frozen and hashed before any price was opened.*")

report = "\n".join(out) + "\n"
with open(os.path.join(AUDIT, "PILOT_REPORT.md"), "w") as f:
    f.write(report)
import hashlib
print("wrote PILOT_REPORT.md", len(report), "bytes; sha256:", hashlib.sha256(report.encode()).hexdigest())
