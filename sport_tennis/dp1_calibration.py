"""SPEC-107 — AFFINE_LOGIT_CALIBRATION_FOR_DP1 (Stage 2G; ADR 0019).

Registration: specs/programme/dp1-glicko2-registration-v1.yaml `calibration` block —
the ONLY registered calibration: z = logit(p_raw); z_cal = intercept + z/temperature;
p_cal = sigmoid(z_cal). Fitted ONLY on leakage-safe out-of-fold DP1 predictions:
consumption re-verifies SPEC-031 through the crossfit contamination check, so a row
whose model saw its own match is REFUSED, never down-weighted. ATP/WTA are fitted
separately by the caller (the object pins its tour). Raw probabilities are never
mutated — calibration returns new values.

Choice-set coherence: the affine intercept breaks two-sided symmetry, so calibration
is applied to the CANONICAL orientation (the lower runner id, matching the family's
sorted orientation) and the opponent takes the exact complement (`apply_pair`). The
fit consumes one canonical row per match for the same reason (both complementary rows
would double-count each match and make the intercept unidentifiable coherently).

No method contest, no isotonic, no band/surface correction, no retrospective change
(directive §7). Temperature must be positive: a fit whose slope is not positive cannot
be represented by the registered form and is refused — never coerced.

"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from l4_pricing.crossfit import CrossFitViolation, OOFFundamental, assert_out_of_fold
from l4_pricing.horizon import HorizonLabel
from l4_pricing.races import Race

__all__ = [
    "AFFINE_CALIBRATION_VERSION",
    "DET_EPSILON",
    "MAX_NEWTON_ITERATIONS",
    "STEP_EPSILON",
    "AffineLogitCalibration",
    "CalibrationFitError",
    "fit_affine_logit_calibration",
    "hessian_is_singular",
    "newton_iteration_allowed",
    "parameters_finite",
    "slope_is_valid",
    "step_has_converged",
]

AFFINE_CALIBRATION_VERSION = "affine-logit-dp1-v1"

# Newton policy (predicate-seam pattern; mirrors the governed harness constants).
MAX_NEWTON_ITERATIONS = 100
DET_EPSILON = 1e-12
STEP_EPSILON = 1e-11


class CalibrationFitError(Exception):
    """The affine-logit fit (or its parameters) cannot honestly be produced."""


def newton_iteration_allowed(iterations: int, maximum: int) -> bool:
    """Predicate seam: may the Newton solver take another step?"""
    return iterations < maximum


def hessian_is_singular(det: float) -> bool:
    """Predicate seam: is the 2x2 Hessian determinant numerically singular?"""
    return abs(det) <= DET_EPSILON


def step_has_converged(step_norm: float) -> bool:
    """Predicate seam: has the Newton step's infinity norm converged?"""
    return step_norm <= STEP_EPSILON


def parameters_finite(a: float, b: float) -> bool:
    """Predicate seam (founder §10): BOTH fitted parameters must be finite. A one-sided
    non-finite value must be refused immediately, never deferred downstream."""
    return math.isfinite(a) and math.isfinite(b)


def slope_is_valid(b: float) -> bool:
    """Predicate seam (founder §11): the fitted slope must be finite AND strictly
    positive (temperature = 1/slope must be finite and > 0). Every non-positive or
    non-finite slope is refused before the reciprocal is ever computed."""
    return math.isfinite(b) and b > 0.0


def _sigmoid(x: float) -> float:
    if x >= 0.0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def _logit(p: float) -> float:
    if not (0.0 < p < 1.0):
        raise CalibrationFitError(f"probability must be strictly inside (0, 1), got {p!r}")
    return math.log(p / (1.0 - p))


@dataclass(frozen=True)
class AffineLogitCalibration:
    """The fitted registered calibration for ONE tour. Immutable."""

    intercept: float
    temperature: float
    tour: str
    n_rows: int

    def __post_init__(self) -> None:
        if not math.isfinite(self.intercept):
            raise CalibrationFitError(f"intercept must be finite, got {self.intercept!r}")
        if not (math.isfinite(self.temperature) and self.temperature > 0.0):
            raise CalibrationFitError(
                f"temperature must be finite and positive, got {self.temperature!r} — the "
                "registered form cannot represent a non-positive temperature"
            )
        if not self.tour or self.tour != self.tour.strip():
            raise CalibrationFitError(f"tour must be non-empty trimmed text, got {self.tour!r}")
        if self.n_rows < 0:
            raise CalibrationFitError(f"n_rows must be >= 0, got {self.n_rows!r}")

    def apply(self, p_raw: float) -> float:
        """The registered map. Identity parameters reproduce the raw value EXACTLY."""
        if not (0.0 < p_raw < 1.0):
            raise CalibrationFitError(f"p_raw must be strictly inside (0, 1), got {p_raw!r}")
        if self.intercept == 0.0 and self.temperature == 1.0:
            return p_raw
        calibrated = _sigmoid(self.intercept + _logit(p_raw) / self.temperature)
        # Governed probability bounds (mirrors SPEC-106's floor): float saturation at
        # extreme parameters must not emit 0.0/1.0 — those are not valid probabilities.
        return min(1.0 - 1e-12, max(1e-12, calibrated))

    def apply_pair(self, p_raw_canonical: float) -> tuple[float, float]:
        """Calibrate the canonical (lower runner id) orientation; the opponent is the
        exact complement, so the choice set stays coherent."""
        p = self.apply(p_raw_canonical)
        return p, 1.0 - p


def fit_affine_logit_calibration(
    races: Sequence[Race],
    oof: Sequence[OOFFundamental],
    *,
    horizon: HorizonLabel,
    tour: str,
    maximum: int = MAX_NEWTON_ITERATIONS,
) -> AffineLogitCalibration:
    """MLE for (intercept, temperature) on strictly out-of-fold DP1 predictions.

    One canonical row per match (lower runner id). Newton on the two-parameter
    Bernoulli likelihood of P(canonical wins) = sigmoid(a + b*z), z = logit(p_raw);
    temperature = 1/b, refused unless b > 0.
    """
    if not races:
        raise CalibrationFitError("cannot fit a calibration on an empty corpus")
    races_by_id: dict[str, Race] = {}
    for race in races:
        if race.race_id in races_by_id:
            raise CalibrationFitError(f"duplicate race id {race.race_id!r} in the corpus")
        races_by_id[race.race_id] = race

    assert_out_of_fold(oof, races_by_id)
    canonical: dict[str, OOFFundamental] = {}
    for row in oof:
        if row.provenance.horizon != horizon:
            raise CrossFitViolation(
                f"OOF row for race {row.race_id!r} carries horizon "
                f"{str(row.provenance.horizon)!r}, expected {str(horizon)!r}"
            )
        race = races_by_id[row.race_id]
        low = min(r.runner_id for r in race.runners if not r.non_runner)
        if row.runner_id == low:
            if row.race_id in canonical:
                raise CalibrationFitError(f"duplicate canonical OOF row for race {row.race_id!r}")
            canonical[row.race_id] = row

    points: list[tuple[float, float]] = []
    for race_id in sorted(canonical):
        race = races_by_id[race_id]
        if race.winner_id is None:
            raise CalibrationFitError(
                f"unlabelled race {race_id!r} in a calibration corpus — exclusions happen "
                "upstream with reasons, never silently here"
            )
        row = canonical[race_id]
        y = 1.0 if race.winner_id == row.runner_id else 0.0
        points.append((_logit(row.p_fundamental), y))
    if not points:
        raise CalibrationFitError("no canonical out-of-fold rows to fit on")

    a, b = 0.0, 1.0
    iterations = 0
    while True:
        grad_a_terms: list[float] = []
        grad_b_terms: list[float] = []
        h_aa_terms: list[float] = []
        h_ab_terms: list[float] = []
        h_bb_terms: list[float] = []
        for z, y in points:
            p = _sigmoid(a + b * z)
            w = p * (1.0 - p)
            grad_a_terms.append(y - p)
            grad_b_terms.append((y - p) * z)
            h_aa_terms.append(w)
            h_ab_terms.append(w * z)
            h_bb_terms.append(w * z * z)
        g_a = math.fsum(grad_a_terms)
        g_b = math.fsum(grad_b_terms)
        h_aa = math.fsum(h_aa_terms)
        h_ab = math.fsum(h_ab_terms)
        h_bb = math.fsum(h_bb_terms)
        det = h_aa * h_bb - h_ab * h_ab
        if hessian_is_singular(det):
            raise CalibrationFitError(
                f"singular Hessian (det={det!r}) — separated or degenerate calibration data "
                "is refused, never regularised"
            )
        step_a = (h_bb * g_a - h_ab * g_b) / det
        step_b = (h_aa * g_b - h_ab * g_a) / det
        a += step_a
        b += step_b
        if not parameters_finite(a, b):
            raise CalibrationFitError("calibration fit diverged to non-finite parameters")
        if step_has_converged(max(abs(step_a), abs(step_b))):
            break
        iterations += 1
        if not newton_iteration_allowed(iterations, maximum):
            raise CalibrationFitError(
                f"calibration fit did not converge in {maximum} Newton "
                "iterations — refused, never truncated"
            )

    if not slope_is_valid(b):
        raise CalibrationFitError(
            f"fitted slope {b!r} is not finite and positive: the registered form "
            "(temperature = 1/slope) cannot represent anti-informative predictions — refused"
        )
    return AffineLogitCalibration(
        intercept=a, temperature=1.0 / b, tour=tour, n_rows=len(points)
    )
