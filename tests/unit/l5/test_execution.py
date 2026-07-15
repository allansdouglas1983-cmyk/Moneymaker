"""Crossing execution policy only in v1 — taker-v1 (SPEC-052).

Marketable limit orders: timeInForce FILL_OR_KILL, minFillSize = full stake, persistenceType
LAPSE always, marketVersion on every order, no resting remainder, no passive posting reachable.
"""
from __future__ import annotations

import pytest

from l5_decision.execution import (
    PersistenceType,
    Side,
    TakerV1Order,
    TimeInForce,
    taker_v1,
)

pytestmark = pytest.mark.spec("SPEC-052")


def _order(**over: object) -> TakerV1Order:
    kw: dict[str, object] = dict(
        market_id="1.100",
        selection_id=11,
        side=Side.BACK,
        stake_minor=200,
        min_fill_size_minor=200,
        worst_acceptable_tick=100,
        time_in_force=TimeInForce.FILL_OR_KILL,
        persistence_type=PersistenceType.LAPSE,
        market_version=42,
    )
    kw.update(over)
    return TakerV1Order(**kw)  # type: ignore[arg-type]


class TestTakerV1Invariants:
    def test_convenience_builder_sets_the_policy(self) -> None:
        o = taker_v1(
            market_id="1.100",
            selection_id=11,
            stake_minor=200,
            worst_acceptable_tick=100,
            market_version=42,
        )
        assert o.time_in_force is TimeInForce.FILL_OR_KILL
        assert o.persistence_type is PersistenceType.LAPSE
        assert o.min_fill_size_minor == o.stake_minor == 200
        assert o.side is Side.BACK
        assert o.market_version == 42

    def test_min_fill_below_stake_rejected(self) -> None:
        # A smaller minFillSize would permit a partial match leaving a resting remainder.
        with pytest.raises((ValueError, TypeError)):
            _order(min_fill_size_minor=100)

    def test_min_fill_above_stake_rejected(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            _order(min_fill_size_minor=300)

    def test_non_lapse_persistence_rejected(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            _order(persistence_type=PersistenceType.PERSIST)

    def test_non_fok_time_in_force_rejected(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            _order(time_in_force=TimeInForce.GOOD_TILL_CANCELLED)

    def test_lay_side_rejected_in_v1(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            _order(side=Side.LAY)

    def test_non_positive_stake_rejected(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            _order(stake_minor=0, min_fill_size_minor=0)

    def test_invalid_worst_acceptable_tick_rejected(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            _order(worst_acceptable_tick=350)

    def test_market_version_required(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            TakerV1Order(  # type: ignore[call-arg]
                market_id="1.100",
                selection_id=11,
                side=Side.BACK,
                stake_minor=200,
                min_fill_size_minor=200,
                worst_acceptable_tick=100,
                time_in_force=TimeInForce.FILL_OR_KILL,
                persistence_type=PersistenceType.LAPSE,
            )

    def test_frozen(self) -> None:
        o = _order()
        with pytest.raises((ValueError, TypeError)):
            o.stake_minor = 500  # type: ignore[misc]

    def test_no_passive_persistence_is_ever_valid(self) -> None:
        # There is no reachable maker/passive order: every non-LAPSE persistence is refused.
        for persistence in (PersistenceType.PERSIST, PersistenceType.MARKET_ON_CLOSE):
            with pytest.raises((ValueError, TypeError)):
                _order(persistence_type=persistence)
