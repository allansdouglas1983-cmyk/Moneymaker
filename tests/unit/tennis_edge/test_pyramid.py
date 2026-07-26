"""Tests for the pyramid rating layer.

The point of this layer is that a main-tour-only rating is *blind below the main tour*, and
the tests are written around that: the ones that matter check that a lower-tier result moves
the rating, that a lower-tier match counts as activity, and that no result inside the
tournament week being priced can reach the state.
"""
from __future__ import annotations

import datetime as dt

import pytest

from tennis_edge.pyramid import (
    TOURNAMENT_LAG_DAYS,
    PyramidRatings,
    pyramid_features,
)
from tennis_edge.sackmann import Level, SackmannMatch, ServeLine

EMPTY = ServeLine(None, None, None, None, None, None, None, None, None)


def make(
    *,
    winner: str,
    loser: str,
    week: dt.date,
    level: Level = Level.CHALLENGER,
    tour: str = "ATP",
    surface: str = "Hard",
    num: int = 1,
    score: str = "6-4 6-4",
) -> SackmannMatch:
    return SackmannMatch(
        tourney_id=f"{week:%Y}-{num}",
        tourney_name="Test",
        tourney_date=week,
        level=level,
        surface=surface,
        round_name="R32",
        best_of=3,
        match_num=num,
        tour=tour,
        winner_id="",
        winner_name=winner,
        loser_id="",
        loser_name=loser,
        winner_rank=None,
        loser_rank=None,
        minutes=None,
        score=score,
        winner_serve=EMPTY,
        loser_serve=EMPTY,
        source_file="test.csv",
    )


WEEK = dt.date(2020, 1, 6)
LATER = WEEK + dt.timedelta(days=TOURNAMENT_LAG_DAYS + 1)


class TestLowerTierIsVisible:
    """The whole reason the layer exists."""

    def test_a_challenger_win_moves_the_rating(self) -> None:
        ratings = PyramidRatings()
        ratings.queue([make(winner="Alan Smith", loser="Bob Jones", week=WEEK)])
        ratings.advance_to(LATER)
        assert ratings.elo("ATP", "Smith A.") > ratings.elo("ATP", "Jones B.")

    def test_a_futures_win_moves_the_rating(self) -> None:
        ratings = PyramidRatings()
        ratings.queue([make(winner="Alan Smith", loser="Bob Jones", week=WEEK,
                            level=Level.ITF)])
        ratings.advance_to(LATER)
        assert ratings.elo("ATP", "Smith A.") > 1500.0

    def test_lower_tier_play_counts_as_activity(self) -> None:
        """The fatigue point: a main-tour rating thinks this player has been resting."""
        ratings = PyramidRatings()
        ratings.queue([make(winner="Alan Smith", loser="Bob Jones", week=WEEK,
                            level=Level.ITF)])
        ratings.advance_to(LATER)
        assert ratings.days_since_last("ATP", "Smith A.", LATER) is not None
        assert ratings.matches_in_last("ATP", "Smith A.", LATER, 30) == 1

    def test_an_unseen_player_is_unrated_not_average(self) -> None:
        """``None`` and 1500 are different claims and must not be conflated."""
        ratings = PyramidRatings()
        assert ratings.matches_played("ATP", "Nobody N.") == 0
        assert ratings.days_since_last("ATP", "Nobody N.", LATER) is None


class TestNoLookahead:
    def test_the_tournament_week_being_priced_is_not_absorbed(self) -> None:
        ratings = PyramidRatings()
        ratings.queue([make(winner="Alan Smith", loser="Bob Jones", week=WEEK)])
        # A match played on the Thursday of that same week.
        ratings.advance_to(WEEK + dt.timedelta(days=3))
        assert ratings.matches_played("ATP", "Smith A.") == 0

    def test_the_lag_covers_the_whole_week(self) -> None:
        ratings = PyramidRatings()
        ratings.queue([make(winner="Alan Smith", loser="Bob Jones", week=WEEK)])
        ratings.advance_to(WEEK + dt.timedelta(days=TOURNAMENT_LAG_DAYS - 1))
        assert ratings.matches_played("ATP", "Smith A.") == 0

    def test_advancing_is_monotone(self) -> None:
        """Walking forward twice to the same day absorbs nothing the second time."""
        ratings = PyramidRatings()
        ratings.queue([make(winner="Alan Smith", loser="Bob Jones", week=WEEK)])
        assert ratings.advance_to(LATER) == 1
        assert ratings.advance_to(LATER) == 0

    def test_advancing_backwards_is_refused(self) -> None:
        ratings = PyramidRatings()
        ratings.advance_to(LATER)
        with pytest.raises(ValueError, match="backwards"):
            ratings.advance_to(WEEK)


class TestTours:
    def test_atp_and_wta_are_separate_namespaces(self) -> None:
        """Same convention as the governed DP1 policy: the tours never mix."""
        ratings = PyramidRatings()
        ratings.queue([make(winner="Alan Smith", loser="Bob Jones", week=WEEK)])
        ratings.advance_to(LATER)
        assert ratings.elo("WTA", "Smith A.") == 1500.0
        assert ratings.matches_played("WTA", "Smith A.") == 0


class TestTierMix:
    def test_tier_share_distinguishes_a_tour_player_from_a_futures_player(self) -> None:
        ratings = PyramidRatings()
        ratings.queue([
            make(winner="Alan Smith", loser="X Y", week=WEEK, level=Level.TOUR, num=1),
            make(winner="Bob Jones", loser="X Y", week=WEEK, level=Level.ITF, num=2),
        ])
        ratings.advance_to(LATER)
        assert ratings.tour_level_share("ATP", "Smith A.") == 1.0
        assert ratings.tour_level_share("ATP", "Jones B.") == 0.0

    def test_tier_share_of_an_unseen_player_is_none(self) -> None:
        ratings = PyramidRatings()
        assert ratings.tour_level_share("ATP", "Nobody N.") is None


class TestOrderInvariance:
    def test_a_day_is_absorbed_as_a_block(self) -> None:
        """Two orderings of the same week must leave identical ratings."""
        first = [make(winner="Alan Smith", loser="Bob Jones", week=WEEK, num=1),
                 make(winner="Carl Ray", loser="Dan Vale", week=WEEK, num=2)]
        forward, backward = PyramidRatings(), PyramidRatings()
        forward.queue(first)
        backward.queue(list(reversed(first)))
        forward.advance_to(LATER)
        backward.advance_to(LATER)
        for name in ("Smith A.", "Jones B.", "Ray C.", "Vale D."):
            assert forward.elo("ATP", name) == backward.elo("ATP", name)


class TestFeatures:
    def test_features_are_absent_rather_than_zero_when_a_player_is_unseen(self) -> None:
        """A zero gap asserts the players are equal; absence asserts nothing."""
        ratings = PyramidRatings()
        ratings.queue([make(winner="Alan Smith", loser="Bob Jones", week=WEEK)])
        ratings.advance_to(LATER)
        assert pyramid_features(ratings, "ATP", "Smith A.", "Nobody N.",
                                LATER, "Hard") == {}

    def test_a_thin_record_yields_no_features(self) -> None:
        """Five prior matches is the documented precondition, and it is enforced."""
        ratings = PyramidRatings()
        ratings.queue([make(winner="Alan Smith", loser="Bob Jones", week=WEEK, num=1)])
        ratings.advance_to(LATER)
        assert pyramid_features(ratings, "ATP", "Smith A.", "Jones B.",
                                LATER, "Hard") == {}

    def test_the_elo_gap_is_antisymmetric(self) -> None:
        ratings = PyramidRatings()
        ratings.queue([make(winner="Alan Smith", loser="Bob Jones", week=WEEK, num=n)
                       for n in range(1, 7)])
        ratings.advance_to(LATER)
        ab = pyramid_features(ratings, "ATP", "Smith A.", "Jones B.", LATER, "Hard")
        ba = pyramid_features(ratings, "ATP", "Jones B.", "Smith A.", LATER, "Hard")
        assert ab["pyramid_elo_gap"] == pytest.approx(-ba["pyramid_elo_gap"])
        assert ab["pyramid_elo_gap"] > 0.0

    def test_workload_counts_lower_tier_matches(self) -> None:
        """Six Futures matches for A, five for B — a gap only this layer can see."""
        ratings = PyramidRatings()
        ratings.queue(
            [make(winner="Alan Smith", loser=f"Op{n} Ponent", week=WEEK,
                  level=Level.ITF, num=n) for n in range(1, 7)]
            + [make(winner="Bob Jones", loser=f"Op{n} Ponent", week=WEEK,
                    level=Level.ITF, num=10 + n) for n in range(1, 6)]
        )
        ratings.advance_to(LATER)
        features = pyramid_features(ratings, "ATP", "Smith A.", "Jones B.", LATER, "Hard")
        assert features["pyramid_workload_gap"] == pytest.approx(1.0)
