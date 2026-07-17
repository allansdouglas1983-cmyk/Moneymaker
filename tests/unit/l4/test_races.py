"""SPEC-030 input contracts: the race is one mutually exclusive choice set.

Features arrive as l3's exact Decimals (floats are refused at this boundary — binary floats
exist only INSIDE the fitter); non-runners are dropped and the remainder renormalised; a race
with fewer than two active runners is refused at construction (an explicit exclusion upstream,
never a silent disappearance).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from l4_pricing.races import FeatureSchema, Race, RaceValidationError, RunnerRow

from sport_core.clustering import ChronologyKey, ClusterAssignment, ClusterId, calendar_day_assignment


def _ca(day):  # racing cluster assignment for tests (A4): meeting-day identity + chronology
    return calendar_day_assignment("horse_racing", day)

pytestmark = pytest.mark.spec("SPEC-030")

DAY = date(2026, 7, 1)


def _runner(runner_id: int, fav: str, non_runner: bool = False) -> RunnerRow:
    return RunnerRow(runner_id=runner_id, features={"fav": Decimal(fav)}, non_runner=non_runner)


def test_schema_requires_sorted_unique_nonempty_names() -> None:
    schema = FeatureSchema(names=("draw", "fav"))
    assert schema.names == ("draw", "fav")
    with pytest.raises(RaceValidationError):
        FeatureSchema(names=())
    with pytest.raises(RaceValidationError):
        FeatureSchema(names=("fav", "draw"))  # not sorted
    with pytest.raises(RaceValidationError):
        FeatureSchema(names=("fav", "fav"))  # duplicate


def test_schema_hash_is_deterministic_and_name_sensitive() -> None:
    a = FeatureSchema(names=("draw", "fav"))
    b = FeatureSchema(names=("draw", "fav"))
    c = FeatureSchema(names=("draw", "pace"))
    assert a.feature_schema_hash == b.feature_schema_hash
    assert a.feature_schema_hash != c.feature_schema_hash


def test_race_requires_two_active_runners() -> None:
    with pytest.raises(RaceValidationError):
        Race(race_id="r1", cluster=_ca(DAY), runners=(_runner(1, "1"),), winner_id=1)
    with pytest.raises(RaceValidationError):
        Race(
            race_id="r1",
            cluster=_ca(DAY),
            runners=(_runner(1, "1"), _runner(2, "0", non_runner=True)),
            winner_id=1,
        )


def test_race_refuses_duplicate_runner_ids() -> None:
    with pytest.raises(RaceValidationError):
        Race(race_id="r1", cluster=_ca(DAY), runners=(_runner(1, "1"), _runner(1, "0")), winner_id=1)


def test_winner_must_be_an_active_runner() -> None:
    with pytest.raises(RaceValidationError):
        Race(race_id="r1", cluster=_ca(DAY), runners=(_runner(1, "1"), _runner(2, "0")), winner_id=9)
    with pytest.raises(RaceValidationError):
        Race(
            race_id="r1",
            cluster=_ca(DAY),
            runners=(_runner(1, "1"), _runner(2, "0"), _runner(3, "0", non_runner=True)),
            winner_id=3,  # a non-runner cannot be the winner
        )


def test_winner_is_optional_for_scoring_races() -> None:
    race = Race(race_id="r1", cluster=_ca(DAY), runners=(_runner(1, "1"), _runner(2, "0")), winner_id=None)
    assert race.winner_id is None
    assert [r.runner_id for r in race.active_runners] == [1, 2]


def test_float_features_are_refused_at_the_boundary() -> None:
    with pytest.raises((RaceValidationError, ValueError, TypeError)):
        RunnerRow(runner_id=1, features={"fav": 0.5}, non_runner=False)  # type: ignore[dict-item]


def test_non_finite_decimal_features_are_refused() -> None:
    with pytest.raises(RaceValidationError):
        RunnerRow(runner_id=1, features={"fav": Decimal("NaN")}, non_runner=False)
    with pytest.raises(RaceValidationError):
        RunnerRow(runner_id=1, features={"fav": Decimal("Infinity")}, non_runner=False)


def test_active_runners_excludes_non_runners() -> None:
    race = Race(
        race_id="r1",
        cluster=_ca(DAY),
        runners=(_runner(1, "1"), _runner(2, "0"), _runner(3, "2", non_runner=True)),
        winner_id=1,
    )
    assert [r.runner_id for r in race.active_runners] == [1, 2]
