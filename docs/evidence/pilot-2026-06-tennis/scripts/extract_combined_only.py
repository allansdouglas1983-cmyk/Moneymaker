"""Metadata-only extraction for COMBINED_ONLY markets, filtered by market_id within
a multiplexed combined ({eventId}.bz2) file. Same discipline as extract_metadata.py:
stop at first CLOSED, never touch rc, only marketDefinition fields.
"""
from __future__ import annotations

import bz2
import json


def extract_one_market(path: str, target_id: str) -> dict:
    result = {
        "market_id": target_id,
        "path": path,
        "event_id": None,
        "event_name": None,
        "competition_name": None,
        "market_type": None,
        "open_date": None,
        "earliest_market_time": None,
        "runner_names": None,
        "runner_count": None,
        "stopped_at_closed": False,
        "line_count": 0,
        "error": None,
    }
    try:
        with bz2.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                result["line_count"] += 1
                obj = json.loads(line)
                for mc in obj.get("mc", []):
                    if mc.get("id") != target_id:
                        continue
                    md = mc.get("marketDefinition")
                    if md is None:
                        continue
                    if md.get("status") == "CLOSED":
                        result["stopped_at_closed"] = True
                        return result
                    if result["event_id"] is None:
                        result["event_id"] = md.get("eventId")
                        result["event_name"] = md.get("eventName")
                        comp = md.get("competition")
                        result["competition_name"] = comp.get("name") if comp else None
                        result["market_type"] = md.get("marketType")
                        result["open_date"] = md.get("openDate")
                    if result["earliest_market_time"] is None and md.get("marketTime"):
                        result["earliest_market_time"] = md.get("marketTime")
                    runners = md.get("runners")
                    if runners and result["runner_names"] is None:
                        result["runner_names"] = [r.get("name") for r in runners]
                        result["runner_count"] = len(runners)
    except Exception as e:  # noqa: BLE001
        result["error"] = str(e)
    return result


if __name__ == "__main__":
    import sys

    targets = [
        ("1.258757587", "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted/ADVANCED/2026/Jun/1/35668353/35668353.bz2"),
        ("1.258757783", "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted/ADVANCED/2026/Jun/1/35668378/35668378.bz2"),
        ("1.258776575", "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted/ADVANCED/2026/Jun/3/35670895/35670895.bz2"),
        ("1.258776577", "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted/ADVANCED/2026/Jun/3/35670895/35670895.bz2"),
        ("1.258776572", "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted/ADVANCED/2026/Jun/3/35670895/35670895.bz2"),
        ("1.258776589", "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted/ADVANCED/2026/Jun/3/35670896/35670896.bz2"),
        ("1.258776585", "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted/ADVANCED/2026/Jun/3/35670896/35670896.bz2"),
        ("1.258776586", "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted/ADVANCED/2026/Jun/3/35670896/35670896.bz2"),
        ("1.258776591", "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted/ADVANCED/2026/Jun/3/35670897/35670897.bz2"),
        ("1.258776592", "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted/ADVANCED/2026/Jun/3/35670897/35670897.bz2"),
        ("1.258776593", "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted/ADVANCED/2026/Jun/3/35670897/35670897.bz2"),
        ("1.258776580", "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted/ADVANCED/2026/Jun/3/35670898/35670898.bz2"),
        ("1.258776581", "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted/ADVANCED/2026/Jun/3/35670898/35670898.bz2"),
        ("1.258776573", "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted/ADVANCED/2026/Jun/3/35670898/35670898.bz2"),
        ("1.258776596", "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted/ADVANCED/2026/Jun/2/35670899/35670899.bz2"),
        ("1.258776597", "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted/ADVANCED/2026/Jun/2/35670899/35670899.bz2"),
        ("1.258776595", "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted/ADVANCED/2026/Jun/2/35670899/35670899.bz2"),
        ("1.258776578", "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted/ADVANCED/2026/Jun/2/35670900/35670900.bz2"),
        ("1.258776579", "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted/ADVANCED/2026/Jun/2/35670900/35670900.bz2"),
        ("1.258776576", "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted/ADVANCED/2026/Jun/2/35670900/35670900.bz2"),
        ("1.258776587", "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted/ADVANCED/2026/Jun/3/35670901/35670901.bz2"),
        ("1.258776588", "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted/ADVANCED/2026/Jun/3/35670901/35670901.bz2"),
        ("1.258776584", "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted/ADVANCED/2026/Jun/3/35670901/35670901.bz2"),
        ("1.258776600", "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted/ADVANCED/2026/Jun/3/35670902/35670902.bz2"),
        ("1.258776601", "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted/ADVANCED/2026/Jun/3/35670902/35670902.bz2"),
        ("1.258776599", "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted/ADVANCED/2026/Jun/3/35670902/35670902.bz2"),
    ]
    out = []
    for mid, path in targets:
        out.append(extract_one_market(path, mid))
    with open("audit/combined_only_metadata.jsonl", "w") as f:
        for r in out:
            f.write(json.dumps(r) + "\n")
    from collections import Counter
    print("market_type counts:", Counter(r["market_type"] for r in out))
    for r in out:
        print(r["market_id"], r["market_type"], r["event_id"], r["earliest_market_time"], r["runner_count"], r["error"])
