"""Head-to-head, retirement risk, and workload — three things the ratings cannot see.

An Elo rating is a scalar summary of who a player beats. It is very good at that and blind
to three things that a market prices and a scalar cannot hold.

**Head-to-head is not implied by the ratings.** Two players with identical Elo can have a
7-1 record against each other, because styles interact: a big server against a poor returner
is a different match from the same server against the best returner on tour. The rating
averages that away by construction. The field on the state snapshot has existed since the
first build and has never been populated.

**A retirement is a settled market.** The corpus drops them — 3,641 matches — and every fit
so far has been conditioned on "the match was completed", which is not the event Betfair
pays out on. A player who retires mid-match loses for settlement purposes, so a player who
retires often is worth less than his rating says. Modelling the *rate* is the point; nobody
can predict a specific retirement.

**Workload accumulates and ratings do not decay it.** Minutes on court over the last
fortnight, five-setters survived, and a surface switch since the last event are all
observable before the off and none of them move an Elo number.

Every quantity here is computed from matches strictly before the one being priced, with the
same eight-day tournament-week lag used everywhere else in this package: the archive dates a
match by the Monday of its week, so without the lag a tournament's later rounds would inform
its own earlier ones.

**Absence is reported as absence.** A player with no prior meeting has no head-to-head
feature — not a zero, which would claim the pair is even. That distinction is the same one
the rest of the feature set makes and it is why a debutant does not land in the middle of
every distribution.
"""
from __future__ import annotations

import datetime as dt
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Iterable

from tennis_edge.sackmann import SackmannMatch
from tennis_edge.serve_stats import PlayerKey, sackmann_player_key, td_player_key

__all__ = [
    "DurabilityEstimator",
    "MIN_H2H_MEETINGS",
    "TOURNAMENT_LAG_DAYS",
    "durability_features",
]

#: Same lag as the rating and serve estimators. A tournament moves as one block.
TOURNAMENT_LAG_DAYS = 8

#: Below this the pairwise record is noise wearing a ratio. Two meetings decided by a
#: retirement and a walkover say nothing about the third.
MIN_H2H_MEETINGS = 2

#: Pseudo-meetings of "even" mixed into the head-to-head rate. At the minimum of two real
#: meetings this pulls a 2-0 to 0.6 rather than 1.0, which is the honest reading of two
#: matches.
H2H_PRIOR = 3.0

#: Prior matches mixed into a retirement rate. Retirements are rare — roughly 3% of matches
#: — so a player with twenty matches and one retirement is not a 5% retirement risk.
RETIREMENT_PRIOR = 60.0

#: How far back workload is accumulated. Two weeks is the span over which a hard tournament
#: is still in the legs; beyond a month it is training, not fatigue.
WORKLOAD_DAYS = 14
LONG_WORKLOAD_DAYS = 28

#: A match this long is a different kind of workload from an hour's work.
LONG_MATCH_MINUTES = 180


@dataclass
class PlayerRecord:
    """One player's accumulated durability history."""

    matches: int = 0
    retirements: int = 0
    #: (date, minutes, went_long) per match, most recent last. Bounded by the pruning in
    #: :meth:`DurabilityEstimator._absorb`, so this does not grow without limit.
    recent: deque[tuple[dt.date, int, bool]] = field(default_factory=deque)
    last_surface: str = ""
    last_played: dt.date | None = None

    def retirement_rate(self, *, baseline: float) -> float:
        """Share of matches ending in retirement, shrunk toward the tour baseline."""
        weight = self.matches / (self.matches + RETIREMENT_PRIOR)
        if self.matches <= 0:
            return baseline
        return baseline + weight * (self.retirements / self.matches - baseline)

    def minutes_within(self, when: dt.date, days: int) -> int:
        cutoff = when - dt.timedelta(days=days)
        return sum(m for date, m, _long in self.recent if date >= cutoff)

    def long_matches_within(self, when: dt.date, days: int) -> int:
        cutoff = when - dt.timedelta(days=days)
        return sum(1 for date, _m, went_long in self.recent if date >= cutoff and went_long)


class DurabilityEstimator:
    """Walk-forward accumulation of head-to-head, retirement and workload history."""

    def __init__(self, *, lag_days: int = TOURNAMENT_LAG_DAYS) -> None:
        self._lag = dt.timedelta(days=lag_days)
        self._players: dict[tuple[str, PlayerKey], PlayerRecord] = defaultdict(PlayerRecord)
        #: (tour, first, second) -> [wins by first, wins by second], names sorted so the
        #: pair has one key regardless of which side is being priced.
        self._h2h: dict[tuple[str, PlayerKey, PlayerKey], list[int]] = defaultdict(
            lambda: [0, 0])
        self._tour_matches: dict[str, int] = defaultdict(int)
        self._tour_retirements: dict[str, int] = defaultdict(int)
        self._pending: list[SackmannMatch] = []
        self._cursor = 0
        self._absorbed_through: dt.date | None = None

    def queue(self, matches: Iterable[SackmannMatch]) -> None:
        """Take every match, retirements included — they are the point of this layer."""
        self._pending.extend(matches)
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

        retired = entry.retired
        self._tour_matches[entry.tour] += 1
        if retired:
            self._tour_retirements[entry.tour] += 1

        minutes = entry.minutes or 0
        went_long = minutes >= LONG_MATCH_MINUTES
        cutoff = entry.tourney_date - dt.timedelta(days=LONG_WORKLOAD_DAYS)
        for key in (winner, loser):
            record = self._players[(entry.tour, key)]
            record.matches += 1
            # Only the loser is credited with the retirement: the score string marks the
            # match, and in this archive the player who retires is always the loser.
            if retired and key == loser:
                record.retirements += 1
            record.recent.append((entry.tourney_date, minutes, went_long))
            while record.recent and record.recent[0][0] < cutoff:
                record.recent.popleft()
            record.last_surface = entry.surface
            record.last_played = entry.tourney_date

        first, second = sorted((winner, loser))
        pair = self._h2h[(entry.tour, first, second)]
        # A walkover was never played and says nothing about the matchup; a retirement was.
        if "W/O" not in entry.score.upper():
            pair[0 if winner == first else 1] += 1

    def record(self, tour: str, name: str) -> PlayerRecord:
        key = td_player_key(name)
        if key is None:
            return PlayerRecord()
        return self._players.get((tour, key), PlayerRecord())

    def head_to_head(self, tour: str, player_a: str, player_b: str) -> tuple[int, int] | None:
        """Wins by A and by B, or ``None`` when they have never met often enough."""
        key_a, key_b = td_player_key(player_a), td_player_key(player_b)
        if key_a is None or key_b is None or key_a == key_b:
            return None
        first, second = sorted((key_a, key_b))
        pair = self._h2h.get((tour, first, second))
        if pair is None or sum(pair) < MIN_H2H_MEETINGS:
            return None
        return (pair[0], pair[1]) if key_a == first else (pair[1], pair[0])

    def retirement_baseline(self, tour: str) -> float:
        played = self._tour_matches.get(tour, 0)
        if played <= 0:
            return 0.03
        return self._tour_retirements.get(tour, 0) / played


_NAMES = (
    "h2h_gap",
    "retirement_risk_gap",
    "workload_minutes_gap",
    "workload_long_gap",
    "surface_switch_gap",
)


def durability_features(
    estimator: DurabilityEstimator, tour: str, player_a: str, player_b: str, *,
    surface: str, when: dt.date,
) -> dict[str, float]:
    """Pairwise durability gaps, oriented player A minus player B.

    Differences rather than levels, so the whole set flips sign when the players are swapped
    — the same convention as every other feature here, and the thing that makes a leaked
    outcome visible as an asymmetry.

    ``h2h_gap`` is absent when the pair has not met enough times. The others are always
    available: "no matches in the last fortnight" is a real observation about a player, not
    a missing one, and zero is its correct encoding.
    """
    a = estimator.record(tour, player_a)
    b = estimator.record(tour, player_b)
    baseline = estimator.retirement_baseline(tour)

    features: dict[str, float] = {
        # Retirement risk is a probability difference; the sign says which player is likelier
        # to hand the market a settled loss without being beaten.
        "retirement_risk_gap": (a.retirement_rate(baseline=baseline)
                                - b.retirement_rate(baseline=baseline)),
        # Hours, not minutes: minutes put this feature two orders of magnitude away from
        # every other column and would make the ridge penalty mean something different for it.
        "workload_minutes_gap": (a.minutes_within(when, WORKLOAD_DAYS)
                                 - b.minutes_within(when, WORKLOAD_DAYS)) / 60.0,
        "workload_long_gap": float(a.long_matches_within(when, LONG_WORKLOAD_DAYS)
                                   - b.long_matches_within(when, LONG_WORKLOAD_DAYS)),
        "surface_switch_gap": float(_switched(a, surface) - _switched(b, surface)),
    }

    meetings = estimator.head_to_head(tour, player_a, player_b)
    if meetings is not None:
        wins_a, wins_b = meetings
        total = wins_a + wins_b
        # Shrunk toward even, then expressed as a log-odds so it lives on the same scale as
        # the market logit the model is correcting.
        rate = (wins_a + 0.5 * H2H_PRIOR) / (total + H2H_PRIOR)
        features["h2h_gap"] = math.log(rate / (1.0 - rate))
    return features


def _switched(record: PlayerRecord, surface: str) -> int:
    """1 when this player's last match was on a different surface, else 0.

    A player arriving from clay onto grass has had no competitive match on the surface; the
    surface Elo knows their history there but not that they have just changed.
    """
    if not record.last_surface or not surface:
        return 0
    return int(record.last_surface != surface)


durability_features.NAMES = _NAMES  # type: ignore[attr-defined]
