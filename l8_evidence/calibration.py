"""SPEC-097: race-level calibration metrics — the reliability-with-CI extension.

SPEC-038 (``l8_evidence.predictor_metrics``) already implements race-level log score,
multiclass Brier, calibration-in-the-large, calibration slope on race-normalised logits,
reliability by approved bands (point estimates only), and cohort breakdowns. This module
does NOT duplicate any of that. It extends the calibration family with exactly what
SPEC-097 adds on top:

* Reliability curves WITH a confidence interval per band (:func:`reliability_curve`,
  :class:`ReliabilityCurvePoint`) — a Wilson score interval (deterministic, no resampling)
  for the observed win rate in each band, with an explicit zero-count band producing NO
  curve point at all (an absent point, never a fabricated zero).
* ADAPTIVE (equal-count) binning (:func:`adaptive_bins`) that derives its own bin edges
  from the empirical quantiles of the pooled predicted probabilities, rather than requiring
  a pre-registered fixed partition the way SPEC-038's approved bands do.
* Cohort calibration (:func:`calibration_by_cohort`) — the odds-band / track / field-size /
  period breakdowns SPEC-097 names are all the SAME operation (a reliability curve computed
  per caller-supplied cohort label). This module never invents a cohort definition; an
  unlabelled race is refused, mirroring ``predictor_metrics.evaluate_cohorts``.
* Post-hoc calibration that RENORMALISES within each race (:func:`apply_posthoc_calibration`,
  :class:`PosthocCalibrator`) — v1 implements exactly one method, temperature scaling on
  log-probabilities. Fitting the temperature is a training-time concern gated elsewhere (a
  future model-training slice, itself subject to its own approval/versioning discipline);
  this module only APPLIES an already-versioned, already-approved calibrator, deterministically,
  to already-produced probabilities. There is no automatic/live fitting anywhere here
  (CLAUDE.md: "No automatic live learning").
* Expected Calibration Error, explicitly and irreversibly marked diagnostic-only
  (:func:`expected_calibration_error`, :class:`EceDiagnostic`) — ``.claude/rules/evidence.md``
  / SPECIFICATION.md §9.3 name ``ECE <= 0.02`` as a REJECTED borrowed-threshold gate. This
  module makes that unenforceable by construction: :class:`EceDiagnostic` has no ordering
  (no ``__lt__``/``__le__``/... , no ``functools.total_ordering``) and there is no
  threshold-comparison helper anywhere in this module.

This module MUST NOT import ``l5_decision``, ``l5b_risk``, ``l6_broker`` or ``l7_settle`` —
like ``predictor_metrics``, it is a read-only analytics consumer (ADR 0013,
``.claude/rules/analytics.md``). It never prices, sizes or decides anything; every number
here is a diagnostic computed by deterministic arithmetic in this file, or reused directly
from ``l8_evidence.predictor_metrics`` / ``l8_evidence.paired_inference`` /
``l8_evidence.sample_size``. No LLM creates, alters, smooths or repairs any probability or
metric value in this module.

Ambiguity resolutions taken while drafting this slice (see the task's final report for the
full list):

* **Confidence interval method.** "Reliability curves ... with CIs" is read as a Wilson
  score interval for the observed win-rate binomial proportion in each band — deterministic
  given the band's (successes, total) counts and a caller-supplied ``confidence_level``, in
  contrast to :mod:`l8_evidence.paired_inference`'s bootstrap CI which needs resampling
  because it is estimating a MEAN over meeting-day blocks, not a single binomial proportion.
  The two-sided normal quantile ``z`` is taken from
  :func:`l8_evidence.sample_size.standard_normal_inverse_cdf` (reused, not re-derived).
  Wilson (1927):

      p_hat  = successes / total
      z      = Phi^-1(1 - (1 - confidence_level) / 2)
      center = (p_hat + z**2 / (2*total)) / (1 + z**2 / total)
      margin = (z / (1 + z**2 / total)) * sqrt(p_hat*(1 - p_hat)/total + z**2/(4*total**2))
      (lower, upper) = (center - margin, center + margin), clipped to [0, 1] to absorb any
      last-bit floating-point overshoot (the closed-form interval is always within [0, 1]).

  :func:`reliability_curve` reuses ``predictor_metrics.reliability_by_band`` for the
  approved-partition validation, the mean predicted probability and the (exact integer)
  band count, but recovers the exact integer number of successes via
  ``round(mean_observed * count)`` rather than re-walking every race a second time: each
  per-runner observed value is exactly ``0.0`` or ``1.0``, so ``sum(obs)`` is an exact
  integer-valued float for any realistic band size, and dividing then re-multiplying by the
  same integer count reintroduces at most a few ULP of floating-point error — far below
  ``0.5``, so ``round()`` recovers the true integer exactly.
* **A zero-count band produces no curve point at all.** A Wilson interval is undefined for
  zero trials; rather than returning a fabricated ``(0.0, 0.0)`` point, the band is simply
  absent from the returned tuple (explicit absence, never a fake zero —
  ``.claude/rules/evidence.md``: "Missing data -> explicit exclusion ... never a
  disappearance" — here read as: never silently present a manufactured value either).
* **Adaptive (equal-count) bins.** Cut points are the empirical ``i/n_bins`` quantiles
  (``i = 1 .. n_bins - 1``) of the POOLED predicted probabilities across every supplied
  runner-outcome pair, computed by :func:`l8_evidence.paired_inference.empirical_percentile`
  (reused, not re-implemented) over the probabilities converted to ``float`` (quantile
  estimation is a diagnostic, not a priced/staked value). Each float cut point is converted
  back to ``Decimal`` via ``Decimal(repr(x))`` — ``repr`` on a Python float is the shortest
  decimal string that round-trips to the same float, so this conversion is exact for any
  cut point that in fact coincides with one of the original (float-converted) probability
  values, which is what an empirical quantile of a finite discrete sample always is. Band
  MEMBERSHIP counts, by contrast, are computed by re-using
  :meth:`predictor_metrics.ReliabilityBand.contains` directly against the ORIGINAL
  (never-converted) ``Decimal`` probabilities, so a race's actual predicted probability is
  never itself passed through a float round-trip for the purpose of assigning it to a band.
  The partition is gap-free and spans ``(0, 1]`` BY CONSTRUCTION (the edge list is always
  ``[0, cut_1, ..., cut_{n_bins-1}, 1]``), so no separate partition-validator call is needed;
  each individual :class:`~l8_evidence.predictor_metrics.ReliabilityBand`'s own
  ``__post_init__`` still enforces ``lower < upper`` per band, which is exactly what catches
  a collapsed (duplicate) quantile edge.
  Refuses ``n_bins < 2`` (an "adaptive binning" of one bin is not a partition, it is
  everything) and refuses when the number of DISTINCT observed ``Decimal`` probabilities is
  below ``n_bins`` — equal-count binning needs at least ``n_bins`` distinct values to even
  in principle produce ``n_bins`` distinct edges; below that it is honest to refuse rather
  than silently emit fewer, unequally-sized bins under an equal-count label. As a second,
  independent defence, the computed float cut points are also checked for strict ascent
  after conversion; a collapse there (which could in principle happen even with enough
  distinct values, e.g. a heavily skewed distribution) is refused with the same error.
  Each returned band's ``label`` carries its member count directly (e.g.
  ``"adaptive-2-of-4 (n=37)"``) since :class:`~l8_evidence.predictor_metrics.ReliabilityBand`
  itself has no count field — reusing that type rather than inventing a parallel one means
  the count has to travel in the label text, and this module documents that as the reason,
  not as an accident.
* **Cohort calibration.** ``calibration_by_cohort`` never invents what a "cohort" is — the
  caller supplies ``cohort_of: race_id -> label`` (derived, at the call site, from an odds
  band, a track, a field-size bucket, a period, or any other grouping), mirroring
  ``predictor_metrics.evaluate_cohorts``. An input race with no cohort label is refused, not
  silently dropped from a breakdown.
* **Post-hoc calibration / temperature scaling.** Given per-runner probabilities ``p_i`` in
  one race and a temperature ``T > 0``, the calibrated probability is
  ``c_i = p_i**(1/T) / sum_j(p_j**(1/T))`` — a monotone reweighting of the SAME race's
  probabilities that always renormalises to sum to 1 within the race (SPEC-097: "any
  post-hoc calibration MUST renormalise across each race"). ``T = 1`` is the identity
  (up to renormalising away any pre-existing sum-to-1 slack in the input); ``T > 1``
  flattens the distribution towards uniform (the maximum probability in the race strictly
  decreases whenever the race's probabilities are not already all equal); ``T < 1`` sharpens
  it. Fitting ``T`` from data is explicitly OUT of scope for this module (a training-time
  concern, gated and versioned elsewhere) — :class:`PosthocCalibrator` is a plain, frozen,
  already-decided value carrier; this module's only job is to APPLY it. The Decimal power
  operation is evaluated inside a ``decimal.localcontext()`` with elevated precision (50
  significant digits) so the renormalised output sums to 1 to a tolerance many orders of
  magnitude tighter than anything this platform treats as economically meaningful.
* **ECE is diagnostic only, unconditionally.** :func:`expected_calibration_error` computes
  the standard count-weighted mean absolute calibration error
  ``sum_b(count_b * |mean_predicted_b - observed_rate_b|) / sum_b(count_b)`` over a supplied
  :func:`reliability_curve` result. Its return type, :class:`EceDiagnostic`, is a frozen
  dataclass with NO ordering support (default ``@dataclass`` generates only ``__eq__``; no
  ``__lt__``/``__le__``/``__gt__``/``__ge__`` are defined and ``functools.total_ordering``
  is never applied), so ``<``/``<=``/``>``/``>=`` between two instances raise ``TypeError`` —
  by construction, not by convention. There is no threshold-comparison helper function
  anywhere in this module, matching ``.claude/rules/evidence.md``'s explicit rejection of
  ``ECE <= 0.02`` as a gate.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from decimal import Decimal, localcontext
from typing import Mapping, Sequence

from l8_evidence.paired_inference import empirical_percentile
from l8_evidence.predictor_metrics import (
    RaceEvaluationInput,
    ReliabilityBand,
    reliability_by_band,
)
from l8_evidence.sample_size import standard_normal_inverse_cdf

__all__ = [
    "CalibrationError",
    "WilsonIntervalError",
    "AdaptiveBinError",
    "CohortCalibrationError",
    "PosthocCalibrationError",
    "EceError",
    "ReliabilityCurvePoint",
    "PosthocCalibrator",
    "EceDiagnostic",
    "TEMPERATURE_SCALING_METHOD_ID",
    "TEMPERATURE_SCALING_VERSION",
    "wilson_score_interval",
    "reliability_curve",
    "adaptive_bins",
    "calibration_by_cohort",
    "apply_posthoc_calibration",
    "expected_calibration_error",
    "reliability_curve_digest",
]

_HASH_PREFIX = "sha256:"
_SUM_TOLERANCE = Decimal("1e-6")
_CALIBRATION_PRECISION = 50

#: The single post-hoc calibration method this module (v1) knows how to APPLY. Fitting a
#: temperature is out of scope here — see the module docstring.
TEMPERATURE_SCALING_METHOD_ID = "temperature-scaling"
TEMPERATURE_SCALING_VERSION = 1


class CalibrationError(ValueError):
    """Base error for this module (SPEC-097)."""


class WilsonIntervalError(CalibrationError):
    """A :func:`wilson_score_interval` argument is invalid."""


class AdaptiveBinError(CalibrationError):
    """:func:`adaptive_bins` cannot honestly form the requested equal-count partition."""


class CohortCalibrationError(CalibrationError):
    """A race supplied to :func:`calibration_by_cohort` has no cohort label."""


class PosthocCalibrationError(CalibrationError):
    """A :class:`PosthocCalibrator` or its input is invalid, or the method is unknown."""


class EceError(CalibrationError):
    """:func:`expected_calibration_error` was asked to summarise an empty curve."""


def wilson_score_interval(
    successes: int,
    total: int,
    *,
    confidence_level: Decimal,
) -> tuple[float, float]:
    """The Wilson score confidence interval for a binomial proportion (SPEC-097).

    Deterministic, closed-form — no resampling. See the module docstring for the exact
    formula. ``z`` is taken from
    :func:`l8_evidence.sample_size.standard_normal_inverse_cdf` (reused, not re-derived).

    Raises :class:`WilsonIntervalError` if ``total <= 0``, if ``successes`` is not in
    ``[0, total]``, or if ``confidence_level`` is not strictly inside ``(0, 1)``.
    """
    if total <= 0:
        raise WilsonIntervalError(f"total must be positive, got {total!r}")
    if not (0 <= successes <= total):
        raise WilsonIntervalError(
            f"successes must be in [0, total]; got successes={successes!r} total={total!r}"
        )
    if not (Decimal(0) < confidence_level < Decimal(1)):
        raise WilsonIntervalError(
            f"confidence_level must be in the open interval (0, 1), got {confidence_level!r}"
        )
    alpha = Decimal(1) - confidence_level
    tail = Decimal(1) - alpha / Decimal(2)
    z = standard_normal_inverse_cdf(float(tail))
    n = float(total)
    p_hat = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p_hat + z2 / (2.0 * n)) / denom
    margin = (z / denom) * math.sqrt(p_hat * (1.0 - p_hat) / n + z2 / (4.0 * n * n))
    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    return lower, upper


@dataclass(frozen=True)
class ReliabilityCurvePoint:
    """One band's reliability-curve point, WITH a confidence interval (SPEC-097).

    Extends ``predictor_metrics.reliability_by_band``'s point estimates with ``ci_lower``/
    ``ci_upper`` (a Wilson interval, see the module docstring). A band with zero members
    never becomes an instance of this type — see :func:`reliability_curve`.
    """

    label: str
    lower: Decimal
    upper: Decimal
    mean_predicted: float
    observed_rate: float
    count: int
    ci_lower: float
    ci_upper: float

    def __post_init__(self) -> None:
        if not self.label or not self.label.strip():
            raise CalibrationError("ReliabilityCurvePoint label must be non-empty")
        if not (Decimal(0) <= self.lower < self.upper <= Decimal(1)):
            raise CalibrationError(
                f"band {self.label!r}: requires 0 <= lower < upper <= 1, got "
                f"lower={self.lower!r} upper={self.upper!r}"
            )
        if self.count <= 0:
            raise CalibrationError(
                f"band {self.label!r}: count must be positive (an empty band gets no "
                "curve point at all, never a zero-count point)"
            )
        if not (0.0 <= self.ci_lower <= self.ci_upper <= 1.0):
            raise CalibrationError(
                f"band {self.label!r}: requires 0 <= ci_lower <= ci_upper <= 1, got "
                f"ci_lower={self.ci_lower!r} ci_upper={self.ci_upper!r}"
            )


def reliability_curve(
    races: Sequence[RaceEvaluationInput],
    bands: Sequence[ReliabilityBand],
    *,
    confidence_level: Decimal,
) -> tuple[ReliabilityCurvePoint, ...]:
    """A reliability curve WITH a Wilson confidence interval per band (SPEC-097).

    Reuses ``predictor_metrics.reliability_by_band`` for the approved-partition validation
    and the (mean_predicted, mean_observed, count) aggregates, then attaches a Wilson
    interval to every band that actually has members. A band with ``count == 0`` produces
    NO point in the returned tuple at all — see the module docstring's "zero-count band"
    ambiguity resolution.
    """
    band_stats = reliability_by_band(races, bands)
    points: list[ReliabilityCurvePoint] = []
    for band in sorted(bands, key=lambda b: b.lower):
        mean_predicted, mean_observed, count = band_stats[band.label]
        if count == 0:
            continue
        successes = round(mean_observed * count)
        ci_lower, ci_upper = wilson_score_interval(
            successes, count, confidence_level=confidence_level
        )
        points.append(
            ReliabilityCurvePoint(
                label=band.label,
                lower=band.lower,
                upper=band.upper,
                mean_predicted=mean_predicted,
                observed_rate=mean_observed,
                count=count,
                ci_lower=ci_lower,
                ci_upper=ci_upper,
            )
        )
    return tuple(points)


def _decimal_from_float(value: float) -> Decimal:
    """Exact-for-quantiles float->Decimal conversion via ``repr`` round-tripping.

    See the module docstring's "Adaptive (equal-count) bins" ambiguity resolution.
    """
    return Decimal(repr(value))


def adaptive_bins(
    races: Sequence[RaceEvaluationInput],
    *,
    n_bins: int,
) -> tuple[ReliabilityBand, ...]:
    """Equal-count (adaptive) reliability bins over the pooled predicted probabilities.

    Cut points are the empirical ``i / n_bins`` quantiles (``i = 1 .. n_bins - 1``) of every
    supplied runner-outcome pair's predicted probability, via
    :func:`l8_evidence.paired_inference.empirical_percentile`. Returns a gap-free ``(0, 1]``
    partition — the first band always starts at 0, the last always ends at 1 — as
    :class:`~l8_evidence.predictor_metrics.ReliabilityBand` instances whose ``label`` carries
    the band's member count. See the module docstring for the full ambiguity resolution.

    Raises :class:`AdaptiveBinError` if ``n_bins < 2``, if there are no runner-outcome pairs
    at all, if fewer than ``n_bins`` DISTINCT probability values are present (equal-count
    binning cannot honestly form ``n_bins`` distinct edges from fewer distinct values), or if
    the computed quantile cut points fail to strictly ascend once converted.
    """
    if n_bins < 2:
        raise AdaptiveBinError(f"n_bins must be >= 2, got {n_bins!r}")
    pooled_decimal: list[Decimal] = [
        r.probability for race in races for r in race.runners
    ]
    if not pooled_decimal:
        raise AdaptiveBinError("cannot form adaptive bins over an empty race set")
    distinct = set(pooled_decimal)
    if len(distinct) < n_bins:
        raise AdaptiveBinError(
            f"need >= {n_bins} distinct predicted probability values to form {n_bins} "
            f"equal-count bins with distinct edges; got {len(distinct)}"
        )
    pooled_float = sorted(float(p) for p in pooled_decimal)
    cut_points: list[Decimal] = []
    for i in range(1, n_bins):
        quantile = Decimal(i) / Decimal(n_bins)
        edge = empirical_percentile(pooled_float, quantile)
        cut_points.append(_decimal_from_float(edge))
    if any(a >= b for a, b in zip(cut_points, cut_points[1:])):
        raise AdaptiveBinError(
            f"adaptive bin edges collapsed (duplicate/unordered quantiles) for n_bins="
            f"{n_bins!r}; cannot form {n_bins} distinct equal-count bins from this "
            "probability distribution"
        )
    edges: list[Decimal] = [Decimal(0), *cut_points, Decimal(1)]
    bands: list[ReliabilityBand] = []
    for i in range(n_bins):
        lower, upper = edges[i], edges[i + 1]
        provisional = ReliabilityBand(label=f"adaptive-{i + 1}-of-{n_bins}", lower=lower, upper=upper)
        count = sum(1 for p in pooled_decimal if provisional.contains(p))
        bands.append(
            ReliabilityBand(
                label=f"adaptive-{i + 1}-of-{n_bins} (n={count})",
                lower=lower,
                upper=upper,
            )
        )
    return tuple(bands)


def calibration_by_cohort(
    races: Sequence[RaceEvaluationInput],
    cohort_of: Mapping[str, str],
    bands: Sequence[ReliabilityBand],
    *,
    confidence_level: Decimal,
) -> Mapping[str, tuple[ReliabilityCurvePoint, ...]]:
    """A :func:`reliability_curve` computed separately for each caller-supplied cohort.

    ``cohort_of`` maps ``race_id -> cohort_label``. This module never invents what a cohort
    is — an odds band, a track, a field-size bucket, a period are all just labels the caller
    derives before calling this function (mirrors ``predictor_metrics.evaluate_cohorts``).
    A race with no entry in ``cohort_of`` is refused, never silently dropped.
    """
    missing = [race.race_id for race in races if race.race_id not in cohort_of]
    if missing:
        raise CohortCalibrationError(f"races missing a cohort label: {sorted(missing)}")
    by_cohort: dict[str, list[RaceEvaluationInput]] = {}
    for race in races:
        by_cohort.setdefault(cohort_of[race.race_id], []).append(race)
    return {
        label: reliability_curve(by_cohort[label], bands, confidence_level=confidence_level)
        for label in sorted(by_cohort)
    }


@dataclass(frozen=True)
class PosthocCalibrator:
    """A versioned, frozen post-hoc calibration method descriptor (SPEC-097).

    Carries ``method_id`` + ``version`` + ``parameters`` only — it is a plain, already-decided
    value; nothing in this dataclass fits or trains anything. See the module docstring's
    "Post-hoc calibration / temperature scaling" ambiguity resolution for why fitting ``T``
    is explicitly out of scope for this module.
    """

    method_id: str
    version: int
    parameters: Mapping[str, Decimal]

    def __post_init__(self) -> None:
        if not self.method_id or not self.method_id.strip():
            raise PosthocCalibrationError("method_id must be non-empty")
        if self.version < 1:
            raise PosthocCalibrationError(f"version must be >= 1, got {self.version!r}")


def apply_posthoc_calibration(
    race_probabilities: Mapping[int, Decimal],
    calibrator: PosthocCalibrator,
) -> Mapping[int, Decimal]:
    """Apply ``calibrator`` to one race's runner probabilities, RENORMALISED within the race.

    v1 implements exactly one method: temperature scaling on log-probabilities,
    ``c_i = p_i**(1/T) / sum_j(p_j**(1/T))``. Refuses an empty input, any probability outside
    the open interval ``(0, 1)``, input probabilities that do not already sum to
    (approximately) 1, an unknown ``(method_id, version)``, a missing ``"T"`` parameter, or a
    non-positive ``T``. See the module docstring for the full formula discussion and why this
    function only APPLIES an already-decided calibrator rather than fitting one.
    """
    if not race_probabilities:
        raise PosthocCalibrationError("cannot apply post-hoc calibration to an empty race")
    for runner_id, probability in race_probabilities.items():
        if not (Decimal(0) < probability < Decimal(1)):
            raise PosthocCalibrationError(
                f"runner {runner_id}: probability {probability!r} must be in the open "
                "interval (0, 1)"
            )
    total = sum(race_probabilities.values(), Decimal(0))
    if abs(total - Decimal(1)) > _SUM_TOLERANCE:
        raise PosthocCalibrationError(
            f"input race probabilities sum to {total!r}, not (approximately) 1"
        )
    if (
        calibrator.method_id != TEMPERATURE_SCALING_METHOD_ID
        or calibrator.version != TEMPERATURE_SCALING_VERSION
    ):
        raise PosthocCalibrationError(
            f"unknown post-hoc calibration method {calibrator.method_id!r} version "
            f"{calibrator.version!r}; v1 implements exactly one method, "
            f"{TEMPERATURE_SCALING_METHOD_ID!r} version {TEMPERATURE_SCALING_VERSION!r}"
        )
    if "T" not in calibrator.parameters:
        raise PosthocCalibrationError(
            "temperature-scaling calibrator requires a 'T' parameter"
        )
    temperature = calibrator.parameters["T"]
    if temperature <= Decimal(0):
        raise PosthocCalibrationError(f"temperature T must be > 0, got {temperature!r}")
    with localcontext() as ctx:
        ctx.prec = _CALIBRATION_PRECISION
        exponent = Decimal(1) / temperature
        scaled = {
            runner_id: probability**exponent
            for runner_id, probability in race_probabilities.items()
        }
        total_scaled = sum(scaled.values(), Decimal(0))
        renormalised = {
            runner_id: value / total_scaled for runner_id, value in scaled.items()
        }
    return renormalised


@dataclass(frozen=True)
class EceDiagnostic:
    """Expected Calibration Error — DIAGNOSTIC ONLY (SPEC-097: "ECE is diagnostic only").

    Deliberately supports NO ordering: this dataclass defines no ``__lt__``/``__le__``/
    ``__gt__``/``__ge__`` and ``functools.total_ordering`` is never applied to it, so
    comparing two instances with any of those operators raises ``TypeError`` — by
    construction. There is no threshold-comparison helper anywhere in this module.
    ``.claude/rules/evidence.md`` names ``ECE <= 0.02`` explicitly as a REJECTED
    borrowed-threshold gate; this type makes that comparison impossible to smuggle in.
    """

    ece_diagnostic_only: float
    n_bands: int
    n_pairs: int


def expected_calibration_error(curve: Sequence[ReliabilityCurvePoint]) -> EceDiagnostic:
    """Count-weighted mean absolute calibration error over a :func:`reliability_curve` result.

    ``sum_b(count_b * |mean_predicted_b - observed_rate_b|) / sum_b(count_b)``. Diagnostic
    only — see :class:`EceDiagnostic`. Raises :class:`EceError` on an empty curve (there is
    nothing to summarise).
    """
    if not curve:
        raise EceError("cannot compute expected calibration error over an empty curve")
    total_count = sum(point.count for point in curve)
    weighted_error = sum(
        point.count * abs(point.mean_predicted - point.observed_rate) for point in curve
    )
    return EceDiagnostic(
        ece_diagnostic_only=weighted_error / total_count,
        n_bands=len(curve),
        n_pairs=total_count,
    )


def _jsonable(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _jsonable(dataclasses.asdict(value))
    return value


def reliability_curve_digest(curve: Sequence[ReliabilityCurvePoint]) -> str:
    """Deterministic ``sha256:<hex>`` over a :func:`reliability_curve` result.

    Same curve (any input order) -> identical digest, since points are sorted by ``label``
    before serialisation. House style — mirrors
    ``predictor_metrics.compute_input_digest`` / ``paired_inference.BootstrapResult
    .content_digest``.
    """
    ordered = sorted(curve, key=lambda point: point.label)
    payload = [_jsonable(asdict(point)) for point in ordered]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return _HASH_PREFIX + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
