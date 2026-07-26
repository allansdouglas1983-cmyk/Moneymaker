"""Tests for pricing upcoming matches.

This is the part a person would actually run, so the tests are about the ways a tool that
prices real fixtures can mislead: a probability that silently comes from somewhere other
than it claims, a break-even that forgets commission, an edge computed off the wrong bound,
and — the one the whole programme is organised around — anything that reads as a
recommendation to bet.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from tennis_edge.residual_model import ResidualModel
from tennis_edge.upcoming import (
    Fixture,
    UpcomingPrediction,
    break_even_probability,
    price_fixture,
)


def model(**coefficients: float) -> ResidualModel:
    names = tuple(coefficients) or ("rank_gap",)
    return ResidualModel(
        coefficients=dict(coefficients) or {"rank_gap": 0.0},
        feature_names=names, l2=25.0, trained_rows=1000,
        trained_from=dt.date(2012, 1, 1), trained_through=dt.date(2026, 5, 1),
        feature_set_version="residual-v1",
    )


def fixture(*, odds_a: float = 2.0, odds_b: float = 2.0) -> Fixture:
    return Fixture(date=dt.date(2026, 8, 1), tour="ATP", player_a="Smith A.",
                   player_b="Jones B.", surface="Hard", best_of=3,
                   odds_a=Decimal(str(odds_a)), odds_b=Decimal(str(odds_b)))


class TestBreakEven:
    def test_commission_raises_the_break_even_above_one_over_odds(self) -> None:
        """The error that credits a strategy with money the exchange keeps."""
        plain = break_even_probability(Decimal("2.0"), commission=Decimal("0"))
        charged = break_even_probability(Decimal("2.0"), commission=Decimal("0.02"))
        assert plain == pytest.approx(0.5)
        assert charged > plain

    def test_it_matches_the_governed_formula(self) -> None:
        """p = 1 / (1 + (O-1)(1-c)), the SPEC-110 definition."""
        assert break_even_probability(
            Decimal("3.0"), commission=Decimal("0.05")
        ) == pytest.approx(1 / (1 + 2 * 0.95))

    def test_worse_odds_need_a_higher_probability(self) -> None:
        assert (break_even_probability(Decimal("1.5"), commission=Decimal("0.02"))
                > break_even_probability(Decimal("3.0"), commission=Decimal("0.02")))

    def test_odds_at_or_below_evens_are_refused(self) -> None:
        with pytest.raises(ValueError, match="above 1"):
            break_even_probability(Decimal("1.0"), commission=Decimal("0.02"))


class TestPricing:
    def test_a_zero_coefficient_model_returns_the_market(self) -> None:
        """The correct degenerate case: absent evidence, the price stands."""
        result = price_fixture(fixture(), {"rank_gap": 5.0}, model(rank_gap=0.0))
        assert result.probability_a == pytest.approx(result.market_probability_a)

    def test_the_market_probability_is_de_vigged(self) -> None:
        """A 1.8/2.1 book overrounds; the two sides must still sum to one."""
        result = price_fixture(fixture(odds_a=1.8, odds_b=2.1), {}, model(rank_gap=0.0))
        assert result.market_probability_a + result.market_probability_b == pytest.approx(1.0)

    def test_the_two_sides_of_the_model_probability_sum_to_one(self) -> None:
        result = price_fixture(fixture(), {"rank_gap": 2.0}, model(rank_gap=0.3))
        assert result.probability_a + result.probability_b == pytest.approx(1.0)

    def test_fair_odds_invert_the_probability(self) -> None:
        result = price_fixture(fixture(), {"rank_gap": 1.0}, model(rank_gap=0.2))
        assert float(result.fair_odds_a) == pytest.approx(1 / result.probability_a,
                                                          rel=1e-3)

    def test_the_edge_is_measured_against_the_commission_aware_break_even(self) -> None:
        result = price_fixture(fixture(), {"rank_gap": 1.0}, model(rank_gap=0.5))
        assert result.edge_a == pytest.approx(
            result.probability_a - break_even_probability(
                result.fixture.odds_a, commission=result.commission))

    def test_an_unknown_feature_is_refused(self) -> None:
        """Pricing with a feature set the model never saw would be invisible downstream."""
        with pytest.raises(ValueError, match="unknown feature"):
            price_fixture(fixture(), {"smuggled": 1.0}, model(rank_gap=0.2))

    def test_a_missing_feature_is_allowed_and_contributes_nothing(self) -> None:
        """Absence is normal — a debutant has no pyramid record — and must not raise."""
        result = price_fixture(fixture(), {}, model(rank_gap=0.5))
        assert result.probability_a == pytest.approx(result.market_probability_a)


class TestItNeverRecommends:
    """The property the whole programme is organised around."""

    def test_recommendation_is_pinned_regardless_of_edge(self) -> None:
        for coefficient in (-5.0, 0.0, 5.0):
            for odds in (1.01, 2.0, 100.0):
                result = price_fixture(fixture(odds_a=odds), {"rank_gap": 3.0},
                                       model(rank_gap=coefficient))
                assert result.recommendation == "NOT_EVALUATED"

    def test_the_field_cannot_be_set_to_anything_else(self) -> None:
        result = price_fixture(fixture(), {}, model(rank_gap=0.0))
        with pytest.raises(Exception):
            object.__setattr__  # noqa: B018 - frozen dataclass, checked below
            result.recommendation = "BET"  # type: ignore[misc]

    def test_a_large_positive_edge_still_reports_not_evaluated(self) -> None:
        result = price_fixture(fixture(odds_a=50.0), {"rank_gap": 3.0},
                               model(rank_gap=2.0))
        assert result.edge_a > 0.0
        assert result.recommendation == "NOT_EVALUATED"


class TestSerialisation:
    def test_a_prediction_renders_without_losing_its_caveat(self) -> None:
        result = price_fixture(fixture(), {"rank_gap": 1.0}, model(rank_gap=0.3))
        line = result.render()
        assert "NOT_EVALUATED" in line
        assert "Smith A." in line

    def test_the_model_digest_travels_with_the_prediction(self) -> None:
        """A row that cannot name the model that produced it cannot be audited."""
        fitted = model(rank_gap=0.3)
        result = price_fixture(fixture(), {"rank_gap": 1.0}, fitted)
        assert result.model_digest == fitted.digest

    def test_as_dict_is_json_safe(self) -> None:
        import json

        result = price_fixture(fixture(), {"rank_gap": 1.0}, model(rank_gap=0.3))
        assert json.loads(json.dumps(result.as_dict()))["recommendation"] == "NOT_EVALUATED"


def test_prediction_is_frozen() -> None:
    assert UpcomingPrediction.__dataclass_params__.frozen  # type: ignore[attr-defined]
