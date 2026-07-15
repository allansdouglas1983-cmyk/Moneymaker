"""Three prices are distinct types (SPEC-051).

`p_market_info`, `odds_exec`, `p_close` are distinct types; the type system must prevent
passing `p_close` or `p_market_info` where `odds_exec` is required. Here we assert the
structural distinctness and per-type validation; the consuming-function guard is tested with
the EV function (SPEC-050).
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from l5_decision.ladder import index_of
from l5_decision.prices import ClosePrice, MarketInfoPrice, OddsExec

pytestmark = pytest.mark.spec("SPEC-051")


class TestDistinctTypes:
    def test_the_three_types_are_unrelated(self) -> None:
        types = (OddsExec, MarketInfoPrice, ClosePrice)
        for a in types:
            for b in types:
                if a is not b:
                    assert not issubclass(a, b)

    def test_same_tick_different_type_are_not_equal(self) -> None:
        # OddsExec and ClosePrice can share a tick index but must never be interchangeable.
        # object-typed bindings: mypy already proves these types are non-overlapping (that IS
        # the SPEC-051 guarantee), so the runtime inequality is asserted via `object`.
        a: object = OddsExec(tick_index=100)
        b: object = ClosePrice(tick_index=100)
        assert a != b


class TestOddsExec:
    def test_decimal_odds_from_ladder(self) -> None:
        o = OddsExec.from_decimal(Decimal("3.0"))
        assert o.tick_index == index_of(Decimal("3"))
        assert o.decimal_odds == Decimal("3")

    def test_invalid_tick_index_rejected(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            OddsExec(tick_index=-1)
        with pytest.raises((ValueError, TypeError)):
            OddsExec(tick_index=350)

    def test_off_ladder_decimal_rejected(self) -> None:
        with pytest.raises(ValueError):
            OddsExec.from_decimal(Decimal("3.03"))

    def test_frozen(self) -> None:
        o = OddsExec(tick_index=10)
        with pytest.raises((ValueError, TypeError)):
            o.tick_index = 11


class TestMarketInfoPrice:
    def test_valid_probability(self) -> None:
        assert MarketInfoPrice(implied_probability=Decimal("0.4")).implied_probability == Decimal("0.4")

    @pytest.mark.parametrize("bad", [Decimal("0"), Decimal("1"), Decimal("-0.1"), Decimal("1.5")])
    def test_probability_bounds(self, bad: Decimal) -> None:
        with pytest.raises((ValueError, TypeError)):
            MarketInfoPrice(implied_probability=bad)


class TestClosePrice:
    def test_valid(self) -> None:
        c = ClosePrice(tick_index=index_of(Decimal("5")))
        assert c.decimal_odds == Decimal("5")

    def test_invalid_index_rejected(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            ClosePrice(tick_index=999)
