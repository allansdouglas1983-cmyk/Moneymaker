"""Aggregate raw reconstruction records into the founder's required pilot tables.

Reads audit/recon_full.jsonl (raw, integer ticks/minor-units, no outcomes) and emits
audit/pilot_metrics.json. Distributions are reported as count/median/p10/p25/p75/p90/p95/
min/max. Per (market, horizon) the PRIMARY instance is the FIRST live-knowable crossing;
the FINAL instance is reported as a labelled comparison. No instance is ever selected
because its prices/liquidity are preferable (founder rule 7).
"""
from __future__ import annotations

import json
import os
import sys
from decimal import Decimal

sys.path.insert(0, "/home/user/Moneymaker")
from price_contracts.ladder import price_of  # noqa: E402

AUDIT = os.path.dirname(os.path.abspath(__file__))
HORIZONS = ["1800", "600", "300", "120", "60"]
HLABEL = {"1800": "T-30m", "600": "T-10m", "300": "T-5m", "120": "T-2m", "60": "T-60s"}
STAKES_MINOR = [200, 1000, 2500, 5000, 10000]
STAKE_LABEL = {200: "£2", 1000: "£10", 2500: "£25", 5000: "£50", 10000: "£100"}
COHORTS = {
    "primary_singles": lambda r: r.get("cohort") == "PRIMARY_JUNE_SINGLES_UNIVERSE",
    "strict_singles": lambda r: r.get("cohort") == "PRIMARY_JUNE_SINGLES_UNIVERSE" and r.get("strict_sensitivity"),
    "doubles": lambda r: r.get("cohort") == "DOUBLES_DESCRIPTIVE_COHORT",
}


def dist(xs: list[float]) -> dict:
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return {"count": 0}

    def q(p):
        if len(xs) == 1:
            return xs[0]
        i = min(len(xs) - 1, int(round(p * (len(xs) - 1))))
        return xs[i]

    return {
        "count": len(xs),
        "min": round(xs[0], 3),
        "p10": round(q(0.10), 3),
        "p25": round(q(0.25), 3),
        "median": round(q(0.50), 3),
        "p75": round(q(0.75), 3),
        "p90": round(q(0.90), 3),
        "p95": round(q(0.95), 3),
        "max": round(xs[-1], 3),
    }


def back_capacity(levels: list, stake_minor: int) -> dict:
    """levels = [[tick, size_minor], ...] best-first (highest odds first)."""
    if not levels:
        return {"best": False, "one_tick": False, "three_levels": False, "worst_odds": None, "vwap_odds": None}
    best_tick = levels[0][0]
    best_size = sum(s for t, s in levels if t == best_tick)
    within1 = sum(s for t, s in levels if t >= best_tick - 1)
    top3 = levels[:3]
    within3 = sum(s for t, s in top3)
    remaining = stake_minor
    filled = 0
    cost = Decimal(0)
    worst = None
    for t, s in top3:
        take = min(remaining, s)
        if take <= 0:
            break
        cost += Decimal(take) * price_of(t)
        filled += take
        remaining -= take
        worst = t
        if remaining <= 0:
            break
    fillable = remaining <= 0
    return {
        "best": best_size >= stake_minor,
        "one_tick": within1 >= stake_minor,
        "three_levels": within3 >= stake_minor,
        "worst_odds": float(price_of(worst)) if (fillable and worst is not None) else None,
        "vwap_odds": float(cost / filled) if (fillable and filled) else None,
    }


def implied(tick: int) -> float:
    return float(Decimal(1) / price_of(tick))


def primary_instance(rec: dict, H: str):
    insts = rec["horizons"][H]["instances"]
    return insts[0] if insts else None


def final_instance(rec: dict, H: str):
    insts = rec["horizons"][H]["instances"]
    return insts[-1] if insts else None


def instance_selection_rows(inst: dict):
    """Yield per-selection dicts for an instance's quality block."""
    if not inst:
        return
    for sid, s in inst["selections"].items():
        yield sid, s


def horizon_completeness(recs: list) -> dict:
    out = {}
    for cname, pred in COHORTS.items():
        crecs = [r for r in recs if pred(r) and not r.get("error")]
        out[cname] = {"total_markets": len(crecs), "never_inplay": sum(1 for r in crecs if r["never_inplay"]), "horizons": {}}
        for H in HORIZONS:
            with_inst = [r for r in crecs if r["horizons"][H]["instance_count"] > 0]
            exactly_one = [r for r in crecs if r["horizons"][H]["instance_count"] == 1]
            multiple = [r for r in crecs if r["horizons"][H]["instance_count"] > 1]
            none = [r for r in crecs if r["horizons"][H]["instance_count"] == 0]
            miss = {}
            for r in none:
                for mr in r["horizons"][H]["miss_reasons"]:
                    miss[mr] = miss.get(mr, 0) + 1
            # time from FIRST instance crossing to first inplay (post-hoc timing description)
            first_to_inplay = [primary_instance(r, H)["seconds_to_first_inplay"] / 60.0 for r in with_inst if primary_instance(r, H)["seconds_to_first_inplay"] is not None]
            final_to_inplay = [final_instance(r, H)["seconds_to_first_inplay"] / 60.0 for r in with_inst if final_instance(r, H)["seconds_to_first_inplay"] is not None]
            revcount = [r["horizons"][H]["instance_count"] for r in with_inst]
            out[cname]["horizons"][H] = {
                "label": HLABEL[H],
                "markets_with_instance": len(with_inst),
                "exactly_one_instance": len(exactly_one),
                "multiple_instances_reschedule": len(multiple),
                "no_instance": len(none),
                "no_instance_reasons": miss,
                "instances_per_market": dist([float(x) for x in revcount]),
                "first_instance_minutes_before_inplay": dist(first_to_inplay),
                "final_instance_minutes_before_inplay": dist(final_to_inplay),
            }
    return out


def market_quality(recs: list, which="primary") -> dict:
    pick = primary_instance if which == "primary" else final_instance
    out = {}
    for cname, pred in COHORTS.items():
        crecs = [r for r in recs if pred(r) and not r.get("error")]
        out[cname] = {}
        for H in HORIZONS:
            insts = [(r, pick(r, H)) for r in crecs if pick(r, H)]
            n = len(insts)
            two_active = sum(1 for _, i in insts if i["two_active_selections"])
            both_sided = sum(1 for _, i in insts if i["both_sided"])
            one_sided = sum(1 for _, i in insts if i["one_sided_selections"] > 0)
            missing = sum(1 for _, i in insts if i["missing_book_selections"] > 0)
            crossed = sum(1 for _, i in insts if i["crossed_or_invalid"])
            # per-(market,selection) distributions over two-sided selection books
            spread_ticks, spread_bp, best_back_sz, best_lay_sz, cum_back, cum_lay, tv = ([] for _ in range(7))
            for _, i in insts:
                for sid, s in i["selections"].items():
                    if s["tv_minor"] is not None:
                        tv.append(s["tv_minor"] / 100.0)
                    if s["best_back_size_minor"] is not None:
                        best_back_sz.append(s["best_back_size_minor"] / 100.0)
                        cum_back.append(sum(sz for _, sz in s["back"]) / 100.0)
                    if s["best_lay_size_minor"] is not None:
                        best_lay_sz.append(s["best_lay_size_minor"] / 100.0)
                        cum_lay.append(sum(sz for _, sz in s["lay"]) / 100.0)
                    if s["spread_ticks"] is not None:
                        spread_ticks.append(float(s["spread_ticks"]))
                    if s["spread_prob_bp"] is not None:
                        spread_bp.append(float(s["spread_prob_bp"]))
            # capacity per stake over back books
            capacity = {}
            for stake in STAKES_MINOR:
                n_sel = 0
                nbest = none1 = n3 = nfill = 0
                worst_odds = []
                vwap_odds = []
                for _, i in insts:
                    for sid, s in i["selections"].items():
                        if not s["back"]:
                            continue
                        n_sel += 1
                        cap = back_capacity(s["back"], stake)
                        nbest += cap["best"]
                        none1 += cap["one_tick"]
                        n3 += cap["three_levels"]
                        if cap["three_levels"]:
                            nfill += 1
                            if cap["worst_odds"] is not None:
                                worst_odds.append(cap["worst_odds"])
                            if cap["vwap_odds"] is not None:
                                vwap_odds.append(cap["vwap_odds"])
                capacity[STAKE_LABEL[stake]] = {
                    "back_selection_opportunities": n_sel,
                    "pct_fill_at_best": round(100 * nbest / n_sel, 1) if n_sel else None,
                    "pct_fill_within_1_tick": round(100 * none1 / n_sel, 1) if n_sel else None,
                    "pct_fill_within_3_levels": round(100 * n3 / n_sel, 1) if n_sel else None,
                    "pct_non_fill_3_levels": round(100 * (n_sel - n3) / n_sel, 1) if n_sel else None,
                    "worst_matched_odds_dist": dist(worst_odds),
                    "vwap_matched_odds_dist": dist(vwap_odds),
                }
            out[cname][H] = {
                "markets_with_state": n,
                "two_active_selections": two_active,
                "complete_two_sided_books": both_sided,
                "one_sided_book_markets": one_sided,
                "missing_book_markets": missing,
                "crossed_or_invalid_markets": crossed,
                "spread_ticks": dist(spread_ticks),
                "spread_prob_bp": dist(spread_bp),
                "best_back_size_gbp": dist(best_back_sz),
                "best_lay_size_gbp": dist(best_lay_sz),
                "cum_back_size_gbp": dist(cum_back),
                "cum_lay_size_gbp": dist(cum_lay),
                "matched_volume_per_selection_gbp": dist(tv),
                "fixed_stake_capacity": capacity,
            }
    return out


def start_suspension(recs: list) -> dict:
    out = {}
    for cname, pred in COHORTS.items():
        crecs = [r for r in recs if pred(r) and not r.get("error")]
        inplay = [r for r in crecs if not r["never_inplay"]]
        # offset scheduled off (final pre-inplay marketTime) -> first inplay
        off_final = []
        off_earliest = []
        early = late = 0
        for r in inplay:
            if r["final_pre_inplay_marketTime_ms"] and r["first_inplay_pt"]:
                d = (r["first_inplay_pt"] - r["final_pre_inplay_marketTime_ms"]) / 60000.0
                off_final.append(d)
                if d < -0.5:
                    early += 1
                elif d > 0.5:
                    late += 1
            if r["earliest_marketTime_ms"] and r["first_inplay_pt"]:
                off_earliest.append((r["first_inplay_pt"] - r["earliest_marketTime_ms"]) / 60000.0)
        nsusp = [len(r["pre_inplay_suspensions"]) for r in crecs]
        durs = [s["duration_s"] for r in crecs for s in r["pre_inplay_suspensions"] if s["duration_s"] is not None]
        out[cname] = {
            "total_markets": len(crecs),
            "never_inplay": len(crecs) - len(inplay),
            "clean_last_pre_inplay_state": sum(1 for r in crecs if r["clean_last_pre_inplay_state"]),
            "early_starts_vs_final_scheduled": early,
            "delayed_starts_vs_final_scheduled": late,
            "offset_first_inplay_minus_final_scheduled_min": dist(off_final),
            "offset_first_inplay_minus_earliest_marketTime_min_SENSITIVITY": dist(off_earliest),
            "schedule_revision_count": dist([float(r["schedule_revision_count"]) for r in crecs]),
            "pre_inplay_suspension_count": dist([float(x) for x in nsusp]),
            "pre_inplay_suspension_duration_s": dist(durs),
            "markets_with_pre_inplay_suspension": sum(1 for r in crecs if r["pre_inplay_suspensions"]),
            "reopenings_before_inplay_total": sum(r["reopenings_before_inplay"] for r in crecs),
            "off_ladder_event_markets": sum(1 for r in crecs if r["off_ladder_events"] > 0),
        }
    return out


def benchmark_feasibility(recs: list) -> dict:
    out = {}
    for cname, pred in COHORTS.items():
        crecs = [r for r in recs if pred(r) and not r.get("error")]
        inplay = [r for r in crecs if not r["never_inplay"]]
        n = len(inplay)
        # candidate availability
        c1 = c2 = c3 = c4 = c5 = 0
        obs_counts = []
        window_overlaps_susp = 0
        avail_windows = 0
        mid_var = []  # numerical-stability proxy: variance of normalized mid across window
        for r in inplay:
            fs = r["final_pre_inplay_state"]
            bw = r["benchmark_window"]
            # candidate 1: final valid normalized midpoint (both selections two-sided at final state)
            if fs and _both_two_sided(fs):
                c1 += 1
            # candidate 5: LTP at final valid pre-inplay state
            if fs and _has_ltp(fs):
                c5 += 1
            if bw["available"]:
                avail_windows += 1
                obs_counts.append(bw["n_observations"])
                if bw["overlaps_suspension"]:
                    window_overlaps_susp += 1
                two_sided_obs = [o for o in bw["observations"] if _both_two_sided(o)]
                # candidate 2 (time-weighted mid) and 3 (microprice): need two-sided obs in window
                if two_sided_obs:
                    c2 += 1
                    if all(_has_both_sizes(o) for o in two_sided_obs[:1]) or any(_has_both_sizes(o) for o in two_sided_obs):
                        c3 += 1
                    mids = [_norm_mid(o) for o in two_sided_obs]
                    mids = [m for m in mids if m is not None]
                    if len(mids) >= 2:
                        mean = sum(mids) / len(mids)
                        mid_var.append(sum((m - mean) ** 2 for m in mids) / len(mids))
                # candidate 4 (WAP): constructible if matched volume grew within window
                if _tv_grew(bw["observations"]):
                    c4 += 1
        out[cname] = {
            "markets_in_play": n,
            "candidate_1_final_midpoint": {"available": c1, "rate_pct": round(100 * c1 / n, 1) if n else None},
            "candidate_2_windowed_midpoint": {"available": c2, "rate_pct": round(100 * c2 / n, 1) if n else None},
            "candidate_3_microprice": {"available": c3, "rate_pct": round(100 * c3 / n, 1) if n else None},
            "candidate_4_traded_wap": {"available": c4, "rate_pct": round(100 * c4 / n, 1) if n else None},
            "candidate_5_last_traded_price": {"available": c5, "rate_pct": round(100 * c5 / n, 1) if n else None},
            "final_60s_window_available": avail_windows,
            "final_60s_window_rate_pct": round(100 * avail_windows / n, 1) if n else None,
            "window_observation_count": dist([float(x) for x in obs_counts]),
            "windows_overlapping_suspension": window_overlaps_susp,
            "windows_overlapping_suspension_pct": round(100 * window_overlaps_susp / avail_windows, 1) if avail_windows else None,
            "normalized_mid_within_window_variance": dist([v * 1e6 for v in mid_var]),  # scaled prob^2 x1e6
        }
    return out


def _both_two_sided(state: dict) -> bool:
    sels = state["selections"]
    return len(sels) == 2 and all(s["back"] and s["lay"] for s in sels.values())


def _has_ltp(state: dict) -> bool:
    return any(s["ltp_tick"] is not None for s in state["selections"].values())


def _has_both_sizes(o: dict) -> bool:
    return all(s["best_back_size_minor"] and s["best_lay_size_minor"] for s in o["selections"].values())


def _norm_mid(o: dict):
    mids = []
    for s in o["selections"].values():
        if not s["back"] or not s["lay"]:
            return None
        bb = s["back"][0][0]
        bl = s["lay"][0][0]
        mids.append((implied(bb) + implied(bl)) / 2.0)
    tot = sum(mids)
    if tot <= 0:
        return None
    return mids[0] / tot  # normalized prob of first selection


def _tv_grew(observations: list) -> bool:
    if len(observations) < 2:
        return False
    first = observations[0]
    last = observations[-1]
    for sid in first["selections"]:
        a = first["selections"][sid]["tv_minor"] or 0
        b = last["selections"].get(sid, {}).get("tv_minor", 0) or 0
        if b > a:
            return True
    return False


def main() -> None:
    recs = [json.loads(l) for l in open(os.path.join(AUDIT, sys.argv[1] if len(sys.argv) > 1 else "recon_full.jsonl"))]
    errors = [r for r in recs if r.get("error")]
    metrics = {
        "n_records": len(recs),
        "n_errors": len(errors),
        "error_market_ids": [r["market_id"] for r in errors][:50],
        "horizon_completeness": horizon_completeness(recs),
        "market_quality_first_instance": market_quality(recs, "primary"),
        "market_quality_final_instance": market_quality(recs, "final"),
        "start_suspension": start_suspension(recs),
        "benchmark_feasibility": benchmark_feasibility(recs),
    }
    with open(os.path.join(AUDIT, "pilot_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2, default=str)
    print("wrote pilot_metrics.json; records=%d errors=%d" % (len(recs), len(errors)))


if __name__ == "__main__":
    main()
