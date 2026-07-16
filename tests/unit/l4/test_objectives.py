"""SPEC-035: grouped-softmax MLE is the only training objective; validation is race-level
proper scores only. No LambdaRank/pairwise-ranking API exists anywhere in the package."""
from __future__ import annotations

import math

import pytest

import l4_pricing
from l4_pricing import _newton, conditional_logit, crossfit, distribution, horizon, manifest
from l4_pricing import objectives, races, stage_two
from l4_pricing.objectives import REGISTERED_OBJECTIVES, race_brier, race_log_score

pytestmark = pytest.mark.spec("SPEC-035")


def test_registry_contains_only_grouped_softmax_mle() -> None:
    assert set(REGISTERED_OBJECTIVES) == {"grouped_softmax_mle"}
    with pytest.raises(TypeError):
        REGISTERED_OBJECTIVES["lambdarank"] = "no"  # type: ignore[index]


def test_no_ranking_objective_exists_in_the_package_api() -> None:
    for module in (l4_pricing, _newton, conditional_logit, crossfit, distribution,
                   horizon, manifest, objectives, races, stage_two):
        for name in dir(module):
            lowered = name.lower()
            assert "lambdarank" not in lowered
            assert "pairwise" not in lowered
            assert "ranknet" not in lowered


def test_race_log_score_is_negative_log_winner_probability() -> None:
    probs = {1: 0.75, 2: 0.25}
    assert abs(race_log_score(probs, winner_id=1) - (-math.log(0.75))) < 1e-15
    assert abs(race_log_score(probs, winner_id=2) - (-math.log(0.25))) < 1e-15


def test_race_brier_matches_hand_computation() -> None:
    probs = {1: 0.75, 2: 0.25}
    # winner 1: (0.75-1)^2 + (0.25-0)^2 = 0.0625 + 0.0625 = 0.125
    assert abs(race_brier(probs, winner_id=1) - 0.125) < 1e-15


def test_proper_scores_reject_a_winner_outside_the_race() -> None:
    with pytest.raises(ValueError):
        race_log_score({1: 0.5, 2: 0.5}, winner_id=9)
    with pytest.raises(ValueError):
        race_brier({1: 0.5, 2: 0.5}, winner_id=9)
