"""Tests for the live state snapshot — what makes the predictor usable on real fixtures.

Until now a fixture could only be priced with features handed to it by hand, which is not a
product. This snapshots everything pricing needs about each player at a date, so a match that
has not been played can be priced in milliseconds instead of a ten-minute corpus walk.

The tests are about the two ways that goes wrong: a snapshot that silently describes a
different day than it claims, and features computed from it that differ from the ones the
model was actually fitted on.
"""
from __future__ import annotations

import datetime as dt
import math
from pathlib import Path

import pytest

from tennis_edge.live_state import (
    PlayerState,
    StateSnapshot,
    live_features,
    load_state,
    save_state,
)
from tennis_edge.residual_features import RESIDUAL_FEATURE_NAMES


def player(**overrides: object) -> PlayerState:
    fields: dict[str, object] = {
        "elo": 1600.0, "weighted_elo": 1580.0, "surface_elo": {"Hard": 1620.0},
        "matches": 40, "last_played": "2026-07-01",
        "serve_rate": 0.64, "return_rate": 0.37, "serve_points": 900.0,
        "serve_matches": 30,
        "pyramid_elo": 1650.0, "pyramid_surface_elo": {"Hard": 1660.0},
        "pyramid_matches": 120, "pyramid_tour_share": 0.6,
        "pyramid_last_played": "2026-07-01", "pyramid_recent_14d": 2,
    }
    fields.update(overrides)
    return PlayerState(**fields)  # type: ignore[arg-type]


def snapshot(**overrides: object) -> StateSnapshot:
    fields: dict[str, object] = {
        "as_of": dt.date(2026, 7, 20),
        "corpus_vintage": "vintage-2026-07-18",
        "players": {("ATP", "Smith A."): player(),
                    ("ATP", "Jones B."): player(elo=1500.0, weighted_elo=1490.0,
                                                surface_elo={"Hard": 1510.0},
                                                pyramid_elo=1520.0,
                                                pyramid_surface_elo={"Hard": 1530.0},
                                                pyramid_tour_share=0.2,
                                                pyramid_recent_14d=0)},
        "tour_serve_baseline": {"ATP": 0.63},
    }
    fields.update(overrides)
    return StateSnapshot(**fields)  # type: ignore[arg-type]


class TestFeatures:
    def test_every_feature_it_emits_is_a_declared_one(self) -> None:
        """An undeclared name would be refused by the model and never reach a fit."""
        features = live_features(snapshot(), "ATP", "Smith A.", "Jones B.",
                                 surface="Hard", best_of=3, market_probability=0.55)
        assert set(features) <= set(RESIDUAL_FEATURE_NAMES)

    def test_the_stronger_player_gets_a_positive_pyramid_gap(self) -> None:
        features = live_features(snapshot(), "ATP", "Smith A.", "Jones B.",
                                 surface="Hard", best_of=3, market_probability=0.55)
        assert features["pyramid_elo_gap"] > 0.0

    def test_the_gaps_are_antisymmetric(self) -> None:
        forward = live_features(snapshot(), "ATP", "Smith A.", "Jones B.",
                                surface="Hard", best_of=3, market_probability=0.55,
                                rank_a=10, rank_b=60)
        reverse = live_features(snapshot(), "ATP", "Jones B.", "Smith A.",
                                surface="Hard", best_of=3, market_probability=0.45,
                                rank_a=60, rank_b=10)
        assert forward["pyramid_elo_gap"] == pytest.approx(-reverse["pyramid_elo_gap"])
        assert forward["rank_gap"] == pytest.approx(-reverse["rank_gap"])

    # TEST CORRECTION (TE-0017 S3). The test previously here asserted that omitting
    # rankings drops rank_gap. That pinned a live train/serve mismatch: training builds
    # rank_gap on EVERY row via `or 500` imputation (residual_features), so coefficients
    # were fitted jointly with it — while the site, serving the rank-absent branch on every
    # prediction, scored the same nominal model on a feature set nobody measured. The
    # corrected specification: rank_gap is always served, from caller-supplied ranks first,
    # the snapshot's latest-known ranks second, and the training-time 500 imputation last.

    def test_rank_gap_falls_back_to_the_snapshots_latest_known_ranks(self) -> None:
        ranked = snapshot(players={
            ("ATP", "Smith A."): player(rank=10, rank_date="2026-07-14"),
            ("ATP", "Jones B."): player(rank=60, rank_date="2026-07-14"),
        })
        features = live_features(ranked, "ATP", "Smith A.", "Jones B.",
                                 surface="Hard", best_of=3, market_probability=0.55)
        assert features["rank_gap"] == math.log1p(60) - math.log1p(10)

    def test_a_caller_supplied_rank_overrides_the_snapshot(self) -> None:
        """The fixture-time ranking is fresher than any match-derived one; it wins."""
        ranked = snapshot(players={
            ("ATP", "Smith A."): player(rank=10),
            ("ATP", "Jones B."): player(rank=60),
        })
        features = live_features(ranked, "ATP", "Smith A.", "Jones B.",
                                 surface="Hard", best_of=3, market_probability=0.55,
                                 rank_a=3, rank_b=90)
        assert features["rank_gap"] == math.log1p(90) - math.log1p(3)

    def test_unknown_ranks_impute_500_exactly_as_training_does(self) -> None:
        """`or 500` is the training-time expression; serving must reproduce it, not drop
        the feature — a coefficient fitted jointly with rank_gap applied to inputs that
        lack it is the train/serve mismatch class TE-0011 refused to deploy over."""
        features = live_features(snapshot(), "ATP", "Smith A.", "Jones B.",
                                 surface="Hard", best_of=3, market_probability=0.55)
        assert features["rank_gap"] == 0.0  # log1p(500) - log1p(500)

        half = snapshot(players={
            ("ATP", "Smith A."): player(rank=10),
            ("ATP", "Jones B."): player(),
        })
        features = live_features(half, "ATP", "Smith A.", "Jones B.",
                                 surface="Hard", best_of=3, market_probability=0.55)
        assert features["rank_gap"] == math.log1p(500) - math.log1p(10)

    def test_an_unknown_player_yields_no_features(self) -> None:
        """Absence is the honest answer; zeros would place a debutant at the centre."""
        assert live_features(snapshot(), "ATP", "Smith A.", "Nobody N.",
                             surface="Hard", best_of=3, market_probability=0.5) == {}

    def test_a_thin_record_yields_no_pyramid_features(self) -> None:
        thin = snapshot(players={
            ("ATP", "Smith A."): player(),
            ("ATP", "Jones B."): player(pyramid_matches=2),
        })
        features = live_features(thin, "ATP", "Smith A.", "Jones B.",
                                 surface="Hard", best_of=3, market_probability=0.5)
        assert not any(name.startswith("pyramid_") for name in features)

    def test_thin_serve_coverage_drops_the_point_model(self) -> None:
        thin = snapshot(players={
            ("ATP", "Smith A."): player(serve_points=10.0),
            ("ATP", "Jones B."): player(),
        })
        features = live_features(thin, "ATP", "Smith A.", "Jones B.",
                                 surface="Hard", best_of=3, market_probability=0.5)
        assert "point_model_residual" not in features

    def test_an_unseen_surface_falls_back_to_overall_rating(self) -> None:
        """A player's first match on clay is not a claim that they are average on it."""
        features = live_features(snapshot(), "ATP", "Smith A.", "Jones B.",
                                 surface="Clay", best_of=3, market_probability=0.55)
        assert "surface_elo_gap" in features


class TestPersistence:
    def test_a_snapshot_round_trips(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        original = snapshot()
        save_state(path, original)
        assert load_state(path) == original

    def test_the_as_of_date_survives(self, tmp_path: Path) -> None:
        """A snapshot that misreports its date would price from the wrong day silently."""
        path = tmp_path / "state.json"
        save_state(path, snapshot())
        assert load_state(path).as_of == dt.date(2026, 7, 20)

    def test_a_foreign_file_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        path.write_text('{"kind": "something-else"}', encoding="utf-8")
        with pytest.raises(ValueError, match="not a state snapshot"):
            load_state(path)

    def test_ranks_round_trip(self, tmp_path: Path) -> None:
        """The latest-known rank travels with the state or the site cannot serve it."""
        path = tmp_path / "state.json"
        original = snapshot(players={
            ("ATP", "Smith A."): player(rank=10, rank_date="2026-07-14"),
            ("ATP", "Jones B."): player(),
        })
        save_state(path, original)
        loaded = load_state(path)
        assert loaded.players[("ATP", "Smith A.")].rank == 10
        assert loaded.players[("ATP", "Smith A.")].rank_date == "2026-07-14"
        assert loaded.players[("ATP", "Jones B.")].rank is None

    def test_a_state_file_from_before_ranks_existed_still_loads(self, tmp_path: Path
                                                                ) -> None:
        """Rank-less files are last week's reality, not an error; they impute like
        training does."""
        path = tmp_path / "state.json"
        save_state(path, snapshot())
        raw = path.read_text(encoding="utf-8").replace('"rank":null,', '').replace(
            '"rank_date":null,', '')
        path.write_text(raw, encoding="utf-8")
        loaded = load_state(path)
        assert loaded.players[("ATP", "Smith A.")].rank is None


class TestStaleness:
    def test_a_snapshot_reports_its_own_age(self) -> None:
        assert snapshot().days_old(dt.date(2026, 7, 27)) == 7

    def test_a_fixture_before_the_snapshot_is_refused(self) -> None:
        """Pricing backwards would use ratings that already contain the result."""
        with pytest.raises(ValueError, match="before the snapshot"):
            live_features(snapshot(), "ATP", "Smith A.", "Jones B.", surface="Hard",
                          best_of=3, market_probability=0.5,
                          match_date=dt.date(2026, 7, 19))

    def test_a_fixture_on_or_after_the_snapshot_is_allowed(self) -> None:
        assert live_features(snapshot(), "ATP", "Smith A.", "Jones B.", surface="Hard",
                             best_of=3, market_probability=0.5,
                             match_date=dt.date(2026, 7, 20))
