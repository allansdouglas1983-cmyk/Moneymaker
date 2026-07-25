"""De-vig tests. This module decides whether the market looks efficient or exploitable,
so its properties are pinned rather than spot-checked."""
from __future__ import annotations

import pytest

from typing import Callable, Sequence

from tennis_edge.devig import (
    DevigResult,
    DevigMethod,
    devig,
    multiplicative,
    overround,
    power,
    proportional,
    shin,
)

_Devigger = Callable[[Sequence[float]], DevigResult]
_ALL: tuple[_Devigger, ...] = (proportional, multiplicative, power, shin)


@pytest.mark.parametrize("method", _ALL)
@pytest.mark.parametrize("odds", [(1.5, 3.0), (1.05, 15.0), (2.0, 2.0), (1.9, 1.9), (1.2, 6.0)])
def test_probabilities_always_sum_to_one(
    method: _Devigger, odds: tuple[float, float]
) -> None:
    result = method(odds)
    assert abs(sum(result.probabilities) - 1.0) < 1e-9
    assert all(0.0 < p < 1.0 for p in result.probabilities)


@pytest.mark.parametrize("method", _ALL)
def test_ordering_is_preserved(method: _Devigger) -> None:
    """A shorter price must always imply a higher probability, whatever the method."""
    result = method((1.4, 3.5))
    assert result.probabilities[0] > result.probabilities[1]


def test_overround_is_the_book_sum_minus_one() -> None:
    assert overround((2.0, 2.0)) == pytest.approx(0.0)
    assert overround((1.9, 1.9)) == pytest.approx(2 / 1.9 - 1.0)


def test_fair_book_is_left_alone() -> None:
    """A book with no margin must pass through every method untouched."""
    for method in _ALL:
        result = method((2.0, 2.0))
        assert result.probabilities == pytest.approx((0.5, 0.5))


def test_power_and_shin_shift_probability_away_from_the_longshot() -> None:
    """The defining property: margin sits on the longshot, so removing it proportionally
    overstates the longshot. Power and Shin must both give the longshot LESS than
    proportional does, and correspondingly give the favourite more."""
    odds = (1.25, 4.5)
    prop = proportional(odds).probabilities
    for method in (power, shin):
        adjusted = method(odds).probabilities
        assert adjusted[1] < prop[1], f"{method.__name__} did not reduce the longshot"
        assert adjusted[0] > prop[0], f"{method.__name__} did not raise the favourite"


def test_multiplicative_is_proportional_under_another_name() -> None:
    odds = (1.7, 2.3)
    assert multiplicative(odds).probabilities == proportional(odds).probabilities
    assert multiplicative(odds).method is DevigMethod.MULTIPLICATIVE


def test_power_parameter_exceeds_one_for_an_overround_book() -> None:
    """Raw implied probabilities are each below 1, so shrinking their sum to 1 requires
    raising them to a power greater than 1 — which takes proportionally more off the
    longshot. A solver that returned k < 1 here would be inflating the book, not deflating it."""
    result = power((1.9, 1.9))
    assert result.parameter is not None and result.parameter > 1.0
    assert result.probabilities == pytest.approx((0.5, 0.5))


def test_power_parameter_falls_below_one_for_an_underround_book() -> None:
    result = power((2.1, 2.1))
    assert result.parameter is not None and result.parameter < 1.0


def test_shin_insider_fraction_is_a_proportion() -> None:
    result = shin((1.9, 1.9))
    assert result.parameter is not None and 0.0 <= result.parameter < 1.0


@pytest.mark.parametrize("bad", [(1.0, 2.0), (0.5, 2.0), (-1.0, 2.0)])
def test_prices_at_or_below_evens_are_refused(bad: tuple[float, float]) -> None:
    with pytest.raises(ValueError):
        proportional(bad)


def test_a_single_price_cannot_be_devigged() -> None:
    with pytest.raises(ValueError):
        devig((2.0,))


def test_dispatch_covers_every_method() -> None:
    for method in DevigMethod:
        result = devig((1.8, 2.1), method)
        assert result.method is method
