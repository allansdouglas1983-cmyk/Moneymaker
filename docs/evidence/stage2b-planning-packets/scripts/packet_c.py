"""Packet C — reschedule dwell W evaluation. OUTCOME-BLIND (founder direction 2026-07-18).

Uses ONLY Stage-1 market/timing metadata: marketTime revisions (pt, value), status
transitions (OPEN/SUSPENDED; extraction stopped at first CLOSED), first inPlay pt.
Actual first-inPlay is used ONLY as a post-hoc lead diagnostic, never as a trigger.

PREDECLARED policy semantics per candidate (W = dwell seconds, L = max nominal lead
minutes): the system decides at the FIRST time t such that
  (a) remaining(t) = marketTime_as_known_at_t - t is in [0, L];
  (b) no marketTime revision occurred in (t - W, t]  (schedule quiet for >= W);
  (c) market status at t is OPEN and t precedes first observed inPlay;
choosing within each revision epoch the earliest t = max(epoch_start + W, M - L,
end_of_suspension_if_needed). A revision before the dwell completes re-arms the pending
decision (counted). If no epoch yields a valid t, the market is an ABSTENTION.

Reported per (W, L): decision availability, abstention rate, subsequent-revision rate
(a revision AFTER the committed decision), re-arm counts, post-hoc lead to first inPlay
(minutes; in-play markets only), primary vs strict cohort split.
"""
from __future__ import annotations

import json
import statistics

META = "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/audit/full_corpus_metadata.jsonl"
MANIFEST = "docs/evidence/pilot-2026-06-tennis/PRIMARY_JUNE_ANALYSIS_UNIVERSE_MANIFEST.csv"
DWELLS_S = [15, 30, 60, 120, 300]
LEADS_MIN = [5, 10, 15]


def parse_mt_ms(mt: str | None) -> int | None:
    if not mt:
        return None
    from datetime import datetime, timezone

    return int(datetime.fromisoformat(mt.replace("Z", "+00:00")).astimezone(timezone.utc).timestamp() * 1000)


def load_universe() -> dict[str, dict]:
    import csv

    out = {}
    for r in csv.DictReader(open(MANIFEST)):
        if r["universe_membership"] == "PRIMARY_JUNE_SINGLES_UNIVERSE":
            out[r["market_id"]] = {"strict": "STRICT" in r["cohort_tags"]}
    return out


def load_markets() -> list[dict]:
    uni = load_universe()
    rows = []
    with open(META) as f:
        for line in f:
            r = json.loads(line)
            mid = r["market_id"]
            if mid not in uni:
                continue
            epochs = [(r["earliest_market_time_pt"], parse_mt_ms(r["earliest_market_time"]))]
            for rev in r.get("market_time_revisions") or []:
                m = parse_mt_ms(rev.get("market_time"))
                if rev.get("pt") is not None and m is not None:
                    epochs.append((rev["pt"], m))
            epochs.sort()
            status = sorted((s["pt"], s["status"]) for s in r.get("status_transitions") or [])
            rows.append(
                {
                    "market_id": mid,
                    "strict": uni[mid]["strict"],
                    "epochs": epochs,
                    "status": status,
                    "fip": r.get("first_in_play_pt"),
                }
            )
    return rows


def status_at(status: list[tuple[int, str]], t: int) -> str | None:
    cur = None
    for pt, st in status:
        if pt <= t:
            cur = st
        else:
            break
    return cur


def next_open_at(status: list[tuple[int, str]], t: int) -> int | None:
    """Earliest time >= t at which status is OPEN (piecewise-constant model)."""
    if status_at(status, t) == "OPEN":
        return t
    for pt, st in status:
        if pt >= t and st == "OPEN":
            return pt
    return None


def decide(m: dict, w_s: int, l_min: int) -> dict:
    w_ms, l_ms = w_s * 1000, l_min * 60000
    end_cap = m["fip"] if m["fip"] is not None else None
    epochs = m["epochs"]
    rearms = 0
    for i, (r_pt, mt_ms) in enumerate(epochs):
        epoch_end = epochs[i + 1][0] if i + 1 < len(epochs) else None
        hard_end_candidates = [e for e in (epoch_end, end_cap) if e is not None]
        hard_end = min(hard_end_candidates) if hard_end_candidates else None
        t = max(r_pt + w_ms, mt_ms - l_ms)
        t_open = next_open_at(m["status"], t)
        if t_open is not None:
            t = t_open
        else:
            t = None
        valid = (
            t is not None
            and (hard_end is None or t < hard_end)
            and 0 <= mt_ms - t <= l_ms
        )
        if valid:
            assert t is not None
            later_revision = any(pt > t for pt, _ in epochs[i + 1 :])
            return {
                "decided": True,
                "t": t,
                "rearms": rearms,
                "later_revision": later_revision,
                "lead_to_fip_min": (m["fip"] - t) / 60000.0 if m["fip"] is not None else None,
            }
        # dwell/lead never satisfied in this epoch before the next revision => re-arm
        if epoch_end is not None and (end_cap is None or epoch_end < end_cap):
            rearms += 1
            continue
        break
    return {"decided": False, "rearms": rearms, "later_revision": False, "lead_to_fip_min": None}


def dist(xs: list[float]) -> dict:
    xs = sorted(xs)
    if not xs:
        return {"n": 0}
    q = lambda p: xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))]  # noqa: E731
    return {"n": len(xs), "p10": round(q(0.1), 2), "median": round(q(0.5), 2), "p90": round(q(0.9), 2)}


def main() -> None:
    markets = load_markets()
    print(f"loaded {len(markets)} primary singles markets")
    out = []
    for w in DWELLS_S:
        for lmin in LEADS_MIN:
            res = [(m, decide(m, w, lmin)) for m in markets]
            for cohort, pred in (("primary", lambda m: True), ("strict", lambda m: m["strict"])):
                sub = [(m, d) for m, d in res if pred(m)]
                n = len(sub)
                dec = [d for _, d in sub if d["decided"]]
                out.append(
                    {
                        "W_s": w,
                        "L_min": lmin,
                        "cohort": cohort,
                        "n": n,
                        "decision_availability_pct": round(100 * len(dec) / n, 1),
                        "abstention_pct": round(100 * (n - len(dec)) / n, 1),
                        "subsequent_revision_pct_of_decided": round(
                            100 * sum(1 for d in dec if d["later_revision"]) / len(dec), 1
                        )
                        if dec
                        else None,
                        "rearm_mean": round(statistics.mean(d["rearms"] for _, d in sub), 2),
                        "posthoc_lead_to_first_inplay_min": dist(
                            [d["lead_to_fip_min"] for d in dec if d["lead_to_fip_min"] is not None]
                        ),
                    }
                )
    with open("docs/evidence/stage2b-planning-packets/packet_c.json", "w") as fh:
        json.dump({"policies": out}, fh, indent=1, sort_keys=True)
    for r in out:
        if r["cohort"] == "primary":
            print(
                f"W={r['W_s']:>3}s L={r['L_min']:>2}m  avail={r['decision_availability_pct']:>5}% "
                f"abst={r['abstention_pct']:>5}%  later_rev={r['subsequent_revision_pct_of_decided']}% "
                f"rearms={r['rearm_mean']}  lead min p10/med/p90="
                f"{r['posthoc_lead_to_first_inplay_min'].get('p10')}/"
                f"{r['posthoc_lead_to_first_inplay_min'].get('median')}/"
                f"{r['posthoc_lead_to_first_inplay_min'].get('p90')}"
            )


if __name__ == "__main__":
    main()
