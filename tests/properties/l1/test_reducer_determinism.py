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
