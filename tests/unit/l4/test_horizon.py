"""SPEC-033: a model trained at one decision horizon must not score another.

Scoring is deployment's only door, so the refusal lives on every scoring entry point:
`predict_race(model, race, horizon=...)` raises HorizonMismatch on any difference.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from l4_pricing.conditional_logit import fit_conditional_logit, predict_race
from l4_pricing.horizon import HorizonLabel, HorizonMismatch, require_horizon_match
from l4_pricing.races import FeatureSchema, Race, RaceValidationError, RunnerRow

pytestmark = pytest.mark.spec("SPEC-033")

DAY = date(2026, 7, 1)
SCHEMA = FeatureSchema(names=("fav",))


def _corpus() -> list[Race]:
    def race(race_id: str, winner_id: int) -> Race:
        return Race(
            race_id=race_id,
            meeting_day=DAY,
            runners=(
                RunnerRow(runner_id=1, features={"fav": Decimal(1)}),
                RunnerRow(runner_id=2, features={"fav": Decimal(0)}),
            ),
            winner_id=winner_id,
        )

    return [race("r1", 1), race("r2", 1), race("r3", 1), race("r4", 2)]


def test_label_requires_nonempty_trimmed_text() -> None:
    assert str(HorizonLabel("T-2m")) == "T-2m"
    assert str(HorizonLabel("pre-off-liquid")) == "pre-off-liquid"  # market-state-based labels allowed
    with pytest.raises((RaceValidationError, ValueError)):
        HorizonLabel("")
    with pytest.raises((RaceValidationError, ValueError)):
        HorizonLabel("  T-2m ")


def test_scoring_refuses_a_horizon_mismatch() -> None:
    model = fit_conditional_logit(_corpus(), SCHEMA, horizon=HorizonLabel("T-2m"))
    race = Race(
        race_id="score-me",
        meeting_day=DAY,
        runners=(
            RunnerRow(runner_id=1, features={"fav": Decimal(1)}),
            RunnerRow(runner_id=2, features={"fav": Decimal(0)}),
        ),
        winner_id=None,
    )
    with pytest.raises(HorizonMismatch):
        predict_race(model, race, horizon=HorizonLabel("T-60s"))
    probs = predict_race(model, race, horizon=HorizonLabel("T-2m"))
    assert set(probs) == {1, 2}


def test_require_horizon_match_message_names_both_labels() -> None:
    with pytest.raises(HorizonMismatch, match="T-2m"):
        require_horizon_match(HorizonLabel("T-2m"), HorizonLabel("T-10m"))
    require_horizon_match(HorizonLabel("T-2m"), HorizonLabel("T-2m"))
