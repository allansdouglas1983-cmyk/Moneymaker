"""Canonical serialisation of derived state (SPEC-010/011).

Deterministic: markets sorted by id, runners by selection, ladders by level/price, Decimals
rendered without scientific notation, keys sorted. The canonical hash is sha256 of these
bytes and is the comparison metric §6.2 mandates in place of unqualified "bit-exact".
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

from l1_reduce.state import MarketBookState, MarketUniverseState, RunnerBookState


def canonical_decimal(value: Decimal) -> str:
    return format(value, "f")


def _level_ladder(ladder: dict[int, tuple[Decimal, Decimal]]) -> list[list[object]]:
    return [[level, canonical_decimal(price), canonical_decimal(size)] for level, (price, size) in sorted(ladder.items())]


def _price_ladder(ladder: dict[Decimal, Decimal]) -> list[list[str]]:
    return [[canonical_decimal(price), canonical_decimal(size)] for price, size in sorted(ladder.items())]


def _runner(runner: RunnerBookState) -> dict[str, Any]:
    return {
        "selection_id": runner.selection_id,
        "batb": _level_ladder(runner.batb),
        "batl": _level_ladder(runner.batl),
        "atb": _price_ladder(runner.atb),
        "atl": _price_ladder(runner.atl),
        "ltp": None if runner.ltp is None else canonical_decimal(runner.ltp),
        "tv": None if runner.tv is None else canonical_decimal(runner.tv),
    }


def _market(market: MarketBookState) -> dict[str, Any]:
    defn = market.definition
    return {
        "market_id": market.market_id,
        "publish_time": market.publish_time,
        "definition": {
            "status": defn.status,
            "in_play": defn.in_play,
            "version": defn.version,
            "bet_delay": defn.bet_delay,
            "number_of_active_runners": defn.number_of_active_runners,
            "runners": [
                {
                    "selection_id": rd.selection_id,
                    "status": rd.status,
                    "adjustment_factor": None
                    if rd.adjustment_factor is None
                    else canonical_decimal(rd.adjustment_factor),
                    "sort_priority": rd.sort_priority,
                    "removal_date": rd.removal_date,
                }
                for _, rd in sorted(defn.runners.items())
            ],
        },
        "runners": [_runner(runner) for _, runner in sorted(market.runners.items())],
    }


def to_canonical(state: MarketUniverseState) -> dict[str, Any]:
    return {"markets": [_market(market) for _, market in sorted(state.markets.items())]}


def canonical_bytes(state: MarketUniverseState) -> bytes:
    return json.dumps(to_canonical(state), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_hash(state: MarketUniverseState) -> str:
    return hashlib.sha256(canonical_bytes(state)).hexdigest()
