"""EV at executable prices (SPEC-050).

EV = p·(O−1)·(1−c) − (1−p) per unit stake, single position only, using odds_exec (never
p_market_info, never p_close) and a conservative win-probability lower bound.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from l5_decision.ev import CommissionRate, WinProbabilityLowerBound, expected_value
from l5_decision.prices import ClosePrice, MarketInfoPrice, OddsExec

pytestmark = pytest.mark.spec("SPEC-050")


def _p(v: str) -> WinProbabilityLowerBound:
    return WinProbabilityLowerBound(value=Decimal(v))


def _c(v: str) -> CommissionRate:
    return CommissionRate(rate=Decimal(v))


def _odds(v: str) -> OddsExec:
    return OddsExec.from_decimal(Decimal(v))


class TestFormula:
    def test_known_value(self) -> None:
        # p=0.5, O=3, c=0.02 -> 0.5*2*0.98 - 0.5 = 0.98 - 0.5 = 0.48
        assert expected_value(_p("0.5"), _odds("3"), _c("0.02")) == Decimal("0.48")

    def test_zero_commission(self) -> None:
        # p=0.5, O=3, c=0 -> 0.5*2 - 0.5 = 0.5
        assert expected_value(_p("0.5"), _odds("3"), _c("0")) == Decimal("0.5")

    def test_result_is_decimal_never_float(self) -> None:
        assert isinstance(expected_value(_p("0.3"), _odds("4"), _c("0.05")), Decimal)

    def test_break_even_probability(self) -> None:
        # At O=3, c=0: EV=0 when p*(O-1) = (1-p) -> 2p = 1-p -> p=1/3
        ev = expected_value(_p("0.3333333333"), _odds("3"), _c("0"))
        assert abs(ev) < Decimal("0.0000001")


class TestUsesOddsExecOnly:
    def test_close_price_rejected_as_odds(self) -> None:
        # SPEC-050/051: p_close must never reach this function (shape per A2/F-03:
        # exact Decimal + benchmark identity — the refusal is type-based, not shape-based).
        close = ClosePrice(
            decimal_odds=Decimal("3"), benchmark_method_id="bsp", benchmark_method_version="close-v1"
        )
        with pytest.raises(TypeError):
            expected_value(_p("0.5"), close, _c("0"))  # type: ignore[arg-type]

    def test_market_info_price_rejected_as_odds(self) -> None:
        with pytest.raises(TypeError):
            expected_value(_p("0.5"), MarketInfoPrice(implied_probability=Decimal("0.3")), _c("0"))  # type: ignore[arg-type]

    def test_bare_probability_rejected_as_win_probability(self) -> None:
        # A point estimate / bare Decimal must not be consumable as the win probability.
        with pytest.raises(TypeError):
            expected_value(Decimal("0.5"), _odds("3"), _c("0"))  # type: ignore[arg-type]


class TestInputValidation:
    @pytest.mark.parametrize("bad", [Decimal("-0.01"), Decimal("1.01")])
    def test_probability_bounds(self, bad: Decimal) -> None:
        with pytest.raises((ValueError, TypeError)):
            WinProbabilityLowerBound(value=bad)

    @pytest.mark.parametrize("bad", [Decimal("-0.01"), Decimal("1")])
    def test_commission_bounds(self, bad: Decimal) -> None:
        with pytest.raises((ValueError, TypeError)):
            CommissionRate(rate=bad)
