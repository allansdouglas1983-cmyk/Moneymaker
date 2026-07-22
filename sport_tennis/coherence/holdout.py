"""CROSS_MARKET_COHERENCE_V1 — PRODUCTION holdout-coherence contract (STAGE3-0005 §15).

SYNTHETIC-ONLY, deterministic. Identification consumes Match-Odds + ONE Total-Games line
(``solver.identify``); EVERY other Total-Games line and EVERY Game-Handicap line is RESERVED as
holdout (coherence-v1.yaml). This module projects the identified serve parameters onto each
reserved holdout line and reports the RAW metrics only — model-implied probability, the observed
back/lay interval and midpoint, the interval violation, the ladder tick-distance, the
first-server range, the line and the market type. It emits ONLY the permitted §15 structural
statuses; it produces NO categorical coherence verdict (COHERENT / INCOHERENT / ... remain
founder-pending) and no tip, edge or final probability. Import-quarantined from
execution/pricing/V0/research.xmarket.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from price_contracts.ladder import LADDER
from sport_tennis.coherence.formats import MatchFormat
from sport_tennis.coherence.match import match_distribution
from sport_tennis.coherence.pmf import handicap_cover, over_under
from sport_tennis.coherence.scoring import CoherenceMathError
from sport_tennis.coherence.solver import (
    BOUNDARY_SOLUTION,
    FIRST_SERVER_SENSITIVE_PENDING_THRESHOLD,
    IDENTIFIED,
    IdentificationResult,
    Root,
)

# Market-type tokens for holdout lines (§15). COMBINED_TOTAL is the Over side; HANDICAP is the
# game handicap carried by player A.
COMBINED_TOTAL_OVER = "COMBINED_TOTAL_OVER"
HANDICAP_A = "HANDICAP_A"
_MARKET_TYPES = frozenset({COMBINED_TOTAL_OVER, HANDICAP_A})

# Holdout structural statuses (subset of coherence-v1.yaml §15).
HOLDOUT_SURFACE_AVAILABLE = "HOLDOUT_SURFACE_AVAILABLE"
HOLDOUT_SURFACE_UNAVAILABLE = "HOLDOUT_SURFACE_UNAVAILABLE"
ORIGIN_UNRESOLVED = "ORIGIN_UNRESOLVED"

# Identification statuses that leave a projectable origin (one or two roots).
_ORIGIN_STATUSES = frozenset({IDENTIFIED, BOUNDARY_SOLUTION,
                              FIRST_SERVER_SENSITIVE_PENDING_THRESHOLD})


@dataclass(frozen=True)
class HoldoutObservation:
    """A reserved holdout line with its observed market-implied probability interval. The
    interval is supplied (synthetic / neutral) — this module never invents market data."""

    market_type: str
    line: Decimal
    observed_back_prob: float
    observed_lay_prob: float


@dataclass(frozen=True)
class HoldoutMetric:
    """Raw projected-vs-observed metrics for ONE holdout line. No verdict, no threshold."""

    market_type: str
    line: Decimal
    model_implied_low: float
    model_implied_high: float
    first_server_range: float
    observed_back_prob: float
    observed_lay_prob: float
    observed_midpoint: float
    interval_violation: float
    tick_distance: int


@dataclass(frozen=True)
class HoldoutSurface:
    """The holdout projection surface for an identification result. ``status`` is a §15 structural
    status only."""

    status: str
    metrics: tuple[HoldoutMetric, ...]


def _model_prob_at(root: Root, obs: HoldoutObservation, fmt: MatchFormat) -> float:
    md = match_distribution(root.p_a, root.p_b, fmt, a_serves_first_match=root.a_serves_first)
    if obs.market_type == COMBINED_TOTAL_OVER:
        return over_under(md.total_games_pmf, obs.line).over
    if obs.market_type == HANDICAP_A:
        return handicap_cover(md.margin_pmf, obs.line).a_covers
    raise CoherenceMathError(f"unknown holdout market_type {obs.market_type!r}")


def _nearest_tick_index(odds: Decimal) -> int:
    """Index of the canonical-ladder tick nearest ``odds`` (ties resolve to the lower index).
    Local scan over the exported ladder; the governed money module is untouched."""
    best_i = 0
    best_d: Decimal | None = None
    for i, price in enumerate(LADDER):
        d = abs(price - odds)
        if best_d is None or d < best_d:
            best_i, best_d = i, d
    return best_i


def _tick_distance(model_mid: float, observed_mid: float) -> int:
    """Absolute canonical-ladder tick distance between the two implied probabilities (compared as
    back-odds = 1/p, snapped to the nearest ladder tick). A raw diagnostic, not a verdict."""
    if not (0.0 < model_mid < 1.0 and 0.0 < observed_mid < 1.0):
        raise CoherenceMathError("implied probabilities for tick-distance must be in (0,1)")
    model_odds = Decimal(1) / Decimal(str(model_mid))
    observed_odds = Decimal(1) / Decimal(str(observed_mid))
    return abs(_nearest_tick_index(model_odds) - _nearest_tick_index(observed_odds))


def _interval_violation(lo: float, hi: float, back: float, lay: float) -> float:
    """Signed probability gap between the model-implied range [lo,hi] and the observed interval
    [min,max]. 0.0 when they intersect; positive when the model sits BELOW the interval; negative
    when ABOVE. Raw distance — carries no coherence judgement."""
    obs_lo, obs_hi = (back, lay) if back <= lay else (lay, back)
    if hi < obs_lo:
        return obs_lo - hi
    if lo > obs_hi:
        return obs_hi - lo
    return 0.0


def evaluate_holdout(ident: IdentificationResult,
                     observations: tuple[HoldoutObservation, ...]) -> HoldoutSurface:
    """Project the identified origin onto each reserved holdout line and return raw metrics.

    ORIGIN_UNRESOLVED when identification did not resolve to a projectable origin;
    HOLDOUT_SURFACE_UNAVAILABLE when it did but no holdout lines were supplied;
    HOLDOUT_SURFACE_AVAILABLE with per-line raw metrics otherwise. No categorical coherence
    verdict is emitted (founder-pending)."""
    if ident.status not in _ORIGIN_STATUSES or not ident.roots:
        return HoldoutSurface(status=ORIGIN_UNRESOLVED, metrics=())
    if not observations:
        return HoldoutSurface(status=HOLDOUT_SURFACE_UNAVAILABLE, metrics=())

    metrics: list[HoldoutMetric] = []
    for obs in observations:
        if obs.market_type not in _MARKET_TYPES:
            raise CoherenceMathError(f"unknown holdout market_type {obs.market_type!r}")
        probs = [_model_prob_at(r, obs, ident.fmt) for r in ident.roots]
        low, high = min(probs), max(probs)
        mid = (low + high) / 2.0
        observed_mid = (obs.observed_back_prob + obs.observed_lay_prob) / 2.0
        metrics.append(HoldoutMetric(
            market_type=obs.market_type,
            line=obs.line,
            model_implied_low=low,
            model_implied_high=high,
            first_server_range=high - low,
            observed_back_prob=obs.observed_back_prob,
            observed_lay_prob=obs.observed_lay_prob,
            observed_midpoint=observed_mid,
            interval_violation=_interval_violation(low, high, obs.observed_back_prob,
                                                   obs.observed_lay_prob),
            tick_distance=_tick_distance(mid, observed_mid),
        ))
    return HoldoutSurface(status=HOLDOUT_SURFACE_AVAILABLE, metrics=tuple(metrics))
