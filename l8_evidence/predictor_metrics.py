"""SPEC-038: predictor performance ledger with versioned benchmark registry.

Race-level evaluation of forecasting quality — distinguished for fundamental,
market-baseline and combined models — joined against settlement AFTER the fact. This module
computes deterministic diagnostics only: race-level log score and multiclass Brier,
calibration-in-the-large and slope, reliability by approved bands, ranking diagnostics,
availability/coverage rates and cohort breakdowns. ROI appears only as a clearly-secondary,
frozen-policy diagnostic field; nothing here is named ``performance`` or bare ``roi`` (SPEC-038
explicitly forbids "no ambiguous field named performance").

This module MUST NOT import ``l5_decision``, ``l5b_risk``, ``l6_broker`` or ``l7_settle`` — it
is a read-only analytics consumer (ADR 0013, ``.claude/rules/analytics.md``) listed in
``tests/unit/governance/test_analytics_import_boundary.py``. It never prices, sizes or decides
anything; every number here is a diagnostic computed by deterministic arithmetic in this file
from probabilities already produced by SPEC-036/037.

No LLM creates, alters, smooths or repairs any probability or metric value in this module.

Benchmark versioning (the "versioned benchmark registry" half of SPEC-038, Amendment A):
:class:`BenchmarkDefinition` pins universe version, forecast-vintage policy (WHICH vintage is
evaluated, so nobody can cherry-pick the best-performing vintage after the result is known),
inclusion/exclusion hashes and a decision horizon. :class:`BenchmarkRegistry` refuses to
re-register the same ``(benchmark_id, version)`` with different content (in-place change
refused) and has no mutation or delete API at all — a changed definition MUST be a new version.

Ambiguity resolutions taken while drafting this slice (see the task's final report for the
full list):

* "Calibration-in-the-large" uses the standard definition from the calibration literature,
  pooled over all runner-outcome pairs (winner-only pooling would be trivially uninformative
  here since every race contributes exactly one winner): the mean predicted probability across
  every runner-outcome pair in the evaluated race set, minus the observed outcome frequency
  (1 for the winner, 0 otherwise) over the SAME pairs. Reported as
  ``mean_predicted - mean_observed`` (0 = perfectly calibrated in the large).
* "Calibration slope on race-normalised logits" is read as: for each runner-outcome pair,
  compute the centered log-probability ``z = ln(p_i) - mean_race(ln(p_j))`` (race-normalised
  logit, i.e. the log-probability minus its within-race mean, which removes the race's overall
  scale so slopes are comparable across field sizes), then fit the ordinary least-squares slope
  of the binary outcome ``y`` on ``z`` pooled across all runner-outcome pairs in the evaluated
  set. Slope of 1 = perfectly calibrated on this scale; documented exactly here since SPEC-038
  names the diagnostic but not its formula.
* "Ranking diagnostics" is read as: the winner's predicted-probability RANK within its race
  (rank 1 = favourite by this model) tabulated as a frequency distribution, plus the
  "top-1 hit rate" (fraction of races where the model's favourite is the actual winner).
* "Reliability by approved bands" bands are NEVER invented by this module — they are a
  mandatory, explicit, non-empty, ascending, gap-free partition of ``(0, 1]`` supplied by the
  caller (typically sourced from the owning ``BenchmarkDefinition``'s registered bands or an
  explicit override), enforced by :func:`reliability_by_band`.
* Coverage takes ``total_universe_races`` as an explicit input distinct from
  ``len(evaluated_races)`` specifically so a missing/excluded race lowers the ratio rather than
  disappearing from it (``.claude/rules/evidence.md``: "the universe is frozen before outcomes
  are known").
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from decimal import Decimal
from enum import Enum
from typing import Mapping, Sequence

__all__ = [
    "ModelKind",
    "ForecastVintagePolicy",
    "PredictorMetricsError",
    "BenchmarkDefinitionError",
    "BenchmarkConflictError",
    "RaceEvaluationError",
    "BenchmarkDefinition",
    "BenchmarkRegistry",
    "RunnerOutcome",
    "RaceEvaluationInput",
    "RaceMetrics",
    "OverallEvaluationResult",
    "CohortEvaluationResult",
    "ReliabilityBand",
    "CoverageResult",
    "evaluate_race",
    "evaluate_overall",
    "evaluate_cohorts",
    "reliability_by_band",
    "coverage_rate",
    "compute_input_digest",
]


class PredictorMetricsError(ValueError):
    """Base error for this module."""


class BenchmarkDefinitionError(PredictorMetricsError):
    """A :class:`BenchmarkDefinition`'s own fields are internally inconsistent."""


class BenchmarkConflictError(PredictorMetricsError):
    """An attempt to re-register ``(benchmark_id, version)`` with different content."""


class RaceEvaluationError(PredictorMetricsError):
    """A race is unfit for evaluation: unsettled, horizon-mismatched, or malformed."""


class ModelKind(Enum):
    """Which of the three SPEC-036 probability kinds a metric result is computed over.

    Every metric result carries exactly one of these — results for different kinds are never
    merged into one ambiguous number.
    """

    FUNDAMENTAL = "FUNDAMENTAL"
    MARKET_BASELINE = "MARKET_BASELINE"
    COMBINED = "COMBINED"


class ForecastVintagePolicy(Enum):
    """Which forecast vintage a benchmark evaluates — pinned so nobody can select the
    best-performing vintage after the result is known (SPEC-038 Amendment A)."""

    INITIAL_ONLY = "INITIAL_ONLY"
    FINAL_APPROVED_HORIZON_ONLY = "FINAL_APPROVED_HORIZON_ONLY"


_HASH_PREFIX = "sha256:"


def _is_sha256(value: str) -> bool:
    return value.startswith(_HASH_PREFIX) and len(value) == len(_HASH_PREFIX) + 64


@dataclass(frozen=True)
class BenchmarkDefinition:
    """A VERSIONED benchmark/evaluation-policy definition (SPEC-038 Amendment A).

    Pins the universe version, which forecast vintage is evaluated, inclusion/exclusion
    hashes, a coverage-policy description, the decision horizon, and the approved reliability
    bands (a caller-supplied, gap-free partition of ``(0, 1]`` — never invented by the metric
    functions). ``version`` is an immutable positive integer; a changed definition is always a
    NEW version, never an in-place edit (enforced by :class:`BenchmarkRegistry`, not by this
    dataclass alone).
    """

    benchmark_id: str
    version: int
    universe_version: str
    forecast_vintage_policy: ForecastVintagePolicy
    inclusion_hash: str
    exclusion_hash: str
    coverage_policy: str
    decision_horizon: str
    approved_reliability_bands: tuple["ReliabilityBand", ...]

    def __post_init__(self) -> None:
        if not self.benchmark_id or not self.benchmark_id.strip():
            raise BenchmarkDefinitionError("benchmark_id must be non-empty")
        if self.version < 1:
            raise BenchmarkDefinitionError("version must be >= 1")
        if not self.universe_version or not self.universe_version.strip():
            raise BenchmarkDefinitionError("universe_version must be non-empty")
        if not _is_sha256(self.inclusion_hash):
            raise BenchmarkDefinitionError("inclusion_hash must be a sha256:<hex> digest")
        if not _is_sha256(self.exclusion_hash):
            raise BenchmarkDefinitionError("exclusion_hash must be a sha256:<hex> digest")
        if not self.coverage_policy or not self.coverage_policy.strip():
            raise BenchmarkDefinitionError("coverage_policy must be non-empty")
        if not self.decision_horizon or not self.decision_horizon.strip():
            raise BenchmarkDefinitionError("decision_horizon must be non-empty")
        _validate_band_partition(self.approved_reliability_bands)

    def content_digest(self) -> str:
        """Deterministic ``sha256:<hex>`` over every field, for equality-of-content checks."""
        payload = _jsonable(asdict(self))
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return _HASH_PREFIX + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ReliabilityBand:
    """One band of an approved, caller-supplied reliability partition of ``(0, 1]``.

    ``lower`` is exclusive, ``upper`` is inclusive — bands are stitched ``(lower, upper]`` so a
    gap-free ascending sequence from 0 to 1 partitions every possible probability exactly once.
    """

    label: str
    lower: Decimal
    upper: Decimal

    def __post_init__(self) -> None:
        if not self.label or not self.label.strip():
            raise BenchmarkDefinitionError("reliability band label must be non-empty")
        if not (Decimal(0) <= self.lower < self.upper <= Decimal(1)):
            raise BenchmarkDefinitionError(
                f"reliability band {self.label!r}: requires 0 <= lower < upper <= 1, "
                f"got lower={self.lower!r} upper={self.upper!r}"
            )

    def contains(self, p: Decimal) -> bool:
        return self.lower < p <= self.upper


def _validate_band_partition(bands: Sequence[ReliabilityBand]) -> None:
    if not bands:
        raise BenchmarkDefinitionError("approved_reliability_bands must be non-empty")
    ordered = sorted(bands, key=lambda b: b.lower)
    if ordered[0].lower != Decimal(0):
        raise BenchmarkDefinitionError("reliability bands must start at 0")
    if ordered[-1].upper != Decimal(1):
        raise BenchmarkDefinitionError("reliability bands must end at 1")
    for prev, nxt in zip(ordered, ordered[1:]):
        if prev.upper != nxt.lower:
            raise BenchmarkDefinitionError(
                f"reliability bands must be gap-free and non-overlapping: "
                f"{prev.label!r} ends at {prev.upper!r} but {nxt.label!r} starts at {nxt.lower!r}"
            )


class BenchmarkRegistry:
    """Append-only registry of :class:`BenchmarkDefinition` keyed by ``(benchmark_id, version)``.

    No mutation or delete API exists here, by construction — a changed definition MUST be
    registered under a NEW version. Re-registering an existing ``(benchmark_id, version)`` with
    identical content is refused as a duplicate (idempotent registration is not offered: the
    caller should look the definition up instead of re-registering it); re-registering it with
    DIFFERENT content is refused as an in-place change.
    """

    def __init__(self) -> None:
        self._definitions: dict[tuple[str, int], BenchmarkDefinition] = {}

    def register(self, definition: BenchmarkDefinition) -> None:
        key = (definition.benchmark_id, definition.version)
        existing = self._definitions.get(key)
        if existing is not None:
            if existing.content_digest() == definition.content_digest():
                raise BenchmarkConflictError(
                    f"benchmark {definition.benchmark_id!r} version {definition.version} "
                    "is already registered (re-registration, even with identical content, "
                    "is refused — look it up instead)"
                )
            raise BenchmarkConflictError(
                f"benchmark {definition.benchmark_id!r} version {definition.version} is "
                "already registered with DIFFERENT content — an in-place change is refused; "
                "register a new version instead"
            )
        self._definitions[key] = definition

    def lookup(self, benchmark_id: str, version: int) -> BenchmarkDefinition:
        try:
            return self._definitions[(benchmark_id, version)]
        except KeyError:
            raise KeyError(
                f"no benchmark {benchmark_id!r} version {version} registered"
            ) from None


@dataclass(frozen=True)
class RunnerOutcome:
    """One runner's evaluated probability, paired with whether it won (SPEC-038)."""

    runner_id: int
    probability: Decimal
    is_winner: bool


@dataclass(frozen=True)
class RaceEvaluationInput:
    """One race's SETTLED evaluation input for a single :class:`ModelKind`.

    ``settled`` MUST be true — results join only AFTER settlement (SPEC-038). ``decision_horizon``
    must match the owning benchmark's horizon or the race is refused (horizon-mismatch guard).
    """

    race_id: str
    model_kind: ModelKind
    decision_horizon: str
    settled: bool
    runners: tuple[RunnerOutcome, ...]

    def __post_init__(self) -> None:
        if not self.race_id or not self.race_id.strip():
            raise RaceEvaluationError("race_id must be non-empty")
        if not self.decision_horizon or not self.decision_horizon.strip():
            raise RaceEvaluationError("decision_horizon must be non-empty")
        if not self.runners:
            raise RaceEvaluationError(f"race {self.race_id!r}: needs at least one runner")
        runner_ids = [r.runner_id for r in self.runners]
        if len(set(runner_ids)) != len(runner_ids):
            raise RaceEvaluationError(f"race {self.race_id!r}: duplicate runner ids")
        for r in self.runners:
            if not (Decimal(0) < r.probability < Decimal(1)):
                raise RaceEvaluationError(
                    f"race {self.race_id!r}: runner {r.runner_id} probability "
                    f"{r.probability!r} must be in the open interval (0, 1)"
                )
        total = sum((r.probability for r in self.runners), Decimal(0))
        if abs(total - Decimal(1)) > Decimal("1e-6"):
            raise RaceEvaluationError(
                f"race {self.race_id!r}: probabilities sum to {total!r}, not 1"
            )
        winners = [r for r in self.runners if r.is_winner]
        if len(winners) != 1:
            raise RaceEvaluationError(
                f"race {self.race_id!r}: exactly one runner must be marked the winner, "
                f"found {len(winners)}"
            )


@dataclass(frozen=True)
class RaceMetrics:
    """Per-race deterministic diagnostics computed by :func:`evaluate_race`."""

    race_id: str
    model_kind: ModelKind
    log_score: float
    brier_score: float
    winner_predicted_probability: Decimal
    winner_rank: int
    field_size: int


def evaluate_race(
    race: RaceEvaluationInput,
    benchmark: BenchmarkDefinition,
) -> RaceMetrics:
    """Evaluate one settled race against ``benchmark``.

    Raises :class:`RaceEvaluationError` if the race is unsettled or its horizon does not match
    the benchmark's pinned decision horizon — results join only after settlement, and a
    horizon-mismatched comparison is never silently accepted.
    """
    if not race.settled:
        raise RaceEvaluationError(
            f"race {race.race_id!r}: results join only AFTER settlement; this race is unsettled"
        )
    if race.decision_horizon != benchmark.decision_horizon:
        raise RaceEvaluationError(
            f"race {race.race_id!r}: decision_horizon {race.decision_horizon!r} does not match "
            f"benchmark {benchmark.benchmark_id!r} horizon {benchmark.decision_horizon!r}"
        )
    winner = next(r for r in race.runners if r.is_winner)
    log_score = -math.log(float(winner.probability))
    brier = sum(
        (float(r.probability) - (1.0 if r.is_winner else 0.0)) ** 2 for r in race.runners
    )
    # Deterministic tie-break: equal probabilities rank by ascending runner_id, so the same
    # race presented with reordered runners always yields the same winner_rank.
    ranked = sorted(race.runners, key=lambda r: (-r.probability, r.runner_id))
    winner_rank = next(i for i, r in enumerate(ranked, start=1) if r.runner_id == winner.runner_id)
    return RaceMetrics(
        race_id=race.race_id,
        model_kind=race.model_kind,
        log_score=log_score,
        brier_score=brier,
        winner_predicted_probability=winner.probability,
        winner_rank=winner_rank,
        field_size=len(race.runners),
    )


@dataclass(frozen=True)
class OverallEvaluationResult:
    """The FULL-universe evaluation result. Never a subgroup — see :class:`CohortEvaluationResult`
    for the type that carries a cohort label; there is no way to construct this type with one,
    which is the enforcement point stopping a subgroup from ever being mislabelled "overall".
    """

    benchmark_id: str
    benchmark_version: int
    model_kind: ModelKind
    races_evaluated: int
    mean_log_score: float
    mean_brier_score: float
    calibration_in_the_large: float
    calibration_slope: float | None
    top1_hit_rate: float
    winner_rank_distribution: Mapping[int, int]
    coverage: "CoverageResult"
    roi_frozen_policy_diagnostic: float | None
    input_digest: str


@dataclass(frozen=True)
class CohortEvaluationResult:
    """A cohort/subgroup evaluation result. Structurally distinct from
    :class:`OverallEvaluationResult` (different type, carries a mandatory ``cohort_label``) so a
    subgroup result can never pass a type check expecting the overall result, and vice versa —
    this is the cherry-pick guard: no code path can label a subgroup "overall".
    """

    cohort_label: str
    benchmark_id: str
    benchmark_version: int
    model_kind: ModelKind
    races_evaluated: int
    mean_log_score: float
    mean_brier_score: float
    calibration_in_the_large: float
    calibration_slope: float | None
    top1_hit_rate: float
    winner_rank_distribution: Mapping[int, int]
    roi_frozen_policy_diagnostic: float | None
    input_digest: str


@dataclass(frozen=True)
class CoverageResult:
    """Availability/coverage: evaluated races over the FULL universe, missing races included in
    the denominator (``.claude/rules/evidence.md``: "the universe is frozen before outcomes are
    known" — a missing prediction never simply disappears from the ratio)."""

    races_evaluated: int
    total_universe_races: int
    coverage_rate: float

    def __post_init__(self) -> None:
        if self.total_universe_races <= 0:
            raise PredictorMetricsError("total_universe_races must be positive")
        if self.races_evaluated < 0 or self.races_evaluated > self.total_universe_races:
            raise PredictorMetricsError(
                "races_evaluated must be between 0 and total_universe_races"
            )


def coverage_rate(races_evaluated: int, total_universe_races: int) -> CoverageResult:
    """``races_evaluated / total_universe_races`` — missing/excluded races stay in the
    denominator via the mandatory ``total_universe_races`` argument, distinct from
    ``len(evaluated_races)``, so a missing race lowers coverage rather than disappearing."""
    return CoverageResult(
        races_evaluated=races_evaluated,
        total_universe_races=total_universe_races,
        coverage_rate=races_evaluated / total_universe_races,
    )


def _race_normalised_logit(race: RaceEvaluationInput) -> dict[int, float]:
    """centred log-probability per runner: ln(p_i) - mean_race(ln(p_j))."""
    logs = {r.runner_id: math.log(float(r.probability)) for r in race.runners}
    mean_log = sum(logs.values()) / len(logs)
    return {rid: lv - mean_log for rid, lv in logs.items()}


def _ols_slope(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Ordinary least-squares slope of ``ys`` on ``xs`` (the standard slope-with-intercept OLS
    estimator, ``cov(x,y)/var(x)``).

    Returns ``None`` when the regressor has zero variance (e.g. every runner in every evaluated
    race carries an identical probability, so every race-normalised logit is 0): the slope is
    mathematically undefined there, and this module marks a diagnostic unavailable rather than
    approximating or failing the rest of the evaluation.
    """
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var = sum((x - mean_x) ** 2 for x in xs)
    if var == 0.0:
        return None
    return cov / var


def _compute_pooled_calibration(
    races: Sequence[RaceEvaluationInput],
) -> tuple[float, float | None]:
    """Returns ``(calibration_in_the_large, calibration_slope)`` pooled over every
    runner-outcome pair in ``races`` (see module docstring for the exact formulas)."""
    predicted: list[float] = []
    observed: list[float] = []
    logits: list[float] = []
    for race in races:
        centred = _race_normalised_logit(race)
        for r in race.runners:
            predicted.append(float(r.probability))
            observed.append(1.0 if r.is_winner else 0.0)
            logits.append(centred[r.runner_id])
    mean_predicted = sum(predicted) / len(predicted)
    mean_observed = sum(observed) / len(observed)
    calibration_in_the_large = mean_predicted - mean_observed
    slope = _ols_slope(logits, observed)
    return calibration_in_the_large, slope


@dataclass(frozen=True)
class _PooledFields:
    """Internal: the fields shared by :class:`OverallEvaluationResult` and
    :class:`CohortEvaluationResult`, computed once and spread into whichever typed result the
    caller needs — never merged into an untyped dict at the public boundary."""

    benchmark_id: str
    benchmark_version: int
    model_kind: ModelKind
    races_evaluated: int
    mean_log_score: float
    mean_brier_score: float
    calibration_in_the_large: float
    calibration_slope: float | None
    top1_hit_rate: float
    winner_rank_distribution: Mapping[int, int]
    roi_frozen_policy_diagnostic: float | None
    input_digest: str


def _pooled_result_fields(
    races: Sequence[RaceEvaluationInput],
    benchmark: BenchmarkDefinition,
    model_kind: ModelKind,
    roi_frozen_policy_diagnostic: float | None,
) -> _PooledFields:
    if not races:
        raise RaceEvaluationError("cannot evaluate an empty race set")
    kinds = {r.model_kind for r in races}
    if kinds != {model_kind}:
        raise RaceEvaluationError(
            f"all races evaluated together must share model_kind {model_kind.value}; got {sorted(k.value for k in kinds)}"
        )
    per_race = [evaluate_race(race, benchmark) for race in races]
    mean_log = sum(m.log_score for m in per_race) / len(per_race)
    mean_brier = sum(m.brier_score for m in per_race) / len(per_race)
    calibration_in_the_large, slope = _compute_pooled_calibration(races)
    top1_hits = sum(1 for m in per_race if m.winner_rank == 1)
    top1_hit_rate = top1_hits / len(per_race)
    rank_distribution: dict[int, int] = {}
    for m in per_race:
        rank_distribution[m.winner_rank] = rank_distribution.get(m.winner_rank, 0) + 1
    return _PooledFields(
        benchmark_id=benchmark.benchmark_id,
        benchmark_version=benchmark.version,
        model_kind=model_kind,
        races_evaluated=len(per_race),
        mean_log_score=mean_log,
        mean_brier_score=mean_brier,
        calibration_in_the_large=calibration_in_the_large,
        calibration_slope=slope,
        top1_hit_rate=top1_hit_rate,
        winner_rank_distribution=rank_distribution,
        roi_frozen_policy_diagnostic=roi_frozen_policy_diagnostic,
        input_digest=compute_input_digest(races),
    )


def evaluate_overall(
    races: Sequence[RaceEvaluationInput],
    benchmark: BenchmarkDefinition,
    model_kind: ModelKind,
    *,
    total_universe_races: int,
    roi_frozen_policy_diagnostic: float | None = None,
) -> OverallEvaluationResult:
    """Evaluate the FULL supplied universe (never a subgroup) against ``benchmark``.

    ``total_universe_races`` is mandatory and independent of ``len(races)`` so missing or
    excluded races lower :class:`CoverageResult` rather than disappearing from it.
    """
    fields = _pooled_result_fields(races, benchmark, model_kind, roi_frozen_policy_diagnostic)
    coverage = coverage_rate(fields.races_evaluated, total_universe_races)
    return OverallEvaluationResult(
        benchmark_id=fields.benchmark_id,
        benchmark_version=fields.benchmark_version,
        model_kind=fields.model_kind,
        races_evaluated=fields.races_evaluated,
        mean_log_score=fields.mean_log_score,
        mean_brier_score=fields.mean_brier_score,
        calibration_in_the_large=fields.calibration_in_the_large,
        calibration_slope=fields.calibration_slope,
        top1_hit_rate=fields.top1_hit_rate,
        winner_rank_distribution=fields.winner_rank_distribution,
        coverage=coverage,
        roi_frozen_policy_diagnostic=fields.roi_frozen_policy_diagnostic,
        input_digest=fields.input_digest,
    )


def evaluate_cohorts(
    races: Sequence[RaceEvaluationInput],
    benchmark: BenchmarkDefinition,
    model_kind: ModelKind,
    cohort_of: Mapping[str, str],
    *,
    roi_frozen_policy_diagnostic: float | None = None,
) -> tuple[CohortEvaluationResult, ...]:
    """Evaluate each cohort named by ``cohort_of`` (``race_id -> cohort_label``) SEPARATELY.

    Every input race_id must have a cohort label (an unlabelled race is refused, not silently
    dropped from a cohort breakdown). Results are typed :class:`CohortEvaluationResult`, never
    :class:`OverallEvaluationResult` — no cohort here can ever be reported as "overall".
    """
    missing = [race.race_id for race in races if race.race_id not in cohort_of]
    if missing:
        raise RaceEvaluationError(f"races missing a cohort label: {sorted(missing)}")
    by_cohort: dict[str, list[RaceEvaluationInput]] = {}
    for race in races:
        by_cohort.setdefault(cohort_of[race.race_id], []).append(race)
    results = []
    for label in sorted(by_cohort):
        fields = _pooled_result_fields(
            by_cohort[label], benchmark, model_kind, roi_frozen_policy_diagnostic
        )
        results.append(
            CohortEvaluationResult(
                cohort_label=label,
                benchmark_id=fields.benchmark_id,
                benchmark_version=fields.benchmark_version,
                model_kind=fields.model_kind,
                races_evaluated=fields.races_evaluated,
                mean_log_score=fields.mean_log_score,
                mean_brier_score=fields.mean_brier_score,
                calibration_in_the_large=fields.calibration_in_the_large,
                calibration_slope=fields.calibration_slope,
                top1_hit_rate=fields.top1_hit_rate,
                winner_rank_distribution=fields.winner_rank_distribution,
                roi_frozen_policy_diagnostic=fields.roi_frozen_policy_diagnostic,
                input_digest=fields.input_digest,
            )
        )
    return tuple(results)


def reliability_by_band(
    races: Sequence[RaceEvaluationInput],
    bands: Sequence[ReliabilityBand],
) -> Mapping[str, tuple[float, float, int]]:
    """Reliability curve keyed by APPROVED band label -> (mean_predicted, mean_observed, count).

    ``bands`` MUST be supplied explicitly by the caller (typically a
    :class:`BenchmarkDefinition`'s ``approved_reliability_bands``) — this function never
    invents default bands. A runner-outcome pair with no matching band raises, since
    :func:`_validate_band_partition`-style callers are expected to supply a full ``(0, 1]``
    partition; this function itself re-validates that invariant defensively.
    """
    _validate_band_partition(bands)
    accum: dict[str, tuple[list[float], list[float]]] = {b.label: ([], []) for b in bands}
    for race in races:
        for r in race.runners:
            band = next((b for b in bands if b.contains(r.probability)), None)
            if band is None:
                raise PredictorMetricsError(
                    f"probability {r.probability!r} in race {race.race_id!r} matches no supplied band"
                )
            preds, obs = accum[band.label]
            preds.append(float(r.probability))
            obs.append(1.0 if r.is_winner else 0.0)
    result: dict[str, tuple[float, float, int]] = {}
    for label, (preds, obs) in accum.items():
        if not preds:
            result[label] = (0.0, 0.0, 0)
        else:
            result[label] = (sum(preds) / len(preds), sum(obs) / len(obs), len(preds))
    return result


def _jsonable(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _jsonable(dataclasses.asdict(value))
    return value


def compute_input_digest(races: Sequence[RaceEvaluationInput]) -> str:
    """Deterministic ``sha256:<hex>`` over the canonically-serialised evaluated race set.

    Same race set (any input order) -> identical digest, since races are sorted by ``race_id``
    before serialisation.
    """
    ordered = sorted(races, key=lambda r: r.race_id)
    payload = [_jsonable(asdict(r)) for r in ordered]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return _HASH_PREFIX + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
