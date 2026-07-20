"""SPEC-107 — AFFINE_LOGIT_CALIBRATION_FOR_DP1 (Stage 2G Slice 3; red tests first).

Registration: specs/programme/dp1-glicko2-registration-v1.yaml `calibration` block.
The ONLY registered form: z = logit(p_raw); z_cal = intercept + z/temperature;
p_cal = sigmoid(z_cal). Fitted ONLY on leakage-safe out-of-fold DP1 predictions
(SPEC-031 refusal at consumption, reusing the crossfit contamination check);
ATP/WTA separate; raw and calibrated both retained; choice-set coherence preserved
by calibrating the canonical (lower runner id) orientation and complementing.

"""
from __future__ import annotations

import math
from datetime import date
from decimal import Decimal

import pytest

from l4_pricing.crossfit import CrossFitViolation, OOFFundamental, StageOneProvenance
from l4_pricing.horizon import HorizonLabel
from l4_pricing.races import FeatureSchema, Race, RunnerRow
from sport_core.clustering import ChronologyKey, calendar_day_assignment
from sport_tennis.dp1_calibration import (
    AFFINE_CALIBRATION_VERSION,
    AffineLogitCalibration,
    CalibrationFitError,
    fit_affine_logit_calibration,
)

pytestmark = pytest.mark.spec("SPEC-107")

_HORIZON = HorizonLabel("pre-off-tennis")
_D0 = Decimal("0")


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _race(race_id: str, day: date, a: int, b: int, winner: int) -> Race:
    return Race(
        race_id=race_id,
        cluster=calendar_day_assignment("tennis", day),
        runners=(
            RunnerRow(runner_id=a, features={"placeholder": _D0}),
            RunnerRow(runner_id=b, features={"placeholder": _D0}),
        ),
        winner_id=winner,
    )


def _oof_row(race: Race, runner_id: int, p: float, *, trained_through: int) -> OOFFundamental:
    return OOFFundamental(
        race_id=race.race_id,
        runner_id=runner_id,
        p_fundamental=p,
        provenance=StageOneProvenance(
            trained_through=ChronologyKey(ordinal=trained_through),
            training_race_ids=frozenset(),
            training_race_ids_digest="0" * 64,
            horizon=_HORIZON,
        ),
    )


def _synthetic_corpus(
    intercept: float, temperature: float, n: int = 4000
) -> tuple[list[Race], list[OOFFundamental]]:
    """Deterministic corpus whose TRUE win law is sigmoid(intercept + z/temperature)
    of the raw prediction's logit — the fit must recover (intercept, temperature).
    Outcomes are assigned by deterministic quantile striping, not randomness."""
    races: list[Race] = []
    rows: list[OOFFundamental] = []
    day0 = date(2024, 1, 1)
    counter = 0
    for i in range(n):
        z = -2.0 + 4.0 * i / (n - 1)
        p_raw = _sigmoid(z)
        p_true = _sigmoid(intercept + z / temperature)
        # deterministic outcome striping: winner 'a' on a fraction ~ p_true of slots
        counter += 1
        frac = (i * 0.6180339887498949) % 1.0  # low-discrepancy, deterministic
        a_wins = frac < p_true
        day = day0
        race = _race(f"s{i}", day, 1, 2, winner=1 if a_wins else 2)
        races.append(race)
        rows.append(_oof_row(race, 1, p_raw, trained_through=day.toordinal() - 1))
        rows.append(_oof_row(race, 2, 1.0 - p_raw, trained_through=day.toordinal() - 1))
    return races, rows


class TestAffineLogitCalibrationObject:
    def test_version_pinned(self) -> None:
        assert AFFINE_CALIBRATION_VERSION == "affine-logit-dp1-v1"

    def test_identity_parameters_reproduce_raw_exactly(self) -> None:
        cal = AffineLogitCalibration(intercept=0.0, temperature=1.0, tour="atp", n_rows=10)
        for p in (1e-9, 0.2, 0.5, 0.731, 1.0 - 1e-9):
            assert cal.apply(p) == p  # exact, not approximate

    def test_output_varies_with_intercept_and_temperature(self) -> None:
        base = AffineLogitCalibration(intercept=0.0, temperature=1.2, tour="atp", n_rows=10)
        shifted = AffineLogitCalibration(intercept=0.3, temperature=1.2, tour="atp", n_rows=10)
        heated = AffineLogitCalibration(intercept=0.0, temperature=1.5, tour="atp", n_rows=10)
        p = 0.7
        assert base.apply(p) != shifted.apply(p)
        assert base.apply(p) != heated.apply(p)

    def test_temperature_shrinks_toward_half(self) -> None:
        cal = AffineLogitCalibration(intercept=0.0, temperature=2.0, tour="atp", n_rows=10)
        assert 0.5 < cal.apply(0.8) < 0.8
        assert 0.2 < cal.apply(0.2) < 0.5  # symmetric side moves up toward 1/2

    def test_pair_application_is_coherent(self) -> None:
        cal = AffineLogitCalibration(intercept=0.15, temperature=1.3, tour="wta", n_rows=10)
        p_a, p_b = cal.apply_pair(0.65)
        assert p_a + p_b == 1.0  # exact complement
        assert p_a == cal.apply(0.65)

    def test_invalid_parameters_refused(self) -> None:
        with pytest.raises(CalibrationFitError):
            AffineLogitCalibration(intercept=0.0, temperature=0.0, tour="atp", n_rows=1)
        with pytest.raises(CalibrationFitError):
            AffineLogitCalibration(intercept=0.0, temperature=-1.0, tour="atp", n_rows=1)
        with pytest.raises(CalibrationFitError):
            AffineLogitCalibration(intercept=math.nan, temperature=1.0, tour="atp", n_rows=1)
        with pytest.raises(CalibrationFitError):
            AffineLogitCalibration(intercept=0.0, temperature=1.0, tour="", n_rows=1)

    def test_frozen(self) -> None:
        import dataclasses

        cal = AffineLogitCalibration(intercept=0.0, temperature=1.0, tour="atp", n_rows=1)
        with pytest.raises(dataclasses.FrozenInstanceError):
            cal.temperature = 2.0  # type: ignore[misc]


class TestFit:
    def test_recovers_known_miscalibration(self) -> None:
        races, rows = _synthetic_corpus(intercept=0.4, temperature=1.5)
        cal = fit_affine_logit_calibration(races, rows, horizon=_HORIZON, tour="atp")
        assert cal.tour == "atp"
        assert cal.intercept == pytest.approx(0.4, abs=0.1)
        assert cal.temperature == pytest.approx(1.5, abs=0.15)
        assert cal.n_rows == len(races)

    def test_deterministic(self) -> None:
        races, rows = _synthetic_corpus(intercept=0.2, temperature=1.2, n=1000)
        c1 = fit_affine_logit_calibration(races, rows, horizon=_HORIZON, tour="atp")
        c2 = fit_affine_logit_calibration(races, rows, horizon=_HORIZON, tour="atp")
        assert (c1.intercept, c1.temperature) == (c2.intercept, c2.temperature)

    def test_contaminated_row_refused_not_downweighted(self) -> None:
        races, rows = _synthetic_corpus(intercept=0.0, temperature=1.0, n=50)
        race = races[0]
        bad = _oof_row(race, 1, 0.6, trained_through=race.cluster.chronology.ordinal)
        with pytest.raises(CrossFitViolation):
            fit_affine_logit_calibration(
                races, [bad] + rows[1:], horizon=_HORIZON, tour="atp"
            )

    def test_horizon_mismatch_refused(self) -> None:
        races, rows = _synthetic_corpus(intercept=0.0, temperature=1.0, n=50)
        with pytest.raises(CrossFitViolation):
            fit_affine_logit_calibration(
                races, rows, horizon=HorizonLabel("other-horizon"), tour="atp"
            )

    def test_empty_corpus_refused(self) -> None:
        with pytest.raises(CalibrationFitError):
            fit_affine_logit_calibration([], [], horizon=_HORIZON, tour="atp")

    def test_anti_informative_predictions_refused(self) -> None:
        """A negative fitted slope would mean temperature < 0 — the registered form
        cannot represent it; the fit must refuse, never emit a nonsense temperature."""
        races, rows = _synthetic_corpus(intercept=0.0, temperature=1.0, n=2000)
        flipped_races = [
            _race(r.race_id, date.fromordinal(r.cluster.chronology.ordinal), 1, 2,
                  winner=2 if r.winner_id == 1 else 1)
            for r in races
        ]
        with pytest.raises(CalibrationFitError):
            fit_affine_logit_calibration(flipped_races, rows, horizon=_HORIZON, tour="atp")

    def test_raw_probabilities_unchanged_by_fitting(self) -> None:
        races, rows = _synthetic_corpus(intercept=0.3, temperature=1.4, n=500)
        before = [(r.race_id, r.runner_id, r.p_fundamental) for r in rows]
        fit_affine_logit_calibration(races, rows, horizon=_HORIZON, tour="atp")
        assert [(r.race_id, r.runner_id, r.p_fundamental) for r in rows] == before
