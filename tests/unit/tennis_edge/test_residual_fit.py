"""Tests for the residual fit — the numerical core of the candidate model.

Written because the fit was rewritten from name-keyed dictionaries to positional indices
for speed, and a speed rewrite of a numerical routine is exactly the kind of change that
silently alters an answer. These pin the behaviour, not the implementation.
"""
from __future__ import annotations

import datetime as dt
import math

import pytest

from tennis_edge.experiments.residual_edge import L2, Row, fit, predict


def row(*, logit: float, won: int, **features: float) -> Row:
    return Row(date=dt.date(2020, 1, 1), tour="ATP", player_a="A", player_b="B",
               market_logit=logit, features=dict(features), won=won,
               odds_a={}, odds_b={})


def balanced(feature_value: float, wins: int, losses: int, name: str = "x") -> list[Row]:
    """Rows at a 50/50 market price so any fitted signal comes from the feature alone."""
    return ([row(logit=0.0, won=1, **{name: feature_value})] * wins
            + [row(logit=0.0, won=0, **{name: feature_value})] * losses)


class TestRecovery:
    def test_a_feature_that_predicts_nothing_gets_a_zero_coefficient(self) -> None:
        rows = balanced(1.0, 500, 500)
        assert fit(rows, ["x"])["x"] == pytest.approx(0.0, abs=1e-6)

    def test_a_feature_that_predicts_wins_gets_a_positive_coefficient(self) -> None:
        rows = balanced(1.0, 700, 300)
        assert fit(rows, ["x"])["x"] > 0.5

    def test_the_sign_follows_the_data(self) -> None:
        assert fit(balanced(1.0, 300, 700), ["x"])["x"] < 0.0

    def test_the_market_offset_is_taken_as_given(self) -> None:
        """Rows already correctly priced leave nothing for the feature to explain."""
        p = 0.7
        z = math.log(p / (1 - p))
        rows = ([row(logit=z, won=1, x=1.0)] * 700 + [row(logit=z, won=0, x=1.0)] * 300)
        assert fit(rows, ["x"])["x"] == pytest.approx(0.0, abs=0.05)


class TestPenalty:
    def test_the_penalty_shrinks_toward_zero_not_away(self) -> None:
        rows = balanced(1.0, 700, 300)
        assert 0.0 < fit(rows, ["x"])["x"] < math.log(700 / 300)

    def test_a_thinner_sample_is_shrunk_harder(self) -> None:
        """The prior is that the price is right, so less evidence means less correction."""
        thin = fit(balanced(1.0, 70, 30), ["x"])["x"]
        thick = fit(balanced(1.0, 7000, 3000), ["x"])["x"]
        assert thin < thick

    def test_the_penalty_is_the_declared_constant(self) -> None:
        """Guards against L2 being quietly retuned: the value is part of the method."""
        assert L2 == 25.0


class TestMissingFeatures:
    def test_a_row_without_a_feature_does_not_vote_on_it(self) -> None:
        """Absence must not act as a zero — a zero is a claim, absence is not."""
        present = balanced(1.0, 700, 300)
        with_absent = present + [row(logit=0.0, won=0)] * 1000
        assert (fit(with_absent, ["x"])["x"]
                == pytest.approx(fit(present, ["x"])["x"], rel=1e-9))

    def test_a_feature_nobody_has_stays_at_zero(self) -> None:
        assert fit(balanced(1.0, 700, 300), ["x", "unseen"])["unseen"] == 0.0

    def test_two_features_are_fitted_together(self) -> None:
        rows = ([row(logit=0.0, won=1, x=1.0, y=-1.0)] * 700
                + [row(logit=0.0, won=0, x=1.0, y=-1.0)] * 300)
        beta = fit(rows, ["x", "y"])
        assert beta["x"] > 0.0 and beta["y"] < 0.0


class TestPredict:
    def test_prediction_reproduces_the_market_when_coefficients_are_zero(self) -> None:
        subject = row(logit=0.5, won=1, x=3.0)
        assert predict(subject, {"x": 0.0}) == pytest.approx(1 / (1 + math.exp(-0.5)))

    def test_prediction_moves_with_the_coefficient(self) -> None:
        subject = row(logit=0.0, won=1, x=1.0)
        assert predict(subject, {"x": 1.0}) > predict(subject, {"x": 0.0})

    def test_a_coefficient_for_an_absent_feature_is_ignored(self) -> None:
        subject = row(logit=0.0, won=1)
        assert predict(subject, {"x": 5.0}) == pytest.approx(0.5)
