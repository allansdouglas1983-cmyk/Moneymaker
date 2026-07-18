"""F3 — Surface-conditional Elo, one governed implementation behind the StageOneFamily
seam (registration: specs/programme/f3-surface-elo-registration-v1.yaml).

Dual-rating design. Each competitor carries a GLOBAL rating (updated on every match,
K_global) and, per surface, a SURFACE rating that is:
  * initialised, at the player's first appearance on that surface, to their CURRENT
    global rating (cold-start SHRINKAGE toward global — not an independent 1500 prior);
  * thereafter updated independently on that surface (K_surface).

Prediction on surface s uses the two surface ratings; on an UNKNOWN surface (code 0:
blank/Greenset/unrecognised) F3 falls back to the GLOBAL rating prediction, so F3 emits a
prediction for EVERY eligible match — keeping the paired F2/F3 comparison aligned on the
same match set (no F3-only exclusions to bias the pairing).

Same-day BATCH update (frozen ordering invariant): all matches on a UTC date are
expected-scored against START-of-date global AND surface ratings, then all deltas apply
together — row-permutation invariant. Surface arrives as a declared per-choice-set
feature `surface` (Decimal code, replicated on both runners; SAFE_FOR_F3 per the field
registry). Registered equation is F2's logistic; no odds, no June, no names reachable.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Mapping, Sequence

from sport_core.clustering import ChronologyKey

from l4_pricing.stage_one import StageOneFitRefusal
from sport_tennis.elo_family import ELO_INITIAL_RATING, elo_win_probability

if TYPE_CHECKING:
    from l4_pricing.horizon import HorizonLabel
    from l4_pricing.races import FeatureSchema, Race

__all__ = ["SURFACE_CODES", "SurfaceEloFamily"]

SURFACE_CODES = {"Hard": 1, "Clay": 2, "Grass": 3, "Carpet": 4}  # 0 => UNKNOWN -> global
_UNKNOWN = 0


def _surface_code(race: "Race") -> int:
    codes = {int(r.features["surface"]) for r in race.runners if "surface" in r.features}
    if len(codes) != 1:
        raise StageOneFitRefusal(
            f"race {race.race_id!r}: surface feature must be a single match-level code, got {codes}"
        )
    return codes.pop()


@dataclass(frozen=True)
class _FittedSurfaceElo:
    global_ratings: Mapping[int, float]
    surface_ratings: Mapping[tuple[int, int], float]  # (competitor, surface_code) -> rating


class SurfaceEloFamily:
    """StageOneFamily-conformant surface Elo (duck-typed against the seam)."""

    def __init__(self, *, k_global: float, k_surface: float) -> None:
        if not (k_global > 0 and k_surface > 0):
            raise ValueError(f"k_global/k_surface must be positive, got {k_global!r}/{k_surface!r}")
        self._kg = k_global
        self._ks = k_surface

    @property
    def family_id(self) -> str:
        return f"surface-elo-v1-kg{self._kg:g}-ks{self._ks:g}"

    def _surf_rating(self, surf: dict[tuple[int, int], float], glob: dict[int, float], cid: int, code: int) -> float:
        # cold-start shrinkage: first appearance on a surface seeds from CURRENT global
        return surf.get((cid, code), glob.get(cid, ELO_INITIAL_RATING))

    def fit(
        self,
        races: "Sequence[Race]",
        _schema: "FeatureSchema",
        *,
        horizon: "HorizonLabel",  # noqa: ARG002  # pylint: disable=unused-argument
        max_iter: int,  # noqa: ARG002  # pylint: disable=unused-argument
    ) -> _FittedSurfaceElo:
        glob: dict[int, float] = {}
        surf: dict[tuple[int, int], float] = {}
        by_day: defaultdict[ChronologyKey, list["Race"]] = defaultdict(list)
        for race in races:
            by_day[race.cluster.chronology].append(race)
        for day in sorted(by_day):
            dg: dict[int, float] = defaultdict(float)
            ds: dict[tuple[int, int], float] = defaultdict(float)
            seed: dict[tuple[int, int], float] = {}
            for race in sorted(by_day[day], key=lambda r: r.race_id):
                active = [r.runner_id for r in race.runners if not r.non_runner]
                if len(active) != 2:
                    raise StageOneFitRefusal(f"surface Elo is two-player; race {race.race_id!r} has {len(active)}")
                if race.winner_id is None:
                    raise StageOneFitRefusal(f"unlabelled race {race.race_id!r} in a training window")
                code = _surface_code(race)
                a, b = sorted(active)
                # global update (all matches)
                rga = glob.get(a, ELO_INITIAL_RATING)
                rgb = glob.get(b, ELO_INITIAL_RATING)
                pga = elo_win_probability(rga, rgb)
                sa = 1.0 if race.winner_id == a else 0.0
                dg[a] += self._kg * (sa - pga)
                dg[b] += self._kg * ((1.0 - sa) - (1.0 - pga))
                # surface update (known surface only; seeds captured at start-of-day)
                if code != _UNKNOWN:
                    for cid in (a, b):
                        if (cid, code) not in surf and (cid, code) not in seed:
                            seed[(cid, code)] = glob.get(cid, ELO_INITIAL_RATING)
                    rsa = self._surf_rating(surf, glob, a, code) if (a, code) in surf else seed[(a, code)]
                    rsb = self._surf_rating(surf, glob, b, code) if (b, code) in surf else seed[(b, code)]
                    psa = elo_win_probability(rsa, rsb)
                    ds[(a, code)] += self._ks * (sa - psa)
                    ds[(b, code)] += self._ks * ((1.0 - sa) - (1.0 - psa))
            for cid, d in dg.items():
                glob[cid] = glob.get(cid, ELO_INITIAL_RATING) + d
            for key, base in seed.items():
                surf.setdefault(key, base)
            for key, d in ds.items():
                surf[key] = surf.get(key, ELO_INITIAL_RATING) + d
        return _FittedSurfaceElo(global_ratings=dict(glob), surface_ratings=dict(surf))

    def predict(
        self, model: object, race: "Race", *, horizon: "HorizonLabel"  # noqa: ARG002  # pylint: disable=unused-argument
    ) -> Mapping[int, float]:
        if not isinstance(model, _FittedSurfaceElo):
            raise TypeError(f"SurfaceEloFamily.predict needs its own fitted artefact, got {type(model).__name__}")
        active = sorted(r.runner_id for r in race.runners if not r.non_runner)
        if len(active) != 2:
            raise ValueError(f"surface Elo predicts two-player choice sets only; got {len(active)}")
        a, b = active
        code = _surface_code(race)
        g = dict(model.global_ratings)
        if code == _UNKNOWN:
            ra, rb = g.get(a, ELO_INITIAL_RATING), g.get(b, ELO_INITIAL_RATING)
        else:
            ra = model.surface_ratings.get((a, code), g.get(a, ELO_INITIAL_RATING))
            rb = model.surface_ratings.get((b, code), g.get(b, ELO_INITIAL_RATING))
        pa = elo_win_probability(ra, rb)
        return {a: pa, b: 1.0 - pa}
