"""The predictor: one match in, one calibrated probability out, with its reasons.

Built around what seventeen years of out-of-sample fitting actually support, not around
what would be nice. The market carries essentially all the information; the fitted model
weight is indistinguishable from zero. So the predictor's answer is the price, recalibrated
— and it says so, rather than dressing a market echo up as a model.

The tests below exist mostly to stop it overclaiming.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from tennis_edge.combine import Combination
from tennis_edge.predictor import (
    Basis,
    Reason,
    predict,
)

FITTED = Combination(alpha=-0.005, beta=0.955, n_train=60_000,
                     alpha_se=0.004, beta_se=0.012, covariance=-1e-6)


# ------------------------------------------------------------------ basis


def test_a_price_and_a_model_view_give_a_recalibrated_market() -> None:
    result = predict(p_model=0.62, p_market=0.55, combination=FITTED)
    assert result.basis is Basis.MARKET_RECALIBRATED
    assert 0.5 < result.probability_a < 0.6


def test_no_price_falls_back_to_the_model_and_says_so() -> None:
    """A model-only answer is a much weaker claim and must be labelled, never blended
    silently into the same output as a priced one."""
    result = predict(p_model=0.62, p_market=None, combination=FITTED)
    assert result.basis is Basis.MODEL_ONLY
    assert result.probability_a == pytest.approx(0.62)
    assert Reason.NO_MARKET_PRICE in result.reasons


def test_no_model_view_still_prices_from_the_market() -> None:
    result = predict(p_model=None, p_market=0.55, combination=FITTED)
    assert result.basis is Basis.MARKET_ONLY
    assert Reason.NO_MODEL_VIEW in result.reasons


def test_neither_input_refuses() -> None:
    """Nothing in, nothing out. There is no default probability."""
    with pytest.raises(ValueError, match="no price and no model"):
        predict(p_model=None, p_market=None, combination=FITTED)


# ------------------------------------------------------------------ honesty


def test_the_model_weight_is_reported_so_it_cannot_be_overstated() -> None:
    result = predict(p_model=0.62, p_market=0.55, combination=FITTED)
    assert result.model_weight == pytest.approx(FITTED.model_share, abs=1e-9)
    assert result.model_weight < 0.02


def test_a_negligible_model_weight_is_flagged() -> None:
    """The finding that matters, surfaced on every prediction rather than buried in a
    report nobody rereads."""
    result = predict(p_model=0.62, p_market=0.55, combination=FITTED)
    assert Reason.MODEL_WEIGHT_NEGLIGIBLE in result.reasons


def test_a_material_model_weight_is_not_flagged() -> None:
    strong = Combination(alpha=0.6, beta=0.6, n_train=60_000,
                         alpha_se=0.02, beta_se=0.02, covariance=0.0)
    result = predict(p_model=0.62, p_market=0.55, combination=strong)
    assert Reason.MODEL_WEIGHT_NEGLIGIBLE not in result.reasons


def test_the_interval_brackets_the_estimate() -> None:
    result = predict(p_model=0.62, p_market=0.55, combination=FITTED)
    assert result.low < result.probability_a < result.high


def test_a_large_model_market_disagreement_is_flagged() -> None:
    result = predict(p_model=0.90, p_market=0.40, combination=FITTED)
    assert Reason.MODEL_DISAGREES_WITH_MARKET in result.reasons


def test_agreement_is_not_flagged_as_disagreement() -> None:
    result = predict(p_model=0.56, p_market=0.55, combination=FITTED)
    assert Reason.MODEL_DISAGREES_WITH_MARKET not in result.reasons


# ------------------------------------------------------------------ money


def test_fair_odds_are_the_reciprocal_of_the_probability() -> None:
    result = predict(p_model=None, p_market=0.5, combination=FITTED)
    assert float(result.fair_odds_a) == pytest.approx(1.0 / result.probability_a, rel=1e-6)


def test_expected_value_needs_a_quoted_price() -> None:
    result = predict(p_model=0.62, p_market=0.55, combination=FITTED)
    assert result.expected_value_a is None


def test_expected_value_uses_the_quoted_price_after_commission() -> None:
    result = predict(p_model=None, p_market=0.5, combination=FITTED,
                     quoted_odds_a=Decimal("3.0"))
    assert result.expected_value_a is not None
    # SPEC-050: p(O-1)(1-c) - (1-p) at p = 0.5, O = 3.0, c = 0.02
    assert result.expected_value_a == pytest.approx(0.5 * 2.0 * 0.98 - 0.5)


def test_a_positive_expectation_is_flagged_but_authorises_nothing() -> None:
    result = predict(p_model=None, p_market=0.5, combination=FITTED,
                     quoted_odds_a=Decimal("3.0"))
    assert Reason.PRICE_ABOVE_FAIR in result.reasons
    assert result.recommendation == "NOT_EVALUATED", (
        "the predictor states probabilities; it never authorises a bet"
    )


def test_a_negative_expectation_is_flagged() -> None:
    result = predict(p_model=None, p_market=0.5, combination=FITTED,
                     quoted_odds_a=Decimal("1.5"))
    assert Reason.PRICE_BELOW_FAIR in result.reasons


def test_an_off_ladder_quote_is_refused() -> None:
    with pytest.raises(ValueError, match="off-ladder"):
        predict(p_model=None, p_market=0.5, combination=FITTED,
                quoted_odds_a=Decimal("2.03"))


def test_probabilities_are_complementary() -> None:
    result = predict(p_model=0.62, p_market=0.55, combination=FITTED)
    assert result.probability_a + result.probability_b == pytest.approx(1.0)


def test_the_recommendation_is_always_not_evaluated() -> None:
    """No input combination may produce anything that reads as advice."""
    for model, market in ((0.99, 0.01), (0.5, 0.5), (0.01, 0.99)):
        result = predict(p_model=model, p_market=market, combination=FITTED,
                         quoted_odds_a=Decimal("5.0"))
        assert result.recommendation == "NOT_EVALUATED"
