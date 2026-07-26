"""Metric tests — the scoreboard has to be right before any model is judged on it."""
from __future__ import annotations

import math
import random

import pytest

from tennis_edge.metrics import (
    BetResult,
    bootstrap_ratio_by_cluster,
    brier,
    brier_decomposition,
    calibration_fit,
    clv_beat,
    log_loss,
    score,
    summarise_bets,
)


def test_log_loss_matches_hand_computation() -> None:
    assert log_loss([0.5, 0.5], [1, 0]) == pytest.approx(math.log(2))
    assert log_loss([0.9], [1]) == pytest.approx(-math.log(0.9))
    assert log_loss([0.9], [0]) == pytest.approx(-math.log(0.1))


def test_log_loss_of_a_certain_correct_forecast_is_near_zero() -> None:
    assert log_loss([1.0], [1]) < 1e-12


def test_log_loss_of_a_certain_wrong_forecast_is_finite_not_infinite() -> None:
    """Clipping keeps one catastrophic forecast from making a whole scorecard unreadable."""
    assert math.isfinite(log_loss([1.0], [0]))


def test_brier_matches_hand_computation() -> None:
    assert brier([0.7, 0.2], [1, 0]) == pytest.approx((0.09 + 0.04) / 2)


def test_brier_decomposition_identity_holds() -> None:
    rng = random.Random(11)
    probabilities = [rng.random() for _ in range(4000)]
    outcomes = [1 if rng.random() < p else 0 for p in probabilities]
    decomposition = brier_decomposition(probabilities, outcomes)
    assert decomposition.check(), "the identity must reconstruct the binned Brier exactly"
    # Binning cannot make the score look better than it is.
    assert decomposition.binning_loss >= -1e-12


def test_a_perfectly_calibrated_forecast_gives_slope_one_intercept_zero() -> None:
    rng = random.Random(7)
    probabilities = [0.05 + 0.9 * rng.random() for _ in range(30000)]
    outcomes = [1 if rng.random() < p else 0 for p in probabilities]
    fit = calibration_fit(probabilities, outcomes)
    assert fit.slope == pytest.approx(1.0, abs=0.06)
    assert fit.intercept == pytest.approx(0.0, abs=0.06)


def test_an_overconfident_forecast_reports_slope_below_one() -> None:
    """Slope < 1 is the signature of predictions that are too extreme — the failure mode
    that destroys Kelly staking."""
    rng = random.Random(3)
    truths = [0.2 + 0.6 * rng.random() for _ in range(20000)]
    outcomes = [1 if rng.random() < p else 0 for p in truths]
    # Push every forecast away from 0.5, i.e. claim more certainty than is warranted.
    stretched = [1.0 / (1.0 + math.exp(-2.0 * math.log(p / (1 - p)))) for p in truths]
    assert calibration_fit(stretched, outcomes).slope < 1.0


def test_clv_is_zero_when_you_take_exactly_the_fair_price() -> None:
    assert clv_beat(2.0, 0.5) == pytest.approx(0.0)
    assert clv_beat(2.5, 0.5) == pytest.approx(0.25)
    assert clv_beat(1.8, 0.5) == pytest.approx(-0.1)


def test_bet_profit_charges_commission_only_on_a_win() -> None:
    winner = BetResult(cluster="d", odds=2.0, stake=1.0, won=True, commission=0.05)
    loser = BetResult(cluster="d", odds=2.0, stake=1.0, won=False, commission=0.05)
    assert winner.profit == pytest.approx(0.95)
    assert loser.profit == pytest.approx(-1.0)


def test_summary_reports_roi_and_a_containing_interval() -> None:
    rng = random.Random(5)
    bets = [
        BetResult(cluster=i // 10, odds=2.0, stake=1.0, won=rng.random() < 0.55, commission=0.0)
        for i in range(2000)
    ]
    summary = summarise_bets(bets, bootstrap=200)
    assert summary.bets == 2000
    assert summary.roi_ci95[0] <= summary.roi <= summary.roi_ci95[1]
    assert summary.max_drawdown >= 0.0


def test_bootstrap_is_deterministic_for_a_fixed_seed() -> None:
    rows = [(i % 50, float(i % 3) - 1.0, 1.0) for i in range(500)]
    first = bootstrap_ratio_by_cluster(rows, draws=100, seed=42)
    second = bootstrap_ratio_by_cluster(rows, draws=100, seed=42)
    assert first == second


def test_clustering_widens_the_interval_versus_treating_bets_as_independent() -> None:
    """Bets on the same day are correlated. If every bet in a cluster shares an outcome,
    the clustered interval must be much wider than a naive per-bet interval would be —
    this is exactly the correction that stops a noise strategy looking significant."""
    clustered = [(day, 1.0 if day % 2 else -1.0, 1.0) for day in range(40) for _ in range(25)]
    independent = [(index, 1.0 if index % 2 else -1.0, 1.0) for index in range(1000)]
    wide = bootstrap_ratio_by_cluster(clustered, draws=400, seed=1)
    narrow = bootstrap_ratio_by_cluster(independent, draws=400, seed=1)
    assert (wide[1] - wide[0]) > (narrow[1] - narrow[0])


def test_scorecard_reports_every_component() -> None:
    rng = random.Random(9)
    probabilities = [rng.random() for _ in range(1000)]
    outcomes = [1 if rng.random() < p else 0 for p in probabilities]
    card = score(probabilities, outcomes)
    assert card.n == 1000
    assert card.decomposition.check()
    assert "logloss" in card.report("x")
