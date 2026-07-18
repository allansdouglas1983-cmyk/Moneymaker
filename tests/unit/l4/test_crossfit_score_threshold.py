"""ADDITIVE cross_fit parameter `score_only_after` (SPEC-031): warm-up semantics.

Folds whose cluster chronology is <= the threshold are not fit and not scored; their
races become typed exclusions (reason WARM_UP_BEFORE_SCORE_THRESHOLD), preserving the
universe-accounting invariant. Scored folds still train on ALL earlier races including
the warm-up. Default None reproduces the existing behaviour exactly (byte-identical).
Motivation: at multi-decade corpus scale, per-fold provenance for never-consumed
warm-up folds is pure memory burn; the endpoint semantics (warm-up is not scored)
belong to the orchestrator, not to caller-side row filtering.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from l4_pricing.crossfit import assert_out_of_fold, cross_fit
from l4_pricing.horizon import HorizonLabel
from l4_pricing.races import FeatureSchema, Race, RunnerRow
from sport_core.clustering import ChronologyKey, calendar_day_assignment
from sport_tennis.structural_null import StructuralNullFamily

pytestmark = pytest.mark.spec("SPEC-031")

SCHEMA = FeatureSchema(names=("unit",))
H = HorizonLabel("T-5m")
_F = {"unit": Decimal(1)}


def _race(rid: str, day: date, a: int, b: int, winner: int) -> Race:
    return Race(
        race_id=rid,
        cluster=calendar_day_assignment("tennis", day),
        runners=(RunnerRow(runner_id=a, features=_F), RunnerRow(runner_id=b, features=_F)),
        winner_id=winner,
    )


def _corpus() -> list[Race]:
    races = []
    for i in range(6):
        d = date(2024, 1, 1 + i)
        races.append(_race(f"r{i}a", d, 1, 2, 1))
        races.append(_race(f"r{i}b", d, 3, 4, 3))
    return races


def test_default_none_is_byte_identical_to_existing_behaviour() -> None:
    corpus = _corpus()
    a = cross_fit(corpus, SCHEMA, horizon=H, family=StructuralNullFamily())
    b = cross_fit(corpus, SCHEMA, horizon=H, family=StructuralNullFamily(), score_only_after=None)
    assert [(r.race_id, r.runner_id, r.p_fundamental) for r in a.oof] == [
        (r.race_id, r.runner_id, r.p_fundamental) for r in b.oof
    ]
    assert a.excluded == b.excluded


def test_threshold_excludes_warmup_folds_with_typed_reason_and_keeps_accounting() -> None:
    corpus = _corpus()
    threshold = ChronologyKey.from_date(date(2024, 1, 3))  # days 1-3 = warm-up
    res = cross_fit(
        corpus, SCHEMA, horizon=H, family=StructuralNullFamily(), score_only_after=threshold
    )
    scored_days = {r.race_id[1] for r in res.oof}  # r{i}...
    assert scored_days == {"3", "4", "5"}  # only days AFTER the threshold are scored
    warmup_excluded = [e for e in res.excluded if "WARM_UP_BEFORE_SCORE_THRESHOLD" in e.reason]
    assert {e.race_id[1] for e in warmup_excluded} == {"0", "1", "2"}
    assert len(res.oof_race_ids) + len(res.excluded) == len(corpus)  # invariant preserved


def test_scored_folds_still_train_on_the_full_prior_history() -> None:
    corpus = _corpus()
    threshold = ChronologyKey.from_date(date(2024, 1, 3))
    res = cross_fit(
        corpus, SCHEMA, horizon=H, family=StructuralNullFamily(), score_only_after=threshold
    )
    # provenance of the first scored fold must include the warm-up races (full history)
    first_scored = min(res.oof, key=lambda r: r.provenance.trained_through)
    assert "r0a" in first_scored.provenance.training_race_ids
    assert "r2b" in first_scored.provenance.training_race_ids
    assert_out_of_fold(res.oof, {r.race_id: r for r in corpus})
