"""F0 — June market-yardstick run (Stage 2B §2). Reads pre-off prices/market state of
the frozen June universe ONLY (SAFE fields; stops before CLOSED; never reads runner
status/settlement). Applies the tested COMMIT_ONCE policy (sport_tennis.market_yardstick)
and the governed info-price formula. One immutable snapshot per committed decision;
explicit refusal reason otherwise. No winner, settlement, P&L, CLV, or model output.
"""
from __future__ import annotations

import bz2
import csv
import hashlib
import json
import os
import sys
from collections import Counter
from decimal import Decimal

sys.path.insert(0, "/home/user/Moneymaker")
from price_contracts.ladder import index_of, is_on_ladder  # noqa: E402
from sport_tennis.market_yardstick import (  # noqa: E402
    BookLevel,
    MarketTimelineEvent,
    commit_once_decision,
    market_probabilities_from_book,
)

ROOT = os.path.dirname(os.path.abspath(__file__))
PILOT = os.path.join(os.path.dirname(ROOT), "pilot-data")


def load_universe():
    uni = {}
    for r in csv.DictReader(open("/home/user/Moneymaker/docs/evidence/pilot-2026-06-tennis/PRIMARY_JUNE_ANALYSIS_UNIVERSE_MANIFEST.csv")):
        if r["universe_membership"] == "PRIMARY_JUNE_SINGLES_UNIVERSE":
            uni[r["market_id"]] = "STRICT" in r["cohort_tags"]
    canon = {}
    with open(os.path.join(PILOT, "audit", "CANONICAL_REPLAY_MANIFEST.jsonl")) as f:
        for line in f:
            r = json.loads(line)
            if r["market_id"] in uni:
                canon[r["market_id"]] = os.path.join(PILOT, r["canonical_source"])
    return uni, canon


def timeline_for(path: str, market_id: str):
    """Pre-off timeline: (pt, marketTime_ms, status, inplay, best back/lay tick+size per
    selection). Stops at first CLOSED; reads no runner status, no settlement."""
    from datetime import datetime, timezone

    def mt_ms(mt):
        return int(datetime.fromisoformat(mt.replace("Z", "+00:00")).astimezone(timezone.utc).timestamp() * 1000)

    events = []
    cur_mt = None
    cur_status = None
    cur_inplay = False
    first_inplay_pt = None
    backs: dict[int, dict[int, tuple[int, int]]] = {}
    lays: dict[int, dict[int, tuple[int, int]]] = {}
    with bz2.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            msg = json.loads(line, parse_float=Decimal)
            pt = int(msg.get("pt"))
            changed = False
            stop = False
            for mc in msg.get("mc", []):
                if mc.get("id") != market_id:
                    continue
                md = mc.get("marketDefinition")
                if md is not None:
                    if md.get("status") == "CLOSED":
                        stop = True
                        break
                    cur_status = md.get("status")
                    ip = bool(md.get("inPlay"))
                    if ip and first_inplay_pt is None:
                        first_inplay_pt = pt
                    cur_inplay = ip
                    if md.get("marketTime"):
                        cur_mt = mt_ms(md["marketTime"])
                    changed = True
                for rc in mc.get("rc", []):
                    sid = rc.get("id")
                    if sid is None:
                        continue
                    for fld, store in (("batb", backs), ("batl", lays)):
                        if fld in rc:
                            lv = store.setdefault(sid, {})
                            for lvl, price, size in rc[fld]:
                                p = price if isinstance(price, Decimal) else Decimal(str(price))
                                s = int((Decimal(str(size)) * 100).to_integral_value())
                                if s <= 0 or not is_on_ladder(p):
                                    lv.pop(int(lvl), None)
                                else:
                                    lv[int(lvl)] = (index_of(p), s)
                            changed = True
            if stop:
                break
            if changed and cur_mt is not None and cur_status is not None:
                bb = {}
                bl = {}
                for sid, levels in backs.items():
                    if levels:
                        t = max(tk for tk, _ in levels.values())
                        bb[sid] = (t, sum(sz for tk, sz in levels.values() if tk == t))
                for sid, levels in lays.items():
                    if levels:
                        t = min(tk for tk, _ in levels.values())
                        bl[sid] = (t, sum(sz for tk, sz in levels.values() if tk == t))
                events.append(
                    MarketTimelineEvent(
                        pt_ms=pt, market_time_ms=cur_mt, status=cur_status, inplay=cur_inplay,
                        best_back_by_selection=bb, best_lay_by_selection=bl,
                    )
                )
    return events, first_inplay_pt


def work(args):
    mid, path, strict = args
    try:
        tl, fip = timeline_for(path, mid)
        d = commit_once_decision(tl, first_inplay_pt_ms=fip)
        row = {
            "market_id": mid,
            "cohort": "STRICT" if strict else "PRIMARY_ONLY_TIER",
            "committed": d.committed,
            "refusal_reason": d.refusal_reason.value if d.refusal_reason else None,
            "commit_pt_ms": d.commit_pt_ms,
            "market_time_ms_at_commit": d.market_time_ms_at_commit,
            "post_commit_revision_count": d.post_commit_revision_count,
            "decision_digest": d.decision_digest,
            "book_state_digest": d.book_state_digest,
            "price_method": "info-price-v2 (implied midpoint best back/lay, normalised; scope betfair MATCH_ODDS)",
            "policy": "COMMIT_ONCE_HOLD_THROUGH_RESCHEDULE W=60s L=300s (reschedule-policy-v1)",
        }
        if d.committed and d.book_at_commit is not None:
            probs = market_probabilities_from_book(d.book_at_commit)
            row["p_market_by_selection"] = {str(k): round(v, 6) for k, v in sorted(probs.items())}
        return row
    except Exception as e:  # noqa: BLE001
        return {"market_id": mid, "committed": False, "refusal_reason": f"ERROR:{e}"}


def main() -> None:
    from concurrent.futures import ProcessPoolExecutor

    uni, canon = load_universe()
    jobs = [(mid, canon[mid], uni[mid]) for mid in sorted(canon)]
    rows = []
    with ProcessPoolExecutor(max_workers=4) as pool:
        for row in pool.map(work, jobs, chunksize=16):
            rows.append(row)
    rows.sort(key=lambda r: r["market_id"])
    body = "\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n"
    digest = hashlib.sha256(body.encode()).hexdigest()
    open(os.path.join(ROOT, "F0_MARKET_YARDSTICK_MANIFEST.jsonl"), "w").write(body)
    reasons = Counter(r.get("refusal_reason") for r in rows if not r["committed"])
    committed = [r for r in rows if r["committed"]]
    summary = {
        "markets": len(rows),
        "committed_decisions": len(committed),
        "committed_strict": sum(1 for r in committed if r["cohort"] == "STRICT"),
        "refusals": dict(reasons),
        "post_commit_revision_markets": sum(1 for r in committed if r["post_commit_revision_count"] > 0),
        "manifest_sha256": digest,
    }
    json.dump(summary, open(os.path.join(ROOT, "F0_SUMMARY.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps(summary, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
