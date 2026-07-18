"""Metadata-only extractor. NEVER reads "rc" (price/traded-volume) data.
Stops processing a file's stream at the first marketDefinition.status == "CLOSED"
line, before any result/settlement-adjacent field (runner WINNER/LOSER status,
reconciled BSP, etc.) can appear. Only marketDefinition-level fields are read.
"""
import bz2
import json
import sys


def extract_market_metadata(path: str) -> dict:
    market_id = None
    event_id = None
    event_name = None
    competition_name = None
    market_type = None
    open_date = None
    earliest_market_time = None
    earliest_market_time_pt = None
    market_time_revisions = []  # list of {"pt": ..., "market_time": ...}
    status_transitions = []  # list of {"pt": ..., "status": ...}
    first_in_play_pt = None
    runner_names = None
    runner_count = None
    last_status = None
    last_market_time = None
    stopped_at_closed = False
    line_count = 0
    error = None

    try:
        with bz2.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                line_count += 1
                obj = json.loads(line)
                pt = obj.get("pt")
                for mc in obj.get("mc", []):
                    mdef = mc.get("marketDefinition")
                    if mdef is None:
                        continue
                    mid = mc.get("id")
                    if market_id is None:
                        market_id = mid
                    status = mdef.get("status")
                    if status == "CLOSED":
                        stopped_at_closed = True
                        break  # never read this line's other fields
                    if event_id is None:
                        event_id = mdef.get("eventId")
                    if event_name is None:
                        event_name = mdef.get("eventName")
                    comp = mdef.get("competition")
                    if competition_name is None and isinstance(comp, dict):
                        competition_name = comp.get("name")
                    if market_type is None:
                        market_type = mdef.get("marketType")
                    if open_date is None:
                        open_date = mdef.get("openDate")
                    mt = mdef.get("marketTime")
                    if mt is not None:
                        if earliest_market_time is None:
                            earliest_market_time = mt
                            earliest_market_time_pt = pt
                            last_market_time = mt
                        elif mt != last_market_time:
                            market_time_revisions.append({"pt": pt, "market_time": mt})
                            last_market_time = mt
                    if status is not None and status != last_status:
                        status_transitions.append({"pt": pt, "status": status})
                        last_status = status
                    if mdef.get("inPlay") is True and first_in_play_pt is None:
                        first_in_play_pt = pt
                    if runner_names is None:
                        runners = mdef.get("runners")
                        if runners:
                            runner_names = [r.get("name") for r in runners]
                            runner_count = len(runners)
                if stopped_at_closed:
                    break
    except Exception as exc:  # noqa: BLE001 - audit tool, report and continue
        error = f"{type(exc).__name__}: {exc}"

    return {
        "path": path,
        "market_id": market_id,
        "event_id": event_id,
        "event_name": event_name,
        "competition_name": competition_name,
        "market_type": market_type,
        "open_date": open_date,
        "earliest_market_time": earliest_market_time,
        "earliest_market_time_pt": earliest_market_time_pt,
        "market_time_revisions": market_time_revisions,
        "status_transitions": status_transitions,
        "first_in_play_pt": first_in_play_pt,
        "runner_names": runner_names,
        "runner_count": runner_count,
        "stopped_at_closed": stopped_at_closed,
        "line_count": line_count,
        "error": error,
    }


if __name__ == "__main__":
    import time
    t0 = time.time()
    result = extract_market_metadata(sys.argv[1])
    dt = time.time() - t0
    print(json.dumps(result, indent=2))
    print(f"\n--- took {dt:.3f}s, {result['line_count']} lines ---", file=sys.stderr)
