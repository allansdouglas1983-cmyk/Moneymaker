"""Three prices are distinct types (SPEC-051).

`p_market_info`, `odds_exec`, `p_close` are distinct types; the type system must prevent
passing `p_close` or `p_market_info` where `odds_exec` is required. Here we assert the
structural distinctness and per-type validation; the consuming-function guard is tested with
the EV function (SPEC-050).

GOVERNED TEST CORRECTION (A2, conceptual audit F-03, founder-approved 2026-07-17):
`ClosePrice` was an integer tick index, but neither declared close benchmark (BSP,
pre-suspension WAP) is tick-valued — both are weighted averages, generally off-ladder, and
no snapping rule exists or may be invented. `ClosePrice` now carries an exact `Decimal`
within the venue price range plus a benchmark-method identity. Tick indices remain for
TRANSACTABLE prices only (`OddsExec`, unchanged). Distinctness guarantees are unweakened.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from l5_decision.ladder import index_of
from l5_decision.prices import ClosePrice, MarketInfoPrice, OddsExec

pytestmark = pytest.mark.spec("SPEC-051")


def _close(odds: Decimal) -> ClosePrice:
    return ClosePrice(
        decimal_odds=odds,
        benchmark_method_id="bsp",
        benchmark_method_version="close-v1",
    )


class TestDistinctTypes:
    def test_the_three_types_are_unrelated(self) -> None:
        types = (OddsExec, MarketInfoPrice, ClosePrice)
        for a in types:
            for b in types:
                if a is not b:
                    assert not issubclass(a, b)

    def test_same_price_different_type_are_not_equal(self) -> None:
        # OddsExec and ClosePrice can represent the same decimal price but must never be
        # interchangeable. object-typed bindings: mypy already proves these types are
        # non-overlapping (that IS the SPEC-051 guarantee), so the runtime inequality is
        # asserted via `object`.
        a: object = OddsExec.from_decimal(Decimal("10"))
        b: object = _close(Decimal("10"))
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
    def test_off_ladder_reconciled_benchmark_is_representable(self) -> None:
        # THE F-03 case: BSP is a reconciled weighted average, generally off-ladder.
        # 4.73 is not a ladder tick (the 4-6 band steps by 0.1) and must be exact here.
        c = _close(Decimal("4.73"))
        assert c.decimal_odds == Decimal("4.73")
        assert c.benchmark_method_id == "bsp"
        assert c.benchmark_method_version == "close-v1"

    def test_on_ladder_value_also_representable(self) -> None:
        assert _close(Decimal("5")).decimal_odds == Decimal("5")

    @pytest.mark.parametrize("bad", [Decimal("1"), Decimal("1.005"), Decimal("1000.5"), Decimal("0")])
    def test_out_of_venue_range_rejected(self, bad: Decimal) -> None:
        # Bounds are the venue price range (ladder MIN_PRICE..MAX_PRICE) WITHOUT requiring
        # an on-ladder value — off-ladder inside the range is the whole point.
        with pytest.raises((ValueError, TypeError)):
            _close(bad)

    @pytest.mark.parametrize("bad_id", ["", "   "])
    def test_empty_benchmark_identity_rejected(self, bad_id: str) -> None:
        with pytest.raises((ValueError, TypeError)):
            ClosePrice(
                decimal_odds=Decimal("4.73"),
                benchmark_method_id=bad_id,
                benchmark_method_version="close-v1",
            )
        with pytest.raises((ValueError, TypeError)):
            ClosePrice(
                decimal_odds=Decimal("4.73"),
                benchmark_method_id="bsp",
                benchmark_method_version=bad_id,
            )

    def test_no_tick_index_surface_exists(self) -> None:
        # No snapping rule is declared anywhere (F-03); the type must not offer a tick
        # conversion that would imply one.
        c = _close(Decimal("4.73"))
        assert not hasattr(c, "tick_index")
