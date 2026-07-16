"""SPEC-030: conditional logit stage one — MLE on the winner, race-grouped (§6.4).

The v1 BASELINE: plain (unregularised) conditional logit. Newton-Raphson with analytic
gradient and Hessian, deterministic step-halving safeguard, and explicit refusals:
``FitDidNotConverge`` when the iteration budget ends, ``SeparationError`` when the MLE is
unbounded or unidentified — never silent regularisation (the regularised variant is a future
progression step that must earn its place on held-out race-level score, §6.4).

Determinism: every accumulation uses ``math.fsum`` (exactly rounded, argument-order
independent) and races are processed in sorted race_id order, so fits are bit-identical under
race reordering and predictions are bit-identical under runner permutation (ADR 0012).
Binary floats live only inside this module; features arrive as exact Decimals and are
converted once.
"""
from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from l4_pricing.horizon import HorizonLabel, require_horizon_match
from l4_pricing.races import FeatureSchema, Race, RaceValidationError, RunnerRow

_GRADIENT_TOL = 1e-10
_MAX_ABS_COEFFICIENT = 1e6
_MAX_STEP_HALVINGS = 30
_CHOLESKY_MIN_PIVOT = 1e-12
_COMPLETE_SEPARATION_LL = -1e-8


class FitDidNotConverge(Exception):
    """The Newton iteration budget was exhausted before the gradient tolerance was met."""


class SeparationError(Exception):
    """The MLE is unbounded or unidentified (complete/quasi separation, collinear features)."""


@dataclass(frozen=True)
class StageOneModel:
    """An immutable fitted stage-one model (§6.11: retraining mints a new object)."""

    coefficients: tuple[float, ...]
    schema: FeatureSchema
    horizon: HorizonLabel
    n_races: int
    log_likelihood: float
    iterations_used: int
    training_race_ids: frozenset[str]
    training_race_ids_digest: str
    trained_through_day: date


def _feature_vector(runner: RunnerRow, schema: FeatureSchema, race_id: str) -> list[float]:
    actual = set(runner.features)
    expected = set(schema.names)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise RaceValidationError(
            f"race {race_id!r} runner {runner.runner_id}: features do not match the schema "
            f"(missing={missing}, extra={extra})"
        )
    return [float(runner.features[name]) for name in schema.names]


def _utilities(vectors: Sequence[Sequence[float]], coefficients: Sequence[float]) -> list[float]:
    return [math.fsum(c * x for c, x in zip(coefficients, vector)) for vector in vectors]


def _softmax(utilities: Sequence[float]) -> list[float]:
    shift = max(utilities)
    exps = [math.exp(u - shift) for u in utilities]
    total = math.fsum(exps)
    return [e / total for e in exps]


_Prepared = list[tuple[list[list[float]], int]]  # per race: (active feature vectors, winner index)


def _log_likelihood(prepared: _Prepared, coefficients: Sequence[float]) -> float:
    terms: list[float] = []
    for vectors, winner_index in prepared:
        utilities = _utilities(vectors, coefficients)
        shift = max(utilities)
        log_norm = shift + math.log(math.fsum(math.exp(u - shift) for u in utilities))
        terms.append(utilities[winner_index] - log_norm)
    return math.fsum(terms)


def _gradient_and_neg_hessian(
    prepared: _Prepared, coefficients: Sequence[float]
) -> tuple[list[float], list[list[float]]]:
    k = len(coefficients)
    grad_terms: list[list[float]] = [[] for _ in range(k)]
    hess_terms: list[list[list[float]]] = [[[] for _ in range(k)] for _ in range(k)]
    for vectors, winner_index in prepared:
        probs = _softmax(_utilities(vectors, coefficients))
        expected = [
            math.fsum(p * vector[j] for p, vector in zip(probs, vectors)) for j in range(k)
        ]
        for j in range(k):
            grad_terms[j].append(vectors[winner_index][j] - expected[j])
            for m in range(j + 1):
                second_moment = math.fsum(
                    p * vector[j] * vector[m] for p, vector in zip(probs, vectors)
                )
                hess_terms[j][m].append(second_moment - expected[j] * expected[m])
    gradient = [math.fsum(terms) for terms in grad_terms]
    neg_hessian = [[0.0] * k for _ in range(k)]
    for j in range(k):
        for m in range(j + 1):
            value = math.fsum(hess_terms[j][m])
            neg_hessian[j][m] = value
            neg_hessian[m][j] = value
    return gradient, neg_hessian


def _solve_spd(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Solve ``matrix @ x = rhs`` for a symmetric positive-definite matrix via Cholesky.

    A non-positive pivot means the negative Hessian is singular: the model is unidentified
    (quasi-separation or collinear features) and the fit MUST refuse rather than pick an
    arbitrary point on the ridge.
    """
    n = len(rhs)
    lower = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = math.fsum(lower[i][m] * lower[j][m] for m in range(j))
            if i == j:
                pivot = matrix[i][i] - s
                if pivot <= _CHOLESKY_MIN_PIVOT:
                    raise SeparationError(
                        "negative Hessian is singular: the MLE is unidentified "
                        "(quasi-separation or collinear features)"
                    )
                lower[i][j] = math.sqrt(pivot)
            else:
                lower[i][j] = (matrix[i][j] - s) / lower[j][j]
    # forward substitution: L y = rhs
    y = [0.0] * n
    for i in range(n):
        y[i] = (rhs[i] - math.fsum(lower[i][m] * y[m] for m in range(i))) / lower[i][i]
    # back substitution: L^T x = y
    x = [0.0] * n
    for i in reversed(range(n)):
        x[i] = (y[i] - math.fsum(lower[m][i] * x[m] for m in range(i + 1, n))) / lower[i][i]
    return x


def fit_conditional_logit(
    races: Sequence[Race],
    schema: FeatureSchema,
    *,
    horizon: HorizonLabel,
    max_iter: int = 100,
) -> StageOneModel:
    """Race-grouped MLE on the winner (SPEC-030). Pure and bit-deterministic."""
    race_list = sorted(races, key=lambda race: race.race_id)
    if not race_list:
        raise RaceValidationError("cannot fit on an empty corpus")
    race_ids = [race.race_id for race in race_list]
    if len(set(race_ids)) != len(race_ids):
        raise RaceValidationError("duplicate race ids in the training corpus")

    prepared: _Prepared = []
    for race in race_list:
        if race.winner_id is None:
            raise RaceValidationError(f"race {race.race_id!r} has no winner; fitting requires outcomes")
        active = race.active_runners
        vectors = [_feature_vector(runner, schema, race.race_id) for runner in active]
        winner_index = next(
            i for i, runner in enumerate(active) if runner.runner_id == race.winner_id
        )
        prepared.append((vectors, winner_index))

    k = len(schema.names)
    beta = [0.0] * k
    current_ll = _log_likelihood(prepared, beta)
    iterations_used = 0
    for iteration in range(1, max_iter + 1):
        gradient, neg_hessian = _gradient_and_neg_hessian(prepared, beta)
        if max(abs(g) for g in gradient) < _GRADIENT_TOL:
            iterations_used = iteration - 1
            break
        step = _solve_spd(neg_hessian, gradient)
        # Deterministic step-halving safeguard: still exact MLE at convergence, never a
        # regulariser — it only prevents an overshooting full Newton step.
        scale = 1.0
        for _ in range(_MAX_STEP_HALVINGS):
            candidate = [b + scale * s for b, s in zip(beta, step)]
            candidate_ll = _log_likelihood(prepared, candidate)
            if candidate_ll >= current_ll - 1e-12:
                beta = candidate
                current_ll = candidate_ll
                break
            scale *= 0.5
        else:
            raise FitDidNotConverge(
                f"no ascent step found after {_MAX_STEP_HALVINGS} halvings at iteration {iteration}"
            )
        if max(abs(b) for b in beta) > _MAX_ABS_COEFFICIENT:
            raise SeparationError(
                "coefficient magnitude exceeded 1e6: the MLE is diverging (separated data)"
            )
        iterations_used = iteration
    else:
        raise FitDidNotConverge(
            f"gradient tolerance {_GRADIENT_TOL} not reached within {max_iter} Newton iteration(s)"
        )

    if current_ll > _COMPLETE_SEPARATION_LL:
        raise SeparationError(
            "complete separation: every winner is predicted perfectly and the MLE is unbounded"
        )

    digest = hashlib.sha256(
        "\n".join(sorted(race_ids)).encode("utf-8")
    ).hexdigest()
    return StageOneModel(
        coefficients=tuple(beta),
        schema=schema,
        horizon=horizon,
        n_races=len(race_list),
        log_likelihood=current_ll,
        iterations_used=iterations_used,
        training_race_ids=frozenset(race_ids),
        training_race_ids_digest=digest,
        trained_through_day=max(race.meeting_day for race in race_list),
    )


def predict_race(
    model: StageOneModel, race: Race, *, horizon: HorizonLabel
) -> Mapping[int, float]:
    """Within-race win probabilities over the ACTIVE runners; sums to 1 (SPEC-030).

    Non-runners are dropped and the remainder renormalised natively by the softmax. The
    horizon declaration is mandatory — scoring is deployment's only door (SPEC-033).
    """
    require_horizon_match(model.horizon, horizon)
    active = race.active_runners
    vectors = [_feature_vector(runner, model.schema, race.race_id) for runner in active]
    probabilities = _softmax(_utilities(vectors, model.coefficients))
    return {runner.runner_id: p for runner, p in zip(active, probabilities)}
