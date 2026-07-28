"""Emit golden vectors: the Python's answers, for the TypeScript to be held against.

The scoring maths exists twice in this deployment — once in Python, where it was measured,
and once in TypeScript, where it runs in the request path. That duplication is the most
dangerous thing in the system. A divergence would not crash; it would quietly produce
numbers no measurement ever validated, wearing the confidence interval of numbers that were.

So the port is never trusted. This writes what the Python actually computes for a spread of
inputs, and ``scoring.test.ts`` replays every one. Disagreement beyond 1e-12 fails CI.

**The cases are chosen to hit the branches, not to look representative.** Feature sets that
are complete, missing serve coverage, missing pyramid coverage, and empty; prices from heavy
odds-on to long odds-against; both match formats; both surfaces with and without a specific
rating; and every rank source (caller-supplied, snapshot fallback, the imputed 500 for one
side and for both). A port can agree on the common path and be
wrong on the branch that matters — a debutant, a missing rating, an extreme price — and those
are exactly the fixtures a person is most likely to be looking at.

**Feature insertion order is carried in the vector.** ``math.fsum`` is order-sensitive in its
final bits and the TypeScript reproduces the compensated sum, so the order the Python built
the dict in is part of the expected answer, not an incidental detail.
"""
from __future__ import annotations

import datetime as dt
import json
import random
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tennis_edge.display_band import band_spread, edge_band  # noqa: E402
from tennis_edge.live_state import PlayerState, StateSnapshot, live_features  # noqa: E402
from tennis_edge.policy_v2 import MIN_EDGE, WATCH_EDGE  # noqa: E402
from tennis_edge.residual_model import load_model  # noqa: E402
from tennis_edge.today import TipStatus, _reasons  # noqa: E402
from tennis_edge.upcoming import Fixture, price_fixture  # noqa: E402

#: Enough to cover every branch several times over without making the vector file unwieldy.
CASES = 500

SURFACES = ("Hard", "Clay", "Grass")
TOURS = ("ATP", "WTA")


def _player(rng: random.Random, *, thin: bool, no_serve: bool,
            no_pyramid: bool, rank: int | None = None) -> PlayerState:
    """One synthetic player, with the coverage switches the branches key off."""
    elo = rng.uniform(1300.0, 2200.0)
    surfaces = {s: elo + rng.uniform(-120.0, 120.0) for s in SURFACES}
    # A deliberately absent surface exercises the fallback-to-overall path.
    if rng.random() < 0.2:
        surfaces.pop(rng.choice(SURFACES))
    pyramid = elo + rng.uniform(-150.0, 150.0)
    return PlayerState(
        elo=elo,
        weighted_elo=elo + rng.uniform(-60.0, 60.0),
        surface_elo=surfaces,
        matches=rng.randint(0, 4) if thin else rng.randint(5, 900),
        last_played=(dt.date(2026, 7, 1) - dt.timedelta(days=rng.randint(0, 400))
                     ).isoformat(),
        serve_rate=rng.uniform(0.52, 0.74),
        return_rate=rng.uniform(0.28, 0.46),
        serve_points=rng.uniform(0.0, 299.0) if no_serve else rng.uniform(300.0, 40000.0),
        serve_matches=rng.randint(0, 400),
        pyramid_elo=pyramid,
        pyramid_surface_elo={s: pyramid + rng.uniform(-100.0, 100.0) for s in SURFACES},
        pyramid_matches=rng.randint(0, 4) if no_pyramid else rng.randint(5, 1200),
        pyramid_tour_share=rng.uniform(0.0, 1.0),
        pyramid_last_played=(dt.date(2026, 7, 1) - dt.timedelta(days=rng.randint(0, 500))
                             ).isoformat(),
        pyramid_recent_14d=rng.randint(0, 6),
        # The decomposed serve/return layer, already shrunk. Dropped entirely for a share of
        # players so the "layer absent for this pair" branch is exercised.
        serve_detail={} if no_serve else {
            "first_serve_rate": rng.uniform(0.55, 0.72),
            "first_win_rate": rng.uniform(0.62, 0.82),
            "second_win_rate": rng.uniform(0.40, 0.62),
            "ace_rate": rng.uniform(0.01, 0.18),
            "double_fault_rate": rng.uniform(0.01, 0.09),
            "break_save_rate": rng.uniform(0.45, 0.75),
            "return_rate": rng.uniform(0.28, 0.48),
        },
        retirement_rate=rng.uniform(0.0, 0.12),
        workload_minutes_14d=float(rng.choice([0, 0, 95, 180, 320, 540])),
        workload_long_28d=rng.randint(0, 3),
        last_surface=rng.choice(("Hard", "Clay", "Grass", "")),
        rank=rank,
        rank_date=None if rank is None else (
            dt.date(2026, 7, 1) - dt.timedelta(days=rng.randint(0, 90))).isoformat(),
    )


def _payload(state: PlayerState) -> dict[str, Any]:
    return {
        "elo": state.elo, "weighted_elo": state.weighted_elo,
        "surface_elo": dict(state.surface_elo), "matches": state.matches,
        "last_played": state.last_played, "serve_rate": state.serve_rate,
        "return_rate": state.return_rate, "serve_points": state.serve_points,
        "serve_matches": state.serve_matches, "pyramid_elo": state.pyramid_elo,
        "pyramid_surface_elo": dict(state.pyramid_surface_elo),
        "pyramid_matches": state.pyramid_matches,
        "pyramid_tour_share": state.pyramid_tour_share,
        "pyramid_last_played": state.pyramid_last_played,
        "pyramid_recent_14d": state.pyramid_recent_14d,
        "serve_detail": dict(state.serve_detail),
        "retirement_rate": state.retirement_rate,
        "workload_minutes_14d": state.workload_minutes_14d,
        "workload_long_28d": state.workload_long_28d,
        "last_surface": state.last_surface,
        "rank": state.rank,
        "rank_date": state.rank_date,
    }


def _price(rng: random.Random) -> Decimal:
    """A price on a plausible spread, exact to two places as a book would quote it."""
    return Decimal(str(round(rng.choice([
        rng.uniform(1.02, 1.5), rng.uniform(1.5, 3.0), rng.uniform(3.0, 12.0),
        rng.uniform(12.0, 60.0),
    ]), 2)))


def build(seed: int = 20260726) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    model = load_model(Path(__file__).resolve().parents[2] / "artifacts"
                       / "residual-model-v3.json")
    vectors: list[dict[str, Any]] = []

    for index in range(CASES):
        # Cycle the coverage switches so every combination appears many times rather than
        # being left to chance on 500 draws.
        thin = index % 17 == 0
        no_serve = index % 5 == 0
        no_pyramid = index % 7 == 0
        with_rank = index % 3 != 0

        tour = TOURS[index % len(TOURS)]
        surface = SURFACES[index % len(SURFACES)]
        best_of = 5 if index % 4 == 0 else 3
        # Snapshot ranks cycle independently of the caller's, so every combination of the
        # rank sources appears: caller wins, snapshot fallback, half-imputed, both imputed.
        a = _player(rng, thin=thin, no_serve=no_serve, no_pyramid=no_pyramid,
                    rank=rng.randint(1, 600) if index % 4 in (0, 2) else None)
        b = _player(rng, thin=False, no_serve=no_serve, no_pyramid=no_pyramid,
                    rank=rng.randint(1, 600) if index % 4 in (0, 1) else None)
        baseline = rng.uniform(0.58, 0.66)
        match_date = dt.date(2026, 7, 26) + dt.timedelta(days=index % 9)

        # Two thirds of cases carry a pairwise record, so both the present and absent
        # head-to-head branches are replayed by the port test.
        meetings: dict[tuple[str, str, str], tuple[int, int]] = {}
        if index % 3 != 1:
            meetings[(tour, "A", "B")] = (rng.randint(0, 6), rng.randint(0, 6))
            if sum(meetings[(tour, "A", "B")]) == 0:
                meetings[(tour, "A", "B")] = (1, 1)
        snapshot = StateSnapshot(
            as_of=dt.date(2026, 7, 26),
            corpus_vintage="golden",
            players={(tour, "A"): a, (tour, "B"): b},
            tour_serve_baseline={tour: baseline},
            tour_retirement_baseline={tour: rng.uniform(0.02, 0.05)},
            head_to_head=meetings,
        )
        odds_a, odds_b = _price(rng), _price(rng)
        implied_a, implied_b = 1.0 / float(odds_a), 1.0 / float(odds_b)
        rank_a = rng.randint(1, 400) if with_rank else None
        rank_b = rng.randint(1, 400) if with_rank else None

        features = live_features(
            snapshot, tour, "A", "B", surface=surface, best_of=best_of,
            market_probability=implied_a / (implied_a + implied_b),
            match_date=match_date, rank_a=rank_a, rank_b=rank_b,
        )
        fixture = Fixture(date=match_date, tour=tour, player_a="A", player_b="B",
                          surface=surface, best_of=best_of, odds_a=odds_a, odds_b=odds_b)
        prediction = price_fixture(fixture, features, model)

        best_edge = max(prediction.edge_a, prediction.edge_b)
        if not features:
            status = TipStatus.INSUFFICIENT_DATA
        elif best_edge >= MIN_EDGE:
            status = TipStatus.BET_CANDIDATE_DISABLED
        elif best_edge >= WATCH_EDGE:
            status = TipStatus.LEAN
        else:
            status = TipStatus.NO_BET
        stale = index % 23
        # The S6 display band: cycle every stratum including the unknown fallback, so the
        # port is held to the whole frozen table, not just the manual-entry path.
        staleness_band = (None, "<60s", "60-600s", ">600s")[index % 4]
        spread = band_spread(staleness_band)

        vectors.append({
            "case": index,
            "input": {
                "tour": tour, "surface": surface, "best_of": best_of,
                "match_date": match_date.isoformat(), "state_as_of": "2026-07-26",
                "serve_baseline": baseline,
                "odds_a": str(odds_a), "odds_b": str(odds_b),
                "rank_a": rank_a, "rank_b": rank_b,
                "stale_days": stale,
                "staleness_band": staleness_band,
                "meetings": list(meetings.get((tour, "A", "B"), ())) or None,
                "a": _payload(a), "b": _payload(b),
            },
            "expected": {
                # Order matters: fsum is order-sensitive in its last bits.
                "feature_order": list(features),
                "features": dict(features),
                "market_probability_a": prediction.market_probability_a,
                "market_probability_b": prediction.market_probability_b,
                "probability_a": prediction.probability_a,
                "probability_b": prediction.probability_b,
                "fair_odds_a": str(prediction.fair_odds_a),
                "fair_odds_b": str(prediction.fair_odds_b),
                "break_even_a": prediction.break_even_a,
                "break_even_b": prediction.break_even_b,
                "edge_a": prediction.edge_a,
                "edge_b": prediction.edge_b,
                "status": status,
                "band_a": edge_band(odds_a, spread),
                "band_b": edge_band(odds_b, spread),
                "reasons": list(_reasons(features, prediction, stale)),
            },
        })
    return vectors


def main() -> int:
    target = (Path(__file__).resolve().parents[2] / "supabase" / "functions" / "tips"
              / "golden.json")
    vectors = build()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(vectors, indent=1, sort_keys=False) + "\n",
                      encoding="utf-8")
    covered = {v["expected"]["status"] for v in vectors}
    empty = sum(1 for v in vectors if not v["expected"]["features"])
    no_serve = sum(1 for v in vectors
                   if v["expected"]["features"]
                   and "point_model_residual" not in v["expected"]["features"])
    no_pyr = sum(1 for v in vectors
                 if v["expected"]["features"]
                 and "pyramid_elo_gap" not in v["expected"]["features"])
    snapshot_rank = sum(1 for v in vectors
                        if v["input"]["rank_a"] is None
                        and v["input"]["a"]["rank"] is not None)
    imputed_rank = sum(1 for v in vectors
                       if v["input"]["rank_a"] is None
                       and v["input"]["a"]["rank"] is None)
    print(f"{len(vectors)} vectors -> {target}")
    print(f"  statuses covered: {sorted(covered)}")
    print(f"  empty feature sets: {empty}   no serve layer: {no_serve}   "
          f"no pyramid layer: {no_pyr}")
    print(f"  rank_gap from snapshot rank: {snapshot_rank}   "
          f"imputed 500 on side A: {imputed_rank}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
