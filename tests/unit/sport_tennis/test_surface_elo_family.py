"""F3 surface Elo family (registration: f3-surface-elo-registration-v1.yaml).

Surface-conditional dual-rating Elo behind the SAME StageOneFamily seam as F2. Surface
arrives as a declared per-choice-set feature (`surface` code, replicated on both runners:
1=Hard 2=Clay 3=Grass 4=Carpet 0=Unknown). Per-surface rating is seeded from the
player's current global rating at first appearance (cold-start shrinkage), then updated
independently on that surface. Unknown surface falls back to the global-rating prediction
(keeps the paired F2/F3 comparison aligned on every eligible match). No odds, no June,
no names. Synthetic corpora only — NO confirmatory F3-vs-F2 scoring here."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from l4_pricing.horizon import HorizonLabel
from l4_pricing.races import FeatureSchema, Race, RunnerRow
from l4_pricing.stage_one import StageOneFamily
from sport_core.clustering import calendar_day_assignment
from sport_tennis.surface_elo_family import SURFACE_CODES, SurfaceEloFamily

pytestmark = [pytest.mark.spec("SPEC-030"), pytest.mark.spec("SPEC-031")]

SCHEMA = FeatureSchema(names=("surface",))
H = HorizonLabel("T-5m")


def m(rid: str, day: date, a: int, b: int, winner: int, surface: str) -> Race:
    f = {"surface": Decimal(SURFACE_CODES.get(surface, 0))}
    return Race(
        race_id=rid,
        cluster=calendar_day_assignment("tennis", day),
        runners=(RunnerRow(runner_id=a, features=f), RunnerRow(runner_id=b, features=f)),
        winner_id=winner,
    )


def test_seam_conformance_and_equal_start_is_half() -> None:
    fam = SurfaceEloFamily(k_global=24.0, k_surface=24.0)
    assert isinstance(fam, StageOneFamily)
    model = fam.fit([], SCHEMA, horizon=H, max_iter=1)
    p = fam.predict(model, m("x", date(2024, 1, 1), 1, 2, 1, "Clay"), horizon=H)
    assert p == {1: 0.5, 2: 0.5}  # both unseen on clay -> seeded from equal globals


def test_surface_conditioning_beats_global_where_ability_is_surface_specific() -> None:
    # player 1 wins all CLAY vs 2; player 2 wins all GRASS vs 1. A global model washes to
    # ~0.5 on both surfaces; a surface model separates.
    races = []
    for i in range(12):
        d = date(2023, 1, 1 + i)
        races.append(m(f"c{i}", d, 1, 2, 1, "Clay"))
        races.append(m(f"g{i}", d, 1, 2, 2, "Grass"))
    fam = SurfaceEloFamily(k_global=24.0, k_surface=32.0)
    model = fam.fit(races, SCHEMA, horizon=H, max_iter=1)
    p_clay = fam.predict(model, m("qc", date(2023, 2, 1), 1, 2, 1, "Clay"), horizon=H)
    p_grass = fam.predict(model, m("qg", date(2023, 2, 1), 1, 2, 1, "Grass"), horizon=H)
    assert p_clay[1] > 0.6  # 1 favoured on clay
    assert p_grass[1] < 0.4  # 1 unfavoured on grass
    # the global-only view (unknown surface -> global fallback) is ~even
    p_unknown = fam.predict(model, m("qu", date(2023, 2, 1), 1, 2, 1, "UnknownXYZ"), horizon=H)
    assert abs(p_unknown[1] - 0.5) < 0.1


def test_unknown_surface_uses_global_fallback_prediction() -> None:
    races = [m(f"h{i}", date(2023, 1, 1 + i), 1, 2, 1, "Hard") for i in range(10)]
    fam = SurfaceEloFamily(k_global=32.0, k_surface=32.0)
    model = fam.fit(races, SCHEMA, horizon=H, max_iter=1)
    # 1 is strong globally (won hard matches); on an UNKNOWN surface F3 must fall back to
    # the global rating, so 1 is still favoured (not reset to 0.5).
    p = fam.predict(model, m("q", date(2023, 2, 1), 1, 2, 1, "Greenset"), horizon=H)
    assert p[1] > 0.6


def test_same_day_row_permutation_invariant() -> None:
    d1 = date(2024, 3, 1)
    day = [m("a", d1, 1, 2, 1, "Clay"), m("b", d1, 1, 3, 1, "Clay"), m("c", d1, 4, 5, 5, "Grass")]
    probe = m("p", date(2024, 3, 2), 1, 4, 1, "Clay")
    fam = SurfaceEloFamily(k_global=24.0, k_surface=24.0)
    outs = [fam.predict(fam.fit(order, SCHEMA, horizon=H, max_iter=1), probe, horizon=H)
            for order in (day, day[::-1], [day[2], day[0], day[1]])]
    assert outs[0] == outs[1] == outs[2]


def test_deterministic_reruns() -> None:
    races = [m(f"r{i}", date(2023, 1, 1 + i), 1, 2, 1 + i % 2, "Clay") for i in range(8)]
    fam = SurfaceEloFamily(k_global=24.0, k_surface=32.0)
    a = fam.fit(races, SCHEMA, horizon=H, max_iter=1)
    b = fam.fit(races, SCHEMA, horizon=H, max_iter=1)
    q = m("q", date(2023, 3, 1), 1, 2, 1, "Clay")
    assert fam.predict(a, q, horizon=H) == fam.predict(b, q, horizon=H)


def test_surface_codes_are_the_registered_set() -> None:
    assert SURFACE_CODES == {"Hard": 1, "Clay": 2, "Grass": 3, "Carpet": 4}
