"""STAGE3-0006 §5.2 — normalization predicate with pinned tolerance boundaries + hard refusal.

A single governed normalization check guards every PMF the engine returns. These tests pin the
exact tolerance, the boundary either side of it (via nextafter), clearly (non-)normalized totals,
and — crucially — NaN and infinities, which the naive `abs(total-1) > tol` test silently ACCEPTS
(a NaN comparison is False). Kills the >/==/>=, tolerance-weakening and normalization-membership
mutants the founder flagged as making the check ineffective.
"""
from __future__ import annotations

import math

import pytest

from sport_tennis.coherence.scoring import (
    NORMALIZATION_TOLERANCE,
    CoherenceMathError,
    check_normalized,
)

_TOL = NORMALIZATION_TOLERANCE


def test_tolerance_is_exactly_1e_9() -> None:
    assert NORMALIZATION_TOLERANCE == 1e-9


def test_exactly_one_passes() -> None:
    check_normalized(1.0)


def test_within_tolerance_passes() -> None:
    check_normalized(1.0 + 0.5 * _TOL)
    check_normalized(1.0 - 0.5 * _TOL)


def test_just_beyond_tolerance_refused() -> None:
    # a total whose deviation is strictly greater than the tolerance is refused
    over = 1.0 + math.nextafter(_TOL, math.inf) + _TOL   # comfortably beyond, robust to rounding
    with pytest.raises(CoherenceMathError):
        check_normalized(over)


def test_clearly_non_normalized_refused() -> None:
    for bad in (0.0, 0.5, 1.5, 2.0, -1.0):
        with pytest.raises(CoherenceMathError):
            check_normalized(bad)


def test_nan_and_infinities_are_refused() -> None:
    # The naive `abs(total-1.0) > tol` guard ACCEPTS these (NaN comparisons are False; inf is
    # caught only because inf>tol, but NaN slips through). The governed check must refuse all.
    for bad in (math.nan, math.inf, -math.inf):
        with pytest.raises(CoherenceMathError):
            check_normalized(bad)


def test_nan_specifically_refused() -> None:
    with pytest.raises(CoherenceMathError):
        check_normalized(float("nan"))
