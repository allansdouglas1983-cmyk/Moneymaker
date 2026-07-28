"""Common opponents and local intransitivity — the shape a scalar rating cannot hold.

An Elo rating is a point on a line, and a line is totally ordered: it can say A is stronger
than B, but it cannot represent A beating B, B beating C, and C beating A. That cycle is
real in tennis, because styles interact — a big server troubles a poor returner and is
troubled by a great one — and it is precisely where a rating-based price should be worst.

DR-TENNIS-FORECAST-LIT-001 returned this as the one genuinely new feature family with
published support. Clegg and Cartlidge (2025) report that bookmaker prices are weakest in
highly intransitive local neighbourhoods, with subset profitability under Bonferroni
control, while their own model still loses to the market overall. That is a claim about
*where* a residual might live, not a claim that the market is beatable in general — which
is exactly the sort of narrowly-scoped lead this project can test cheaply.

Two quantities, both from matches strictly before the priced one under the same eight-day
tournament lag used everywhere else in the package.

**``common_opponent_gap``** — over the opponents *both* players have faced, how much better
A did than B against those same people, shrunk toward even and expressed as a log-odds so it
shares a scale with the market logit it corrects. Restricting to the shared sub-graph is the
whole point: two players can earn identical ratings against disjoint fields, and this is the
estimate that notices.

**``intransitivity``** — how much those shared opponents disagree about who is stronger.
Near zero when every one of them points the same way, which is a hierarchy the rating
already represents; large when they contradict each other, which is a cycle it cannot. It
carries no direction and is symmetric under a swap, unlike the gap.

**Absence is absence.** Fewer than :data:`MIN_COMMON_OPPONENTS` shared opponents emits no
feature at all rather than a zero: zero asserts the pair is even, which is a claim, and a
pair with no shared history supports no claim.
"""
from __future__ import annotations

import datetime as dt
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from tennis_edge.sackmann import SackmannMatch

__all__ = [
    "TOURNAMENT_LAG_DAYS",
    "MIN_COMMON_OPPONENTS",
    "COMMON_PRIOR",
    "COMMON_COUNT_PRIOR",
    "NetworkEstimator",
    "network_features",
]

#: The archive dates a match by the Monday of its week, so a tournament's later rounds would
#: otherwise inform its own earlier ones. Same constant as the rest of the package.
TOURNAMENT_LAG_DAYS = 8

#: Below this, the shared sub-graph is too small to say anything and no feature is emitted.
#: Two is the minimum at which opponents can disagree at all — with one, intransitivity is
#: identically zero and would be a constant masquerading as a measurement.
MIN_COMMON_OPPONENTS = 2

#: Beta-prior strength for the per-opponent win rate. Shrinks a 1-0 record toward even
#: without erasing a 5-0 one, and keeps a perfect sweep off the infinite logit.
COMMON_PRIOR = 2.0

#: Shrinkage on the NUMBER of shared opponents, which is a different question from the
#: number of matches against each. Two opponents agreeing and five agreeing are not equally
#: strong evidence, and a bare mean cannot tell them apart — it is scale-free in the count
#: by construction. Without this the feature hands the ridge fit a two-opponent estimate and
#: a five-opponent estimate as though they were equally trustworthy.
COMMON_COUNT_PRIOR = 2.0


@dataclass
class _Record:
    """One player's results against each opponent: opponent -> [wins, losses]."""

    versus: dict[str, list[int]] = field(default_factory=lambda: defaultdict(
        lambda: [0, 0]))


class NetworkEstimator:
    """Walk-forward accumulation of the per-tour result graph."""

    def __init__(self, *, lag_days: int = TOURNAMENT_LAG_DAYS) -> None:
        self._lag = dt.timedelta(days=lag_days)
        self._players: dict[tuple[str, str], _Record] = defaultdict(_Record)
        self._pending: list[SackmannMatch] = []
        self._cursor = 0
        self._absorbed_through: dt.date | None = None

    def queue(self, matches: Iterable[SackmannMatch]) -> None:
        self._pending.extend(matches)
        self._pending.sort(key=lambda m: (m.tourney_date, m.tour, m.tourney_id,
                                          m.match_num))

    def advance_to(self, today: dt.date) -> int:
        """Absorb every match whose week is at least ``lag_days`` before ``today``."""
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
            winner = self._players[(entry.tour, entry.winner_name)]
            loser = self._players[(entry.tour, entry.loser_name)]
            winner.versus[entry.loser_name][0] += 1
            loser.versus[entry.winner_name][1] += 1
            self._cursor += 1
            absorbed += 1
        self._absorbed_through = cutoff
        return absorbed

    def record(self, tour: str, player: str) -> _Record:
        return self._players[(tour, player)]


def _rate(wins: int, losses: int) -> float:
    """Shrunk win rate against one opponent. Never 0 or 1, so the logit stays finite."""
    return (wins + 0.5 * COMMON_PRIOR) / (wins + losses + COMMON_PRIOR)


def network_features(
    estimator: NetworkEstimator, tour: str, player_a: str, player_b: str, *,
    when: dt.date,
) -> dict[str, float]:
    """Shared-opponent gap and local intransitivity, oriented player A minus player B.

    ``when`` is accepted for signature symmetry with the other feature builders and to make
    the knowledge-time contract explicit at every call site; the estimator's own cursor is
    what actually bounds visibility, so passing a later date never reveals more than
    :meth:`NetworkEstimator.advance_to` has absorbed.
    """
    a = estimator.record(tour, player_a)
    b = estimator.record(tour, player_b)
    shared = sorted((set(a.versus) & set(b.versus)) - {player_a, player_b})
    if len(shared) < MIN_COMMON_OPPONENTS:
        return {}

    # Per shared opponent, how much better A did than B against that same person, in
    # log-odds. Positive means A handled the common opponent better.
    verdicts: list[float] = []
    for opponent in shared:
        rate_a = _rate(*a.versus[opponent])
        rate_b = _rate(*b.versus[opponent])
        verdicts.append(math.log(rate_a / (1.0 - rate_a))
                        - math.log(rate_b / (1.0 - rate_b)))

    # Mean verdict, then shrunk toward zero by how many opponents produced it. Monotone
    # increasing in the count, so more agreement is a stronger signal rather than the same
    # one.
    mean_verdict = math.fsum(verdicts) / len(verdicts)
    confidence = len(verdicts) / (len(verdicts) + COMMON_COUNT_PRIOR)
    gap = mean_verdict * confidence

    # Disagreement among those verdicts, normalised so it is a share rather than a scale.
    # 0 when every opponent points the same way; ->1 when they cancel exactly. Using the
    # mean absolute verdict as the denominator keeps it comparable across pairs whose
    # opponents were merely emphatic rather than contradictory.
    # Compared against the UNSHRUNK mean: intransitivity asks whether the opponents agree,
    # which is a property of the verdicts themselves and must not move with the count.
    spread = math.fsum(abs(v) for v in verdicts) / len(verdicts)
    intransitivity = 0.0 if spread == 0.0 else 1.0 - abs(mean_verdict) / spread

    return {
        "common_opponent_gap": gap,
        "intransitivity": intransitivity,
        "common_opponents": float(len(shared)),
    }
