"""Canonical Betfair tick ladder & integer tick-index arithmetic (SPEC-053).

Price is an **integer index** into the canonical ladder; floats must not represent price and
the index<->decimal round-trip must be exact.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from l5_decision.ladder import (
    LADDER,
    MAX_PRICE,
    MIN_PRICE,
    TICK_COUNT,
    index_of,
    is_on_ladder,
    is_valid_index,
    price_of,
)

pytestmark = pytest.mark.spec("SPEC-053")


class TestLadderShape:
    def test_ladder_has_350_ticks(self) -> None:
        assert TICK_COUNT == 350
        assert len(LADDER) == 350

    def test_endpoints(self) -> None:
        assert LADDER[0] == Decimal("1.01")
        assert LADDER[-1] == Decimal("1000")
        assert MIN_PRICE == Decimal("1.01")
        assert MAX_PRICE == Decimal("1000")

    def test_strictly_increasing(self) -> None:
        assert all(LADDER[i] < LADDER[i + 1] for i in range(len(LADDER) - 1))

    def test_all_prices_are_decimal_never_float(self) -> None:
        assert all(isinstance(p, Decimal) for p in LADDER)


class TestBandSteps:
    @pytest.mark.parametrize(
        ("low", "nxt", "step"),
        [
            (Decimal("1.01"), Decimal("1.02"), Decimal("0.01")),
            (Decimal("1.99"), Decimal("2"), Decimal("0.01")),
            (Decimal("2"), Decimal("2.02"), Decimal("0.02")),
            (Decimal("2.98"), Decimal("3"), Decimal("0.02")),
            (Decimal("3"), Decimal("3.05"), Decimal("0.05")),
            (Decimal("4"), Decimal("4.1"), Decimal("0.1")),
            (Decimal("6"), Decimal("6.2"), Decimal("0.2")),
            (Decimal("10"), Decimal("10.5"), Decimal("0.5")),
            (Decimal("20"), Decimal("21"), Decimal("1")),
            (Decimal("30"), Decimal("32"), Decimal("2")),
            (Decimal("50"), Decimal("55"), Decimal("5")),
            (Decimal("100"), Decimal("110"), Decimal("10")),
            (Decimal("990"), Decimal("1000"), Decimal("10")),
        ],
    )
    def test_adjacent_step(self, low: Decimal, nxt: Decimal, step: Decimal) -> None:
        i = index_of(low)
        assert LADDER[i + 1] == nxt
        assert LADDER[i + 1] - LADDER[i] == step


class TestPriceOf:
    def test_known_indices(self) -> None:
        assert price_of(0) == Decimal("1.01")
        assert price_of(len(LADDER) - 1) == Decimal("1000")

    def test_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError):
            price_of(-1)
        with pytest.raises(ValueError):
            price_of(len(LADDER))

    def test_float_index_rejected(self) -> None:
        with pytest.raises(TypeError):
            price_of(3.0)  # type: ignore[arg-type]

    def test_bool_index_rejected(self) -> None:
        # bool is an int subclass; a boolean is not a tick index.
        with pytest.raises(TypeError):
            price_of(True)  # type: ignore[arg-type]


class TestIndexOf:
    def test_maps_price_to_index(self) -> None:
        assert index_of(Decimal("1.01")) == 0
        assert index_of(Decimal("1000")) == len(LADDER) - 1

    def test_representation_independent(self) -> None:
        # Decimal equality is by value; scale must not matter.
        assert index_of(Decimal("2")) == index_of(Decimal("2.0")) == index_of(Decimal("2.00"))

    def test_price_off_ladder_raises(self) -> None:
        for bad in (Decimal("1.005"), Decimal("2.01"), Decimal("2.03"), Decimal("1000.01"), Decimal("0.5")):
            with pytest.raises(ValueError):
                index_of(bad)

    def test_float_price_rejected(self) -> None:
        with pytest.raises(TypeError):
            index_of(2.0)  # type: ignore[arg-type]


class TestPredicates:
    def test_is_valid_index(self) -> None:
        assert is_valid_index(0)
        assert is_valid_index(349)
        assert not is_valid_index(-1)
        assert not is_valid_index(350)
        assert not is_valid_index(True)

    def test_is_on_ladder(self) -> None:
        assert is_on_ladder(Decimal("3.05"))
        assert not is_on_ladder(Decimal("3.06"))
        assert not is_on_ladder(2.0)  # float is never on the ladder
