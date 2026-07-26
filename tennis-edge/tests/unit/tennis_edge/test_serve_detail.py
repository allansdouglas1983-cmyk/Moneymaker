"""Tests for the detailed serve/return layer.

The archive carries nine serve fields per player per match — aces, double faults, first
serves in, first-serve points won, second-serve points won, service games, break points
saved and faced. The existing estimator collapses all of it into one ratio: serve points
won. That discards the two things the tennis-modelling literature cites most often.

**First and second serve are different skills.** A player who lands 70% of first serves and
wins 78% of them is a different problem from one landing 55% and winning 85%, and the
aggregate cannot tell them apart. Their opponents' returns differ accordingly.

**Break points are where matches are decided, and performance on them is not the average.**
Break points faced and saved measure holding under pressure directly, and a match is decided
by a handful of them.

Every rate here is shrunk toward the tour baseline by its own denominator, because a ratio of
two small counts is not a probability — the same discipline the aggregate estimator already
applies, extended to each component separately rather than to their sum.
"""
from __future__ import annotations

import datetime as dt

import pytest

from tennis_edge.sackmann import Level, SackmannMatch, ServeLine
from tennis_edge.serve_detail import (
    PRIOR_POINTS,
    DetailEstimator,
    ServeProfile,
    serve_detail_features,
)


def line(*, aces: int = 5, double_faults: int = 2, serve_points: int = 70,
         first_in: int = 42, first_won: int = 32, second_won: int = 16,
         serve_games: int = 11, bp_saved: int = 3,
         bp_faced: int = 5) -> ServeLine:
    return ServeLine(aces=aces, double_faults=double_faults, serve_points=serve_points,
                     first_in=first_in, first_won=first_won, second_won=second_won,
                     serve_games=serve_games, break_points_saved=bp_saved,
                     break_points_faced=bp_faced)


def match(*, winner: str = "Alan Smith", loser: str = "Bob Jones",
          week: dt.date = dt.date(2020, 1, 6), num: int = 1,
          winner_line: ServeLine | None = None,
          loser_line: ServeLine | None = None) -> SackmannMatch:
    return SackmannMatch(
        tourney_id=f"2020-{num}", tourney_name="Test", tourney_date=week,
        level=Level.TOUR, surface="Hard", round_name="R32", best_of=3, match_num=num,
        tour="ATP", winner_id="", winner_name=winner, loser_id="", loser_name=loser,
        winner_rank=None, loser_rank=None, minutes=None, score="6-4 6-4",
        winner_serve=winner_line or line(), loser_serve=loser_line or line(),
        source_file="test.csv",
    )


LATER = dt.date(2020, 1, 20)


class TestProfileRates:
    def test_first_serve_percentage_is_in_of_points(self) -> None:
        profile = ServeProfile(first_in=42, serve_points=70, first_won=32, second_won=16,
                               aces=5, double_faults=2, bp_saved=3, bp_faced=5,
                               matches=1)
        assert profile.first_serve_rate(baseline=0.6) == pytest.approx(42 / 70, abs=0.05)

    def test_first_serve_win_rate_is_won_of_in(self) -> None:
        """Denominator is first serves *landed*, not points played — a different rate."""
        profile = ServeProfile(first_in=42, serve_points=70, first_won=32, second_won=16,
                               aces=5, double_faults=2, bp_saved=3, bp_faced=5,
                               matches=1)
        assert profile.first_win_rate(baseline=0.7) == pytest.approx(32 / 42, abs=0.06)

    def test_second_serve_win_rate_uses_the_second_serve_denominator(self) -> None:
        profile = ServeProfile(first_in=42, serve_points=70, first_won=32, second_won=16,
                               aces=5, double_faults=2, bp_saved=3, bp_faced=5,
                               matches=1)
        assert profile.second_win_rate(baseline=0.5) == pytest.approx(16 / 28, abs=0.08)

    def test_an_empty_profile_returns_the_baseline(self) -> None:
        """No evidence must mean the prior, never a division or a fabricated rate."""
        empty = ServeProfile(0, 0, 0, 0, 0, 0, 0, 0, 0)
        assert empty.first_serve_rate(baseline=0.61) == pytest.approx(0.61)
        assert empty.break_point_save_rate(baseline=0.6) == pytest.approx(0.6)

    def test_shrinkage_pulls_a_thin_sample_toward_the_baseline(self) -> None:
        thin = ServeProfile(first_in=8, serve_points=10, first_won=8, second_won=2,
                            aces=0, double_faults=0, bp_saved=0, bp_faced=0, matches=1)
        assert thin.first_serve_rate(baseline=0.60) < 0.75

    def test_a_thick_sample_moves_close_to_its_raw_rate(self) -> None:
        thick = ServeProfile(first_in=int(0.8 * 20 * PRIOR_POINTS),
                             serve_points=int(20 * PRIOR_POINTS),
                             first_won=0, second_won=0, aces=0, double_faults=0,
                             bp_saved=0, bp_faced=0, matches=200)
        assert thick.first_serve_rate(baseline=0.60) > 0.78


class TestEstimator:
    def test_it_absorbs_both_players(self) -> None:
        estimator = DetailEstimator()
        estimator.queue([match()])
        estimator.advance_to(LATER)
        assert estimator.profile("ATP", "Smith A.").matches == 1
        assert estimator.profile("ATP", "Jones B.").matches == 1

    def test_an_unseen_player_has_an_empty_profile(self) -> None:
        assert DetailEstimator().profile("ATP", "Nobody N.").matches == 0

    def test_a_tournament_in_progress_is_not_absorbed(self) -> None:
        """Same lag discipline as everywhere: the week must have closed."""
        estimator = DetailEstimator()
        estimator.queue([match()])
        estimator.advance_to(dt.date(2020, 1, 8))
        assert estimator.profile("ATP", "Smith A.").matches == 0

    def test_return_statistics_come_from_the_opponent_serve_line(self) -> None:
        """A player's return record is the mirror of what they faced, not a separate feed."""
        estimator = DetailEstimator()
        estimator.queue([match(winner_line=line(serve_points=70, first_won=60,
                                                second_won=8))])
        estimator.advance_to(LATER)
        assert estimator.profile("ATP", "Jones B.").return_points > 0


class TestFeatures:
    def test_it_emits_only_declared_names(self) -> None:
        estimator = DetailEstimator()
        estimator.queue([match(num=n) for n in range(1, 20)])
        estimator.advance_to(LATER)
        features = serve_detail_features(estimator, "ATP", "Smith A.", "Jones B.")
        assert set(features) <= set(serve_detail_features.NAMES)  # type: ignore[attr-defined]

    def test_a_player_with_no_record_yields_nothing(self) -> None:
        estimator = DetailEstimator()
        estimator.queue([match(num=n) for n in range(1, 20)])
        estimator.advance_to(LATER)
        assert serve_detail_features(estimator, "ATP", "Smith A.", "Nobody N.") == {}

    def test_gaps_are_antisymmetric(self) -> None:
        estimator = DetailEstimator()
        strong = line(first_in=50, first_won=45, second_won=15, aces=15,
                      double_faults=1, bp_saved=8, bp_faced=8)
        weak = line(first_in=30, first_won=18, second_won=10, aces=1,
                    double_faults=8, bp_saved=1, bp_faced=9)
        estimator.queue([match(num=n, winner_line=strong, loser_line=weak)
                         for n in range(1, 20)])
        estimator.advance_to(LATER)
        forward = serve_detail_features(estimator, "ATP", "Smith A.", "Jones B.")
        reverse = serve_detail_features(estimator, "ATP", "Jones B.", "Smith A.")
        for name, value in forward.items():
            assert value == pytest.approx(-reverse[name])

    def test_the_stronger_server_gets_a_positive_ace_gap(self) -> None:
        estimator = DetailEstimator()
        estimator.queue([match(num=n, winner_line=line(aces=20),
                               loser_line=line(aces=1)) for n in range(1, 20)])
        estimator.advance_to(LATER)
        features = serve_detail_features(estimator, "ATP", "Smith A.", "Jones B.")
        assert features["ace_rate_gap"] > 0.0
