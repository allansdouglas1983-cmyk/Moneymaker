"""PERSONAL_TENNIS_ASSISTANT_V0 — local CLI (STAGE3-0003 §9A).

Accepts a manual market snapshot (a local JSON file), produces deterministic JSON. No
network, no accounts, no credentials, no order placement. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from assistant_v0.manual_input import ManualMarketSnapshot
from assistant_v0.pipeline import RatingLookup, assemble


def _snapshot_from_dict(d: dict[str, Any]) -> ManualMarketSnapshot:
    return ManualMarketSnapshot(
        competitor_a=d["competitor_a"], competitor_b=d["competitor_b"],
        competitor_a_id=d.get("competitor_a_id"), competitor_b_id=d.get("competitor_b_id"),
        tour=d["tour"], scheduled_start_ms=int(d["scheduled_start_ms"]),
        input_timestamp_ms=int(d["input_timestamp_ms"]), source=d["source"],
        back_a=Decimal(str(d["back_a"])), back_a_size=Decimal(str(d["back_a_size"])),
        lay_a=Decimal(str(d["lay_a"])), lay_a_size=Decimal(str(d["lay_a_size"])),
        back_b=Decimal(str(d["back_b"])), back_b_size=Decimal(str(d["back_b_size"])),
        lay_b=Decimal(str(d["lay_b"])), lay_b_size=Decimal(str(d["lay_b_size"])),
        market_status=d["market_status"], in_play=bool(d["in_play"]),
        market_id=d.get("market_id"), event_id=d.get("event_id"),
    )


def run_snapshot_file(path: str, *, reference_time_ms: int,
                      rating_lookup: RatingLookup | None = None) -> str:
    """Read a manual-snapshot JSON file and return the deterministic V0 output JSON."""
    data = json.loads(Path(path).read_text())
    snap = _snapshot_from_dict(data)
    out = assemble(snap, reference_time_ms=reference_time_ms, rating_lookup=rating_lookup)
    return out.to_json()


def main() -> None:
    ap = argparse.ArgumentParser(description="PERSONAL_TENNIS_ASSISTANT_V0 (research/shadow only)")
    ap.add_argument("--snapshot", required=True, help="path to a manual market snapshot JSON")
    ap.add_argument("--reference-time-ms", type=int, required=True)
    ap.add_argument("--out", default=None, help="optional path to write the JSON output")
    args = ap.parse_args()
    result = run_snapshot_file(args.snapshot, reference_time_ms=args.reference_time_ms)
    if args.out:
        Path(args.out).write_text(result + "\n")
    print(result)


if __name__ == "__main__":
    main()
