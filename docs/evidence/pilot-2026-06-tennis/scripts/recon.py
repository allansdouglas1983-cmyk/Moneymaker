"""Market-feasibility reconstruction (founder-authorised 2026-07-18, governed horizon
protocol as corrected 2026-07-18).

PRIMARY horizon protocol — as-of published-marketTime state machine (live-replicable):
  At every stream publish time t, using ONLY the marketTime known at t:
    remaining(t) = marketTime_as_known_at_t - t
  For each horizon H, an IMMUTABLE instance is created when remaining crosses from > H to
  <= H while the market is OPEN and inPlay == false. If a later marketTime revision moves
  remaining back above H, the horizon RE-ARMS; the next crossing mints a NEW instance,
  linked to the previous via schedule-revision lineage. Earlier instances are never
  rewritten and instances are never retrospectively selected. first inPlay is used ONLY
  post-hoc to describe timing error, never to construct a pre-match snapshot.

Descriptive sensitivity anchors (NOT primary): earliest marketTime, final pre-in-play
marketTime, first-inPlay alignment — recorded for reporting, never used to build the
primary instances.

Discipline: reads ONLY marketDefinition {status, inPlay, marketTime, numberOfActiveRunners,
version} and rc {batb, batl, trd, tv, ltp, id}. NEVER reads runner win/lose status, sp*
(BSP) fields, settled prices, or anything past the first CLOSED marketDefinition. Prices
are canonical integer tick indices (price_contracts.ladder, SPEC-053); sizes are integer
minor units (pence). No float price or size ever leaves this module. No outcome, no
settlement, no P&L.
"""
from __future__ import annotations

import bz2
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

sys.path.insert(0, "/home/user/Moneymaker")
from price_contracts.ladder import index_of, is_on_ladder  # noqa: E402

HORIZONS_S = [1800, 600, 300, 120, 60]  # T-30m, T-10m, T-5m, T-2m, T-60s
BENCH_WINDOW_S = 60


def _to_minor(size_dec: Decimal) -> int:
    # integer minor units (pence); Betfair sizes carry 2dp so *100 is exact after quantize
    return int((size_dec * 100).to_integral_value())


def _to_tick(price_dec: Decimal) -> int | None:
    if is_on_ladder(price_dec):
        return index_of(price_dec)
    return None


def _mt_to_ms(mt: str | None) -> int | None:
    if not mt:
        return None
    dt = datetime.fromisoformat(mt.replace("Z", "+00:00")).astimezone(timezone.utc)
    return int(dt.timestamp() * 1000)


@dataclass
class SelBook:
    back: dict[int, tuple[int, int]] = field(default_factory=dict)  # level -> (tick, size_minor)
    lay: dict[int, tuple[int, int]] = field(default_factory=dict)
    trd: dict[int, int] = field(default_factory=dict)  # tick -> cumulative matched minor
    ltp_tick: int | None = None
    tv_minor: int = 0
    off_ladder_events: int = 0

    def apply_side(self, side: dict[int, tuple[int, int]], entries: list) -> None:
        for lvl, price, size in entries:
            price_dec = price if isinstance(price, Decimal) else Decimal(str(price))
            size_min = _to_minor(size if isinstance(size, Decimal) else Decimal(str(size)))
            if size_min <= 0:
                side.pop(int(lvl), None)
                continue
            tick = _to_tick(price_dec)
            if tick is None:
                self.off_ladder_events += 1
                side.pop(int(lvl), None)
                continue
            side[int(lvl)] = (tick, size_min)

    def apply_rc(self, rc: dict) -> None:
        if "batb" in rc:
            self.apply_side(self.back, rc["batb"])
        if "batl" in rc:
            self.apply_side(self.lay, rc["batl"])
        if "trd" in rc:
            for price, size in rc["trd"]:
                price_dec = price if isinstance(price, Decimal) else Decimal(str(price))
                size_min = _to_minor(size if isinstance(size, Decimal) else Decimal(str(size)))
                tick = _to_tick(price_dec)
                if tick is None:
                    self.off_ladder_events += 1
                    continue
                if size_min <= 0:
                    self.trd.pop(tick, None)
                else:
                    self.trd[tick] = size_min
        if "ltp" in rc:
            p = rc["ltp"]
            p_dec = p if isinstance(p, Decimal) else Decimal(str(p))
            self.ltp_tick = _to_tick(p_dec) if p_dec > 0 else None
        if "tv" in rc:
            v = rc["tv"]
            self.tv_minor = _to_minor(v if isinstance(v, Decimal) else Decimal(str(v)))

    def best_back(self) -> tuple[int, int] | None:
        # best available to back = highest odds (max tick) among present levels
        if not self.back:
            return None
        tick = max(t for t, _ in self.back.values())
        size = sum(s for t, s in self.back.values() if t == tick)
        return (tick, size)

    def best_lay(self) -> tuple[int, int] | None:
        if not self.lay:
            return None
        tick = min(t for t, _ in self.lay.values())
        size = sum(s for t, s in self.lay.values() if t == tick)
        return (tick, size)

    def back_ladder(self) -> list[list[int]]:
        # delivered levels, best (highest odds) first
        agg: dict[int, int] = {}
        for t, s in self.back.values():
            agg[t] = agg.get(t, 0) + s
        return [[t, agg[t]] for t in sorted(agg, reverse=True)]

    def lay_ladder(self) -> list[list[int]]:
        agg: dict[int, int] = {}
        for t, s in self.lay.values():
            agg[t] = agg.get(t, 0) + s
        return [[t, agg[t]] for t in sorted(agg)]


def _book_summary(books: dict[int, SelBook], sel_ids: list[int]) -> dict:
    out = {}
    for sid in sel_ids:
        b = books.get(sid)
        if b is None:
            out[str(sid)] = None
            continue
        out[str(sid)] = {
            "back": b.back_ladder(),
            "lay": b.lay_ladder(),
            "ltp_tick": b.ltp_tick,
            "tv_minor": b.tv_minor,
        }
    return out


def reconstruct(path: str, market_id: str) -> dict:
    """Deterministic pure function of the canonical file bytes. Returns raw measurements
    only (integer ticks / minor units / timestamps); no aggregation, no outcomes."""
    books: dict[int, SelBook] = {}
    sel_ids: list[int] = []
    timeline: list[dict] = []  # compact per-message pre-CLOSED snapshot
    revisions: list[dict] = []
    cur_mt = None
    cur_status = None
    cur_inplay = None
    cur_nar = None
    cur_ver = None
    first_inplay_pt = None
    n_messages = 0
    stopped_at_closed = False

    with bz2.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            msg = json.loads(line, parse_float=Decimal)
            pt = msg.get("pt")
            if pt is not None:
                pt = int(pt)
            for mc in msg.get("mc", []):
                if mc.get("id") != market_id:
                    continue
                md = mc.get("marketDefinition")
                if md is not None:
                    if md.get("status") == "CLOSED":
                        stopped_at_closed = True
                        break
                    st = md.get("status")
                    ip = bool(md.get("inPlay"))
                    mt = md.get("marketTime")
                    nar = md.get("numberOfActiveRunners")
                    ver = md.get("version")
                    if mt != cur_mt:
                        revisions.append({"pt": pt, "marketTime": mt, "marketTime_ms": _mt_to_ms(mt)})
                        cur_mt = mt
                    cur_status = st
                    cur_inplay = ip
                    if ip and first_inplay_pt is None:
                        first_inplay_pt = pt
                    cur_nar = nar
                    cur_ver = ver
                for rc in mc.get("rc", []):
                    sid = rc.get("id")
                    if sid is None:
                        continue
                    if sid not in books:
                        books[sid] = SelBook()
                        sel_ids.append(sid)
                    books[sid].apply_rc(rc)
            else:
                # capture a compact snapshot for this message (state after applying it)
                n_messages += 1
                timeline.append(
                    {
                        "pt": pt,
                        "status": cur_status,
                        "inplay": cur_inplay,
                        "marketTime_ms": _mt_to_ms(cur_mt),
                        "nar": cur_nar,
                        "book": _book_summary(books, sel_ids),
                    }
                )
                continue
            # inner break (CLOSED) propagates here
            break

    return _finalize(
        market_id=market_id,
        path=path,
        sel_ids=sel_ids,
        timeline=timeline,
        revisions=revisions,
        first_inplay_pt=first_inplay_pt,
        n_messages=n_messages,
        stopped_at_closed=stopped_at_closed,
        off_ladder=sum(b.off_ladder_events for b in books.values()),
    )


def _implied_bp(tick: int) -> Decimal:
    from price_contracts.ladder import price_of

    return (Decimal(1) / price_of(tick)) * 10000


def _instance_quality(entry: dict, sel_ids: list[int]) -> dict:
    book = entry["book"]
    n_two_sided = 0
    n_one_sided = 0
    n_missing = 0
    crossed = False
    per_sel = {}
    for sid in sel_ids:
        b = book.get(str(sid))
        has_back = bool(b and b["back"])
        has_lay = bool(b and b["lay"])
        bb = b["back"][0] if has_back else None
        bl = b["lay"][0] if has_lay else None
        spread_ticks = None
        spread_bp = None
        if bb and bl:
            spread_ticks = bl[0] - bb[0]  # best_lay_tick - best_back_tick
            spread_bp = float(_implied_bp(bb[0]) - _implied_bp(bl[0]))
            if bl[0] <= bb[0]:
                crossed = True
        if has_back and has_lay:
            n_two_sided += 1
        elif has_back or has_lay:
            n_one_sided += 1
        else:
            n_missing += 1
        per_sel[str(sid)] = {
            "best_back_tick": bb[0] if bb else None,
            "best_back_size_minor": bb[1] if bb else None,
            "best_lay_tick": bl[0] if bl else None,
            "best_lay_size_minor": bl[1] if bl else None,
            "back": b["back"] if b else [],
            "lay": b["lay"] if b else [],
            "ltp_tick": b["ltp_tick"] if b else None,
            "tv_minor": b["tv_minor"] if b else 0,
            "spread_ticks": spread_ticks,
            "spread_prob_bp": spread_bp,
        }
    return {
        "two_active_selections": entry.get("nar") == 2,
        "n_active_runners": entry.get("nar"),
        "both_sided": n_two_sided == len(sel_ids) and len(sel_ids) == 2,
        "two_sided_selections": n_two_sided,
        "one_sided_selections": n_one_sided,
        "missing_book_selections": n_missing,
        "crossed_or_invalid": crossed,
        "selections": per_sel,
    }


def _finalize(market_id, path, sel_ids, timeline, revisions, first_inplay_pt, n_messages, stopped_at_closed, off_ladder):
    # pre-inplay slice of the timeline
    pre = [e for e in timeline if (first_inplay_pt is None or e["pt"] < first_inplay_pt)]
    # --- suspensions before in-play ---
    suspensions = []
    cur_start = None
    reopenings = 0
    prev_status = None
    for e in pre:
        if e["status"] == "SUSPENDED" and prev_status != "SUSPENDED":
            cur_start = e["pt"]
        if e["status"] == "OPEN" and prev_status == "SUSPENDED":
            suspensions.append({"start_pt": cur_start, "end_pt": e["pt"], "duration_s": (e["pt"] - cur_start) / 1000.0 if cur_start else None})
            reopenings += 1
            cur_start = None
        prev_status = e["status"]
    if cur_start is not None:  # suspended right up to in-play / end
        suspensions.append({"start_pt": cur_start, "end_pt": None, "duration_s": None})

    open_pre = [e for e in pre if e["status"] == "OPEN" and not e["inplay"]]
    final_pre_open = open_pre[-1] if open_pre else None
    final_pre_inplay_mt = None
    if pre:
        # marketTime known at the last pre-inplay message
        final_pre_inplay_mt = pre[-1]["marketTime_ms"]

    earliest_mt_ms = revisions[0]["marketTime_ms"] if revisions else None

    # --- horizon state machine over intervals ---
    # An interval [t_a, t_b) carries the constant state after message k. Remaining time
    # r(t)=M-t decreases across it (M constant). A crossing of r from >H to <=H mints an
    # immutable instance iff the interval is OPEN & pre-match; a later revision lifting r
    # back above H re-arms the horizon for a new, lineage-linked instance.
    horizons_out = {}
    n_intervals = len(timeline)
    any_open_prematch = any(e["status"] == "OPEN" and not e["inplay"] for e in timeline)
    for H in HORIZONS_S:
        H_ms = H * 1000
        armed = True
        instances = []
        crossing_during_suspension = False
        entered_below_at_first_open = False
        seen_first_open = False
        for k in range(n_intervals):
            e = timeline[k]
            t_a = e["pt"]
            t_b = timeline[k + 1]["pt"] if k + 1 < n_intervals else (first_inplay_pt if first_inplay_pt is not None else t_a)
            M = e["marketTime_ms"]
            if M is None:
                continue
            is_open_prematch = (e["status"] == "OPEN" and not e["inplay"])
            rem_a = M - t_a
            rem_b = M - t_b
            if rem_a > H_ms and not armed:
                armed = True  # re-arm: revision lifted remaining back above H
            crosses = rem_a > H_ms >= rem_b
            if is_open_prematch and not seen_first_open:
                seen_first_open = True
                if armed and rem_a <= H_ms and not instances:
                    entered_below_at_first_open = True
            if not is_open_prematch:
                if armed and crosses:
                    crossing_during_suspension = True  # H crossed while not OPEN pre-match
                continue
            if armed and crosses:
                crossing_pt = M - H_ms
                q = _instance_quality(e, sel_ids)
                instances.append(
                    {
                        "horizon_s": H,
                        "lineage_index": len(instances),
                        "prior_crossing_pt": instances[-1]["crossing_pt"] if instances else None,
                        "crossing_pt": crossing_pt,
                        "marketTime_ms_at_crossing": M,
                        "message_pt": t_a,
                        "seconds_to_first_inplay": ((first_inplay_pt - crossing_pt) / 1000.0) if first_inplay_pt is not None else None,
                        **q,
                    }
                )
                armed = False
        miss_reasons = []
        if not instances:
            if not any_open_prematch:
                miss_reasons.append("NO_OPEN_PREMATCH_STATE")
            elif entered_below_at_first_open:
                miss_reasons.append("FIRST_OPEN_STATE_ALREADY_WITHIN_H")
            elif crossing_during_suspension:
                miss_reasons.append("CROSSING_DURING_PRE_MATCH_SUSPENSION")
            else:
                miss_reasons.append("HORIZON_NEVER_REACHED_PRE_MATCH")
        horizons_out[str(H)] = {
            "instances": instances,
            "instance_count": len(instances),
            "schedule_revision_instances": max(0, len(instances) - 1),
            "no_instance": len(instances) == 0,
            "miss_reasons": miss_reasons,
        }

    # --- benchmark window: final 60s before first in-play, valid pre-inplay OPEN states ---
    if first_inplay_pt is None:
        bench = {"available": False, "reason": "NO_INPLAY_OBSERVED", "n_observations": 0, "observations": [], "overlaps_suspension": False, "window_start_pt": None, "window_end_pt": None}
    else:
        w_start = first_inplay_pt - BENCH_WINDOW_S * 1000
        win = [e for e in pre if e["pt"] >= w_start]
        open_win = [e for e in win if e["status"] == "OPEN" and not e["inplay"]]
        overlaps_susp = any(e["status"] == "SUSPENDED" for e in win)
        obs = []
        for e in open_win:
            q = _instance_quality(e, sel_ids)
            obs.append({"pt": e["pt"], "seconds_before_inplay": (first_inplay_pt - e["pt"]) / 1000.0, **q})
        bench = {
            "available": len(obs) > 0,
            "reason": None if obs else ("SUSPENDED_THROUGH_WINDOW" if overlaps_susp else "NO_VALID_OPEN_STATE_IN_WINDOW"),
            "n_observations": len(obs),
            "overlaps_suspension": overlaps_susp,
            "window_start_pt": w_start,
            "window_end_pt": first_inplay_pt,
            "observations": obs,
        }

    final_state_q = _instance_quality(final_pre_open, sel_ids) if final_pre_open else None

    return {
        "market_id": market_id,
        "path": path,
        "selection_ids": sel_ids,
        "n_messages": n_messages,
        "stopped_at_closed": stopped_at_closed,
        "off_ladder_events": off_ladder,
        "schedule_revision_count": max(0, len(revisions) - 1),
        "marketTime_revisions": revisions,
        "earliest_marketTime_ms": earliest_mt_ms,
        "final_pre_inplay_marketTime_ms": final_pre_inplay_mt,
        "first_inplay_pt": first_inplay_pt,
        "never_inplay": first_inplay_pt is None,
        "pre_inplay_suspensions": suspensions,
        "reopenings_before_inplay": reopenings,
        "clean_last_pre_inplay_state": final_pre_open is not None,
        "horizons": horizons_out,
        "benchmark_window": bench,
        "final_pre_inplay_state": ({"pt": final_pre_open["pt"], **final_state_q} if final_pre_open else None),
    }


if __name__ == "__main__":
    import sys as _s

    rec = reconstruct(_s.argv[1], _s.argv[2])
    # print a compact view (no full observation arrays)
    view = {k: v for k, v in rec.items() if k not in ("benchmark_window", "marketTime_revisions")}
    view["benchmark_window"] = {k: v for k, v in rec["benchmark_window"].items() if k != "observations"}
    view["marketTime_revision_count"] = len(rec["marketTime_revisions"])
    print(json.dumps(view, indent=2, default=str)[:6000])
