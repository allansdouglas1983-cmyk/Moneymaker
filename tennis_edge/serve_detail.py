"""Serve and return, decomposed. The signal the aggregate estimator throws away.

:mod:`tennis_edge.serve_stats` collapses nine archive fields per player per match into one
ratio — serve points won. That ratio is the input to the Barnett–Clarke point model, and it
is the right input *for that model*, which assumes a single serve-win probability. It is not
all the information available, and the two things it discards are the two the tennis
literature cites most.

**First and second serve are different skills.** A player landing 70% of first serves and
winning 78% of them is a different problem from one landing 55% and winning 85%; the
aggregate cannot tell them apart, and their opponents' returns differ accordingly. The
split also drives the variance of a service game, which drives break probability, which
drives the match.

**Break points are where matches are decided, and pressure performance is not the average.**
Break points faced and saved measure holding under pressure directly. A tight match turns on
a handful of them, and a player's record on them is not implied by their overall serve rate.

Also carried: ace and double-fault rates, which are the tails of the serve distribution and
move a match's variance without moving its mean much — relevant because the same expected
win probability at higher variance is worth a different price.

**Every rate is shrunk by its own denominator, separately.** First-serve win rate is measured
over first serves landed, second-serve win rate over second serves played, break-point saves
over break points faced. Those denominators differ by an order of magnitude within a single
match, so shrinking the aggregate and splitting afterwards would apply one sample size to
quantities that do not share it.

**Return statistics are the mirror of what was faced**, taken from the opponent's serve line
rather than a separate feed — that is how the archive is shaped, and inventing a return feed
would double-count.

Same tournament-week lag as everywhere else: the archive dates a match by the Monday of its
week, so a whole tournament moves as one block or its own later rounds inform it.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from tennis_edge.sackmann import SackmannMatch
from tennis_edge.serve_stats import PlayerKey, sackmann_player_key, td_player_key

__all__ = [
    "PRIOR_POINTS",
    "TOURNAMENT_LAG_DAYS",
    "ServeProfile",
    "DetailEstimator",
    "serve_detail_features",
]

#: Pseudo-observations of the baseline mixed into every rate. Each rate uses it against its
#: own denominator, so a break-point rate on twelve break points is shrunk far harder than a
#: first-serve rate on nine hundred points — which is the point of doing this per component.
PRIOR_POINTS = 200.0

TOURNAMENT_LAG_DAYS = 8


@dataclass
class ServeProfile:
    """Accumulated serve counts for one player, plus what they faced on return."""

    first_in: int = 0
    serve_points: int = 0
    first_won: int = 0
    second_won: int = 0
    aces: int = 0
    double_faults: int = 0
    bp_saved: int = 0
    bp_faced: int = 0
    matches: int = 0
    #: Return side: points faced on the opponent's serve, and how many were won.
    return_points: int = 0
    return_won: int = 0

    @staticmethod
    def _shrink(won: float, total: float, baseline: float,
                prior: float = PRIOR_POINTS) -> float:
        """Rate shrunk toward ``baseline`` by its own denominator.

        With no observations this is exactly the baseline — the prior, not a division and
        not a fabricated number.
        """
        if total <= 0:
            return baseline
        weight = total / (total + prior)
        return baseline + weight * (won / total - baseline)

    def first_serve_rate(self, *, baseline: float) -> float:
        """Share of service points where the first serve landed."""
        return self._shrink(self.first_in, self.serve_points, baseline)

    def first_win_rate(self, *, baseline: float) -> float:
        """Points won when the first serve landed. Denominator is serves in, not played."""
        return self._shrink(self.first_won, self.first_in, baseline)

    def second_win_rate(self, *, baseline: float) -> float:
        """Points won on second serve. Denominator is points where the first missed."""
        second = self.serve_points - self.first_in
        return self._shrink(self.second_won, second, baseline)

    def ace_rate(self, *, baseline: float) -> float:
        return self._shrink(self.aces, self.serve_points, baseline)

    def double_fault_rate(self, *, baseline: float) -> float:
        return self._shrink(self.double_faults, self.serve_points, baseline)

    def break_point_save_rate(self, *, baseline: float) -> float:
        """Break points saved. The smallest denominator here and the hardest shrunk."""
        return self._shrink(self.bp_saved, self.bp_faced, baseline)

    def return_rate(self, *, baseline: float) -> float:
        return self._shrink(self.return_won, self.return_points, baseline)


class DetailEstimator:
    """Walk-forward accumulation of the decomposed serve record."""

    def __init__(self, *, lag_days: int = TOURNAMENT_LAG_DAYS) -> None:
        self._lag = dt.timedelta(days=lag_days)
        self._players: dict[tuple[str, PlayerKey], ServeProfile] = defaultdict(ServeProfile)
        self._tour: dict[str, ServeProfile] = defaultdict(ServeProfile)
        self._pending: list[SackmannMatch] = []
        self._cursor = 0
        self._absorbed_through: dt.date | None = None

    def queue(self, matches: Iterable[SackmannMatch]) -> None:
        for entry in matches:
            if entry.has_serve_stats and not entry.retired:
                self._pending.append(entry)
        self._pending.sort(key=lambda m: (m.tourney_date, m.tour, m.tourney_id,
                                          m.match_num))

    def advance_to(self, today: dt.date) -> int:
        cutoff = today - self._lag
        if self._absorbed_through is not None and cutoff < self._absorbed_through:
            raise ValueError(
                f"cannot advance backwards: absorbed through {self._absorbed_through}, "
                f"asked for {cutoff}")
        absorbed = 0
        while self._cursor < len(self._pending):
            entry = self._pending[self._cursor]
            if entry.tourney_date > cutoff:
                break
            self._absorb(entry)
            self._cursor += 1
            absorbed += 1
        self._absorbed_through = cutoff
        return absorbed

    def _absorb(self, entry: SackmannMatch) -> None:
        winner = sackmann_player_key(entry.winner_name)
        loser = sackmann_player_key(entry.loser_name)
        if winner is None or loser is None or winner == loser:
            return
        for key, own, opponent in ((winner, entry.winner_serve, entry.loser_serve),
                                   (loser, entry.loser_serve, entry.winner_serve)):
            if own.serve_points is None or own.first_in is None:
                continue
            if own.first_won is None or own.second_won is None:
                continue
            for target in (self._players[(entry.tour, key)], self._tour[entry.tour]):
                target.serve_points += own.serve_points
                target.first_in += own.first_in
                target.first_won += own.first_won
                target.second_won += own.second_won
                target.aces += own.aces or 0
                target.double_faults += own.double_faults or 0
                target.bp_saved += own.break_points_saved or 0
                target.bp_faced += own.break_points_faced or 0
                target.matches += 1
                # Return record is the mirror of the opponent's serve line.
                if opponent.serve_points is not None:
                    won = (opponent.first_won or 0) + (opponent.second_won or 0)
                    target.return_points += opponent.serve_points
                    target.return_won += opponent.serve_points - won

    def profile(self, tour: str, name: str) -> ServeProfile:
        key = td_player_key(name)
        if key is None:
            return ServeProfile()
        return self._players.get((tour, key), ServeProfile())

    def baselines(self, tour: str) -> "_Baselines":
        """Tour-wide rates, used as the shrinkage target for every player rate."""
        pool = self._tour.get(tour, ServeProfile())
        second = max(pool.serve_points - pool.first_in, 1)
        return _Baselines(
            first_serve=pool.first_in / pool.serve_points if pool.serve_points else 0.61,
            first_win=pool.first_won / pool.first_in if pool.first_in else 0.72,
            second_win=pool.second_won / second if pool.serve_points else 0.50,
            ace=pool.aces / pool.serve_points if pool.serve_points else 0.06,
            double_fault=(pool.double_faults / pool.serve_points
                          if pool.serve_points else 0.04),
            break_save=pool.bp_saved / pool.bp_faced if pool.bp_faced else 0.60,
            return_won=(pool.return_won / pool.return_points
                        if pool.return_points else 0.38),
        )


@dataclass(frozen=True)
class _Baselines:
    first_serve: float
    first_win: float
    second_win: float
    ace: float
    double_fault: float
    break_save: float
    return_won: float


#: Minimum service points behind both players before the layer contributes anything.
MIN_POINTS = 500

_NAMES = (
    "first_serve_rate_gap",
    "first_win_rate_gap",
    "second_win_rate_gap",
    "ace_rate_gap",
    "double_fault_rate_gap",
    "break_save_rate_gap",
    "return_rate_gap",
)


def serve_detail_features(
    estimator: DetailEstimator, tour: str, player_a: str, player_b: str,
) -> dict[str, float]:
    """Pairwise decomposed serve gaps, or ``{}`` when either record is too thin.

    Differences rather than levels, so the orientation is player A minus player B and the
    whole set flips sign when the players are swapped — the same convention as every other
    feature here, and the thing that makes a leaked outcome visible as an asymmetry.
    """
    a = estimator.profile(tour, player_a)
    b = estimator.profile(tour, player_b)
    if min(a.serve_points, b.serve_points) < MIN_POINTS:
        return {}
    base = estimator.baselines(tour)
    return {
        "first_serve_rate_gap": (a.first_serve_rate(baseline=base.first_serve)
                                 - b.first_serve_rate(baseline=base.first_serve)),
        "first_win_rate_gap": (a.first_win_rate(baseline=base.first_win)
                               - b.first_win_rate(baseline=base.first_win)),
        "second_win_rate_gap": (a.second_win_rate(baseline=base.second_win)
                                - b.second_win_rate(baseline=base.second_win)),
        "ace_rate_gap": (a.ace_rate(baseline=base.ace) - b.ace_rate(baseline=base.ace)),
        "double_fault_rate_gap": (a.double_fault_rate(baseline=base.double_fault)
                                  - b.double_fault_rate(baseline=base.double_fault)),
        "break_save_rate_gap": (a.break_point_save_rate(baseline=base.break_save)
                                - b.break_point_save_rate(baseline=base.break_save)),
        "return_rate_gap": (a.return_rate(baseline=base.return_won)
                            - b.return_rate(baseline=base.return_won)),
    }


serve_detail_features.NAMES = _NAMES  # type: ignore[attr-defined]
