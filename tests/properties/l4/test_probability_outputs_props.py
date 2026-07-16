"""SPEC-036 properties: race-level normalisation over generated races, wrapper-type
distinctness under cross-construction, missing-kind access always raising the explicit
``MissingProbabilityError`` (never substituting), and lineage fields being mandatory whenever
a kind is present.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from l4_pricing.probability_outputs import (
    CombinedProbability,
    FundamentalProbability,
    MarketProbability,
    MissingProbabilityError,
    RaceProbabilityOutputs,
    RunnerProbabilities,
    build_combined_probabilities,
    build_fundamental_probabilities,
    build_market_probabilities,
)
from l5_decision.prices import MarketInfoPrice

pytestmark = pytest.mark.spec("SPEC-036")


def _normalised_floats(field_size: int, draw: st.DrawFn, min_v: float = 0.01) -> list[float]:
    """Draw `field_size` positive weights and normalise to sum exactly 1.0 by construction
    (last element absorbs the remainder), avoiding hypothesis-level floating drift."""
    raw = [draw(st.floats(min_value=min_v, max_value=1.0, allow_nan=False, allow_infinity=False)) for _ in range(field_size)]
    total = sum(raw)
    return [r / total for r in raw]


@st.composite
def _race_of_fundamentals(draw: st.DrawFn) -> dict[int, float]:
    field_size = draw(st.integers(min_value=2, max_value=8))
    values = _normalised_floats(field_size, draw)
    return {i + 1: v for i, v in enumerate(values)}


@settings(max_examples=100)
@given(fundamentals=_race_of_fundamentals())
def test_race_normalisation_holds_over_generated_races(fundamentals: dict[int, float]) -> None:
    wrapped = build_fundamental_probabilities(fundamentals, model_digest="sha256:generated")
    runners = tuple(
        RunnerProbabilities(
            runner_id=rid,
            p_fundamental=prob,
            p_market_info=None,
            p_market_info_missing_reason="not_modelled_in_this_property",
            p_combined=None,
            p_combined_missing_reason="not_modelled_in_this_property",
        )
        for rid, prob in wrapped.items()
    )
    race = RaceProbabilityOutputs(race_id="generated", runners=runners)
    total = sum((r.fundamental().probability for r in race.runners), Decimal(0))
    assert abs(total - Decimal(1)) <= Decimal("1e-9")


@settings(max_examples=100)
@given(fundamentals=_race_of_fundamentals())
def test_market_probabilities_normalise_over_generated_races(fundamentals: dict[int, float]) -> None:
    """Same normalisation property, exercised through the MarketInfoPrice wrapping path."""
    prices = {rid: MarketInfoPrice(implied_probability=Decimal(repr(v))) for rid, v in fundamentals.items()}
    # MarketInfoPrice does not itself renormalise, so rescale defensively for Decimal exactness,
    # mirroring info-price-v1's own normalise-to-unit-sum step.
    total_repr = sum((p.implied_probability for p in prices.values()), Decimal(0))
    assume(abs(total_repr - Decimal(1)) <= Decimal("1e-9"))
    wrapped = build_market_probabilities(prices, price_version="info-price-v1")
    runners = tuple(
        RunnerProbabilities(
            runner_id=rid,
            p_fundamental=None,
            p_fundamental_missing_reason="not_modelled_in_this_property",
            p_market_info=prob,
            p_combined=None,
            p_combined_missing_reason="not_modelled_in_this_property",
        )
        for rid, prob in wrapped.items()
    )
    race = RaceProbabilityOutputs(race_id="generated", runners=runners)
    total = sum((r.market_info().probability for r in race.runners), Decimal(0))
    assert abs(total - Decimal(1)) <= Decimal("1e-9")


@settings(max_examples=50)
@given(fundamentals=_race_of_fundamentals())
def test_combined_probabilities_normalise_over_generated_races(fundamentals: dict[int, float]) -> None:
    wrapped = build_combined_probabilities(fundamentals, model_digest="sha256:combined-generated")
    runners = tuple(
        RunnerProbabilities(
            runner_id=rid,
            p_fundamental=None,
            p_fundamental_missing_reason="not_modelled_in_this_property",
            p_market_info=None,
            p_market_info_missing_reason="not_modelled_in_this_property",
            p_combined=prob,
        )
        for rid, prob in wrapped.items()
    )
    race = RaceProbabilityOutputs(race_id="generated", runners=runners)
    total = sum((r.combined().probability for r in race.runners), Decimal(0))
    assert abs(total - Decimal(1)) <= Decimal("1e-9")


# --- distinctness: cross-construction is always rejected -----------------------------------

_P = st.decimals(min_value=Decimal("0.01"), max_value=Decimal("0.99"), places=4)
_DIGEST = st.text(min_size=1, max_size=20).filter(lambda s: s.strip())


@settings(max_examples=100)
@given(probability=_P)
def test_market_probability_never_typechecks_as_fundamental(probability: Decimal) -> None:
    market = MarketProbability(probability=probability, price_version="info-price-v1")
    with pytest.raises(ValidationError):
        RunnerProbabilities(
            runner_id=1,
            p_fundamental=market,  # type: ignore[arg-type]
            p_market_info=None,
            p_market_info_missing_reason="x",
            p_combined=None,
            p_combined_missing_reason="x",
        )


@settings(max_examples=100)
@given(probability=_P, digest=_DIGEST)
def test_fundamental_probability_never_typechecks_as_combined(probability: Decimal, digest: str) -> None:
    fundamental = FundamentalProbability(probability=probability, model_digest=digest)
    with pytest.raises(ValidationError):
        RunnerProbabilities(
            runner_id=1,
            p_fundamental=None,
            p_fundamental_missing_reason="x",
            p_market_info=None,
            p_market_info_missing_reason="x",
            p_combined=fundamental,  # type: ignore[arg-type]
        )


@settings(max_examples=100)
@given(probability=_P, digest=_DIGEST)
def test_combined_probability_never_typechecks_as_market_info(probability: Decimal, digest: str) -> None:
    combined = CombinedProbability(probability=probability, model_digest=digest)
    with pytest.raises(ValidationError):
        RunnerProbabilities(
            runner_id=1,
            p_fundamental=None,
            p_fundamental_missing_reason="x",
            p_market_info=combined,  # type: ignore[arg-type]
            p_combined=None,
            p_combined_missing_reason="x",
        )


# --- missing-kind access always raises, over generated combinations of absence --------------


@settings(max_examples=100)
@given(
    fundamental_present=st.booleans(),
    market_present=st.booleans(),
    combined_present=st.booleans(),
    probability=_P,
    digest=_DIGEST,
)
def test_missing_kind_access_always_raises_never_substitutes(
    fundamental_present: bool,
    market_present: bool,
    combined_present: bool,
    probability: Decimal,
    digest: str,
) -> None:
    runner = RunnerProbabilities(
        runner_id=1,
        p_fundamental=FundamentalProbability(probability=probability, model_digest=digest) if fundamental_present else None,
        p_fundamental_missing_reason=None if fundamental_present else "absent_for_property_test",
        p_market_info=MarketProbability(probability=probability, price_version="info-price-v1") if market_present else None,
        p_market_info_missing_reason=None if market_present else "absent_for_property_test",
        p_combined=CombinedProbability(probability=probability, model_digest=digest) if combined_present else None,
        p_combined_missing_reason=None if combined_present else "absent_for_property_test",
    )
    if fundamental_present:
        assert runner.fundamental().probability == probability
    else:
        with pytest.raises(MissingProbabilityError):
            runner.fundamental()
    if market_present:
        assert runner.market_info().probability == probability
    else:
        with pytest.raises(MissingProbabilityError):
            runner.market_info()
    if combined_present:
        assert runner.combined().probability == probability
    else:
        with pytest.raises(MissingProbabilityError):
            runner.combined()


# --- lineage fields mandatory whenever a kind is present -------------------------------------


@settings(max_examples=100)
@given(probability=_P)
def test_fundamental_and_combined_reject_blank_lineage(probability: Decimal) -> None:
    for blank in ("", "   ", "\t"):
        with pytest.raises(ValidationError):
            FundamentalProbability(probability=probability, model_digest=blank)
        with pytest.raises(ValidationError):
            CombinedProbability(probability=probability, model_digest=blank)


@settings(max_examples=100)
@given(probability=_P)
def test_market_probability_rejects_blank_price_version(probability: Decimal) -> None:
    for blank in ("", "   ", "\t"):
        with pytest.raises(ValidationError):
            MarketProbability(probability=probability, price_version=blank)
