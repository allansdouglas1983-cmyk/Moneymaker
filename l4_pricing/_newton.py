"""Shared race-grouped MLE core for both pricing stages (ADR 0012 decisions 1 and 5).

Grouped-softmax (conditional logit / winner-only Plackett-Luce) maximum likelihood via
Newton-Raphson with an analytic gradient and Hessian, a deterministic step-halving safeguard
(never a regulariser), and explicit refusals. Every accumulation uses ``math.fsum`` (exactly
rounded, argument-order independent) so results are bit-identical under any reordering of
races or runners. Binary floats live only inside this package.

A "prepared" corpus is ``[(vectors, winner_index), ...]`` per race, where ``vectors`` is the
active runners' feature rows in a fixed order.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

_GRADIENT_TOL = 1e-10
_MAX_ABS_COEFFICIENT = 1e6
_MAX_STEP_HALVINGS = 30
_CHOLESKY_MIN_PIVOT = 1e-12
_COMPLETE_SEPARATION_LL = -1e-8

PreparedRace = tuple[list[list[float]], int]


class FitDidNotConverge(Exception):
    """The Newton iteration budget was exhausted before the gradient tolerance was met."""


class SeparationError(Exception):
    """The MLE is unbounded or unidentified; the fit refuses rather than truncating."""


class SingularHessianError(SeparationError):
    """The negative Hessian is singular: quasi-separation or collinear inputs."""


def utilities(vectors: Sequence[Sequence[float]], coefficients: Sequence[float]) -> list[float]:
    return [math.fsum(c * x for c, x in zip(coefficients, vector)) for vector in vectors]


def softmax(values: Sequence[float]) -> list[float]:
    shift = max(values)
    exps = [math.exp(v - shift) for v in values]
    total = math.fsum(exps)
    return [e / total for e in exps]


def log_likelihood(prepared: Sequence[PreparedRace], coefficients: Sequence[float]) -> float:
    terms: list[float] = []
    for vectors, winner_index in prepared:
        race_utilities = utilities(vectors, coefficients)
        shift = max(race_utilities)
        log_norm = shift + math.log(math.fsum(math.exp(u - shift) for u in race_utilities))
        terms.append(race_utilities[winner_index] - log_norm)
    return math.fsum(terms)


def _gradient_and_neg_hessian(
    prepared: Sequence[PreparedRace], coefficients: Sequence[float]
) -> tuple[list[float], list[list[float]]]:
    k = len(coefficients)
    grad_terms: list[list[float]] = [[] for _ in range(k)]
    hess_terms: list[list[list[float]]] = [[[] for _ in range(k)] for _ in range(k)]
    for vectors, winner_index in prepared:
        probs = softmax(utilities(vectors, coefficients))
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


def solve_spd(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Solve ``matrix @ x = rhs`` for a symmetric positive-definite matrix via Cholesky.

    A non-positive pivot means the negative Hessian is singular: the model is unidentified,
    and the fit MUST refuse rather than pick an arbitrary point on the ridge.
    """
    n = len(rhs)
    lower = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = math.fsum(lower[i][m] * lower[j][m] for m in range(j))
            if i == j:
                pivot = matrix[i][i] - s
                if pivot <= _CHOLESKY_MIN_PIVOT:
                    raise SingularHessianError(
                        "negative Hessian is singular: the MLE is unidentified "
                        "(quasi-separation or collinear inputs)"
                    )
                lower[i][j] = math.sqrt(pivot)
            else:
                lower[i][j] = (matrix[i][j] - s) / lower[j][j]
    y = [0.0] * n
    for i in range(n):
        y[i] = (rhs[i] - math.fsum(lower[i][m] * y[m] for m in range(i))) / lower[i][i]
    x = [0.0] * n
    for i in reversed(range(n)):
        x[i] = (y[i] - math.fsum(lower[m][i] * x[m] for m in range(i + 1, n))) / lower[i][i]
    return x


def newton_mle(
    prepared: Sequence[PreparedRace], n_features: int, max_iter: int
) -> tuple[list[float], float, int]:
    """Maximise the grouped-softmax log likelihood. Returns (coefficients, LL, iterations).

    Raises ``FitDidNotConverge`` when the budget ends, ``SingularHessianError`` on an
    unidentified model, and ``SeparationError`` on divergence or complete separation
    (LL reaching zero means every winner is predicted perfectly and the MLE is unbounded).
    """
    beta = [0.0] * n_features
    current_ll = log_likelihood(prepared, beta)
    iterations_used = 0
    for iteration in range(1, max_iter + 1):
        gradient, neg_hessian = _gradient_and_neg_hessian(prepared, beta)
        if max(abs(g) for g in gradient) < _GRADIENT_TOL:
            iterations_used = iteration - 1
            break
        step = solve_spd(neg_hessian, gradient)
        # Deterministic step-halving safeguard: still exact MLE at convergence, never a
        # regulariser — it only prevents an overshooting full Newton step.
        scale = 1.0
        for _ in range(_MAX_STEP_HALVINGS):
            candidate = [b + scale * s for b, s in zip(beta, step)]
            candidate_ll = log_likelihood(prepared, candidate)
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
    return beta, current_ll, iterations_used
