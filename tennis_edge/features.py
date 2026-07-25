"""Feature construction, and the registry that keeps prices out of the model.

Two hard rules, enforced here rather than remembered:

**No odds-derived quantity may become a model feature.** The market price is the thing we
are trying to beat; feeding it in as a predictor and then betting against it is circular,
and it is the flaw that invalidates several widely-cited tennis papers. The market enters
this system in exactly one place — as an *offset* in the residual model — and never as a
column in the feature matrix. :func:`assert_no_price_features` is the guard.

**Every feature is computed from state that existed before the match started.** Features
come from a :class:`~tennis_edge.ratings.RatingEngine` that has not yet observed the current
day, so a same-day result cannot reach them.

Features are all differences or symmetric pairs oriented on ``player_a``. Because the corpus
loader orders players by name rather than by result, a feature being large for player_a
carries no information about who won.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from tennis_edge.corpus import Match
from tennis_edge.ratings import RatingEngine

__all__ = [
    "FEATURE_NAMES",
    "BANNED_FEATURE_TOKENS",
    "FeatureRow",
    "build_features",
    "assert_no_price_features",
]

#: Substrings that must never appear in a feature name. A price, an implied probability or a
#: bookmaker name in the feature matrix means the model is being shown the answer.
BANNED_FEATURE_TOKENS = (
    "odds", "price", "implied", "market", "pinnacle", "b365", "bet365", "betfair",
    "bfe", "avg_w", "max_w", "vig", "overround", "book",
)

FEATURE_NAMES: tuple[str, ...] = (
    "elo_diff",
    "surface_elo_diff",
    "blended_elo_diff",
    "weighted_elo_diff",
    "form_gap_a",
    "form_gap_b",
    "log_rank_ratio",
    "log_points_ratio",
    "experience_min",
    "experience_diff",
    "rest_days_a",
    "rest_days_b",
    "rest_diff",
    "games_14d_diff",
    "matches_30d_diff",
    "h2h_diff",
    "h2h_total",
    "best_of_five",
    "indoor",
    "surface_clay",
    "surface_grass",
    "surface_hard",
    "grand_slam",
)

_MAX_REST_DAYS = 120.0


@dataclass(frozen=True)
class FeatureRow:
    """One match's features, the market's view, and the outcome — kept strictly apart."""

    match: Match
    values: tuple[float, ...]
    market_logit: float | None
    outcome: int

    def as_dict(self) -> dict[str, float]:
        return dict(zip(FEATURE_NAMES, self.values))


def assert_no_price_features(names: Sequence[str] = FEATURE_NAMES) -> None:
    """Raise if any feature name looks like a price. Called by the tests and the builder."""
    for name in names:
        lowered = name.lower()
        for token in BANNED_FEATURE_TOKENS:
            if token in lowered:
                raise ValueError(
                    f"feature {name!r} looks price-derived (matched {token!r}); the market "
                    "may only enter as a residual offset, never as a feature"
                )


def _safe_log_ratio(first: int | None, second: int | None) -> float:
    """Log ratio of two positive quantities; 0.0 when either is unknown.

    Zero is the neutral value for a difference feature, so a missing rank contributes
    nothing rather than pretending the players are equal in some other way.
    """
    if not first or not second or first <= 0 or second <= 0:
        return 0.0
    return math.log(first / second)


def _rest(engine: RatingEngine, match: Match, player: str) -> float:
    days = engine.days_since_last(match.tour, player, match.match_date)
    if days is None:
        return _MAX_REST_DAYS
    return float(min(days, _MAX_REST_DAYS))


def build_features(engine: RatingEngine, match: Match) -> tuple[float, ...]:
    """The pre-match feature vector for ``match``, read from ``engine``'s current state."""
    tour, surface = match.tour, match.surface
    a, b = match.player_a, match.player_b

    elo_a, elo_b = engine.elo(tour, a), engine.elo(tour, b)
    selo_a = engine.surface_elo(tour, a, surface)
    selo_b = engine.surface_elo(tour, b, surface)
    blend_a = engine.blended(tour, a, surface)
    blend_b = engine.blended(tour, b, surface)
    welo_a, welo_b = engine.weighted_elo(tour, a), engine.weighted_elo(tour, b)

    played_a = engine.matches_played(tour, a)
    played_b = engine.matches_played(tour, b)
    rest_a, rest_b = _rest(engine, match, a), _rest(engine, match, b)
    h2h_a, h2h_b = engine.head_to_head(tour, a, b)
    tier = match.tier.lower()

    return (
        elo_a - elo_b,
        selo_a - selo_b,
        blend_a - blend_b,
        welo_a - welo_b,
        # Angelini's form proxy: plain Elo minus games-weighted Elo. Weighted is bounded
        # above by plain, so a large gap means recent wins were narrower than the rating.
        elo_a - welo_a,
        elo_b - welo_b,
        _safe_log_ratio(match.rank_a, match.rank_b),
        _safe_log_ratio(match.points_a, match.points_b),
        float(min(played_a, played_b)),
        float(played_a - played_b),
        rest_a,
        rest_b,
        rest_a - rest_b,
        float(engine.games_in_last(tour, a, match.match_date, 14)
              - engine.games_in_last(tour, b, match.match_date, 14)),
        float(engine.matches_in_last(tour, a, match.match_date, 30)
              - engine.matches_in_last(tour, b, match.match_date, 30)),
        float(h2h_a - h2h_b),
        float(h2h_a + h2h_b),
        1.0 if match.best_of == 5 else 0.0,
        1.0 if match.indoor else 0.0,
        1.0 if surface.lower() == "clay" else 0.0,
        1.0 if surface.lower() == "grass" else 0.0,
        1.0 if surface.lower() == "hard" else 0.0,
        1.0 if "grand slam" in tier else 0.0,
    )


assert_no_price_features()
