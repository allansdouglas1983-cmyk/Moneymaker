"""SPEC-035 properties: the validation helpers are race-level proper scores — exact
definitions, bounded, and computed on the race as one choice set."""
from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from l4_pricing.objectives import race_brier, race_log_score

pytestmark = pytest.mark.spec("SPEC-035")


@st.composite
def _race_probs(draw: st.DrawFn) -> tuple[dict[int, float], int]:
    field = draw(st.integers(min_value=2, max_value=8))
    raw = [draw(st.floats(min_value=0.01, max_value=1.0)) for _ in range(field)]
    total = math.fsum(raw)
    probs = {i + 1: value / total for i, value in enumerate(raw)}
    winner = draw(st.integers(min_value=1, max_value=field))
    return probs, winner


@settings(max_examples=200)
@given(data=_race_probs())
def test_log_score_matches_definition(data: tuple[dict[int, float], int]) -> None:
    probs, winner = data
    assert race_log_score(probs, winner_id=winner) == -math.log(probs[winner])


@settings(max_examples=200)
@given(data=_race_probs())
def test_brier_is_bounded_and_exact(data: tuple[dict[int, float], int]) -> None:
    probs, winner = data
    score = race_brier(probs, winner_id=winner)
    expected = math.fsum(
        (p - (1.0 if rid == winner else 0.0)) ** 2 for rid, p in sorted(probs.items())
    )
    assert score == expected
    assert 0.0 <= score <= 2.0


@settings(max_examples=100)
@given(data=_race_probs())
def test_scores_reject_unnormalised_races(data: tuple[dict[int, float], int]) -> None:
    probs, winner = data
    broken = dict(probs)
    broken[winner] = broken[winner] + 0.5  # no longer sums to ~1
    with pytest.raises(ValueError):
        race_log_score(broken, winner_id=winner)
    with pytest.raises(ValueError):
        race_brier(broken, winner_id=winner)
