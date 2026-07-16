"""SPEC-032: stage-two market combination (§6.4).

``score_i = alpha·log(p_fundamental_i) + beta·log(p_market_info_i)``, ``c = softmax(score)``
within the race; (alpha, beta) by MLE on the winner — the same grouped-softmax core as stage
one, over the two-feature design ``[ln p_fundamental, ln p_market]``.

Type coupling (SPEC-031→032): training accepts only provenance-carrying ``OOFFundamental``
values and re-verifies out-of-fold-ness at consumption; the market input is l5's
``MarketInfoPrice``, extending SPEC-051's price separation upstream — a close price cannot
type into the combiner. Collinear inputs (fundamental ≡ market) leave (alpha, beta)
unidentified along a ridge and are refused with ``CollinearInputsError``.
"""
from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from l4_pricing._newton import PreparedRace, SingularHessianError, newton_mle, softmax
from l4_pricing.conditional_logit import race_ids_digest
from l4_pricing.crossfit import CrossFitViolation, ExcludedRace, OOFFundamental, assert_out_of_fold
from l4_pricing.horizon import HorizonLabel, require_horizon_match
from l4_pricing.races import Race, RaceValidationError
from l5_decision.prices import MarketInfoPrice


class CollinearInputsError(Exception):
    """(alpha, beta) are unidentified: fundamental and market inputs are collinear."""


@dataclass(frozen=True)
class CombinedModel:
    """An immutable fitted stage-two model (§6.11: retraining mints a new object)."""

    alpha: float
    beta: float
    horizon: HorizonLabel
    n_races: int
    log_likelihood: float
    iterations_used: int
    training_race_ids: frozenset[str]
    training_race_ids_digest: str
    trained_through_day: date
    stage_one_provenance_digest: str


@dataclass(frozen=True)
class StageTwoFitResult:
    model: CombinedModel
    used_race_ids: frozenset[str]
    excluded: tuple[ExcludedRace, ...]


def _log_pairs(
    p_fundamental: Mapping[int, float],
    p_market: Mapping[int, MarketInfoPrice],
    where: str,
) -> dict[int, tuple[float, float]]:
    if set(p_fundamental) != set(p_market):
        raise RaceValidationError(f"{where}: fundamental and market runner sets differ")
    pairs: dict[int, tuple[float, float]] = {}
    for runner_id, p_fund in p_fundamental.items():
        if not isinstance(p_fund, float) or not 0.0 < p_fund < 1.0:
            raise RaceValidationError(
                f"{where}: p_fundamental for runner {runner_id} must be a float in (0, 1), "
                f"got {p_fund!r}"
            )
        price = p_market[runner_id]
        if not isinstance(price, MarketInfoPrice):
            raise RaceValidationError(
                f"{where}: p_market for runner {runner_id} must be MarketInfoPrice, "
                f"got {type(price).__name__}"
            )
        pairs[runner_id] = (math.log(p_fund), math.log(float(price.implied_probability)))
    return pairs


def combine(
    *,
    alpha: float,
    beta: float,
    p_fundamental: Mapping[int, float],
    p_market: Mapping[int, MarketInfoPrice],
) -> Mapping[int, float]:
    """The pure SPEC-032 combiner: softmax of alpha·ln(p_f) + beta·ln(p_m) within the race.

    Runner iteration is by sorted runner_id, so the output is bit-identical regardless of
    input mapping order.
    """
    pairs = _log_pairs(p_fundamental, p_market, "combine")
    runner_ids = sorted(pairs)
    scores = [
        math.fsum((alpha * pairs[rid][0], beta * pairs[rid][1])) for rid in runner_ids
    ]
    probabilities = softmax(scores)
    return {rid: p for rid, p in zip(runner_ids, probabilities)}


def fit_stage_two(
    races: Sequence[Race],
    oof: Sequence[OOFFundamental],
    market_prices: Mapping[str, Mapping[int, MarketInfoPrice]],
    *,
    horizon: HorizonLabel,
    max_iter: int = 100,
) -> StageTwoFitResult:
    """MLE for (alpha, beta) on strictly out-of-fold fundamentals + as-of market prices."""
    race_list = sorted(races, key=lambda race: race.race_id)
    if not race_list:
        raise RaceValidationError("cannot fit stage two on an empty corpus")
    races_by_id = {race.race_id: race for race in race_list}
    if len(races_by_id) != len(race_list):
        raise RaceValidationError("duplicate race ids in the stage-two corpus")

    # SPEC-031 at consumption: refuse contaminated or untyped fundamentals outright.
    assert_out_of_fold(oof, races_by_id)
    fundamentals: dict[tuple[str, int], OOFFundamental] = {}
    provenance_digests: set[str] = set()
    for row in oof:
        if row.provenance.horizon != horizon:
            raise CrossFitViolation(
                f"OOF row for race {row.race_id!r} carries horizon "
                f"{str(row.provenance.horizon)!r}, expected {str(horizon)!r}"
            )
        key = (row.race_id, row.runner_id)
        if key in fundamentals:
            raise RaceValidationError(f"duplicate OOF fundamental for {key!r}")
        fundamentals[key] = row

    prepared: list[PreparedRace] = []
    used_race_ids: list[str] = []
    excluded: list[ExcludedRace] = []
    for race in race_list:
        winner_id = race.winner_id
        if winner_id is None:
            raise RaceValidationError(
                f"race {race.race_id!r} has no winner; stage-two fitting requires outcomes"
            )
        active = race.active_runners
        missing_fund = [r.runner_id for r in active if (race.race_id, r.runner_id) not in fundamentals]
        if missing_fund:
            excluded.append(
                ExcludedRace(race.race_id, f"missing fundamental probabilities for runners {missing_fund}")
            )
            continue
        race_market = market_prices.get(race.race_id)
        missing_market = [
            r.runner_id for r in active if race_market is None or r.runner_id not in race_market
        ]
        if missing_market:
            excluded.append(
                ExcludedRace(race.race_id, f"missing market prices for runners {missing_market}")
            )
            continue
        assert race_market is not None  # narrowed by the missing_market check above
        p_fundamental = {
            r.runner_id: fundamentals[(race.race_id, r.runner_id)].p_fundamental for r in active
        }
        pairs = _log_pairs(p_fundamental, dict(race_market), f"race {race.race_id!r}")
        runner_ids = sorted(pairs)
        vectors = [[pairs[rid][0], pairs[rid][1]] for rid in runner_ids]
        winner_index = runner_ids.index(winner_id)  # winner is active (Race invariant)
        prepared.append((vectors, winner_index))
        used_race_ids.append(race.race_id)
        for rid in runner_ids:
            provenance_digests.add(fundamentals[(race.race_id, rid)].provenance.training_race_ids_digest)

    if not prepared:
        raise RaceValidationError("no usable races: every race lacked fundamentals or market prices")

    try:
        coefficients, final_ll, iterations_used = newton_mle(prepared, 2, max_iter)
    except SingularHessianError as exc:
        raise CollinearInputsError(
            f"alpha/beta are unidentified on this corpus: {exc}"
        ) from exc

    model = CombinedModel(
        alpha=coefficients[0],
        beta=coefficients[1],
        horizon=horizon,
        n_races=len(used_race_ids),
        log_likelihood=final_ll,
        iterations_used=iterations_used,
        training_race_ids=frozenset(used_race_ids),
        training_race_ids_digest=race_ids_digest(used_race_ids),
        trained_through_day=max(races_by_id[rid].meeting_day for rid in used_race_ids),
        stage_one_provenance_digest=hashlib.sha256(
            "\n".join(sorted(provenance_digests)).encode("utf-8")
        ).hexdigest(),
    )
    return StageTwoFitResult(
        model=model,
        used_race_ids=frozenset(used_race_ids),
        excluded=tuple(excluded),
    )


def predict_combined(
    model: CombinedModel,
    p_fundamental: Mapping[int, float],
    p_market: Mapping[int, MarketInfoPrice],
    *,
    horizon: HorizonLabel,
) -> Mapping[int, float]:
    """Combined within-race probabilities; the horizon door is deployment's only entry."""
    require_horizon_match(model.horizon, horizon)
    return combine(
        alpha=model.alpha, beta=model.beta, p_fundamental=p_fundamental, p_market=p_market
    )
