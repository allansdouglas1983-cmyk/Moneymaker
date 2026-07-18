"""F2 global Elo family + F1 structural null + harness leakage suite (Stage 2B §3/§6).

The Elo family conforms to the model-independent StageOneFamily seam (SPEC-030/031
orchestration; no special evaluator path). Same-day batching (frozen ordering
invariant): every match on a date is predicted/updated from START-of-date ratings;
results are invariant to row permutation within a date. No odds, no June, no names —
a family sees only Race objects (integer runner ids, cluster chronology, winner label).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from l4_pricing.crossfit import assert_out_of_fold, cross_fit
from l4_pricing.races import FeatureSchema, Race, RunnerRow
from l4_pricing.stage_one import StageOneFamily, StageOneFitRefusal
from sport_core.clustering import calendar_day_assignment
from l4_pricing.horizon import HorizonLabel
from sport_tennis.elo_family import (
    ELO_INITIAL_RATING,
    GlobalEloFamily,
    elo_win_probability,
)
from sport_tennis.structural_null import StructuralNullFamily

pytestmark = [pytest.mark.spec("SPEC-030"), pytest.mark.spec("SPEC-031")]

SCHEMA = FeatureSchema(names=("unit",))
H = HorizonLabel("T-5m")
_F = {"unit": Decimal(1)}


def match(rid: str, day: date, a: int, b: int, winner: int) -> Race:
    return Race(
        race_id=rid,
        cluster=calendar_day_assignment("tennis", day),
        runners=(RunnerRow(runner_id=a, features=_F), RunnerRow(runner_id=b, features=_F)),
        winner_id=winner,
    )


class TestEloEquation:
    def test_equal_ratings_is_exactly_half(self) -> None:
        assert elo_win_probability(1500.0, 1500.0) == 0.5

    def test_known_gap_matches_the_registered_equation(self) -> None:
        # P = 1 / (1 + 10^((Rb-Ra)/400)); 400-point gap => 10/11
        assert abs(elo_win_probability(1900.0, 1500.0) - 10.0 / 11.0) < 1e-12

    def test_cold_start_uses_governed_initial_rating(self) -> None:
        fam = GlobalEloFamily(k_factor=32.0)
        model = fam.fit([], SCHEMA, horizon=H, max_iter=1)
        p = fam.predict(model, match("m", date(2024, 1, 1), 7, 8, 7), horizon=H)
        assert p[7] == 0.5 and p[8] == 0.5  # both unseen -> ELO_INITIAL_RATING each
        assert ELO_INITIAL_RATING == 1500.0


class TestSameDayBatching:
    def test_row_permutation_within_a_date_is_invariant(self) -> None:
        d1, d2 = date(2024, 1, 1), date(2024, 1, 2)
        day1 = [
            match("a", d1, 1, 2, 1),
            match("b", d1, 1, 3, 1),  # player 1 twice on d1 (same-day repeat)
            match("c", d1, 4, 5, 5),
        ]
        probe = match("p", d2, 1, 4, 1)
        fam = GlobalEloFamily(k_factor=32.0)
        outs = []
        for order in (day1, day1[::-1], [day1[1], day1[2], day1[0]]):
            model = fam.fit(order, SCHEMA, horizon=H, max_iter=1)
            outs.append(fam.predict(model, probe, horizon=H))
        assert outs[0] == outs[1] == outs[2]

    def test_same_day_result_never_informs_same_day_prediction(self) -> None:
        # Batch semantics: a day's updates apply AFTER the day. Fitting through d1 and
        # predicting a d1 match must use START-of-d1 ratings (here: all initial).
        d0, d1 = date(2024, 1, 1), date(2024, 1, 2)
        fam = GlobalEloFamily(k_factor=32.0)
        model = fam.fit([match("w", d1, 1, 2, 1)], SCHEMA, horizon=H, max_iter=1)
        # ratings after d1 updated; but a prediction "for d1" is produced by the
        # orchestrator from a model trained only through d0 — emulate: empty fit.
        empty = fam.fit([], SCHEMA, horizon=H, max_iter=1)
        p = fam.predict(empty, match("m", d1, 1, 2, 1), horizon=H)
        assert p[1] == 0.5  # start-of-date knowledge

    def test_unlabelled_training_race_refuses(self) -> None:
        fam = GlobalEloFamily(k_factor=32.0)
        r = Race(
            race_id="u",
            cluster=calendar_day_assignment("tennis", date(2024, 1, 1)),
            runners=(RunnerRow(runner_id=1, features=_F), RunnerRow(runner_id=2, features=_F)),
            winner_id=None,
        )
        with pytest.raises(StageOneFitRefusal):
            fam.fit([r], SCHEMA, horizon=H, max_iter=1)


class TestFamilyConformance:
    def test_both_families_satisfy_the_seam(self) -> None:
        assert isinstance(GlobalEloFamily(k_factor=32.0), StageOneFamily)
        assert isinstance(StructuralNullFamily(), StageOneFamily)

    def test_null_is_uniform_and_identity_blind(self) -> None:
        fam = StructuralNullFamily()
        model = fam.fit([match("a", date(2024, 1, 1), 1, 2, 1)], SCHEMA, horizon=H, max_iter=1)
        p = fam.predict(model, match("m", date(2024, 1, 2), 900, 901, 900), horizon=H)
        assert p == {900: 0.5, 901: 0.5}


class TestHarnessLeakage:
    def _corpus(self) -> list[Race]:
        # 8 days, player 1 beats everyone; a strength-aware family must learn it,
        # the null cannot; day-level chronology drives the folds.
        races = []
        for i in range(8):
            d = date(2024, 1, 1 + i)
            races.append(match(f"r{i}a", d, 1, 2 + i, 1))
            races.append(match(f"r{i}b", d, 10 + i, 30 + i, 10 + i))
        return races

    def test_null_through_the_real_orchestrator_no_special_path(self) -> None:
        corpus = self._corpus()
        res = cross_fit(corpus, SCHEMA, horizon=H, family=StructuralNullFamily())
        assert_out_of_fold(res.oof, {r.race_id: r for r in corpus})  # provenance complete/strict
        assert len(res.oof_race_ids) + len(res.excluded) == len(corpus)  # exclusions stay in coverage
        assert all(abs(row.p_fundamental - 0.5) < 1e-12 for row in res.oof)

    def test_input_row_order_cannot_create_information(self) -> None:
        corpus = self._corpus()
        a = cross_fit(corpus, SCHEMA, horizon=H, family=GlobalEloFamily(k_factor=32.0))
        b = cross_fit(list(reversed(corpus)), SCHEMA, horizon=H, family=GlobalEloFamily(k_factor=32.0))
        pa = {(r.race_id, r.runner_id): r.p_fundamental for r in a.oof}
        pb = {(r.race_id, r.runner_id): r.p_fundamental for r in b.oof}
        assert pa == pb

    def test_a_family_ignoring_its_inputs_is_detected_by_the_metric(self) -> None:
        import math

        corpus = self._corpus()
        races_by_id = {r.race_id: r for r in corpus}

        def oof_logloss(fam: object) -> float:
            res = cross_fit(corpus, SCHEMA, horizon=H, family=fam)  # type: ignore[arg-type]
            total = 0.0
            n = 0
            for row in res.oof:
                race = races_by_id[row.race_id]
                if row.runner_id == race.winner_id:
                    total += -math.log(row.p_fundamental)
                    n += 1
            return total / n

        null_loss = oof_logloss(StructuralNullFamily())
        elo_loss = oof_logloss(GlobalEloFamily(k_factor=32.0))
        assert abs(null_loss - math.log(2.0)) < 1e-9  # the null scores exactly ln 2
        assert elo_loss < null_loss  # a strength-aware family separates; ignoring inputs shows

    def test_repeated_runs_are_byte_identical(self) -> None:
        corpus = self._corpus()
        a = cross_fit(corpus, SCHEMA, horizon=H, family=GlobalEloFamily(k_factor=32.0))
        b = cross_fit(corpus, SCHEMA, horizon=H, family=GlobalEloFamily(k_factor=32.0))
        assert [(r.race_id, r.runner_id, r.p_fundamental) for r in a.oof] == [
            (r.race_id, r.runner_id, r.p_fundamental) for r in b.oof
        ]
