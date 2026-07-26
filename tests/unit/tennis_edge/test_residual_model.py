"""Tests for the residual model as a saved artefact.

The fit itself is tested in ``test_residual_fit.py``. These cover what turns a fit into
something that can be deployed: that it round-trips exactly, that it refuses to price a
match whose features it was not trained on, and that a saved model cannot be quietly
mistaken for a different one.
"""
from __future__ import annotations

import datetime as dt
import math
from pathlib import Path

import pytest

from tennis_edge.feature_cache import FeatureRow
from tennis_edge.residual_model import (
    ResidualModel,
    fit_model,
    load_model,
    save_model,
)


def row(*, logit: float, won: int, date: dt.date | None = None,
        **features: float) -> FeatureRow:
    return FeatureRow(date=date or dt.date(2020, 1, 1), tour="ATP",
                      player_a="Smith A.", player_b="Jones B.",
                      market_logit=logit, features=dict(features), won=won,
                      odds_a={}, odds_b={})


def sample(wins: int = 700, losses: int = 300) -> list[FeatureRow]:
    return ([row(logit=0.0, won=1, x=1.0)] * wins
            + [row(logit=0.0, won=0, x=1.0)] * losses)


class TestFitting:
    def test_a_fit_records_what_it_was_trained_on(self) -> None:
        rows = [row(logit=0.0, won=1, x=1.0, date=dt.date(2019, 5, 1))] * 500 + \
               [row(logit=0.0, won=0, x=1.0, date=dt.date(2021, 5, 1))] * 500
        model = fit_model(rows, ["x"])
        assert model.trained_rows == 1000
        assert model.trained_from == dt.date(2019, 5, 1)
        assert model.trained_through == dt.date(2021, 5, 1)

    def test_the_coefficients_are_the_fit(self) -> None:
        model = fit_model(sample(), ["x"])
        assert model.coefficients["x"] > 0.5

    def test_an_empty_training_set_is_refused(self) -> None:
        """Silently returning a zero model would look exactly like "the price is right"."""
        with pytest.raises(ValueError, match="no training rows"):
            fit_model([], ["x"])

    def test_no_feature_names_is_refused(self) -> None:
        with pytest.raises(ValueError, match="no features"):
            fit_model(sample(), [])


class TestPricing:
    def test_zero_coefficients_reproduce_the_market(self) -> None:
        model = ResidualModel(coefficients={"x": 0.0}, feature_names=("x",),
                              l2=25.0, trained_rows=1, trained_from=dt.date(2020, 1, 1),
                              trained_through=dt.date(2020, 1, 1),
                              feature_set_version="test")
        assert model.probability(0.5, {"x": 3.0}) == pytest.approx(
            1 / (1 + math.exp(-0.5)))

    def test_a_missing_feature_contributes_nothing(self) -> None:
        """Absence must not act as a zero *value* — it must act as no term at all."""
        model = fit_model(sample(), ["x"])
        assert model.probability(0.0, {}) == pytest.approx(0.5)

    def test_an_unknown_feature_is_refused_not_ignored(self) -> None:
        """Silently dropping it would price a match the model was never trained for."""
        model = fit_model(sample(), ["x"])
        with pytest.raises(ValueError, match="unknown feature"):
            model.probability(0.0, {"x": 1.0, "smuggled": 5.0})

    def test_probability_moves_the_right_way(self) -> None:
        model = fit_model(sample(), ["x"])
        assert model.probability(0.0, {"x": 1.0}) > model.probability(0.0, {"x": -1.0})

    def test_probabilities_stay_strictly_inside_zero_and_one(self) -> None:
        model = fit_model(sample(), ["x"])
        for logit in (-50.0, 0.0, 50.0):
            p = model.probability(logit, {"x": 100.0})
            assert 0.0 < p < 1.0


class TestPersistence:
    def test_a_saved_model_round_trips_exactly(self, tmp_path: Path) -> None:
        model = fit_model(sample(), ["x"])
        path = tmp_path / "model.json"
        save_model(path, model)
        assert load_model(path) == model

    def test_the_digest_changes_when_a_coefficient_does(self) -> None:
        """The digest is how a ledger row proves which model produced it."""
        first = fit_model(sample(700, 300), ["x"])
        second = fit_model(sample(600, 400), ["x"])
        assert first.digest != second.digest

    def test_the_digest_survives_a_round_trip(self, tmp_path: Path) -> None:
        model = fit_model(sample(), ["x"])
        path = tmp_path / "model.json"
        save_model(path, model)
        assert load_model(path).digest == model.digest

    def test_a_foreign_file_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "model.json"
        path.write_text('{"kind": "something-else"}', encoding="utf-8")
        with pytest.raises(ValueError, match="not a residual model"):
            load_model(path)
