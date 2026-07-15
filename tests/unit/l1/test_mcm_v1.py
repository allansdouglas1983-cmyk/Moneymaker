"""Unit tests for reducer-mcm-v1 reduction logic (SPEC-010 pure reduction)."""
from __future__ import annotations

import json
from decimal import Decimal

import pytest

from l1_reduce.mcm_v1 import REDUCER_VERSION
from l1_reduce.reducer import reduce
from l1_reduce.state import MarketUniverseState

pytestmark = pytest.mark.spec("SPEC-010")


def _mcm(pt: int, mcs: list[dict[str, object]]) -> bytes:
    return json.dumps({"op": "mcm", "pt": pt, "mc": mcs}).encode("utf-8")


def _reduce(*events: bytes) -> MarketUniverseState:
    return reduce(list(events), REDUCER_VERSION).state


def test_image_sets_book_and_definition() -> None:
    ev = _mcm(
        1000,
        [
            {
                "id": "1.1",
                "img": True,
                "marketDefinition": {
                    "status": "OPEN",
                    "inPlay": False,
                    "version": 7,
                    "betDelay": 0,
                    "numberOfActiveRunners": 1,
                    "runners": [{"id": 111, "status": "ACTIVE", "adjustmentFactor": 50.0, "sortPriority": 1}],
                },
                "rc": [{"id": 111, "batb": [[0, 3.45, 10.5], [1, 3.5, 20]], "ltp": 3.45, "tv": 100}],
            }
        ],
    )
    st = _reduce(ev)
    m = st.markets["1.1"]
    assert m.definition.status == "OPEN"
    assert m.definition.in_play is False
    assert m.definition.version == 7
    assert m.definition.number_of_active_runners == 1
    assert m.definition.runners[111].status == "ACTIVE"
    assert m.definition.runners[111].adjustment_factor == Decimal("50.0")
    r = m.runners[111]
    assert r.batb[0] == (Decimal("3.45"), Decimal("10.5"))
    assert r.batb[1] == (Decimal("3.5"), Decimal("20"))
    assert r.ltp == Decimal("3.45")
    assert r.tv == Decimal("100")


def test_delta_updates_and_size_zero_removes() -> None:
    img = _mcm(1000, [{"id": "1.1", "img": True, "rc": [{"id": 111, "batb": [[0, 3.45, 10], [1, 3.5, 20]]}]}])
    delta = _mcm(1001, [{"id": "1.1", "rc": [{"id": 111, "batb": [[0, 3.4, 15], [1, 3.5, 0]]}]}])
    r = _reduce(img, delta).markets["1.1"].runners[111]
    assert r.batb[0] == (Decimal("3.4"), Decimal("15"))
    assert 1 not in r.batb  # size 0 removes the level


def test_image_replaces_whole_market_state() -> None:
    img1 = _mcm(
        1000,
        [{"id": "1.1", "img": True, "rc": [{"id": 111, "batb": [[0, 3.45, 10]]}, {"id": 222, "batb": [[0, 5, 5]]}]}],
    )
    img2 = _mcm(1001, [{"id": "1.1", "img": True, "rc": [{"id": 111, "batb": [[0, 4, 8]]}]}])
    m = _reduce(img1, img2).markets["1.1"]
    assert set(m.runners) == {111}  # the image cleared runner 222
    assert m.runners[111].batb[0] == (Decimal("4"), Decimal("8"))


def test_runner_removal_records_adjustment_factor() -> None:
    ev = _mcm(
        1000,
        [
            {
                "id": "1.1",
                "img": True,
                "marketDefinition": {
                    "status": "OPEN",
                    "runners": [
                        {"id": 111, "status": "ACTIVE"},
                        {"id": 222, "status": "REMOVED", "adjustmentFactor": 12.5, "removalDate": "2026-07-15T12:00:00.000Z"},
                    ],
                },
            }
        ],
    )
    defn = _reduce(ev).markets["1.1"].definition
    assert defn.runners[222].status == "REMOVED"
    assert defn.runners[222].adjustment_factor == Decimal("12.5")
    assert defn.runners[222].removal_date == "2026-07-15T12:00:00.000Z"


def test_atb_atl_and_multiple_markets() -> None:
    ev = _mcm(
        1000,
        [
            {"id": "1.1", "img": True, "rc": [{"id": 111, "atb": [[3.45, 10], [3.5, 20]], "atl": [[3.6, 5]]}]},
            {"id": "1.2", "img": True, "rc": [{"id": 333, "ltp": 2.0}]},
        ],
    )
    st = _reduce(ev)
    assert set(st.markets) == {"1.1", "1.2"}
    r = st.markets["1.1"].runners[111]
    assert r.atb[Decimal("3.45")] == Decimal("10")
    assert r.atl[Decimal("3.6")] == Decimal("5")
    assert st.markets["1.2"].runners[333].ltp == Decimal("2.0")


def test_non_market_ops_are_ignored() -> None:
    st = _reduce(
        json.dumps({"op": "connection", "connectionId": "x"}).encode("utf-8"),
        _mcm(1000, []),  # heartbeat with no market changes
        json.dumps({"op": "status", "statusCode": "SUCCESS"}).encode("utf-8"),
    )
    assert st.markets == {}
