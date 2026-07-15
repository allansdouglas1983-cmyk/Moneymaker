"""reducer-mcm-v1: reduce Betfair Market Change Messages into book state (SPEC-010).

Declared scope (ADR 0003): marketDefinition (status/inPlay/version/betDelay/
numberOfActiveRunners + per-runner status/adjustmentFactor/sortPriority/removalDate) and
per-runner book (batb, batl, atb, atl, ltp, tv). Image (`img`) replaces a market; deltas
mutate it; a size of 0 removes a level/price. Pure and deterministic — no clock, no
randomness, no I/O. Numbers are parsed as Decimal, never float.
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from l1_reduce.state import (
    MarketBookState,
    MarketDefinitionState,
    MarketUniverseState,
    RunnerBookState,
    RunnerDefinition,
)

REDUCER_VERSION = "reducer-mcm-v1"
REDUCER_DIGEST = "mcm-v1:batb,batl,atb,atl,ltp,tv,marketDefinition"


def _dec(value: Any) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _apply_level_ladder(ladder: dict[int, tuple[Decimal, Decimal]], updates: Any) -> None:
    for entry in updates:
        level = int(entry[0])
        size = _dec(entry[2])
        if size == 0:
            ladder.pop(level, None)
        else:
            ladder[level] = (_dec(entry[1]), size)


def _apply_price_ladder(ladder: dict[Decimal, Decimal], updates: Any) -> None:
    for entry in updates:
        price = _dec(entry[0])
        size = _dec(entry[1])
        if size == 0:
            ladder.pop(price, None)
        else:
            ladder[price] = size


def _apply_definition(defn: MarketDefinitionState, md: dict[str, Any]) -> None:
    if "status" in md:
        defn.status = md["status"]
    if "inPlay" in md:
        defn.in_play = bool(md["inPlay"])
    if "version" in md:
        defn.version = int(md["version"])
    if "betDelay" in md:
        defn.bet_delay = int(md["betDelay"])
    if "numberOfActiveRunners" in md:
        defn.number_of_active_runners = int(md["numberOfActiveRunners"])
    if "runners" in md:
        defn.runners = {}
        for rd in md["runners"]:
            selection_id = int(rd["id"])
            factor = rd.get("adjustmentFactor")
            sort_priority = rd.get("sortPriority")
            defn.runners[selection_id] = RunnerDefinition(
                selection_id=selection_id,
                status=rd.get("status"),
                adjustment_factor=None if factor is None else _dec(factor),
                sort_priority=None if sort_priority is None else int(sort_priority),
                removal_date=rd.get("removalDate"),
            )


def _apply_runner_change(runner: RunnerBookState, rc: dict[str, Any]) -> None:
    if "batb" in rc:
        _apply_level_ladder(runner.batb, rc["batb"])
    if "batl" in rc:
        _apply_level_ladder(runner.batl, rc["batl"])
    if "atb" in rc:
        _apply_price_ladder(runner.atb, rc["atb"])
    if "atl" in rc:
        _apply_price_ladder(runner.atl, rc["atl"])
    if "ltp" in rc:
        runner.ltp = _dec(rc["ltp"])
    if "tv" in rc:
        runner.tv = _dec(rc["tv"])


def _apply_market_change(state: MarketUniverseState, mc: dict[str, Any], publish_time: int | None) -> None:
    market_id = str(mc["id"])
    market = state.markets.get(market_id)
    if market is None:
        market = MarketBookState(market_id=market_id)
        state.markets[market_id] = market
    if mc.get("img"):
        # An image is a full replacement of the market's state.
        market.runners = {}
        market.definition = MarketDefinitionState()
    if "marketDefinition" in mc:
        _apply_definition(market.definition, mc["marketDefinition"])
    for rc in mc.get("rc", []):
        selection_id = int(rc["id"])
        runner = market.runners.get(selection_id)
        if runner is None:
            runner = RunnerBookState(selection_id=selection_id)
            market.runners[selection_id] = runner
        _apply_runner_change(runner, rc)
    if publish_time is not None:
        market.publish_time = publish_time


def reduce_events(events: Sequence[bytes]) -> MarketUniverseState:
    state = MarketUniverseState()
    for payload in events:
        message: Any = json.loads(payload.decode("utf-8"), parse_float=Decimal)
        if not isinstance(message, dict) or message.get("op") != "mcm":
            continue
        raw_pt = message.get("pt")
        publish_time = int(raw_pt) if raw_pt is not None else None
        for mc in message.get("mc", []):
            _apply_market_change(state, mc, publish_time)
    return state
