"""Stage-two market combination: score = alpha*logit(model) + beta*logit(market).

This is the canonical way to ask "does my model add anything to the price?" — fit both
weights by maximum likelihood on the winner and read what the fit gives the model. A fixed
shrinkage constant (the frozen policy's 10%) asserts an answer; this measures one.

The fit must be strictly time-respecting. A combination fitted on data that includes the
match it later prices is not a forecast, and the resulting weights would flatter the model
exactly where it matters most.
"""
from __future__ import annotations

import math

import pytest

from tennis_edge.combine import (
    Combination,
    apply_combination,
    fit_combination,
    logit,
)


def _rows(alpha: float, beta: float, n: int = 4000) -> list[tuple[float, float, int]]:
    """Synthetic rows whose true generating weights are (alpha, beta).

    Deterministic, no RNG: outcomes are assigned to match the implied probability as
    closely as an integer count allows, so the recovered fit is checkable exactly.
    """
    rows: list[tuple[float, float, int]] = []
    for i in range(n):
        p_model = 0.05 + 0.9 * ((i * 7919) % 1000) / 1000.0
        p_market = 0.05 + 0.9 * ((i * 104729) % 997) / 997.0
        z = alpha * logit(p_model) + beta * logit(p_market)
        p_true = 1.0 / (1.0 + math.exp(-z))
        # Deterministic outcome assignment tracking p_true.
        rows.append((p_model, p_market, 1 if ((i * 2654435761) % 1000) / 1000.0 < p_true
                     else 0))
    return rows


# ------------------------------------------------------------------ fitting


def test_the_fit_recovers_a_market_only_generator() -> None:
    """When outcomes follow the market alone, the model must earn a weight near zero.
    A method that cannot return 'your model adds nothing' is not a measurement."""
    fit = fit_combination(_rows(alpha=0.0, beta=1.0))
    assert abs(fit.alpha) < 0.15
    assert fit.beta > 0.7


def test_the_fit_recovers_a_model_only_generator() -> None:
    fit = fit_combination(_rows(alpha=1.0, beta=0.0))
    assert fit.alpha > 0.7
    assert abs(fit.beta) < 0.15


def test_the_fit_recovers_a_genuine_blend() -> None:
    fit = fit_combination(_rows(alpha=0.5, beta=0.8))
    assert 0.25 < fit.alpha < 0.85
    assert 0.5 < fit.beta < 1.2


def test_the_fit_records_its_training_size() -> None:
    fit = fit_combination(_rows(alpha=0.3, beta=0.9, n=500))
    assert fit.n_train == 500


def test_too_few_rows_refuse_rather_than_return_noise() -> None:
    with pytest.raises(ValueError, match="at least"):
        fit_combination([(0.5, 0.5, 1)] * 3)


def test_a_degenerate_outcome_column_is_refused() -> None:
    """All-winners or all-losers cannot identify a logistic fit; it separates and the
    weights run away. Refusing is the honest answer, not a regularised guess."""
    rows = [(0.4, 0.6, 1)] * 200
    with pytest.raises(ValueError, match="both outcomes"):
        fit_combination(rows)


# ------------------------------------------------------------------ applying


def test_applying_identity_weights_returns_the_market() -> None:
    combination = Combination(alpha=0.0, beta=1.0, n_train=100)
    assert apply_combination(combination, 0.9, 0.3) == pytest.approx(0.3)


def test_applying_pure_model_weights_returns_the_model() -> None:
    combination = Combination(alpha=1.0, beta=0.0, n_train=100)
    assert apply_combination(combination, 0.9, 0.3) == pytest.approx(0.9)


def test_the_output_moves_with_the_model_when_alpha_is_positive() -> None:
    combination = Combination(alpha=0.4, beta=0.8, n_train=100)
    low = apply_combination(combination, 0.3, 0.5)
    high = apply_combination(combination, 0.7, 0.5)
    assert high > low


def test_the_output_moves_with_the_market() -> None:
    combination = Combination(alpha=0.4, beta=0.8, n_train=100)
    assert (apply_combination(combination, 0.5, 0.7)
            > apply_combination(combination, 0.5, 0.3))


def test_the_output_is_always_a_probability() -> None:
    combination = Combination(alpha=3.0, beta=3.0, n_train=100)
    for model, market in ((0.999, 0.999), (0.001, 0.001), (0.999, 0.001)):
        value = apply_combination(combination, model, market)
        assert 0.0 < value < 1.0


def test_extreme_inputs_do_not_produce_infinities() -> None:
    combination = Combination(alpha=1.0, beta=1.0, n_train=100)
    assert 0.0 < apply_combination(combination, 0.0, 1.0) < 1.0
