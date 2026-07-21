"""PERSONAL_TENNIS_ASSISTANT_V0 — cross-market audit VIEW loader (STAGE3-0003 §11).

Reads the FROZEN STAGE3-0002 per-match audit artifact as plain DATA (JSONL), for a single
historical June market, and projects the outcome-blind display fields. It does NOT import
``research.xmarket`` (the live audit code) into the probability path — the report shows this
strictly as "RESEARCH AUDIT — NOT USED IN THE PROBABILITY". It never produces a latent
parameter or a competitiveness tip.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_RECORDS = "docs/evidence/stage3-cross-market-audit/PER_MATCH_RECORDS.jsonl"


def load_xmarket_view(market_id: str, *, records_path: str = DEFAULT_RECORDS) -> dict[str, Any] | None:
    """Return the outcome-blind cross-market audit display fields for a June MO market, or
    None if the artifact or the market is not present. Display-only; no probability input."""
    p = Path(records_path)
    if not p.exists():
        return None
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("mo_market_id") != market_id:
            continue
        tg = rec.get("total_games")
        gh = rec.get("game_handicap")

        def _d(d: dict[str, Any] | None) -> dict[str, Any]:
            if d is None:
                return {"present": False}
            return {
                "present": True,
                "exclusion_reason": d.get("exclusion_reason"),
                "quote_age_seconds": d.get("quote_age_seconds"),
                "two_sided_line_count": d.get("two_sided_line_count"),
                "min_spread_ticks": d.get("min_spread_ticks"),
                "lines_offered": d.get("lines_offered"),
            }

        return {
            "mo_market_id": rec.get("mo_market_id"),
            "cohort": rec.get("cohort"),
            "tour": rec.get("tour"),
            "total_games": _d(tg),
            "game_handicap": _d(gh),
            "linkage_anomalies": rec.get("linkage_anomalies", []),
            "cross_market_layer_status": "BLOCKED_EXTERNAL_FACTS",
            "settlement_semantics_status": "UNRESOLVED",
        }
    return None
