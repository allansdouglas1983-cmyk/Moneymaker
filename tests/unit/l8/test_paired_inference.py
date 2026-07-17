"""SPEC-090: race-level paired inference.

Primary unit is the race: ``d_r = L_r(market) - L_r(combined)`` using ``-log p`` on the
actual winner, with a block bootstrap clustered by meeting-day. Runner-level independence
assumptions must not appear anywhere in this module's API.
"""
from __future__ import annotations

import inspect
import math
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from l8_evidence.paired_inference import (
    BootstrapConfigError,
    BootstrapResult,
    InsufficientMeetingDaysError,
    PairedDifferencesError,
    PairedRace,
    PairedRaceError,
    RaceDifference,
    block_bootstrap_ci,
    bootstrap_resample_means,
    empirical_percentile,
    paired_differences,
)

from sport_core.clustering import ClusterId


def _cid(day: date) -> ClusterId:
    # racing dependence-group identity for tests (A4); identity only, no order
    return ClusterId(f"horse_racing:day:{day.isoformat()}")

pytestmark = pytest.mark.spec("SPEC-090")

_DAY1 = date(2026, 6, 1)
_DAY2 = date(2026, 6, 2)


def _race(
    race_id: str = "race-1",
    meeting_day: date = _DAY1,
    p_market: Decimal = Decimal("0.4"),
    p_combined: Decimal = Decimal("0.5"),
) -> PairedRace:
    return PairedRace(
        race_id=race_id,
        cluster_id=_cid(meeting_day),
        p_market_winner=p_market,
        p_combined_winner=p_combined,
    )


# --- d_r sign convention, hand-computed --------------------------------------------------


def test_d_r_hand_computed_positive_when_combined_beats_market() -> None:
    race = _race(p_market=Decimal("0.4"), p_combined=Decimal("0.5"))
    expected = math.log(0.5) - math.log(0.4)
    assert race.d_r == pytest.approx(expected)
    assert race.d_r > 0.0


def test_d_r_hand_computed_negative_when_market_beats_combined() -> None:
    race = _race(p_market=Decimal("0.6"), p_combined=Decimal("0.3"))
    expected = math.log(0.3) - math.log(0.6)
    assert race.d_r == pytest.approx(expected)
    assert race.d_r < 0.0


def test_d_r_zero_when_probabilities_equal() -> None:
    race = _race(p_market=Decimal("0.25"), p_combined=Decimal("0.25"))
    assert race.d_r == pytest.approx(0.0, abs=1e-12)


# --- PairedRace validation ----------------------------------------------------------------


def test_paired_race_rejects_empty_race_id() -> None:
    with pytest.raises(PairedRaceError):
        _race(race_id="")


@pytest.mark.parametrize("bad", [Decimal("0"), Decimal("1"), Decimal("-0.1"), Decimal("1.1")])
def test_paired_race_rejects_out_of_range_p_market(bad: Decimal) -> None:
    with pytest.raises(PairedRaceError):
        _race(p_market=bad)


@pytest.mark.parametrize("bad", [Decimal("0"), Decimal("1"), Decimal("-0.1"), Decimal("1.1")])
def test_paired_race_rejects_out_of_range_p_combined(bad: Decimal) -> None:
    with pytest.raises(PairedRaceError):
        _race(p_combined=bad)


# --- paired_differences: duplicates, empty ------------------------------------------------


def test_paired_differences_refuses_empty_input() -> None:
    with pytest.raises(PairedDifferencesError):
        paired_differences(())


def test_paired_differences_refuses_duplicate_race_ids() -> None:
    races = (_race(race_id="race-1"), _race(race_id="race-1", meeting_day=_DAY2))
    with pytest.raises(PairedDifferencesError):
        paired_differences(races)


def test_paired_differences_preserves_order_and_values() -> None:
    races = (
        _race(race_id="race-1", p_market=Decimal("0.4"), p_combined=Decimal("0.5")),
        _race(race_id="race-2", meeting_day=_DAY2, p_market=Decimal("0.3"), p_combined=Decimal("0.2")),
    )
    diffs = paired_differences(races)
    assert isinstance(diffs, tuple)
    assert [d.race_id for d in diffs] == ["race-1", "race-2"]
    assert all(isinstance(d, RaceDifference) for d in diffs)
    assert diffs[0].d_r == pytest.approx(math.log(0.5) - math.log(0.4))
    assert diffs[1].d_r == pytest.approx(math.log(0.2) - math.log(0.3))


def test_paired_differences_works_on_a_single_meeting_day() -> None:
    # paired_differences itself has no meeting-day-count restriction: that restriction is
    # specific to the bootstrap (which needs >= 2 days to estimate between-day variance).
    races = (_race(race_id="race-1"), _race(race_id="race-2"))
    diffs = paired_differences(races)
    assert len(diffs) == 2


# --- empirical_percentile: hand-computed fixture -------------------------------------------


def test_empirical_percentile_hand_fixture() -> None:
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert empirical_percentile(values, Decimal("0.5")) == pytest.approx(30.0)
    assert empirical_percentile(values, Decimal("0.25")) == pytest.approx(20.0)
    assert empirical_percentile(values, Decimal("0.1")) == pytest.approx(14.0)
    assert empirical_percentile(values, Decimal("0")) == pytest.approx(10.0)
    assert empirical_percentile(values, Decimal("1")) == pytest.approx(50.0)


def test_empirical_percentile_single_value() -> None:
    assert empirical_percentile([42.0], Decimal("0.3")) == pytest.approx(42.0)


def test_empirical_percentile_refuses_empty_sample() -> None:
    with pytest.raises(BootstrapConfigError):
        empirical_percentile([], Decimal("0.5"))


@pytest.mark.parametrize("bad_q", [Decimal("-0.01"), Decimal("1.01")])
def test_empirical_percentile_refuses_out_of_range_quantile(bad_q: Decimal) -> None:
    with pytest.raises(BootstrapConfigError):
        empirical_percentile([1.0, 2.0], bad_q)


# --- block_bootstrap_ci / bootstrap_resample_means: config validation ----------------------


def _two_day_races(n_per_day: int = 3) -> tuple[PairedRace, ...]:
    races = []
    for i in range(n_per_day):
        races.append(_race(race_id=f"a-{i}", meeting_day=_DAY1, p_market=Decimal("0.5"), p_combined=Decimal("0.5")))
    for i in range(n_per_day):
        races.append(
            _race(
                race_id=f"b-{i}",
                meeting_day=_DAY2,
                p_market=Decimal("0.5"),
                p_combined=Decimal("0.6"),
            )
        )
    return tuple(races)


def test_block_bootstrap_ci_refuses_single_meeting_day() -> None:
    races = (_race(race_id="race-1"), _race(race_id="race-2"))  # both default to _DAY1
    with pytest.raises(InsufficientMeetingDaysError):
        block_bootstrap_ci(races, n_resamples=10, confidence_level=Decimal("0.9"), seed=1)


def test_bootstrap_resample_means_refuses_single_meeting_day() -> None:
    races = (_race(race_id="race-1"), _race(race_id="race-2"))
    with pytest.raises(InsufficientMeetingDaysError):
        bootstrap_resample_means(races, n_resamples=10, seed=1)


@pytest.mark.parametrize("bad_conf", [Decimal("0"), Decimal("1"), Decimal("-0.5"), Decimal("1.5")])
def test_block_bootstrap_ci_refuses_bad_confidence_level(bad_conf: Decimal) -> None:
    races = _two_day_races()
    with pytest.raises(BootstrapConfigError):
        block_bootstrap_ci(races, n_resamples=10, confidence_level=bad_conf, seed=1)


@pytest.mark.parametrize("bad_n", [0, -1, -10])
def test_block_bootstrap_ci_refuses_non_positive_n_resamples(bad_n: int) -> None:
    races = _two_day_races()
    with pytest.raises(BootstrapConfigError):
        block_bootstrap_ci(races, n_resamples=bad_n, confidence_level=Decimal("0.9"), seed=1)


@pytest.mark.parametrize("bad_n", [0, -1, -10])
def test_bootstrap_resample_means_refuses_non_positive_n_resamples(bad_n: int) -> None:
    races = _two_day_races()
    with pytest.raises(BootstrapConfigError):
        bootstrap_resample_means(races, n_resamples=bad_n, seed=1)


def test_block_bootstrap_ci_refuses_empty_and_duplicate_input() -> None:
    with pytest.raises(PairedDifferencesError):
        block_bootstrap_ci((), n_resamples=10, confidence_level=Decimal("0.9"), seed=1)
    dup = (_race(race_id="dup", meeting_day=_DAY1), _race(race_id="dup", meeting_day=_DAY2))
    with pytest.raises(PairedDifferencesError):
        block_bootstrap_ci(dup, n_resamples=10, confidence_level=Decimal("0.9"), seed=1)


# --- determinism ----------------------------------------------------------------------------


def test_block_bootstrap_ci_same_seed_is_byte_identical() -> None:
    races = _two_day_races(n_per_day=5)
    result_a = block_bootstrap_ci(races, n_resamples=200, confidence_level=Decimal("0.9"), seed=42)
    result_b = block_bootstrap_ci(races, n_resamples=200, confidence_level=Decimal("0.9"), seed=42)
    assert result_a == result_b
    assert result_a.content_digest() == result_b.content_digest()


def test_bootstrap_resample_means_same_seed_is_identical() -> None:
    races = _two_day_races(n_per_day=5)
    means_a = bootstrap_resample_means(races, n_resamples=200, seed=7)
    means_b = bootstrap_resample_means(races, n_resamples=200, seed=7)
    assert means_a == means_b


def test_block_bootstrap_ci_different_seed_generally_differs() -> None:
    races = _two_day_races(n_per_day=5)
    result_a = block_bootstrap_ci(races, n_resamples=200, confidence_level=Decimal("0.9"), seed=1)
    result_b = block_bootstrap_ci(races, n_resamples=200, confidence_level=Decimal("0.9"), seed=2)
    assert result_a.content_digest() != result_b.content_digest()


# --- blocks stay together: day-clustering property -----------------------------------------


def test_block_bootstrap_keeps_meeting_days_together() -> None:
    # Two days, each internally homogeneous but very different from each other: day 1's
    # races all have d_r = d1, day 2's races all have d_r = d2. Because each resample draws
    # exactly 2 (whole) days with replacement, only three day-combinations exist: AA, AB (==
    # BA, since a mean is order-invariant), BB. If races were instead resampled individually
    # across days, resample means would take on many more distinct values (any of the
    # possible per-race mixtures), not just these three.
    day1_races = tuple(
        _race(race_id=f"a-{i}", meeting_day=_DAY1, p_market=Decimal("0.5"), p_combined=Decimal("0.5"))
        for i in range(4)
    )  # d_r = 0.0 for every race on day 1
    day2_races = tuple(
        _race(race_id=f"b-{i}", meeting_day=_DAY2, p_market=Decimal("0.1"), p_combined=Decimal("0.9"))
        for i in range(4)
    )  # a large positive d_r for every race on day 2
    races = day1_races + day2_races

    d1 = day1_races[0].d_r
    d2 = day2_races[0].d_r
    achievable = {
        "AA": d1,
        "AB": (d1 * 4 + d2 * 4) / 8,
        "BB": d2,
    }

    means = bootstrap_resample_means(races, n_resamples=300, seed=99)
    assert len(means) == 300
    for m in means:
        assert any(math.isclose(m, target, rel_tol=1e-9, abs_tol=1e-9) for target in achievable.values()), (
            f"resample mean {m!r} is not one of the day-combination-achievable means {achievable!r}; "
            "a race must have been resampled independently of its meeting-day"
        )
    # With 300 draws from 3 equally-likely-ish combinations, we expect to see all three.
    seen_buckets = {
        min(achievable, key=lambda k: abs(achievable[k] - m)) for m in means
    }
    assert seen_buckets == set(achievable)


def test_block_bootstrap_ci_mean_d_is_plain_mean_not_resample_derived() -> None:
    races = _two_day_races(n_per_day=3)
    diffs = paired_differences(races)
    expected_mean = sum(d.d_r for d in diffs) / len(diffs)
    result = block_bootstrap_ci(races, n_resamples=50, confidence_level=Decimal("0.9"), seed=5)
    assert result.mean_d == pytest.approx(expected_mean)


def test_block_bootstrap_ci_lower_le_upper() -> None:
    races = _two_day_races(n_per_day=6)
    result = block_bootstrap_ci(races, n_resamples=100, confidence_level=Decimal("0.8"), seed=3)
    assert result.lower <= result.upper


def test_block_bootstrap_ci_reports_expected_counts() -> None:
    races = _two_day_races(n_per_day=4)
    result = block_bootstrap_ci(races, n_resamples=64, confidence_level=Decimal("0.95"), seed=11)
    assert result.n_races == 8
    assert result.n_clusters == 2
    assert result.n_resamples == 64
    assert result.seed == 11
    assert result.confidence_level == Decimal("0.95")
    assert isinstance(result, BootstrapResult)


# --- no runner-level entry point anywhere ---------------------------------------------------


def test_no_public_callable_accepts_a_runner_parameter() -> None:
    import l8_evidence.paired_inference as module

    for name in module.__all__:
        obj = getattr(module, name)
        if not (inspect.isfunction(obj) or inspect.isclass(obj)):
            continue
        try:
            sig = inspect.signature(obj)
        except (TypeError, ValueError):
            continue
        for param_name in sig.parameters:
            assert "runner" not in param_name.lower(), (
                f"{name}'s parameter {param_name!r} looks runner-level; SPEC-090 requires "
                "race-level-only inputs everywhere in this module"
            )


def test_module_source_has_no_runner_id_anywhere() -> None:
    import l8_evidence.paired_inference as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "runner_id" not in source
    assert "runner_ids" not in source
