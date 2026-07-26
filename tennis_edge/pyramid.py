"""Ratings that can see below the main tour.

Every rating this programme has built so far was fed only the priced corpus, and the priced
corpus is main tour. That means the rating layer has been **blind to the Challenger and ITF
circuits** — which is precisely where most professional tennis is played, and precisely where
a main-tour market has least to price from.

TE-0001 measured what that blindness costs. An Elo trained on the whole 1.69M-match pyramid
scored ``b1 = +0.16`` (t = 6.69) against the displayed price on main tour, where the
main-tour-only Elo scored ``-0.027`` against a genuine closing price. Those two numbers were
never comparable — the pyramid one was measured against a stale OddsPortal aggregate, and
TE-0001 says so plainly — so the question the difference raises was left open:

**does knowing a player's lower-tier record explain anything a real closing price misses?**

This module exists to answer that, and nothing in it is allowed to prejudge the answer.

Three specific things a main-tour rating gets wrong, all of which this layer can see:

- **A qualifier is not a new player.** Someone entering their first main draw has often
  played fifty Challengers. A main-tour rating starts them at 1500 — the population mean —
  which is an assertion of averageness, not an absence of information.
- **A "rested" player may have played five matches this week.** Days-since-last computed
  over main-tour appearances alone reads a Challenger campaign as a holiday. Fatigue is one
  of the few effects where a market genuinely may not have the data.
- **A returning player's form is invisible.** Comebacks are rebuilt through Challengers.

**Provenance and the no-lookahead rule.** Fed from Jeff Sackmann's archive (CC BY-NC-SA 4.0,
non-commercial; see :mod:`tennis_edge.sackmann`). The archive dates a match by the *Monday of
its tournament week*, not by the day it was played, so a whole tournament must be treated as
one indivisible block: absorbing "everything before today" inside a live tournament would
absorb that tournament's own later rounds. :data:`TOURNAMENT_LAG_DAYS` holds every result
back until its week has certainly closed. That costs up to a week of freshness and removes
the entire class of leakage — the same discipline, and the same constant, as
:mod:`tennis_edge.serve_stats`.

Players are keyed the way the priced corpus names them (surname plus initial, via
``sport_tennis.identity_bridge``), because the join to prices is the only reason this state
is being built. ATP and WTA are separate namespaces throughout — the same convention the
governed DP1 policy uses, for the same reason: a rating is meaningless across tours.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from tennis_edge.ratings import INITIAL_RATING, RatingConfig, elo_expected
from tennis_edge.sackmann import Level, SackmannMatch
from tennis_edge.serve_stats import PlayerKey, sackmann_player_key, td_player_key

__all__ = [
    "TOURNAMENT_LAG_DAYS",
    "TOUR_LEVELS",
    "PyramidRatings",
    "pyramid_features",
]

#: Days a tournament week is held back before any of its results may be seen. Eight covers
#: a Monday-start week plus a Sunday final. Identical to the serve-statistics lag, and for
#: the identical reason: the archive has no per-match date to be more precise with.
TOURNAMENT_LAG_DAYS = 8

#: Levels that count as main-tour play. Everything else is the pyramid below it.
TOUR_LEVELS = frozenset({Level.GRAND_SLAM, Level.MASTERS, Level.TOUR, Level.FINALS})

#: Window for the workload feature. Two weeks is the span over which accumulated matches
#: plausibly still cost a player something physically.
WORKLOAD_DAYS = 14


@dataclass
class _State:
    """One player's pyramid state, in one tour's namespace."""

    elo: float = INITIAL_RATING
    surface: dict[str, float] = field(default_factory=dict)
    matches: int = 0
    tour_level_matches: int = 0
    last_played: dt.date | None = None
    recent: list[dt.date] = field(default_factory=list)


class PyramidRatings:
    """Walk-forward Elo over the whole professional pyramid, keyed to priced-corpus names.

    Deliberately *not* a subclass of, or a change to, :class:`~tennis_edge.ratings.
    RatingEngine`. That engine is pinned by a regression test on the market benchmark, and
    an experiment that might fail has no business perturbing the one measurement that is
    already trusted.
    """

    def __init__(
        self,
        config: RatingConfig | None = None,
        *,
        lag_days: int = TOURNAMENT_LAG_DAYS,
        workload_days: int = WORKLOAD_DAYS,
    ) -> None:
        self._config = config or RatingConfig()
        self._lag = dt.timedelta(days=lag_days)
        self._workload = dt.timedelta(days=workload_days)
        self._players: dict[tuple[str, PlayerKey], _State] = defaultdict(_State)
        self._pending: list[SackmannMatch] = []
        self._cursor = 0
        self._absorbed_through: dt.date | None = None

    # ------------------------------------------------------------------ ingest

    def queue(self, matches: Iterable[SackmannMatch]) -> None:
        """Hold archive rows until their tournament week is safely in the past.

        Sorting by ``(week, tournament, match number)`` makes absorption a forward walk and
        makes the result independent of the order the files happened to be read in.
        """
        for match in matches:
            if not match.retired:
                self._pending.append(match)
        self._pending.sort(key=lambda m: (m.tourney_date, m.tour, m.tourney_id, m.match_num))

    def advance_to(self, today: dt.date) -> int:
        """Absorb every queued match whose tournament week closed before ``today``.

        Refuses to walk backwards. A backtest that rewound would silently score a match
        against state built from later results, which is the failure this whole class of
        code exists to prevent, so it raises rather than quietly re-deriving.
        """
        cutoff = today - self._lag
        if self._absorbed_through is not None and cutoff < self._absorbed_through:
            raise ValueError(
                f"cannot advance backwards: absorbed through {self._absorbed_through}, "
                f"asked for {cutoff}"
            )
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
        if winner is None or loser is None or winner == loser:
            return
        tour, surface = match.tour, match.surface or "Hard"
        w_state = self._players[(tour, winner)]
        l_state = self._players[(tour, loser)]

        grand_slam = match.level is Level.GRAND_SLAM
        k_w = self._config.k_factor(w_state.matches, grand_slam=grand_slam)
        k_l = self._config.k_factor(l_state.matches, grand_slam=grand_slam)

        surprise = 1.0 - elo_expected(w_state.elo, l_state.elo)
        w_surface = w_state.surface.get(surface, w_state.elo)
        l_surface = l_state.surface.get(surface, l_state.elo)
        surface_surprise = 1.0 - elo_expected(w_surface, l_surface)

        w_state.elo += k_w * surprise
        l_state.elo -= k_l * surprise
        w_state.surface[surface] = w_surface + k_w * surface_surprise
        l_state.surface[surface] = l_surface - k_l * surface_surprise

        tour_level = 1 if match.level in TOUR_LEVELS else 0
        for state in (w_state, l_state):
            state.matches += 1
            state.tour_level_matches += tour_level
            state.last_played = match.tourney_date
            state.recent.append(match.tourney_date)
            cutoff = match.tourney_date - dt.timedelta(days=120)
            state.recent = [when for when in state.recent if when > cutoff]

    # ------------------------------------------------------------------ query

    def _lookup(self, tour: str, name: str) -> _State | None:
        key = td_player_key(name)
        if key is None:
            return None
        return self._players.get((tour, key))

    def known_players(self, tour: str) -> set[PlayerKey]:
        """Every player with pyramid history in one tour's namespace.

        Exposed because an exchange market does not say whether it is men's or women's
        tennis, so the tour has to be inferred from which pool contains both players.
        """
        return {key for (t, key) in self._players if t == tour}

    def matches_for(self, tour: str, key: PlayerKey) -> int:
        """Match count by key rather than by display name.

        The name-keyed accessors go through the Tennis-Data naming convention, which is the
        right door for the priced main-tour corpus and the wrong one for a Betfair runner
        name. Callers that already hold a resolved key use this and skip the round trip.
        """
        state = self._players.get((tour, key))
        return 0 if state is None else state.matches

    def elo_for(self, tour: str, key: PlayerKey) -> float:
        state = self._players.get((tour, key))
        return INITIAL_RATING if state is None else state.elo

    def surface_elo_for(self, tour: str, key: PlayerKey, surface: str) -> float:
        state = self._players.get((tour, key))
        if state is None:
            return INITIAL_RATING
        return state.surface.get(surface or "Hard", state.elo)

    def elo(self, tour: str, name: str) -> float:
        """Pyramid Elo. Falls back to the population mean for a player never seen."""
        state = self._lookup(tour, name)
        return INITIAL_RATING if state is None else state.elo

    def surface_elo(self, tour: str, name: str, surface: str) -> float:
        state = self._lookup(tour, name)
        if state is None:
            return INITIAL_RATING
        return state.surface.get(surface or "Hard", state.elo)

    def matches_played(self, tour: str, name: str) -> int:
        state = self._lookup(tour, name)
        return 0 if state is None else state.matches

    def days_since_last(self, tour: str, name: str, today: dt.date) -> int | None:
        """``None`` for a player with no recorded pyramid history.

        Not zero, and not some large sentinel: "never seen" and "played today" are different
        claims, and collapsing them is how an absent player acquires a fabricated feature.
        """
        state = self._lookup(tour, name)
        if state is None or state.last_played is None:
            return None
        return (today - state.last_played).days

    def matches_in_last(self, tour: str, name: str, today: dt.date, days: int) -> int:
        state = self._lookup(tour, name)
        if state is None:
            return 0
        floor = today - dt.timedelta(days=days)
        return sum(1 for when in state.recent if when > floor)

    def tour_level_share(self, tour: str, name: str) -> float | None:
        """Share of a player's pyramid matches played at main-tour level.

        Near 1.0 is an established tour player; near 0.0 is someone whose record is almost
        entirely Challenger and Futures. ``None`` when there is no record to take a share of.
        """
        state = self._lookup(tour, name)
        if state is None or state.matches == 0:
            return None
        return state.tour_level_matches / state.matches


def pyramid_features(
    ratings: PyramidRatings,
    tour: str,
    player_a: str,
    player_b: str,
    when: dt.date,
    surface: str,
    *,
    minimum_matches: int = 5,
) -> dict[str, float]:
    """Pairwise features, or an empty dict when either player has too thin a record.

    Returning nothing rather than zeros is the important part. A zero gap is the positive
    claim "these two players are equal on this dimension"; an absent feature claims nothing.
    Feeding zeros in for unseen players would put the entire population of debutants at the
    exact centre of every distribution, which is both false and systematically so.
    """
    played_a = ratings.matches_played(tour, player_a)
    played_b = ratings.matches_played(tour, player_b)
    if played_a < minimum_matches or played_b < minimum_matches:
        return {}
    share_a = ratings.tour_level_share(tour, player_a)
    share_b = ratings.tour_level_share(tour, player_b)
    rest_a = ratings.days_since_last(tour, player_a, when)
    rest_b = ratings.days_since_last(tour, player_b, when)
    if share_a is None or share_b is None or rest_a is None or rest_b is None:
        return {}
    return {
        # Scaled by 400 so a coefficient of 1.0 means "one Elo point of logit per Elo point
        # of gap" on the usual scale, keeping it comparable with the main-tour features.
        "pyramid_elo_gap": (ratings.elo(tour, player_a)
                            - ratings.elo(tour, player_b)) / 400.0,
        "pyramid_surface_gap": (ratings.surface_elo(tour, player_a, surface)
                                - ratings.surface_elo(tour, player_b, surface)) / 400.0,
        # The three things a main-tour rating cannot see at all.
        "pyramid_workload_gap": float(
            ratings.matches_in_last(tour, player_a, when, WORKLOAD_DAYS)
            - ratings.matches_in_last(tour, player_b, when, WORKLOAD_DAYS)
        ),
        "pyramid_rest_gap": (min(rest_a, 180) - min(rest_b, 180)) / 30.0,
        "pyramid_tier_gap": share_a - share_b,
    }
