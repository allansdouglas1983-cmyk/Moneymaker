"""SPEC-090: race-level paired inference.

The race is the primary unit of comparison between the market baseline and the combined
model (``.claude/rules/evidence.md``: "runners in a race are one mutually exclusive choice
set... runner-level independence is wrong and produces standard errors that are far too
small"). For each settled race ``r`` this module computes the paired race-level log-score
difference

    d_r = L_r(market) - L_r(combined)

where ``L_r(x) = -ln(p_x)`` is the negative log-likelihood the model ``x`` assigned to the
ACTUAL winner of race ``r``. A positive ``d_r`` means the combined model's loss was lower
than the market's for that race, i.e. the combined model beat the market on that race.
Algebraically ``d_r = ln(p_combined_winner) - ln(p_market_winner)`` — the two negative
signs cancel, so this module computes that form directly rather than round-tripping
through an intermediate loss value.

Between-race variation is estimated with a BLOCK bootstrap clustered by meeting-day, never
by resampling individual races: races run on the same day at the same meeting share going,
weather, jockeys and liquidity, so treating them as independent draws would understate the
true standard error (the exact failure mode ``.claude/rules/evidence.md`` names). The block
bootstrap here resamples whole meeting-days WITH REPLACEMENT and keeps every race that
occurred on a resampled day together in that resample — a day is never split apart, and a
race is never moved to a different day's resample.

This module has NO runner-level entry point anywhere: every public callable takes only
race-level data (:class:`PairedRace`, already reduced to the market/combined probability
the two models placed on the actual winner). There is nothing here for a caller to pass a
per-runner list into, by construction, not by convention — enforced by
``tests/unit/l8/test_paired_inference.py``'s signature/source scan.

:class:`BootstrapResult` reports a confidence interval only. It is deliberately NOT a
verdict: no p-value, no boolean, no field named ``t`` or any other borrowed-threshold
statistic lives on it (SPEC-094 / ``.claude/rules/evidence.md``: "no borrowed thresholds").
Interpreting the interval against a pre-registered economically-meaningful boundary is the
deterministic gate evaluator's job (SPEC-093), never this module's.

Ambiguity resolutions taken while drafting this slice:

* **Percentile method.** The confidence interval bounds are the empirical ``alpha/2`` and
  ``1 - alpha/2`` quantiles of the resampled means, computed by :func:`empirical_percentile`
  using linear interpolation between order statistics — Hyndman & Fan's Type 7 definition,
  the same method ``numpy.percentile``'s default ``'linear'`` interpolation and R's
  ``quantile(type = 7)`` use. For ``n`` sorted values the fractional 0-indexed rank is
  ``quantile * (n - 1)``; the result linearly interpolates between the values at
  ``floor(rank)`` and ``ceil(rank)``. Hand fixture: over ``[10, 20, 30, 40, 50]``,
  quantile ``0.5`` gives rank ``2.0`` (exactly index 2, value ``30``); quantile ``0.25``
  gives rank ``1.0`` (exactly index 1, value ``20``); quantile ``0.1`` gives rank ``0.4``
  giving ``10 + 0.4 * (20 - 10) = 14.0``. This exact formula and fixture are tested in
  ``tests/unit/l8/test_paired_inference.py``.
* **Number of day-draws per resample.** Each bootstrap resample draws exactly
  ``n_meeting_days`` days, independently and with replacement, from the set of distinct
  meeting-days actually observed — the standard block-bootstrap convention of resampling
  as many blocks as were originally observed.
* **A single meeting-day is refused for CI purposes, not silently degraded.** A block
  bootstrap clustered by meeting-day cannot estimate between-day variation from one day —
  there is nothing to resample between. Rather than returning a degenerate
  zero-width interval that looks like real evidence, :func:`block_bootstrap_ci` and
  :func:`bootstrap_resample_means` both raise :class:`InsufficientMeetingDaysError` when
  fewer than two distinct meeting-days are present. :func:`paired_differences` itself has
  no such restriction — computing the per-race ``d_r`` values needs no day-clustering at
  all, so a single-day corpus can still be inspected race-by-race.
* **Determinism.** :func:`bootstrap_resample_means` and :func:`block_bootstrap_ci` build
  their own ``random.Random(seed)`` instance and never touch the global ``random`` module
  or numpy's RNG — the same ``seed`` over the same race set always produces byte-identical
  output (checked via :meth:`BootstrapResult.content_digest`, the same
  hash-of-canonical-JSON pattern used across ``l8_evidence``).
* **Input types.** Per ``CLAUDE.md``, the two probabilities that feed ``d_r`` are
  ``Decimal`` (exact, not float — they are read directly off approved probability
  objects); ``d_r`` itself and every summary statistic derived from it are ``float``,
  since they are diagnostics, not prices, stakes or decisions.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from typing import Mapping, Sequence

__all__ = [
    "PairedInferenceError",
    "PairedRaceError",
    "PairedDifferencesError",
    "BootstrapConfigError",
    "InsufficientMeetingDaysError",
    "PairedRace",
    "RaceDifference",
    "BootstrapResult",
    "paired_differences",
    "empirical_percentile",
    "bootstrap_resample_means",
    "block_bootstrap_ci",
]

_PERCENTILE_METHOD = "linear-interpolation (Hyndman-Fan Type 7 / numpy 'linear' default)"


class PairedInferenceError(ValueError):
    """Base error for this module (SPEC-090)."""


class PairedRaceError(PairedInferenceError):
    """A :class:`PairedRace`'s own fields are internally inconsistent."""


class PairedDifferencesError(PairedInferenceError):
    """The race set given to :func:`paired_differences` is empty or has duplicate ids."""


class BootstrapConfigError(PairedInferenceError):
    """A bootstrap parameter (``confidence_level``, ``n_resamples``, a quantile) is invalid."""


class InsufficientMeetingDaysError(PairedInferenceError):
    """Fewer than two distinct meeting-days are present.

    A block bootstrap clustered by meeting-day cannot estimate between-day variation from
    a single day. Refusing is the honest move, not a degraded/silent CI.
    """


@dataclass(frozen=True)
class PairedRace:
    """One settled race's two probabilities ON THE ACTUAL WINNER (SPEC-090).

    ``p_market_winner`` and ``p_combined_winner`` are the market-baseline model's and the
    combined model's probability for the runner that actually won — that is all the paired
    race-level log-score comparison needs; no other runner's probability, and no runner
    identifier, enters this type or anything derived from it.
    """

    race_id: str
    meeting_day: date
    p_market_winner: Decimal
    p_combined_winner: Decimal

    def __post_init__(self) -> None:
        if not self.race_id or not self.race_id.strip():
            raise PairedRaceError("race_id must be non-empty")
        if not (Decimal(0) < self.p_market_winner < Decimal(1)):
            raise PairedRaceError(
                f"race {self.race_id!r}: p_market_winner {self.p_market_winner!r} must be "
                "in the open interval (0, 1)"
            )
        if not (Decimal(0) < self.p_combined_winner < Decimal(1)):
            raise PairedRaceError(
                f"race {self.race_id!r}: p_combined_winner {self.p_combined_winner!r} must be "
                "in the open interval (0, 1)"
            )

    @property
    def d_r(self) -> float:
        """``d_r = L_r(market) - L_r(combined) = ln(p_combined_winner) - ln(p_market_winner)``.

        Positive means the combined model's loss on this race's actual winner was lower
        than the market's, i.e. the combined model beat the market on this race.
        Deterministic: a pure function of the two stored ``Decimal`` fields, recomputed
        every access rather than cached, so there is nowhere for a stale value to hide.
        """
        return math.log(float(self.p_combined_winner)) - math.log(float(self.p_market_winner))


@dataclass(frozen=True)
class RaceDifference:
    """One race's materialised paired difference — the output unit of :func:`paired_differences`."""

    race_id: str
    meeting_day: date
    d_r: float


def paired_differences(races: Sequence[PairedRace]) -> tuple[RaceDifference, ...]:
    """Compute the per-race ``d_r`` for every race in ``races``.

    Refuses an empty race set and refuses duplicate ``race_id`` values — both would let a
    caller silently double-count or vacuously "prove" a result from zero evidence. Order of
    the output matches the order of ``races``; no meeting-day clustering happens here (that
    is :func:`bootstrap_resample_means`'s job) so a single-meeting-day race set can still be
    inspected race-by-race through this function alone.
    """
    if not races:
        raise PairedDifferencesError("cannot compute paired differences over an empty race set")
    race_ids = [r.race_id for r in races]
    if len(set(race_ids)) != len(race_ids):
        duplicates = sorted({rid for rid in race_ids if race_ids.count(rid) > 1})
        raise PairedDifferencesError(f"duplicate race_id(s) in input: {duplicates}")
    return tuple(
        RaceDifference(race_id=r.race_id, meeting_day=r.meeting_day, d_r=r.d_r) for r in races
    )


def empirical_percentile(sorted_values: Sequence[float], quantile: Decimal) -> float:
    """The empirical ``quantile`` of ``sorted_values`` (which MUST already be ascending).

    Linear interpolation between order statistics — Hyndman & Fan's Type 7 definition, the
    same method as ``numpy.percentile``'s default ``'linear'`` interpolation and R's
    ``quantile(type = 7)``. See the module docstring for the exact formula and a
    hand-computed fixture.
    """
    if not sorted_values:
        raise BootstrapConfigError("cannot compute a percentile over an empty sample")
    if not (Decimal(0) <= quantile <= Decimal(1)):
        raise BootstrapConfigError(f"quantile must be in the closed interval [0, 1], got {quantile!r}")
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    rank = float(quantile) * (n - 1)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return sorted_values[lo]
    frac = rank - lo
    return sorted_values[lo] + frac * (sorted_values[hi] - sorted_values[lo])


def _blocks_by_meeting_day(
    races: Sequence[PairedRace],
) -> tuple[tuple[date, ...], Mapping[date, tuple[float, ...]], tuple[RaceDifference, ...]]:
    """Group each race's ``d_r`` by ``meeting_day`` (the resampling block).

    Returns the sorted distinct day keys (sorted so day-index -> day assignment is
    deterministic independent of input order), each day's tuple of ``d_r`` values in the
    order their races appeared in ``races``, and the flat per-race differences.
    """
    differences = paired_differences(races)
    by_day: dict[date, list[float]] = {}
    for diff in differences:
        by_day.setdefault(diff.meeting_day, []).append(diff.d_r)
    day_keys = tuple(sorted(by_day))
    day_blocks: dict[date, tuple[float, ...]] = {day: tuple(values) for day, values in by_day.items()}
    return day_keys, day_blocks, differences


def bootstrap_resample_means(
    races: Sequence[PairedRace],
    *,
    n_resamples: int,
    seed: int,
) -> tuple[float, ...]:
    """The raw block-bootstrap resample means, clustered by meeting-day (SPEC-090).

    Each of ``n_resamples`` draws picks ``n_meeting_days`` days INDEPENDENTLY AND WITH
    REPLACEMENT from the distinct meeting-days present in ``races``; every race that
    occurred on a picked day travels with it into that resample — races are NEVER
    resampled individually across days. The mean of the resulting pooled ``d_r`` values is
    one element of the returned tuple, in resample order (index 0 is the first draw).

    Refuses fewer than two distinct meeting-days (:class:`InsufficientMeetingDaysError`,
    see module docstring) and refuses ``n_resamples < 1``. Uses a private
    ``random.Random(seed)`` instance — never the global ``random`` module, never numpy —
    so the same ``seed`` over the same race set always yields byte-identical output.
    """
    if n_resamples < 1:
        raise BootstrapConfigError(f"n_resamples must be >= 1, got {n_resamples!r}")
    day_keys, day_blocks, _differences = _blocks_by_meeting_day(races)
    n_days = len(day_keys)
    if n_days < 2:
        raise InsufficientMeetingDaysError(
            f"block bootstrap clustered by meeting-day needs >= 2 distinct meeting-days to "
            f"estimate between-day variation; got {n_days}. Refusing rather than returning a "
            "degenerate interval."
        )
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(n_resamples):
        picked_days = [day_keys[rng.randrange(n_days)] for _ in range(n_days)]
        pooled: list[float] = []
        for day in picked_days:
            pooled.extend(day_blocks[day])
        means.append(math.fsum(pooled) / len(pooled))  # fsum: exactly rounded, order-independent
    return tuple(means)


@dataclass(frozen=True)
class BootstrapResult:
    """A block-bootstrap confidence interval for the race-level paired mean ``d_r`` (SPEC-090).

    This reports an interval, NOT a verdict: no p-value, no boolean pass/fail, and no field
    named ``t`` or any other borrowed-threshold statistic lives here
    (``.claude/rules/evidence.md``: "no borrowed thresholds"). Interpreting this interval
    against a pre-registered economically-meaningful boundary is the deterministic gate
    evaluator's job (SPEC-093), never this module's.
    """

    mean_d: float
    lower: float
    upper: float
    confidence_level: Decimal
    n_races: int
    n_meeting_days: int
    n_resamples: int
    seed: int
    percentile_method: str

    def __post_init__(self) -> None:
        if self.lower > self.upper:
            raise PairedInferenceError(
                f"lower bound {self.lower!r} must not exceed upper bound {self.upper!r}"
            )
        if self.n_meeting_days < 2:
            raise PairedInferenceError("a BootstrapResult must be backed by >= 2 meeting-days")
        if self.n_races < self.n_meeting_days:
            raise PairedInferenceError("n_races cannot be fewer than n_meeting_days")
        if self.n_resamples < 1:
            raise PairedInferenceError("n_resamples must be >= 1")
        if not (Decimal(0) < self.confidence_level < Decimal(1)):
            raise PairedInferenceError("confidence_level must be in the open interval (0, 1)")

    def content_digest(self) -> str:
        """Deterministic ``sha256:<hex>`` over every field, for equality-of-content checks.

        Same fields -> identical digest; any field change -> a different digest. This is
        what makes "same seed -> byte-identical result" mechanically checkable rather than
        asserted by eye.
        """
        payload = _jsonable(asdict(self))
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def block_bootstrap_ci(
    races: Sequence[PairedRace],
    *,
    n_resamples: int,
    confidence_level: Decimal,
    seed: int,
) -> BootstrapResult:
    """The block-bootstrap-by-meeting-day confidence interval for the mean ``d_r`` (SPEC-090).

    ``mean_d`` is the plain arithmetic mean of the ACTUAL observed per-race ``d_r`` values
    (never a resample-derived quantity), so it is always exactly within
    ``[min(d_r), max(d_r)]`` regardless of bootstrap draws. ``(lower, upper)`` are the
    empirical ``alpha/2`` and ``1 - alpha/2`` percentiles (see
    :func:`empirical_percentile`) of :func:`bootstrap_resample_means`'s output, where
    ``alpha = 1 - confidence_level``.

    Refuses ``confidence_level`` outside the open interval ``(0, 1)``; delegates
    ``n_resamples`` and meeting-day-count validation to :func:`bootstrap_resample_means`.
    """
    if not (Decimal(0) < confidence_level < Decimal(1)):
        raise BootstrapConfigError(
            f"confidence_level must be in the open interval (0, 1), got {confidence_level!r}"
        )
    resampled_means = bootstrap_resample_means(races, n_resamples=n_resamples, seed=seed)
    day_keys, _day_blocks, differences = _blocks_by_meeting_day(races)
    mean_d = math.fsum(d.d_r for d in differences) / len(differences)
    alpha = Decimal(1) - confidence_level
    lower_q = alpha / Decimal(2)
    upper_q = Decimal(1) - lower_q
    sorted_means = sorted(resampled_means)
    lower = empirical_percentile(sorted_means, lower_q)
    upper = empirical_percentile(sorted_means, upper_q)
    return BootstrapResult(
        mean_d=mean_d,
        lower=lower,
        upper=upper,
        confidence_level=confidence_level,
        n_races=len(differences),
        n_meeting_days=len(day_keys),
        n_resamples=n_resamples,
        seed=seed,
        percentile_method=_PERCENTILE_METHOD,
    )


def _jsonable(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _jsonable(dataclasses.asdict(value))
    return value
