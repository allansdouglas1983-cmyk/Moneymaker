"""SPEC-035: grouped-softmax MLE is the ONLY training objective; validation is race-level
proper scores (§6.4 progression step 4 prohibition, §8 objective separation, §9.1).

LambdaRank optimises ranking, not calibration; softmaxing its scores does not produce
coherent probabilities. This package therefore exposes no pairwise/ranking loss anywhere;
the registry below is immutable and names the single permitted objective (winner-only
Plackett-Luce reduces to it). Model selection consumes race-level proper scores only.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from types import MappingProxyType

REGISTERED_OBJECTIVES: Mapping[str, str] = MappingProxyType(
    {
        "grouped_softmax_mle": (
            "race-grouped softmax/cross-entropy maximum likelihood on the winner "
            "(l4_pricing._newton.newton_mle)"
        )
    }
)

_NORMALISATION_TOL = 1e-9


def _validated_winner_probability(probabilities: Mapping[int, float], winner_id: int) -> float:
    if winner_id not in probabilities:
        raise ValueError(f"winner {winner_id} is not in the race's probability map")
    total = math.fsum(probabilities[rid] for rid in sorted(probabilities))
    if abs(total - 1.0) > _NORMALISATION_TOL:
        raise ValueError(
            f"race probabilities must sum to 1 (got {total!r}); the race is one choice set"
        )
    return probabilities[winner_id]


def race_log_score(probabilities: Mapping[int, float], *, winner_id: int) -> float:
    """§9.1: L_r = −log p_(r, w_r) — the race-level log score on the actual winner."""
    return -math.log(_validated_winner_probability(probabilities, winner_id))


def race_brier(probabilities: Mapping[int, float], *, winner_id: int) -> float:
    """Race-level multiclass Brier score (§9.4) over the active runners."""
    _validated_winner_probability(probabilities, winner_id)
    return math.fsum(
        (p - (1.0 if rid == winner_id else 0.0)) ** 2
        for rid, p in sorted(probabilities.items())
    )
