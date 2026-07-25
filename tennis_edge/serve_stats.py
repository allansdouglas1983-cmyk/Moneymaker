"""Opponent-adjusted serve and return estimates, and the join to the priced corpus.

Two published ideas, implemented as stated:

**Barnett & Clarke (2005) additive combination.** A player's serve-point probability against
a specific opponent is ``f_ij = f_t + (f_i - f_av) - (g_j - g_av)`` — tour baseline, plus the
server's serve strength above average, minus the returner's return strength above average.
Because the tour serve and return averages themselves sum to 1, the construction is
consistent *within a service game*: A's serve probability and B's return probability against
that serve are complements by definition. It does **not** make the two players' own serve
probabilities sum to 1 — those describe different service games, and in a mismatch they
correctly sum to well over 1 (two good servers both hold often). Anything asserting
``f_ij + f_ji == 1`` has confused the two.

**Shrinkage toward the tour mean, weighted by serve points.** A single match's serve
percentage carries a standard error near five points, and the match model amplifies the
*difference* between two players by roughly five times. Unshrunk estimates would therefore
produce swings of tens of points of match probability out of pure noise. Weight is
``n / (n + prior)`` in serve points, not matches, because a three-set match carries twice the
evidence of a straight-sets one.

**The timing rule that keeps it honest.** Sackmann stamps every match with the *Monday of the
tournament week*, not the match date — there is no per-match timestamp. A tournament that
started on Monday is still running on Thursday, so its later rounds lie in the future of a
Thursday match. This module therefore only ever absorbs tournaments whose week closed at
least :data:`TOURNAMENT_LAG_DAYS` before the date being priced. That costs up to a week of
freshness and removes an entire class of silent leakage.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from sport_tennis.identity_bridge import _betfair_keys, _td_key, normalize_name

from tennis_edge.point_model import match_probability
from tennis_edge.sackmann import SackmannMatch

__all__ = [
    "TOURNAMENT_LAG_DAYS",
    "PRIOR_SERVE_POINTS",
    "RECENCY_HALF_LIFE_DAYS",
    "PlayerKey",
    "td_player_key",
    "sackmann_player_key",
    "ServeEstimate",
    "ServeEstimator",
]

#: A tournament week is only absorbed once this many days have passed since its Monday
#: stamp, so no still-running event can contribute a future round.
TOURNAMENT_LAG_DAYS = 8

#: Prior strength in serve points. Roughly seven matches' worth: enough to stop a debutant's
#: three good service games becoming a rating, small enough that a season overwhelms it.
PRIOR_SERVE_POINTS = 500.0

#: Exponential recency decay. Form and physical condition move over months, not years.
RECENCY_HALF_LIFE_DAYS = 365.0

PlayerKey = tuple[str, str]


def td_player_key(name: str) -> PlayerKey | None:
    """Key for a Tennis-Data style name (``"Alcaraz C."``)."""
    key = _td_key(normalize_name(name))
    return None if key is None else (key[0], key[1])


def sackmann_player_key(name: str) -> PlayerKey | None:
    """Key for an archive full name (``"Carlos Alcaraz"``).

    The archive gives full names and the priced corpus gives surname-plus-initial, so the
    join runs through the same ``td-norm-v1`` normalisation both sides. Where a full name
    splits several ways only the first surname/initials candidate is taken; an ambiguous
    join is better refused downstream than guessed at here.
    """
    candidates = _betfair_keys(normalize_name(name))
    if not candidates:
        return None
    surname, initials = candidates[0]
    return (surname, initials[:1])


@dataclass
class _Accumulator:
    """Exponentially decayed serve and return counts for one player."""

    serve_points: float = 0.0
    serve_won: float = 0.0
    return_points: float = 0.0
    return_won: float = 0.0
    last_decay: dt.date | None = None
    matches: int = 0

    def decay_to(self, when: dt.date, half_life_days: float) -> None:
        if self.last_decay is None:
            self.last_decay = when
            return
        elapsed = (when - self.last_decay).days
        if elapsed <= 0:
            return
        factor = 0.5 ** (elapsed / half_life_days)
        self.serve_points *= factor
        self.serve_won *= factor
        self.return_points *= factor
        self.return_won *= factor
        self.last_decay = when


@dataclass(frozen=True)
class ServeEstimate:
    """Opponent-adjusted serve probabilities for both sides, plus coverage."""

    p_serve_a: float
    p_serve_b: float
    serve_points_a: float
    serve_points_b: float
    matches_a: int
    matches_b: int

    @property
    def coverage(self) -> float:
        """Serve points behind the weaker of the two estimates."""
        return min(self.serve_points_a, self.serve_points_b)

    def match_probability(self, *, best_of: int = 3) -> float:
        """P(player A wins), via the hierarchical Markov model."""
        return match_probability(self.p_serve_a, 1.0 - self.p_serve_b, best_of=best_of)


class ServeEstimator:
    """Walk-forward serve/return state, fed from the archive, queried by the priced corpus."""

    def __init__(
        self,
        *,
        prior_serve_points: float = PRIOR_SERVE_POINTS,
        half_life_days: float = RECENCY_HALF_LIFE_DAYS,
        lag_days: int = TOURNAMENT_LAG_DAYS,
    ) -> None:
        self._prior = prior_serve_points
        self._half_life = half_life_days
        self._lag = dt.timedelta(days=lag_days)
        self._players: dict[tuple[str, PlayerKey], _Accumulator] = defaultdict(_Accumulator)
        self._tour_serve: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
        self._pending: list[SackmannMatch] = []
        # Index of the next unabsorbed row. The queue is sorted by tournament week, so
        # absorbing is a forward walk; rebuilding the list on every call would make the
        # whole backtest quadratic in corpus size.
        self._cursor = 0
        self._absorbed_through: dt.date | None = None

    # ------------------------------------------------------------------ ingest

    def queue(self, matches: Iterable[SackmannMatch]) -> None:
        """Hold archive rows until their tournament week is safely in the past."""
        for match in matches:
            if match.has_serve_stats and not match.retired:
                self._pending.append(match)
        self._pending.sort(key=lambda m: (m.tourney_date, m.tourney_id, m.match_num))

    def advance_to(self, today: dt.date) -> int:
        """Absorb every queued match whose tournament week closed before ``today``."""
        cutoff = today - self._lag
        absorbed = 0
        while self._cursor < len(self._pending):
            match = self._pending[self._cursor]
            if match.tourney_date > cutoff:
                break
            self._absorb(match)
            self._cursor += 1
            absorbed += 1
        self._absorbed_through = cutoff
        return absorbed

    def _absorb(self, match: SackmannMatch) -> None:
        winner = sackmann_player_key(match.winner_name)
        loser = sackmann_player_key(match.loser_name)
        if winner is None or loser is None:
            return
        w_line, l_line = match.winner_serve, match.loser_serve
        w_points, l_points = w_line.serve_points, l_line.serve_points
        w_won, l_won = w_line.serve_points_won, l_line.serve_points_won
        if w_points is None or l_points is None or w_won is None or l_won is None:
            return

        tour_total = self._tour_serve[match.tour]
        tour_total[0] += w_points + l_points
        tour_total[1] += w_won + l_won

        for key, own_points, own_won, opp_points, opp_won in (
            (winner, w_points, w_won, l_points, l_won),
            (loser, l_points, l_won, w_points, w_won),
        ):
            state = self._players[(match.tour, key)]
            state.decay_to(match.tourney_date, self._half_life)
            state.serve_points += own_points
            state.serve_won += own_won
            # Return points are the opponent's serve points; return points won is the
            # complement of what the opponent won on serve.
            state.return_points += opp_points
            state.return_won += opp_points - opp_won
            state.matches += 1

    # ------------------------------------------------------------------ query

    def tour_serve_average(self, tour: str) -> float:
        points, won = self._tour_serve[tour]
        if points <= 0:
            return 0.62
        return won / points

    def _shrunk(self, tour: str, key: PlayerKey, when: dt.date) -> tuple[float, float, float, int]:
        """Shrunk serve %, shrunk return %, serve-point weight, matches seen."""
        baseline = self.tour_serve_average(tour)
        state = self._players.get((tour, key))
        if state is None:
            return baseline, 1.0 - baseline, 0.0, 0
        state.decay_to(when, self._half_life)
        serve = baseline
        if state.serve_points > 0:
            raw = state.serve_won / state.serve_points
            weight = state.serve_points / (state.serve_points + self._prior)
            serve = baseline + weight * (raw - baseline)
        returned = 1.0 - baseline
        if state.return_points > 0:
            raw = state.return_won / state.return_points
            weight = state.return_points / (state.return_points + self._prior)
            returned = (1.0 - baseline) + weight * (raw - (1.0 - baseline))
        return serve, returned, state.serve_points, state.matches

    def estimate(
        self, tour: str, name_a: str, name_b: str, when: dt.date
    ) -> ServeEstimate | None:
        """Barnett-Clarke adjusted serve probabilities for a Tennis-Data style matchup."""
        key_a, key_b = td_player_key(name_a), td_player_key(name_b)
        if key_a is None or key_b is None or key_a == key_b:
            return None
        baseline = self.tour_serve_average(tour)
        serve_a, return_a, points_a, matches_a = self._shrunk(tour, key_a, when)
        serve_b, return_b, points_b, matches_b = self._shrunk(tour, key_b, when)
        if points_a <= 0.0 or points_b <= 0.0:
            return None
        return_average = 1.0 - baseline
        # f_ij = f_t + (f_i - f_av) - (g_j - g_av); the two sides sum to 1 by construction.
        p_a = baseline + (serve_a - baseline) - (return_b - return_average)
        p_b = baseline + (serve_b - baseline) - (return_a - return_average)
        return ServeEstimate(
            p_serve_a=min(max(p_a, 0.30), 0.90),
            p_serve_b=min(max(p_b, 0.30), 0.90),
            serve_points_a=points_a,
            serve_points_b=points_b,
            matches_a=matches_a,
            matches_b=matches_b,
        )
