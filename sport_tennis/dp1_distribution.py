"""SPEC-106 — the governed DP1 WinProbabilityDistribution (Stage 2G; ADR 0019).

Registration: specs/programme/dp1-glicko2-registration-v1.yaml `prediction` block.
Central probability = frozen 20-node Gauss-Hermite posterior mean of
sigmoid(delta + s*sqrt(2)*x) over N(0,1), delta = mu_A - mu_B, s^2 = phi_A^2 + phi_B^2.
Interval = ANALYTIC_PROPAGATION: sigmoid is monotone, so the two-sided 90% interval is
the EXACT sigmoid image of delta +/- 1.644854*s — never a fabricated percentage around
the point. Coherence is exact by construction: player B's distribution is the
complement of player A's. All probabilities live strictly inside
(PROBABILITY_FLOOR, 1 - PROBABILITY_FLOOR).

The quadrature rule is computed deterministically in pure Python (orthonormal Hermite
recurrence + Newton with fixed iteration policy) and is SELF-VERIFIED by the SPEC-106
test suite (weights sum to sqrt(pi); polynomial exactness) rather than trusted from a
transcribed table. No randomness, no environment dependence.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

from sport_tennis.glicko2_family import PlayerState

__all__ = [
    "DP1_MODEL_VERSION",
    "GH_NODE_COUNT",
    "INTERVAL_Z",
    "PROBABILITY_FLOOR",
    "UNCERTAINTY_METHOD",
    "DistributionValidationError",
    "WinProbabilityDistribution",
    "central_win_probability",
    "gauss_hermite_nodes",
    "interval_bounds",
    "win_probability_distributions",
]

DP1_MODEL_VERSION = "dynamic-glicko2-v1"
UNCERTAINTY_METHOD = "ANALYTIC_PROPAGATION"
GH_NODE_COUNT = 20
INTERVAL_Z = 1.644854  # two-sided 90%, frozen in the registration
PROBABILITY_FLOOR = 1e-12

_NEWTON_STEPS = 64  # fixed, deterministic polish budget per root
_SQRT_PI = math.sqrt(math.pi)


class DistributionValidationError(Exception):
    """A WinProbabilityDistribution field violates the governed contract."""


def _sigmoid(x: float) -> float:
    if x >= 0.0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def _clamp(p: float) -> float:
    return min(1.0 - PROBABILITY_FLOOR, max(PROBABILITY_FLOOR, p))


def _hermite_value_and_prev(x: float, n: int) -> tuple[float, float]:
    """Orthonormal (w.r.t. e^{-x^2}) Hermite recurrence: returns (h_n(x), h_{n-1}(x))."""
    p1 = math.pi ** -0.25
    p2 = 0.0
    for j in range(1, n + 1):
        p3 = p2
        p2 = p1
        p1 = x * math.sqrt(2.0 / j) * p2 - math.sqrt((j - 1.0) / j) * p3
    return p1, p2


@lru_cache(maxsize=4)
def gauss_hermite_nodes(n: int) -> tuple[tuple[float, float], ...]:
    """Deterministic Gauss-Hermite rule for integrals against e^{-x^2}: ascending
    (node, weight) pairs, exactly symmetric (each root is mirrored, sharing its weight)."""
    if n < 2 or n % 2 != 0:
        raise ValueError(f"the frozen rule uses an even node count >= 2, got {n}")
    half = n // 2
    positive: list[tuple[float, float]] = []
    x = 0.0
    for i in range(half):
        # Numerical Recipes 'gauher' initial guesses, largest root first.
        if i == 0:
            x = math.sqrt(2.0 * n + 1.0) - 1.85575 * (2.0 * n + 1.0) ** (-1.0 / 6.0)
        elif i == 1:
            x -= 1.14 * n**0.426 / x
        elif i == 2:
            x = 1.86 * x - 0.86 * positive[0][0]
        elif i == 3:
            x = 1.91 * x - 0.91 * positive[1][0]
        else:
            x = 2.0 * x - positive[i - 2][0]
        for _ in range(_NEWTON_STEPS):
            p1, p2 = _hermite_value_and_prev(x, n)
            pp = math.sqrt(2.0 * n) * p2
            dx = p1 / pp
            x -= dx
            if abs(dx) <= 1e-15 * max(1.0, abs(x)):
                break
        else:
            raise ArithmeticError(f"Gauss-Hermite root {i} did not polish in {_NEWTON_STEPS} steps")
        _, p2 = _hermite_value_and_prev(x, n)
        pp = math.sqrt(2.0 * n) * p2
        positive.append((x, 2.0 / (pp * pp)))
    negative = [(-node, weight) for node, weight in positive]
    return tuple(sorted(negative) + sorted((abs(nd), w) for nd, w in positive))


def central_win_probability(delta: float, s: float) -> float:
    """Posterior mean of sigmoid(theta_A - theta_B), theta difference ~ N(delta, s^2),
    via the frozen GH_NODE_COUNT-node rule. Exact sigmoid at s=0; exactly 0.5 at
    delta=0 (symmetry of the rule)."""
    if not (math.isfinite(delta) and math.isfinite(s)) or s < 0.0:
        raise DistributionValidationError(f"delta/s must be finite with s >= 0, got {delta!r}, {s!r}")
    if delta == 0.0:
        return 0.5
    if s == 0.0:
        return _clamp(_sigmoid(delta))
    scale = s * math.sqrt(2.0)
    rule = gauss_hermite_nodes(GH_NODE_COUNT)
    integral = math.fsum(w * _sigmoid(delta + scale * x) for x, w in rule)
    return _clamp(integral / _SQRT_PI)


def interval_bounds(delta: float, s: float) -> tuple[float, float]:
    """ANALYTIC_PROPAGATION: the exact sigmoid image of delta +/- INTERVAL_Z * s."""
    if not (math.isfinite(delta) and math.isfinite(s)) or s < 0.0:
        raise DistributionValidationError(f"delta/s must be finite with s >= 0, got {delta!r}, {s!r}")
    lower = _clamp(_sigmoid(delta - INTERVAL_Z * s))
    upper = _clamp(_sigmoid(delta + INTERVAL_Z * s))
    return lower, upper


_HEX64 = frozenset("0123456789abcdef")


def _require_digest(value: str, field: str) -> None:
    if len(value) != 64 or not set(value) <= _HEX64:
        raise DistributionValidationError(f"{field} must be 64 lowercase hex chars, got {value!r}")


@dataclass(frozen=True)
class WinProbabilityDistribution:
    """One player's governed DP1 output (founder directive §6 — all thirteen fields).

    Immutable; validated on construction; probabilities strictly inside the governed
    bounds with lower <= central <= upper. No outcome field exists here or ever will."""

    central_win_probability: float
    lower_probability_bound: float
    upper_probability_bound: float
    uncertainty_method: str
    rating: float
    rating_deviation: float
    volatility: float
    prior_match_count: int
    last_active_date: date | None
    data_quality_status: str
    model_version: str
    state_digest: str
    feature_input_digest: str

    def __post_init__(self) -> None:
        for name in ("central_win_probability", "lower_probability_bound", "upper_probability_bound"):
            p = getattr(self, name)
            if not isinstance(p, float) or not math.isfinite(p):
                raise DistributionValidationError(f"{name} must be a finite float, got {p!r}")
            if not (PROBABILITY_FLOOR <= p <= 1.0 - PROBABILITY_FLOOR):
                raise DistributionValidationError(
                    f"{name} must lie in [{PROBABILITY_FLOOR}, {1.0 - PROBABILITY_FLOOR}], got {p!r}"
                )
        if not (
            self.lower_probability_bound
            <= self.central_win_probability
            <= self.upper_probability_bound
        ):
            raise DistributionValidationError(
                "bounds must satisfy lower <= central <= upper, got "
                f"{self.lower_probability_bound!r} / {self.central_win_probability!r} / "
                f"{self.upper_probability_bound!r}"
            )
        if not math.isfinite(self.rating):
            raise DistributionValidationError(f"rating must be finite, got {self.rating!r}")
        if not (math.isfinite(self.rating_deviation) and self.rating_deviation > 0.0):
            raise DistributionValidationError(
                f"rating_deviation must be finite and positive, got {self.rating_deviation!r}"
            )
        if not (math.isfinite(self.volatility) and self.volatility > 0.0):
            raise DistributionValidationError(
                f"volatility must be finite and positive, got {self.volatility!r}"
            )
        if self.prior_match_count < 0:
            raise DistributionValidationError(
                f"prior_match_count must be >= 0, got {self.prior_match_count!r}"
            )
        for name in ("uncertainty_method", "data_quality_status", "model_version"):
            text = getattr(self, name)
            if not text or text != text.strip():
                raise DistributionValidationError(f"{name} must be non-empty trimmed text, got {text!r}")
        _require_digest(self.state_digest, "state_digest")
        _require_digest(self.feature_input_digest, "feature_input_digest")


def _pair_state_digest(
    state_a: PlayerState,
    state_b: PlayerState,
    last_active_date_a: date | None,
    last_active_date_b: date | None,
    prior_match_count_a: int,
    prior_match_count_b: int,
) -> str:
    canonical = json.dumps(
        {
            "model_version": DP1_MODEL_VERSION,
            "a": [repr(state_a.mu), repr(state_a.phi), repr(state_a.sigma)],
            "b": [repr(state_b.mu), repr(state_b.phi), repr(state_b.sigma)],
            "last_active_a": last_active_date_a.isoformat() if last_active_date_a else None,
            "last_active_b": last_active_date_b.isoformat() if last_active_date_b else None,
            "prior_a": prior_match_count_a,
            "prior_b": prior_match_count_b,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def win_probability_distributions(
    state_a: PlayerState,
    state_b: PlayerState,
    *,
    prior_match_count_a: int,
    prior_match_count_b: int,
    last_active_date_a: date | None,
    last_active_date_b: date | None,
    data_quality_status_a: str,
    data_quality_status_b: str,
    feature_input_digest: str,
) -> tuple[WinProbabilityDistribution, WinProbabilityDistribution]:
    """The coherent two-player choice set: B's distribution is EXACTLY A's complement
    (same delta and s, so P(B) = 1 - P(A) and the interval reflects)."""
    delta = state_a.mu - state_b.mu
    s = math.sqrt(state_a.phi * state_a.phi + state_b.phi * state_b.phi)
    central_a = central_win_probability(delta, s)
    lower_a, upper_a = interval_bounds(delta, s)
    digest = _pair_state_digest(
        state_a, state_b, last_active_date_a, last_active_date_b,
        prior_match_count_a, prior_match_count_b,
    )
    dist_a = WinProbabilityDistribution(
        central_win_probability=central_a,
        lower_probability_bound=lower_a,
        upper_probability_bound=upper_a,
        uncertainty_method=UNCERTAINTY_METHOD,
        rating=state_a.rating,
        rating_deviation=state_a.rating_deviation,
        volatility=state_a.sigma,
        prior_match_count=prior_match_count_a,
        last_active_date=last_active_date_a,
        data_quality_status=data_quality_status_a,
        model_version=DP1_MODEL_VERSION,
        state_digest=digest,
        feature_input_digest=feature_input_digest,
    )
    dist_b = WinProbabilityDistribution(
        central_win_probability=1.0 - central_a,
        lower_probability_bound=1.0 - upper_a,
        upper_probability_bound=1.0 - lower_a,
        uncertainty_method=UNCERTAINTY_METHOD,
        rating=state_b.rating,
        rating_deviation=state_b.rating_deviation,
        volatility=state_b.sigma,
        prior_match_count=prior_match_count_b,
        last_active_date=last_active_date_b,
        data_quality_status=data_quality_status_b,
        model_version=DP1_MODEL_VERSION,
        state_digest=digest,
        feature_input_digest=feature_input_digest,
    )
    return dist_a, dist_b
