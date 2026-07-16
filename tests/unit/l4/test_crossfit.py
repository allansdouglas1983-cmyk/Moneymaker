"""SPEC-031: time-respecting, strictly out-of-fold cross-fitting.

If p_fundamental is not out-of-sample, alpha is spuriously inflated and the entire result is
worthless (§6.4). Every out-of-fold fundamental carries provenance (trained-through day plus
the training race-id set); the plan self-verifies, and stage two re-verifies at consumption.
Universe accounting: every input race is either an OOF race or an explicit exclusion.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from l4_pricing.crossfit import (
    CrossFitResult,
    CrossFitViolation,
    ExcludedRace,
    OOFFundamental,
    StageOneProvenance,
    assert_out_of_fold,
    cross_fit,
)
from l4_pricing.horizon import HorizonLabel
from l4_pricing.races import FeatureSchema, Race, RunnerRow

pytestmark = pytest.mark.spec("SPEC-031")

SCHEMA = FeatureSchema(names=("fav",))
H = HorizonLabel("T-2m")


def _race(race_id: str, day: date, winner_id: int) -> Race:
    return Race(
        race_id=race_id,
        meeting_day=day,
        runners=(
            RunnerRow(runner_id=1, features={"fav": Decimal(1)}),
            RunnerRow(runner_id=2, features={"fav": Decimal(0)}),
        ),
        winner_id=winner_id,
    )


def _three_day_corpus() -> list[Race]:
    d0, d1, d2 = date(2026, 7, 1), date(2026, 7, 2), date(2026, 7, 3)
    return [
        # day 0: mixed winners (fits cleanly once used as training data)
        _race("a1", d0, 1),
        _race("a2", d0, 1),
        _race("a3", d0, 1),
        _race("a4", d0, 2),
        # day 1
        _race("b1", d1, 1),
        _race("b2", d1, 2),
        # day 2
        _race("c1", d2, 1),
        _race("c2", d2, 2),
    ]


def test_first_day_is_excluded_and_later_days_get_oof_rows() -> None:
    result = cross_fit(_three_day_corpus(), SCHEMA, horizon=H)
    assert isinstance(result, CrossFitResult)
    excluded_ids = {e.race_id for e in result.excluded}
    assert excluded_ids == {"a1", "a2", "a3", "a4"}
    assert all("no earlier" in e.reason for e in result.excluded)
    assert result.oof_race_ids == {"b1", "b2", "c1", "c2"}


def test_provenance_is_strictly_time_respecting() -> None:
    result = cross_fit(_three_day_corpus(), SCHEMA, horizon=H)
    races = {r.race_id: r for r in _three_day_corpus()}
    for row in result.oof:
        race = races[row.race_id]
        assert row.provenance.trained_through_day < race.meeting_day
        assert row.race_id not in row.provenance.training_race_ids


def test_day_two_model_trains_on_both_earlier_days() -> None:
    result = cross_fit(_three_day_corpus(), SCHEMA, horizon=H)
    day_two_rows = [row for row in result.oof if row.race_id in {"c1", "c2"}]
    assert day_two_rows
    for row in day_two_rows:
        assert row.provenance.training_race_ids == frozenset({"a1", "a2", "a3", "a4", "b1", "b2"})


def test_every_active_runner_of_an_oof_race_is_covered() -> None:
    result = cross_fit(_three_day_corpus(), SCHEMA, horizon=H)
    covered = {(row.race_id, row.runner_id) for row in result.oof}
    for race_id in result.oof_race_ids:
        assert (race_id, 1) in covered
        assert (race_id, 2) in covered


def test_universe_accounting_is_exact() -> None:
    corpus = _three_day_corpus()
    result = cross_fit(corpus, SCHEMA, horizon=H)
    assert len(result.oof_race_ids) + len(result.excluded) == len(corpus)
    assert result.oof_race_ids.isdisjoint({e.race_id for e in result.excluded})


def test_deployment_model_uses_the_full_window() -> None:
    corpus = _three_day_corpus()
    result = cross_fit(corpus, SCHEMA, horizon=H)
    assert result.deployment_model.training_race_ids == frozenset(r.race_id for r in corpus)
    assert result.deployment_model.trained_through_day == date(2026, 7, 3)
    assert result.deployment_model.horizon == H


def test_cross_fit_is_deterministic_and_input_order_invariant() -> None:
    corpus = _three_day_corpus()
    a = cross_fit(corpus, SCHEMA, horizon=H)
    b = cross_fit(list(reversed(corpus)), SCHEMA, horizon=H)
    assert [(r.race_id, r.runner_id, r.p_fundamental) for r in a.oof] == [
        (r.race_id, r.runner_id, r.p_fundamental) for r in b.oof
    ]
    assert a.deployment_model.coefficients == b.deployment_model.coefficients


def test_fit_failure_day_is_excluded_with_reason_but_still_trains_later_models() -> None:
    # Day 0 alone is completely separated (favourite always wins), so day 1 has no usable
    # model and is excluded with a fit-failure reason. Day 2's model trains on day 0 AND
    # day 1 races regardless — they are valid outcomes even though they got no OOF row.
    d0, d1, d2 = date(2026, 7, 1), date(2026, 7, 2), date(2026, 7, 3)
    corpus = [
        _race("a1", d0, 1),
        _race("a2", d0, 1),
        _race("b1", d1, 1),
        _race("b2", d1, 2),
        _race("c1", d2, 1),
        _race("c2", d2, 2),
    ]
    result = cross_fit(corpus, SCHEMA, horizon=H)
    excluded = {e.race_id: e.reason for e in result.excluded}
    assert set(excluded) == {"a1", "a2", "b1", "b2"}
    assert "no earlier" in excluded["a1"]
    assert "fit" in excluded["b1"].lower()
    day_two_rows = [row for row in result.oof if row.race_id in {"c1", "c2"}]
    assert day_two_rows
    for row in day_two_rows:
        assert row.provenance.training_race_ids == frozenset({"a1", "a2", "b1", "b2"})


def test_oof_fundamental_requires_open_unit_interval() -> None:
    provenance = StageOneProvenance(
        trained_through_day=date(2026, 7, 1),
        training_race_ids=frozenset({"a1"}),
        training_race_ids_digest="d",
        horizon=H,
    )
    for bad in (0.0, 1.0, -0.1, 1.1):
        with pytest.raises(ValueError):
            OOFFundamental(race_id="b1", runner_id=1, p_fundamental=bad, provenance=provenance)


def test_assert_out_of_fold_catches_contaminated_rows() -> None:
    races = {r.race_id: r for r in _three_day_corpus()}
    saw_own_race = StageOneProvenance(
        trained_through_day=date(2026, 7, 1),
        training_race_ids=frozenset({"b1"}),  # the model saw the race it prices
        training_race_ids_digest="d",
        horizon=H,
    )
    row = OOFFundamental(race_id="b1", runner_id=1, p_fundamental=0.5, provenance=saw_own_race)
    with pytest.raises(CrossFitViolation):
        assert_out_of_fold([row], races)

    same_day = StageOneProvenance(
        trained_through_day=date(2026, 7, 2),  # not strictly earlier than b1's meeting day
        training_race_ids=frozenset({"a1"}),
        training_race_ids_digest="d",
        horizon=H,
    )
    row2 = OOFFundamental(race_id="b1", runner_id=1, p_fundamental=0.5, provenance=same_day)
    with pytest.raises(CrossFitViolation):
        assert_out_of_fold([row2], races)


def test_excluded_race_records_are_frozen_values() -> None:
    e = ExcludedRace(race_id="a1", reason="no earlier meeting day to train on")
    with pytest.raises(Exception):
        e.reason = "other"  # type: ignore[misc]
