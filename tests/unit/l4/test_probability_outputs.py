"""SPEC-036: separate probability outputs (p_fundamental / p_market_info / p_combined).

Behavioural coverage: unit-interval + lineage validation per wrapper type; race-level
normalisation (each PRESENT kind sums to 1 across active runners within 1e-9); explicit
missingness (accessors never fall back to another kind); type distinctness (cross-
construction is a runtime/type error, mirroring l5's three-price separation); p_market_info
is never labelled a model prediction (no model_digest field); builders wrap the real upstream
types (stage-one/combined float maps, l5's MarketInfoPrice) without ever inventing a value.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from l4_pricing.probability_outputs import (
    CombinedProbability,
    FundamentalProbability,
    MarketProbability,
    MissingProbabilityError,
    RaceProbabilityOutputs,
    RunnerProbabilities,
    assemble_race_probability_outputs,
    build_combined_probabilities,
    build_fundamental_probabilities,
    build_market_probabilities,
)
from l5_decision.prices import MarketInfoPrice

pytestmark = pytest.mark.spec("SPEC-036")


# --- wrapper-type validation -------------------------------------------------------------


def test_fundamental_probability_requires_open_unit_interval() -> None:
    FundamentalProbability(probability=Decimal("0.5"), model_digest="sha256:abc")
    for bad in (Decimal(0), Decimal(1), Decimal("-0.1"), Decimal("1.1")):
        with pytest.raises(ValidationError):
            FundamentalProbability(probability=bad, model_digest="sha256:abc")


def test_market_probability_requires_open_unit_interval() -> None:
    MarketProbability(probability=Decimal("0.5"), price_version="info-price-v1")
    with pytest.raises(ValidationError):
        MarketProbability(probability=Decimal(0), price_version="info-price-v1")


def test_combined_probability_requires_open_unit_interval() -> None:
    CombinedProbability(probability=Decimal("0.5"), model_digest="sha256:abc")
    with pytest.raises(ValidationError):
        CombinedProbability(probability=Decimal(1), model_digest="sha256:abc")


def test_fundamental_probability_requires_nonempty_model_digest() -> None:
    with pytest.raises(ValidationError):
        FundamentalProbability(probability=Decimal("0.5"), model_digest="")
    with pytest.raises(ValidationError):
        FundamentalProbability(probability=Decimal("0.5"), model_digest="   ")


def test_combined_probability_requires_nonempty_model_digest() -> None:
    with pytest.raises(ValidationError):
        CombinedProbability(probability=Decimal("0.5"), model_digest="")


def test_market_probability_requires_nonempty_price_version() -> None:
    with pytest.raises(ValidationError):
        MarketProbability(probability=Decimal("0.5"), price_version="")


def test_market_probability_is_never_labelled_a_model_prediction() -> None:
    """SPEC-036: p_market_info exposes no model_digest — the type cannot be mistaken for a
    model prediction even by accident (no attribute exists to alias)."""
    price = MarketProbability(probability=Decimal("0.5"), price_version="info-price-v1")
    assert not hasattr(price, "model_digest")
    assert set(MarketProbability.model_fields) == {"probability", "price_version"}


def test_fundamental_and_combined_expose_model_digest_not_price_version() -> None:
    fundamental = FundamentalProbability(probability=Decimal("0.5"), model_digest="sha256:abc")
    combined = CombinedProbability(probability=Decimal("0.5"), model_digest="sha256:def")
    assert not hasattr(fundamental, "price_version")
    assert not hasattr(combined, "price_version")


# --- type distinctness: cross-construction is a runtime and mypy type error --------------


def test_wrapper_types_reject_cross_construction_in_runner_probabilities() -> None:
    """A MarketProbability instance may never occupy the p_fundamental slot, even though
    both wrappers hold a `probability: Decimal`. Distinct pydantic classes with strict mode
    make this a real ValidationError, not silent duck-typed acceptance."""
    market = MarketProbability(probability=Decimal("0.4"), price_version="info-price-v1")
    with pytest.raises(ValidationError):
        RunnerProbabilities(runner_id=1, p_fundamental=market)  # type: ignore[arg-type]


def test_combined_cannot_occupy_the_market_info_slot() -> None:
    combined = CombinedProbability(probability=Decimal("0.4"), model_digest="sha256:abc")
    with pytest.raises(ValidationError):
        RunnerProbabilities(runner_id=1, p_market_info=combined)  # type: ignore[arg-type]


def test_fundamental_cannot_occupy_the_combined_slot() -> None:
    fundamental = FundamentalProbability(probability=Decimal("0.4"), model_digest="sha256:abc")
    with pytest.raises(ValidationError):
        RunnerProbabilities(runner_id=1, p_combined=fundamental)  # type: ignore[arg-type]


def test_coinciding_values_across_kinds_are_allowed_but_not_aliased() -> None:
    """Values may coincide (a fundamental model may agree numerically with the combined
    output) — that is permitted. What is forbidden is one kind's *object* standing in for
    another's slot, which the distinct types above already prevent."""
    fundamental = FundamentalProbability(probability=Decimal("0.5"), model_digest="sha256:abc")
    combined = CombinedProbability(probability=Decimal("0.5"), model_digest="sha256:def")
    runner = RunnerProbabilities(
        runner_id=1,
        p_fundamental=fundamental,
        p_combined=combined,
        p_market_info=None,
        p_market_info_missing_reason="book_crossed_at_decision_time",
    )
    assert runner.fundamental().probability == runner.combined().probability
    assert runner.fundamental() is not runner.combined()


# --- explicit missingness: never a silent fallback ----------------------------------------


def test_missing_kind_requires_a_nonempty_reason() -> None:
    with pytest.raises(ValidationError):
        RunnerProbabilities(runner_id=1)  # all three absent, no reasons given


def test_present_kind_must_not_also_carry_a_missing_reason() -> None:
    fundamental = FundamentalProbability(probability=Decimal("0.5"), model_digest="sha256:abc")
    with pytest.raises(ValidationError):
        RunnerProbabilities(
            runner_id=1,
            p_fundamental=fundamental,
            p_fundamental_missing_reason="should not coexist",
            p_market_info=None,
            p_market_info_missing_reason="no_book",
            p_combined=None,
            p_combined_missing_reason="no_model",
        )


def test_accessor_raises_missing_probability_error_with_reason() -> None:
    runner = RunnerProbabilities(
        runner_id=7,
        p_fundamental=None,
        p_fundamental_missing_reason="stage_one_model_not_yet_fitted_for_horizon",
        p_market_info=None,
        p_market_info_missing_reason="crossed_book_at_decision_time",
        p_combined=None,
        p_combined_missing_reason="stage_two_model_unavailable",
    )
    with pytest.raises(MissingProbabilityError) as fundamental_exc:
        runner.fundamental()
    assert fundamental_exc.value.reason == "stage_one_model_not_yet_fitted_for_horizon"
    assert fundamental_exc.value.runner_id == 7

    with pytest.raises(MissingProbabilityError) as market_exc:
        runner.market_info()
    assert market_exc.value.reason == "crossed_book_at_decision_time"

    with pytest.raises(MissingProbabilityError):
        runner.combined()


def test_missing_fundamental_never_returns_market_or_combined_values() -> None:
    """The literal anti-substitution assertion: when p_fundamental is absent, no accessor
    silently returns a market or combined number instead."""
    market = MarketProbability(probability=Decimal("0.6"), price_version="info-price-v1")
    combined = CombinedProbability(probability=Decimal("0.6"), model_digest="sha256:abc")
    runner = RunnerProbabilities(
        runner_id=3,
        p_fundamental=None,
        p_fundamental_missing_reason="no_independent_model_for_this_field_size",
        p_market_info=market,
        p_combined=combined,
    )
    with pytest.raises(MissingProbabilityError):
        runner.fundamental()
    # the other two kinds remain independently readable — proving the absence of
    # p_fundamental did not get patched over by either of them.
    assert runner.market_info().probability == Decimal("0.6")
    assert runner.combined().probability == Decimal("0.6")


# --- race-level normalisation --------------------------------------------------------------


def _fundamental(p: str, digest: str = "sha256:abc") -> FundamentalProbability:
    return FundamentalProbability(probability=Decimal(p), model_digest=digest)


def test_race_normalisation_holds_within_tolerance() -> None:
    race = RaceProbabilityOutputs(
        race_id="r1",
        runners=(
            RunnerProbabilities(
                runner_id=1,
                p_fundamental=_fundamental("0.6"),
                p_market_info=None,
                p_market_info_missing_reason="no_book",
                p_combined=None,
                p_combined_missing_reason="no_model",
            ),
            RunnerProbabilities(
                runner_id=2,
                p_fundamental=_fundamental("0.4"),
                p_market_info=None,
                p_market_info_missing_reason="no_book",
                p_combined=None,
                p_combined_missing_reason="no_model",
            ),
        ),
    )
    assert race.runners[0].fundamental().probability + race.runners[1].fundamental().probability == Decimal("1.0")


def test_race_normalisation_fails_outside_tolerance() -> None:
    with pytest.raises(ValidationError):
        RaceProbabilityOutputs(
            race_id="r1",
            runners=(
                RunnerProbabilities(
                    runner_id=1,
                    p_fundamental=_fundamental("0.6"),
                    p_market_info=None,
                    p_market_info_missing_reason="no_book",
                    p_combined=None,
                    p_combined_missing_reason="no_model",
                ),
                RunnerProbabilities(
                    runner_id=2,
                    p_fundamental=_fundamental("0.5"),
                    p_market_info=None,
                    p_market_info_missing_reason="no_book",
                    p_combined=None,
                    p_combined_missing_reason="no_model",
                ),
            ),
        )


def test_partial_presence_of_a_kind_is_refused() -> None:
    """A kind present for one runner but absent for another is not a valid race-level state
    — the assembler must resolve it one way or the other, not leave a silent gap."""
    with pytest.raises(ValidationError):
        RaceProbabilityOutputs(
            race_id="r1",
            runners=(
                RunnerProbabilities(
                    runner_id=1,
                    p_fundamental=_fundamental("0.6"),
                    p_market_info=None,
                    p_market_info_missing_reason="no_book",
                    p_combined=None,
                    p_combined_missing_reason="no_model",
                ),
                RunnerProbabilities(
                    runner_id=2,
                    p_fundamental=None,
                    p_fundamental_missing_reason="excluded_runner",
                    p_market_info=None,
                    p_market_info_missing_reason="no_book",
                    p_combined=None,
                    p_combined_missing_reason="no_model",
                ),
            ),
        )


def test_race_requires_at_least_one_runner_and_unique_runner_ids() -> None:
    with pytest.raises(ValidationError):
        RaceProbabilityOutputs(race_id="empty", runners=())
    dup = RunnerProbabilities(
        runner_id=1,
        p_fundamental=_fundamental("0.6"),
        p_market_info=None,
        p_market_info_missing_reason="no_book",
        p_combined=None,
        p_combined_missing_reason="no_model",
    )
    with pytest.raises(ValueError):
        RaceProbabilityOutputs(race_id="dup", runners=(dup, dup))


# --- builders wrap the real upstream types -------------------------------------------------


def test_build_fundamental_probabilities_wraps_stage_one_style_predictions() -> None:
    wrapped = build_fundamental_probabilities({1: 0.6, 2: 0.4}, model_digest="sha256:stage-one")
    assert wrapped[1].probability == Decimal("0.6")
    assert wrapped[1].model_digest == "sha256:stage-one"
    assert wrapped[2].probability == Decimal("0.4")


def test_build_market_probabilities_wraps_marketinfoprice_never_labels_it_a_model() -> None:
    prices = {
        1: MarketInfoPrice(implied_probability=Decimal("0.7")),
        2: MarketInfoPrice(implied_probability=Decimal("0.3")),
    }
    wrapped = build_market_probabilities(prices, price_version="info-price-v1")
    assert wrapped[1].probability == Decimal("0.7")
    assert wrapped[1].price_version == "info-price-v1"
    assert not hasattr(wrapped[1], "model_digest")


def test_build_combined_probabilities_wraps_stage_two_style_predictions() -> None:
    wrapped = build_combined_probabilities({1: 0.55, 2: 0.45}, model_digest="sha256:stage-two")
    assert wrapped[1].probability == Decimal("0.55")
    assert wrapped[1].model_digest == "sha256:stage-two"


def test_assemble_race_probability_outputs_end_to_end() -> None:
    fundamental = build_fundamental_probabilities({1: 0.6, 2: 0.4}, model_digest="sha256:stage-one")
    market = build_market_probabilities(
        {
            1: MarketInfoPrice(implied_probability=Decimal("0.55")),
            2: MarketInfoPrice(implied_probability=Decimal("0.45")),
        },
        price_version="info-price-v1",
    )
    combined = build_combined_probabilities({1: 0.58, 2: 0.42}, model_digest="sha256:stage-two")

    race = assemble_race_probability_outputs(
        "race-1",
        [1, 2],
        fundamental=fundamental,
        market_info=market,
        combined=combined,
    )
    assert race.runners[0].fundamental().probability == Decimal("0.6")
    assert race.runners[0].market_info().probability == Decimal("0.55")
    assert race.runners[0].combined().probability == Decimal("0.58")


def test_assemble_refuses_a_partial_map_for_a_present_kind() -> None:
    fundamental = build_fundamental_probabilities({1: 0.6}, model_digest="sha256:stage-one")  # missing runner 2
    with pytest.raises(ValueError):
        assemble_race_probability_outputs(
            "race-1",
            [1, 2],
            fundamental=fundamental,
            market_info_missing_reason="no_book",
            combined_missing_reason="no_model",
        )


def test_assemble_requires_a_reason_when_a_kind_is_absent() -> None:
    with pytest.raises(ValueError):
        assemble_race_probability_outputs(
            "race-1",
            [1, 2],
            fundamental_missing_reason="no_model",
            market_info_missing_reason="no_book",
            combined=None,
            # combined_missing_reason omitted -> must raise
        )
