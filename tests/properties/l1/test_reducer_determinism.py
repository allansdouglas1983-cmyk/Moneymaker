"""SPEC-010: reduce is pure and deterministic over generated MCM event sequences."""
from __future__ import annotations

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from l1_reduce.mcm_v1 import REDUCER_VERSION
from l1_reduce.reducer import reduce

pytestmark = pytest.mark.spec("SPEC-010")

_PRICE = st.sampled_from([1.5, 2.0, 2.5, 3.0, 3.45, 3.5, 5.0, 10.0])
_SIZE = st.integers(min_value=0, max_value=100)
_LEVEL = st.integers(min_value=0, max_value=2)
_SELECTION = st.sampled_from([111, 222, 333])


@st.composite
def _events(draw: st.DrawFn) -> list[bytes]:
    count = draw(st.integers(min_value=1, max_value=6))
    out: list[bytes] = []
    for i in range(count):
        runner_changes: list[dict[str, object]] = []
        for _ in range(draw(st.integers(min_value=0, max_value=3))):
            change: dict[str, object] = {"id": draw(_SELECTION)}
            if draw(st.booleans()):
                change["batb"] = [
                    [draw(_LEVEL), draw(_PRICE), draw(_SIZE)] for _ in range(draw(st.integers(min_value=0, max_value=3)))
                ]
            if draw(st.booleans()):
                change["ltp"] = draw(_PRICE)
            runner_changes.append(change)
        market_change = {"id": "1.1", "img": draw(st.booleans()), "rc": runner_changes}
        out.append(json.dumps({"op": "mcm", "pt": i, "mc": [market_change]}).encode("utf-8"))
    return out


@settings(max_examples=150)
@given(events=_events())
def test_reduce_is_deterministic(events: list[bytes]) -> None:
    first = reduce(events, REDUCER_VERSION)
    second = reduce(events, REDUCER_VERSION)
    assert first.canonical_bytes == second.canonical_bytes
    assert first.canonical_hash == second.canonical_hash


# A richer strategy exercising multiple markets, every ladder, tv, and marketDefinition —
# so determinism is asserted over the reducer's full declared surface (advisory review F3).
_MARKET = st.sampled_from(["1.1", "1.2", "1.3"])
_STATUS = st.sampled_from(["OPEN", "SUSPENDED", "CLOSED"])


def _price_levels() -> st.SearchStrategy[list[list[object]]]:
    return st.lists(st.tuples(_PRICE, _SIZE).map(lambda t: [t[0], t[1]]), max_size=3)


def _level_levels() -> st.SearchStrategy[list[list[object]]]:
    return st.lists(st.tuples(_LEVEL, _PRICE, _SIZE).map(lambda t: [t[0], t[1], t[2]]), max_size=3)


@st.composite
def _rich_events(draw: st.DrawFn) -> list[bytes]:
    out: list[bytes] = []
    for i in range(draw(st.integers(min_value=1, max_value=5))):
        mcs: list[dict[str, object]] = []
        for market_id in draw(st.lists(_MARKET, min_size=1, max_size=3, unique=True)):
            mc: dict[str, object] = {"id": market_id, "img": draw(st.booleans())}
            if draw(st.booleans()):
                mc["marketDefinition"] = {
                    "status": draw(_STATUS),
                    "version": draw(st.integers(0, 5)),
                    "runners": [{"id": sel, "status": "ACTIVE", "sortPriority": sel} for sel in (111, 222)],
                }
            changes: list[dict[str, object]] = []
            for _ in range(draw(st.integers(min_value=0, max_value=2))):
                change: dict[str, object] = {"id": draw(_SELECTION)}
                for field_name, strat in (("batb", _level_levels()), ("batl", _level_levels()), ("atb", _price_levels()), ("atl", _price_levels())):
                    if draw(st.booleans()):
                        change[field_name] = draw(strat)
                if draw(st.booleans()):
                    change["ltp"] = draw(_PRICE)
                if draw(st.booleans()):
                    change["tv"] = draw(_PRICE)
                changes.append(change)
            mc["rc"] = changes
            mcs.append(mc)
        out.append(json.dumps({"op": "mcm", "pt": i, "mc": mcs}).encode("utf-8"))
    return out


@settings(max_examples=150)
@given(events=_rich_events())
def test_reduce_is_deterministic_full_surface(events: list[bytes]) -> None:
    first = reduce(events, REDUCER_VERSION)
    second = reduce(events, REDUCER_VERSION)
    assert first.canonical_bytes == second.canonical_bytes
    assert first.canonical_hash == second.canonical_hash
