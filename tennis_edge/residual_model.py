"""The residual model as a deployable artefact, not a function inside an experiment.

The fit lived in an experiment script, which was fine while the only consumer was that
script. It is not fine once a weekly job has to price real upcoming matches: a deployed
model has to be *identifiable*, so that a prediction recorded today can be attributed to a
specific set of coefficients months later, and it has to *refuse* inputs it was not trained
for rather than quietly pricing them anyway.

**What the model is.** A correction to the market. ``probability(market_logit, features)``
adds a weighted sum of feature corrections to the de-vigged market logit and returns a
probability. With zero coefficients it reproduces the market exactly, which is the correct
degenerate case: absent evidence, the price stands.

**Why full Newton with a line search.** The first implementation stepped each coefficient by
its own second derivative and applied every update at once. That is Jacobi iteration — it
ignores the off-diagonal curvature and diverges as soon as features are correlated. These
features are strongly correlated, so it diverged to coefficients in the thousands and a log
score nine nats *worse* than the market it was correcting. That looked like a finding and
was a bug. The line search is a guard rather than a cure: a Newton step on a well-posed
penalised problem is almost always accepted whole, and halving it when the penalised
likelihood fails to improve means the fit can no longer walk away from its own optimum
without that showing up as a refusal to converge.

**Why the penalty is not tuned.** The ridge penalty shrinks *corrections to the price*
toward zero, which encodes the correct prior — absent evidence, the market is right. A
penalty chosen by looking at the answer would be a fitted parameter wearing a prior's
clothes, so it is fixed here and asserted by a test.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from tennis_edge.digests import digest_bytes
from tennis_edge.feature_cache import FEATURE_SET_VERSION, FeatureRow

__all__ = [
    "L2",
    "ResidualModel",
    "fit_model",
    "save_model",
    "load_model",
]

#: Fixed before any result was seen and never tuned against one. See the module docstring.
L2 = 25.0

_KIND = "tennis-edge-residual-model-v1"
_MAX_NEWTON_STEPS = 50
_MAX_HALVINGS = 20


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(min(z, 30.0), -30.0)))


@dataclass(frozen=True)
class ResidualModel:
    """Fitted coefficients plus everything needed to identify them later."""

    coefficients: Mapping[str, float]
    feature_names: tuple[str, ...]
    l2: float
    trained_rows: int
    trained_from: dt.date
    trained_through: dt.date
    feature_set_version: str

    @property
    def digest(self) -> str:
        """Stable identity for a ledger row to cite.

        Over the coefficients and the training window, so two models that would price
        differently cannot share a digest and a re-fit on the same data reproduces one.
        """
        payload = json.dumps({
            "coefficients": {k: repr(v) for k, v in sorted(self.coefficients.items())},
            "l2": repr(self.l2),
            "trained_rows": self.trained_rows,
            "trained_from": self.trained_from.isoformat(),
            "trained_through": self.trained_through.isoformat(),
            "feature_set_version": self.feature_set_version,
        }, sort_keys=True)
        return digest_bytes(payload.encode("utf-8"))

    def probability(self, market_logit: float, features: Mapping[str, float]) -> float:
        """P(player A wins), as the market's view corrected by what it missed.

        A feature the model does not know raises. Dropping it silently would price a match
        using a different feature set than the one trained on, and the resulting prediction
        would be indistinguishable from a valid one.
        """
        unknown = set(features) - set(self.feature_names)
        if unknown:
            raise ValueError(
                f"unknown feature(s) {sorted(unknown)} — this model was trained on "
                f"{list(self.feature_names)} and cannot price a different set"
            )
        correction = math.fsum(self.coefficients.get(name, 0.0) * value
                               for name, value in features.items())
        return _sigmoid(market_logit + correction)


def _compile(rows: Sequence[FeatureRow], names: Sequence[str]) -> list[
    tuple[float, int, list[tuple[int, float]]]
]:
    """Rows as ``(offset, outcome, [(index, value)])``, present features only.

    Hashing a feature name in the innermost loop dominated the cost — tens of millions of
    row-feature pairs per fit. Emitting only present features is also what keeps a partially
    covered feature honest: a row without serve coverage contributes nothing to that
    coefficient rather than contributing an imputed zero.
    """
    index = {name: i for i, name in enumerate(names)}
    return [
        (r.market_logit, r.won,
         [(index[n], v) for n, v in r.features.items() if n in index])
        for r in rows
    ]


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting. One row per feature, so this is cheap.

    Partial pivoting because the penalised Hessian is well conditioned but not diagonally
    dominant when features are near-copies of each other, which these are.
    """
    width = len(vector)
    augmented = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
    for column in range(width):
        pivot = max(range(column, width), key=lambda r: abs(augmented[r][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            raise ValueError("singular Hessian — features are exactly collinear")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        scale = augmented[column][column]
        for r in range(width):
            if r == column:
                continue
            factor = augmented[r][column] / scale
            if factor == 0.0:
                continue
            for c in range(column, width + 1):
                augmented[r][c] -= factor * augmented[column][c]
    return [augmented[i][width] / augmented[i][i] for i in range(width)]


def _penalised_loglik(
    compiled: Sequence[tuple[float, int, list[tuple[int, float]]]],
    beta: Sequence[float], l2: float,
) -> float:
    total = -0.5 * l2 * math.fsum(b * b for b in beta)
    for offset, won, pairs in compiled:
        z = max(min(offset + math.fsum(beta[i] * x for i, x in pairs), 30.0), -30.0)
        # log sigmoid(z) for a win, log sigmoid(-z) for a loss, written to avoid overflow.
        total += -math.log1p(math.exp(-z)) if won else -math.log1p(math.exp(z))
    return total


def fit_coefficients(
    rows: Sequence[FeatureRow], names: Sequence[str], *, l2: float = L2
) -> dict[str, float]:
    """Ridge logistic on the residual, market logit as an unpenalised offset."""
    compiled = _compile(rows, names)
    width = len(names)
    beta = [0.0] * width
    current = _penalised_loglik(compiled, beta, l2)
    for _ in range(_MAX_NEWTON_STEPS):
        gradient = [-l2 * b for b in beta]
        hessian = [[l2 if i == j else 0.0 for j in range(width)] for i in range(width)]
        for offset, won, pairs in compiled:
            z = offset
            for i, x in pairs:
                z += beta[i] * x
            p = _sigmoid(z)
            residual, weight = won - p, p * (1 - p)
            for i, x in pairs:
                gradient[i] += x * residual
                wx = weight * x
                for j, y in pairs:
                    hessian[i][j] += wx * y
        try:
            step = _solve(hessian, gradient)
        except ValueError:
            break
        scale = 1.0
        for _attempt in range(_MAX_HALVINGS):
            candidate = [b + scale * s for b, s in zip(beta, step)]
            value = _penalised_loglik(compiled, candidate, l2)
            if value >= current:
                beta, current = candidate, value
                break
            scale *= 0.5
        else:
            break
        if max(abs(scale * s) for s in step) < 1e-10:
            break
    return dict(zip(names, beta))


def fit_model(
    rows: Sequence[FeatureRow], names: Sequence[str], *, l2: float = L2
) -> ResidualModel:
    """Fit, and record what the fit saw so the result can be identified later."""
    if not rows:
        raise ValueError("no training rows — refusing to return a zero model, which would "
                         "be indistinguishable from 'the price is already right'")
    if not names:
        raise ValueError("no features to fit")
    dates = [r.date for r in rows]
    return ResidualModel(
        coefficients=fit_coefficients(rows, names, l2=l2),
        feature_names=tuple(names),
        l2=l2,
        trained_rows=len(rows),
        trained_from=min(dates),
        trained_through=max(dates),
        feature_set_version=FEATURE_SET_VERSION,
    )


def save_model(path: Path | str, model: ResidualModel) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({
        "kind": _KIND,
        "coefficients": dict(sorted(model.coefficients.items())),
        "feature_names": list(model.feature_names),
        "l2": model.l2,
        "trained_rows": model.trained_rows,
        "trained_from": model.trained_from.isoformat(),
        "trained_through": model.trained_through.isoformat(),
        "feature_set_version": model.feature_set_version,
        "digest": model.digest,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_model(path: Path | str) -> ResidualModel:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("kind") != _KIND:
        raise ValueError(f"not a residual model: {path}")
    model = ResidualModel(
        coefficients=dict(raw["coefficients"]),
        feature_names=tuple(raw["feature_names"]),
        l2=float(raw["l2"]),
        trained_rows=int(raw["trained_rows"]),
        trained_from=dt.date.fromisoformat(raw["trained_from"]),
        trained_through=dt.date.fromisoformat(raw["trained_through"]),
        feature_set_version=raw["feature_set_version"],
    )
    stored = raw.get("digest")
    if stored is not None and stored != model.digest:
        raise ValueError(
            f"model file {path} carries digest {stored} but its contents digest to "
            f"{model.digest} — the file has been edited since it was written"
        )
    return model
