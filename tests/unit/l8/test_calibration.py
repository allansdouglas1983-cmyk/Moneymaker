"""SPEC-097: race-level calibration metrics — reliability curves with CIs, adaptive
(equal-count) bins, cohort calibration, renormalising post-hoc temperature scaling, and a
non-comparable ECE diagnostic.

This extends SPEC-038 (``l8_evidence.predictor_metrics``), which already owns race-level
log score, Brier, calibration-in-the-large, calibration slope and point-estimate reliability
by band. Nothing here duplicates that — see ``l8_evidence.calibration``'s module docstring.
"""
from __future__ import annotations

import math
from decimal import Decimal

import pytest

from l8_evidence.prediction_snapshots import VintageType
from l8_evidence.predictor_metrics import (
    ModelKind,
    RaceEvaluationInput,
    ReliabilityBand,
    RunnerOutcome,
)
from l8_evidence.sample_size import standard_normal_inverse_cdf
from l8_evidence.calibration import (
    AdaptiveBinError,
    CalibrationError,
    CohortCalibrationError,
    EceDiagnostic,
    EceError,
    PosthocCalibrationError,
    PosthocCalibrator,
    ReliabilityCurvePoint,
    TEMPERATURE_SCALING_METHOD_ID,
    TEMPERATURE_SCALING_VERSION,
    WilsonIntervalError,
    adaptive_bins,
    apply_posthoc_calibration,
    calibration_by_cohort,
    expected_calibration_error,
    reliability_curve,
    reliability_curve_digest,
    wilson_score_interval,
)

pytestmark = pytest.mark.spec("SPEC-097")

_HORIZON = "T-60m"


def _bands() -> tuple[ReliabilityBand, ...]:
    return (
        ReliabilityBand(label="low", lower=Decimal("0"), upper=Decimal("0.5")),
        ReliabilityBand(label="high", lower=Decimal("0.5"), upper=Decimal("1")),
    )


def _race(
    race_id: str,
    probs: tuple[Decimal, ...],
    winner_index: int = 0,
) -> RaceEvaluationInput:
    runners = tuple(
        RunnerOutcome(runner_id=i + 1, probability=p, is_winner=(i == winner_index))
        for i, p in enumerate(probs)
    )
    return RaceEvaluationInput(
        race_id=race_id,
        model_kind=ModelKind.COMBINED,
        decision_horizon=_HORIZON,
        settled=True,
        vintage_type=VintageType.FINAL_APPROVED_HORIZON,
        runners=runners,
    )


# --- Wilson score interval: hand-computed fixture -----------------------------------------


def test_wilson_interval_hand_fixture_8_of_10_95pct() -> None:
    successes, total = 8, 10
    confidence_level = Decimal("0.95")
    z = standard_normal_inverse_cdf(0.975)
    n = float(total)
    p_hat = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p_hat + z2 / (2.0 * n)) / denom
    margin = (z / denom) * math.sqrt(p_hat * (1.0 - p_hat) / n + z2 / (4.0 * n * n))
    expected_lower = round(center - margin, 4)
    expected_upper = round(center + margin, 4)

    lower, upper = wilson_score_interval(successes, total, confidence_level=confidence_level)

    assert round(lower, 4) == expected_lower
    assert round(upper, 4) == expected_upper
    # Sanity: the interval must contain the point estimate and stay inside [0, 1].
    assert 0.0 <= lower <= p_hat <= upper <= 1.0


def test_wilson_interval_rejects_non_positive_total() -> None:
    with pytest.raises(WilsonIntervalError):
        wilson_score_interval(0, 0, confidence_level=Decimal("0.95"))


def test_wilson_interval_rejects_successes_out_of_range() -> None:
    with pytest.raises(WilsonIntervalError):
        wilson_score_interval(11, 10, confidence_level=Decimal("0.95"))


@pytest.mark.parametrize("bad", [Decimal("0"), Decimal("1"), Decimal("-0.1"), Decimal("1.5")])
def test_wilson_interval_rejects_bad_confidence_level(bad: Decimal) -> None:
    with pytest.raises(WilsonIntervalError):
        wilson_score_interval(5, 10, confidence_level=bad)


# --- reliability_curve: zero-count band absence, CI attached -------------------------------


def _three_bands() -> tuple[ReliabilityBand, ...]:
    return (
        ReliabilityBand(label="low", lower=Decimal("0"), upper=Decimal("0.3")),
        ReliabilityBand(label="mid", lower=Decimal("0.3"), upper=Decimal("0.7")),
        ReliabilityBand(label="high", lower=Decimal("0.7"), upper=Decimal("1")),
    )


def test_reliability_curve_omits_zero_count_bands() -> None:
    # Both runners land in "mid" (0.6 and 0.4); "low" and "high" have zero members.
    races = [_race("r1", (Decimal("0.6"), Decimal("0.4")), winner_index=0)]
    curve = reliability_curve(races, _three_bands(), confidence_level=Decimal("0.95"))
    labels = {point.label for point in curve}
    assert "low" not in labels
    assert "high" not in labels
    assert "mid" in labels
    for point in curve:
        assert isinstance(point, ReliabilityCurvePoint)
        assert point.count > 0
        assert 0.0 <= point.ci_lower <= point.ci_upper <= 1.0


def test_reliability_curve_ci_matches_wilson_for_known_band() -> None:
    # 10 races, each with the SAME two probabilities so all 20 runner-outcome pairs land in
    # a single band; 10 winners at p=0.8 fall in "high", 10 losers at p=0.2 fall in "low".
    races = [
        _race(f"r{i}", (Decimal("0.8"), Decimal("0.2")), winner_index=0) for i in range(10)
    ]
    curve = reliability_curve(races, _bands(), confidence_level=Decimal("0.95"))
    high = next(p for p in curve if p.label == "high")
    assert high.count == 10
    expected_lower, expected_upper = wilson_score_interval(
        10, 10, confidence_level=Decimal("0.95")
    )
    assert high.ci_lower == pytest.approx(expected_lower)
    assert high.ci_upper == pytest.approx(expected_upper)


# --- adaptive_bins --------------------------------------------------------------------------


def test_adaptive_bins_gap_free_partition_with_counts() -> None:
    probs = [Decimal(f"0.{i:02d}") for i in range(5, 100, 5)]  # 19 distinct values
    races = [_race(f"r{i}", (p, Decimal(1) - p)) for i, p in enumerate(probs)]
    bands = adaptive_bins(races, n_bins=4)
    assert len(bands) == 4
    ordered = sorted(bands, key=lambda b: b.lower)
    assert ordered[0].lower == Decimal(0)
    assert ordered[-1].upper == Decimal(1)
    for prev, nxt in zip(ordered, ordered[1:]):
        assert prev.upper == nxt.lower
    total_pairs = sum(len(race.runners) for race in races)
    # Every band label carries its member count; the counts sum to the total pairs pooled.
    counted = 0
    for band in ordered:
        assert "n=" in band.label
        n_str = band.label.split("n=")[1].rstrip(")")
        counted += int(n_str)
    assert counted == total_pairs


def test_adaptive_bins_refuses_n_bins_below_two() -> None:
    races = [_race("r1", (Decimal("0.5"), Decimal("0.5")))]
    with pytest.raises(AdaptiveBinError):
        adaptive_bins(races, n_bins=1)


def test_adaptive_bins_refuses_insufficient_distinct_values() -> None:
    # Only 2 distinct probability values in the whole pool, but 4 bins requested.
    races = [
        _race("r1", (Decimal("0.5"), Decimal("0.5"))),
        _race("r2", (Decimal("0.5"), Decimal("0.5"))),
    ]
    with pytest.raises(AdaptiveBinError):
        adaptive_bins(races, n_bins=4)


def test_adaptive_bins_refuses_empty_race_set() -> None:
    with pytest.raises(AdaptiveBinError):
        adaptive_bins([], n_bins=2)


# --- calibration_by_cohort ------------------------------------------------------------------


def test_calibration_by_cohort_refuses_unlabelled_race() -> None:
    races = [
        _race("r1", (Decimal("0.6"), Decimal("0.4"))),
        _race("r2", (Decimal("0.7"), Decimal("0.3"))),
    ]
    cohort_of = {"r1": "track-a"}  # r2 missing
    with pytest.raises(CohortCalibrationError):
        calibration_by_cohort(races, cohort_of, _bands(), confidence_level=Decimal("0.95"))


def test_calibration_by_cohort_partitions_by_label() -> None:
    races = [
        _race("r1", (Decimal("0.6"), Decimal("0.4"))),
        _race("r2", (Decimal("0.7"), Decimal("0.3"))),
    ]
    cohort_of = {"r1": "track-a", "r2": "track-b"}
    result = calibration_by_cohort(races, cohort_of, _bands(), confidence_level=Decimal("0.95"))
    assert set(result.keys()) == {"track-a", "track-b"}
    for curve in result.values():
        for point in curve:
            assert isinstance(point, ReliabilityCurvePoint)


# --- apply_posthoc_calibration: temperature scaling ----------------------------------------


def _calibrator(temperature: Decimal) -> PosthocCalibrator:
    return PosthocCalibrator(
        method_id=TEMPERATURE_SCALING_METHOD_ID,
        version=TEMPERATURE_SCALING_VERSION,
        parameters={"T": temperature},
    )


def test_temperature_scaling_identity_at_t_equals_1() -> None:
    race = {1: Decimal("0.7"), 2: Decimal("0.3")}
    result = apply_posthoc_calibration(race, _calibrator(Decimal("1")))
    assert abs(result[1] - Decimal("0.7")) < Decimal("1e-9")
    assert abs(result[2] - Decimal("0.3")) < Decimal("1e-9")


def test_temperature_scaling_sums_to_one() -> None:
    race = {1: Decimal("0.7"), 2: Decimal("0.2"), 3: Decimal("0.1")}
    result = apply_posthoc_calibration(race, _calibrator(Decimal("2.5")))
    total = sum(result.values(), Decimal(0))
    assert abs(total - Decimal(1)) < Decimal("1e-9")


def test_temperature_scaling_flattens_when_t_greater_than_one() -> None:
    race = {1: Decimal("0.8"), 2: Decimal("0.2")}
    original_max = max(race.values())
    result = apply_posthoc_calibration(race, _calibrator(Decimal("3")))
    assert max(result.values()) < original_max


def test_temperature_scaling_rejects_unknown_method() -> None:
    bad = PosthocCalibrator(
        method_id="platt-scaling", version=1, parameters={"a": Decimal("1"), "b": Decimal("0")}
    )
    with pytest.raises(PosthocCalibrationError):
        apply_posthoc_calibration({1: Decimal("0.5"), 2: Decimal("0.5")}, bad)


@pytest.mark.parametrize("bad_t", [Decimal("0"), Decimal("-1")])
def test_temperature_scaling_rejects_non_positive_temperature(bad_t: Decimal) -> None:
    with pytest.raises(PosthocCalibrationError):
        apply_posthoc_calibration({1: Decimal("0.5"), 2: Decimal("0.5")}, _calibrator(bad_t))


def test_temperature_scaling_rejects_probabilities_not_summing_to_one() -> None:
    race = {1: Decimal("0.7"), 2: Decimal("0.7")}
    with pytest.raises(PosthocCalibrationError):
        apply_posthoc_calibration(race, _calibrator(Decimal("1")))


def test_temperature_scaling_rejects_empty_race() -> None:
    with pytest.raises(PosthocCalibrationError):
        apply_posthoc_calibration({}, _calibrator(Decimal("1")))


def test_posthoc_calibrator_rejects_empty_method_id() -> None:
    with pytest.raises(PosthocCalibrationError):
        PosthocCalibrator(method_id="", version=1, parameters={})


def test_posthoc_calibrator_rejects_version_below_one() -> None:
    with pytest.raises(PosthocCalibrationError):
        PosthocCalibrator(method_id="temperature-scaling", version=0, parameters={})


# --- ECE: diagnostic only, non-comparable ---------------------------------------------------


def test_expected_calibration_error_is_a_diagnostic_value() -> None:
    races = [
        _race("r1", (Decimal("0.6"), Decimal("0.4")), winner_index=0),
        _race("r2", (Decimal("0.7"), Decimal("0.3")), winner_index=1),
    ]
    curve = reliability_curve(races, _bands(), confidence_level=Decimal("0.95"))
    diagnostic = expected_calibration_error(curve)
    assert isinstance(diagnostic, EceDiagnostic)
    assert isinstance(diagnostic.ece_diagnostic_only, float)
    assert diagnostic.n_bands == len(curve)


def test_expected_calibration_error_refuses_empty_curve() -> None:
    with pytest.raises(EceError):
        expected_calibration_error(())


@pytest.mark.parametrize("op_name", ["__lt__", "__le__", "__gt__", "__ge__"])
def test_ece_diagnostic_has_no_ordering_dunder_defined_on_the_class_itself(op_name: str) -> None:
    # object() supplies no meaningful __lt__ etc either, but EceDiagnostic must not have
    # ADDED one — this asserts the class body itself carries none of the four.
    assert op_name not in EceDiagnostic.__dict__


def test_ece_diagnostic_comparison_raises_type_error() -> None:
    a = EceDiagnostic(ece_diagnostic_only=0.1, n_bands=2, n_pairs=10)
    b = EceDiagnostic(ece_diagnostic_only=0.2, n_bands=2, n_pairs=10)
    with pytest.raises(TypeError):
        _ = a < b  # type: ignore[operator]
    with pytest.raises(TypeError):
        _ = a <= b  # type: ignore[operator]
    with pytest.raises(TypeError):
        _ = a > b  # type: ignore[operator]
    with pytest.raises(TypeError):
        _ = a >= b  # type: ignore[operator]


# --- digest determinism ---------------------------------------------------------------------


def test_reliability_curve_digest_is_deterministic() -> None:
    races = [_race("r1", (Decimal("0.6"), Decimal("0.4")), winner_index=0)]
    curve = reliability_curve(races, _bands(), confidence_level=Decimal("0.95"))
    d1 = reliability_curve_digest(curve)
    d2 = reliability_curve_digest(curve)
    assert d1 == d2
    assert d1.startswith("sha256:")


def test_calibration_error_is_a_value_error_subclass() -> None:
    assert issubclass(WilsonIntervalError, CalibrationError)
    assert issubclass(AdaptiveBinError, CalibrationError)
    assert issubclass(CohortCalibrationError, CalibrationError)
    assert issubclass(PosthocCalibrationError, CalibrationError)
    assert issubclass(EceError, CalibrationError)
    assert issubclass(CalibrationError, ValueError)


# --- descriptive-only interval marker (governed clarification, founder 2026-07-16) -----------


def test_interval_kind_is_a_single_member_descriptive_enum() -> None:
    from l8_evidence.calibration import IntervalKind

    assert [m.name for m in IntervalKind] == ["DESCRIPTIVE_WILSON"]


def test_every_curve_point_is_marked_descriptive_wilson() -> None:
    from l8_evidence.calibration import IntervalKind

    races = [_race("r1", (Decimal("0.6"), Decimal("0.4")), winner_index=0)]
    curve = reliability_curve(races, _bands(), confidence_level=Decimal("0.95"))
    assert curve, "fixture must produce at least one curve point"
    for point in curve:
        assert point.interval_kind is IntervalKind.DESCRIPTIVE_WILSON


def test_interval_kind_is_a_mandatory_field() -> None:
    import dataclasses as _dc

    from l8_evidence.calibration import ReliabilityCurvePoint

    field_names = [f.name for f in _dc.fields(ReliabilityCurvePoint)]
    assert "interval_kind" in field_names
    kind_field = next(f for f in _dc.fields(ReliabilityCurvePoint) if f.name == "interval_kind")
    assert kind_field.default is _dc.MISSING, "interval_kind must have no default"
