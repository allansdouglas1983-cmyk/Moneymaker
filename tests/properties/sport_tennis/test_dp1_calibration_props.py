"""SPEC-107 properties — AFFINE_LOGIT_CALIBRATION_FOR_DP1 (Stage 2G Slice 3)."""
from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sport_tennis.dp1_calibration import AffineLogitCalibration, CalibrationFitError

pytestmark = pytest.mark.spec("SPEC-107")

_p = st.floats(min_value=1e-9, max_value=1.0 - 1e-9, allow_nan=False)
_intercept = st.floats(min_value=-2.0, max_value=2.0, allow_nan=False)
_temperature = st.floats(min_value=0.2, max_value=5.0, allow_nan=False)


@given(p=_p)
def test_identity_parameters_reproduce_raw_exactly(p: float) -> None:
    cal = AffineLogitCalibration(intercept=0.0, temperature=1.0, tour="atp", n_rows=1)
    assert cal.apply(p) == p


@given(p=_p, intercept=_intercept, temperature=_temperature)
def test_registered_form_exact(p: float, intercept: float, temperature: float) -> None:
    cal = AffineLogitCalibration(intercept=intercept, temperature=temperature, tour="atp", n_rows=1)
    z = math.log(p / (1.0 - p))
    expected = 1.0 / (1.0 + math.exp(-(intercept + z / temperature)))
    assert cal.apply(p) == pytest.approx(expected, abs=1e-12)


@given(
    p_lo=st.floats(min_value=1e-6, max_value=0.98, allow_nan=False),
    bump=st.floats(min_value=1e-6, max_value=0.019, allow_nan=False),
    intercept=_intercept,
    temperature=_temperature,
)
def test_calibration_is_strictly_monotone(
    p_lo: float, bump: float, intercept: float, temperature: float
) -> None:
    """temperature > 0 makes the registered map order-preserving: calibration can
    reshape probabilities but never reverse a ranking."""
    cal = AffineLogitCalibration(intercept=intercept, temperature=temperature, tour="wta", n_rows=1)
    assert cal.apply(p_lo + bump) > cal.apply(p_lo)


@given(p=_p, intercept=_intercept, temperature=_temperature)
def test_pair_application_coherent(p: float, intercept: float, temperature: float) -> None:
    cal = AffineLogitCalibration(intercept=intercept, temperature=temperature, tour="atp", n_rows=1)
    p_a, p_b = cal.apply_pair(p)
    assert p_a + p_b == 1.0
    assert 0.0 < p_a < 1.0


@given(temperature=st.floats(max_value=0.0, allow_nan=False))
def test_non_positive_temperature_always_refused(temperature: float) -> None:
    with pytest.raises(CalibrationFitError):
        AffineLogitCalibration(intercept=0.0, temperature=temperature, tour="atp", n_rows=1)
