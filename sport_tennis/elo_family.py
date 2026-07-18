"""F2 — Global Elo, one governed implementation behind the StageOneFamily seam
(registration: specs/programme/f2-global-elo-registration-v1.yaml).

Registered equation:  P(a beats b) = 1 / (1 + 10 ** ((R_b - R_a) / 400))
Scale: initial rating 1500.0, logistic base 10, divisor 400. Cold start: every unseen
competitor enters at the initial rating (governed prior; NO minimum-prior-match
exclusion — founder §5). Update rule: same-day BATCH — all matches on a calendar date
are expected-scored against START-of-date ratings, then all deltas apply together, so
results are invariant to row permutation within a date and a day's outcome can never
inform a same-day prediction. K is a registered constant per model instance (the grid
and selection rule live in the registration, never here).

The family sees only Race objects: integer runner ids (governed competitor indices),
UTC-day chronology, winner label. No name, no odds, no surface, no June data can reach
it through this interface. Deterministic: iteration is sorted by (chronology, race_id);
ties in rating give exactly 0.5.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Mapping, Sequence

from sport_core.clustering import ChronologyKey

from l4_pricing.stage_one import StageOneFitRefusal

if TYPE_CHECKING:
    from l4_pricing.horizon import HorizonLabel
    from l4_pricing.races import FeatureSchema, Race

__all__ = ["ELO_INITIAL_RATING", "elo_win_probability", "GlobalEloFamily"]

ELO_INITIAL_RATING = 1500.0


def elo_win_probability(rating_a: float, rating_b: float) -> float:
    """The registered equation. Equal ratings give exactly 0.5."""
    if rating_a == rating_b:
        return 0.5
    return float(1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0)))


@dataclass(frozen=True)
class _FittedElo:
    """Opaque fitted artefact: final ratings map. Carries NO training metadata —
    provenance is the orchestrator's bookkeeping, never the family's."""

    ratings: Mapping[int, float]
    k_factor: float


class GlobalEloFamily:
    """StageOneFamily-conformant global Elo (duck-typed against the seam)."""

    def __init__(self, *, k_factor: float) -> None:
        if not (k_factor > 0):
            raise ValueError(f"k_factor must be positive, got {k_factor!r}")
        self._k = k_factor

    @property
    def family_id(self) -> str:
        return f"global-elo-v1-k{self._k:g}"

    def fit(
        self,
        races: "Sequence[Race]",
        _schema: "FeatureSchema",
        *,
        horizon: "HorizonLabel",  # noqa: ARG002  # pylint: disable=unused-argument
        max_iter: int,  # noqa: ARG002  # pylint: disable=unused-argument
    ) -> _FittedElo:
        ratings: dict[int, float] = {}
        by_day: defaultdict[ChronologyKey, list["Race"]] = defaultdict(list)
        for race in races:
            by_day[race.cluster.chronology].append(race)
        for day in sorted(by_day):
            deltas: dict[int, float] = defaultdict(float)
            for race in sorted(by_day[day], key=lambda r: r.race_id):
                active = [r.runner_id for r in race.runners if not r.non_runner]
                if len(active) != 2:
                    raise StageOneFitRefusal(
                        f"global Elo is a two-player family; race {race.race_id!r} has {len(active)} active"
                    )
                if race.winner_id is None:
                    raise StageOneFitRefusal(
                        f"unlabelled race {race.race_id!r} in an Elo training window — the label "
                        "policy excludes it upstream; reaching here is a defect, not a default"
                    )
                a, b = sorted(active)
                ra = ratings.get(a, ELO_INITIAL_RATING)
                rb = ratings.get(b, ELO_INITIAL_RATING)
                pa = elo_win_probability(ra, rb)
                score_a = 1.0 if race.winner_id == a else 0.0
                deltas[a] += self._k * (score_a - pa)
                deltas[b] += self._k * ((1.0 - score_a) - (1.0 - pa))
            for rid, d in deltas.items():
                ratings[rid] = ratings.get(rid, ELO_INITIAL_RATING) + d
        return _FittedElo(ratings=dict(ratings), k_factor=self._k)

    def predict(
        self, model: object, race: "Race", *, horizon: "HorizonLabel"  # noqa: ARG002  # pylint: disable=unused-argument
    ) -> Mapping[int, float]:
        if not isinstance(model, _FittedElo):
            raise TypeError(f"GlobalEloFamily.predict needs its own fitted artefact, got {type(model).__name__}")
        active = [r.runner_id for r in race.runners if not r.non_runner]
        if len(active) != 2:
            raise ValueError(f"global Elo predicts two-player choice sets only; got {len(active)}")
        a, b = sorted(active)
        pa = elo_win_probability(
            model.ratings.get(a, ELO_INITIAL_RATING), model.ratings.get(b, ELO_INITIAL_RATING)
        )
        return {a: pa, b: 1.0 - pa}
