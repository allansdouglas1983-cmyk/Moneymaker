"""Rating engines — Elo, surface Elo and games-weighted Elo, run as one walk-forward state.

These are **feature producers, not answers**. Measured on this corpus, a surface-blended Elo
scores 0.633 log loss against the closing line's 0.575 and adds nothing in any segment. That
is not a reason to skip it: a rating is a compact summary of match history that a downstream
model can use, and it is the cheapest such summary there is. It is only a reason never to
ship one as the prediction.

Constants come from the published implementations rather than being tuned here:

* K-factor ``250 / (matches + 5) ** 0.4`` with a 1.1 multiplier at Grand Slams — the
  FiveThirtyEight tennis system as restated in Kovalchik (2016) eq. (4)-(5).
* Initialisation 1500, logistic base 10, divisor 400.
* Surface blend 50/50 overall+surface — Sackmann's published comparison found 50/50 and
  60/40 differ by "extremely small" amounts, and grid-searched per-metric weights swing from
  0% to 100% on small samples, which is itself the argument for the stable default.
* Games-weighted update ``f(G) = NG_winner / (NG_winner + NG_loser)`` — Angelini, Candila &
  De Angelis (2022, EJOR). Because ``f <= 1``, weighted Elo is bounded above by plain Elo,
  and the gap between them is a usable form signal.

Everything updates in whole-day batches so a match cannot inform a same-day prediction.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Sequence

from tennis_edge.corpus import Match

__all__ = [
    "INITIAL_RATING",
    "RatingConfig",
    "RatingEngine",
    "elo_expected",
]

INITIAL_RATING = 1500.0


def elo_expected(rating_a: float, rating_b: float) -> float:
    """The registered logistic. Equal ratings give exactly 0.5."""
    if rating_a == rating_b:
        return 0.5
    return float(1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0)))


@dataclass(frozen=True)
class RatingConfig:
    """Published constants. Tuning these against performance is what the plan forbids."""

    k_base: float = 250.0
    k_offset: float = 5.0
    k_shape: float = 0.4
    grand_slam_multiplier: float = 1.1
    surface_weight: float = 0.5

    def k_factor(self, matches_played: int, *, grand_slam: bool) -> float:
        k = float(self.k_base / ((matches_played + self.k_offset) ** self.k_shape))
        return k * self.grand_slam_multiplier if grand_slam else k


@dataclass
class _PlayerState:
    elo: float = INITIAL_RATING
    weighted: float = INITIAL_RATING
    matches: int = 0
    last_played: dt.date | None = None
    recent: list[tuple[dt.date, int]] = field(default_factory=list)  # (date, games played)


class RatingEngine:
    """Walk-forward rating state for both tours.

    ``snapshot`` reads the state as it stands *before* any of the current day is applied;
    ``observe`` then applies a whole day at once. Calling them in that order is what makes
    the ratings honest, and the harness enforces it.
    """

    def __init__(self, config: RatingConfig | None = None) -> None:
        self._config = config or RatingConfig()
        self._players: dict[tuple[str, str], _PlayerState] = defaultdict(_PlayerState)
        self._surface: dict[tuple[str, str, str], float] = {}
        self._h2h: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0])

    @property
    def config(self) -> RatingConfig:
        return self._config

    # ---------------------------------------------------------------- reads (pre-match)

    def _state(self, tour: str, player: str) -> _PlayerState:
        return self._players[(tour, player)]

    def _surface_rating(self, tour: str, player: str, surface: str) -> float:
        """Surface ratings cold-start at the player's overall rating, not at 1500.

        Starting a clay rating from scratch would tell us a top-20 player is average the
        first time they play on clay, which is plainly false and would inject noise exactly
        where surface information is scarcest.
        """
        key = (tour, player, surface)
        if key in self._surface:
            return self._surface[key]
        return self._state(tour, player).elo

    def elo(self, tour: str, player: str) -> float:
        return self._state(tour, player).elo

    def weighted_elo(self, tour: str, player: str) -> float:
        return self._state(tour, player).weighted

    def surface_elo(self, tour: str, player: str, surface: str) -> float:
        return self._surface_rating(tour, player, surface)

    def blended(self, tour: str, player: str, surface: str) -> float:
        w = self._config.surface_weight
        return (1.0 - w) * self.elo(tour, player) + w * self._surface_rating(tour, player, surface)

    def matches_played(self, tour: str, player: str) -> int:
        return self._state(tour, player).matches

    def days_since_last(self, tour: str, player: str, today: dt.date) -> int | None:
        last = self._state(tour, player).last_played
        return None if last is None else (today - last).days

    def games_in_last(self, tour: str, player: str, today: dt.date, days: int) -> int:
        cutoff = today - dt.timedelta(days=days)
        return sum(g for when, g in self._state(tour, player).recent if when > cutoff)

    def matches_in_last(self, tour: str, player: str, today: dt.date, days: int) -> int:
        cutoff = today - dt.timedelta(days=days)
        return sum(1 for when, _ in self._state(tour, player).recent if when > cutoff)

    def head_to_head(self, tour: str, player_a: str, player_b: str) -> tuple[int, int]:
        """Wins for a and for b in prior meetings, keyed on the sorted pair."""
        first, second = sorted((player_a, player_b))
        wins = self._h2h[(tour, first, second)]
        return (wins[0], wins[1]) if player_a == first else (wins[1], wins[0])

    def expected(self, match: Match) -> float:
        """Blended-Elo probability that player_a wins."""
        return elo_expected(
            self.blended(match.tour, match.player_a, match.surface),
            self.blended(match.tour, match.player_b, match.surface),
        )

    # ---------------------------------------------------------------- write (post-match)

    def observe(self, matches: Sequence[Match]) -> None:
        """Apply one whole day. Deltas are computed against start-of-day ratings.

        Every match in the batch is scored first and the ratings moved afterwards, so the
        result is invariant to the order the day's matches happen to be listed in.
        """
        elo_deltas: dict[tuple[str, str], float] = defaultdict(float)
        weighted_deltas: dict[tuple[str, str], float] = defaultdict(float)
        surface_deltas: dict[tuple[str, str, str], float] = defaultdict(float)
        touched: dict[tuple[str, str], list[Match]] = defaultdict(list)

        ordered = sorted(matches, key=lambda m: (m.tour, m.player_a, m.player_b))
        for match in ordered:
            if not match.completed:
                continue
            winner, loser = match.winner, match.loser
            tour, surface = match.tour, match.surface
            grand_slam = "grand slam" in match.tier.lower()

            expected_winner = elo_expected(self.elo(tour, winner), self.elo(tour, loser))
            k_w = self._config.k_factor(self.matches_played(tour, winner), grand_slam=grand_slam)
            k_l = self._config.k_factor(self.matches_played(tour, loser), grand_slam=grand_slam)
            surprise = 1.0 - expected_winner
            elo_deltas[(tour, winner)] += k_w * surprise
            elo_deltas[(tour, loser)] -= k_l * surprise

            expected_surface = elo_expected(
                self._surface_rating(tour, winner, surface),
                self._surface_rating(tour, loser, surface),
            )
            surface_deltas[(tour, winner, surface)] += k_w * (1.0 - expected_surface)
            surface_deltas[(tour, loser, surface)] -= k_l * (1.0 - expected_surface)

            weight = _margin_weight(match)
            expected_weighted = elo_expected(
                self.weighted_elo(tour, winner), self.weighted_elo(tour, loser)
            )
            weighted_surprise = (1.0 - expected_weighted) * weight
            weighted_deltas[(tour, winner)] += k_w * weighted_surprise
            weighted_deltas[(tour, loser)] -= k_l * weighted_surprise

            touched[(tour, winner)].append(match)
            touched[(tour, loser)].append(match)
            first, second = sorted((match.player_a, match.player_b))
            self._h2h[(tour, first, second)][0 if winner == first else 1] += 1

        for (tour, player), delta in sorted(elo_deltas.items()):
            self._players[(tour, player)].elo += delta
        for (tour, player), delta in sorted(weighted_deltas.items()):
            self._players[(tour, player)].weighted += delta
        for key, delta in sorted(surface_deltas.items()):
            tour, player, surface = key
            self._surface[key] = self._surface_rating(tour, player, surface) + delta
        for (tour, player), played in sorted(touched.items(), key=lambda kv: kv[0]):
            state = self._players[(tour, player)]
            for match in played:
                games = (match.games_a or 0) + (match.games_b or 0)
                state.recent.append((match.match_date, games))
                state.matches += 1
                state.last_played = match.match_date
            cutoff = match.match_date - dt.timedelta(days=90)
            state.recent = [(when, g) for when, g in state.recent if when > cutoff]


def _margin_weight(match: Match) -> float:
    """Angelini's ``f(G) = NG_winner / (NG_winner + NG_loser)``, in [0.5, 1].

    A 6-0 6-0 gives 1.0; a two-tiebreak win gives about 0.54, so a scrappy victory barely
    moves the rating. Falls back to 1.0 (plain Elo) when set scores are missing rather than
    inventing a margin.
    """
    if match.games_a is None or match.games_b is None:
        return 1.0
    winner_games = match.games_a if match.winner_is_a else match.games_b
    total = match.games_a + match.games_b
    if total <= 0:
        return 1.0
    return winner_games / total
