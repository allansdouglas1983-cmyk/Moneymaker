"""Serve-estimator tests, centred on the tournament-week timing guard.

The archive stamps every match with the Monday of its tournament week, so a naive "absorb
everything dated before today" rule would feed Thursday's prediction with Saturday's final.
That is the subtlest leak in this whole system — it produces a model that looks brilliant and
is worthless — so it gets the most direct test here.
"""
from __future__ import annotations

import datetime as dt

import pytest

from tennis_edge.sackmann import Level, SackmannMatch, ServeLine
from tennis_edge.serve_stats import (
    TOURNAMENT_LAG_DAYS,
    ServeEstimator,
    sackmann_player_key,
    td_player_key,
)


def _line(points: int, won: int) -> ServeLine:
    """A serve line winning ``won`` of ``points``, split plausibly across first/second."""
    first_in = points // 2
    first_won = min(won, first_in)
    return ServeLine(
        aces=0, double_faults=0, serve_points=points, first_in=first_in,
        first_won=first_won, second_won=won - first_won, serve_games=points // 6,
        break_points_saved=0, break_points_faced=0,
    )


def _archive(week: dt.date, winner: str, loser: str, *, w_points: int = 80, w_won: int = 56,
             l_points: int = 80, l_won: int = 44, score: str = "6-4 6-4") -> SackmannMatch:
    return SackmannMatch(
        tourney_id=f"{week.year}-X", tourney_name="Test", tourney_date=week,
        level=Level.TOUR, surface="Hard", round_name="R32", best_of=3, match_num=1,
        tour="ATP", winner_id="1", winner_name=winner, loser_id="2", loser_name=loser,
        winner_rank=10, loser_rank=20, minutes=90, score=score,
        winner_serve=_line(w_points, w_won), loser_serve=_line(l_points, l_won),
        source_file="test.csv",
    )


def test_name_keys_join_the_two_sources() -> None:
    """The archive gives full names, the priced corpus gives surname plus initial. Both must
    normalise to the same key or the join silently returns nothing."""
    assert sackmann_player_key("Carlos Alcaraz") == td_player_key("Alcaraz C.")
    assert sackmann_player_key("Jannik Sinner") == td_player_key("Sinner J.")


def test_a_still_running_tournament_is_not_absorbed() -> None:
    """The decisive timing test. A tournament stamped this Monday has rounds still to come,
    so nothing from it may inform a prediction made during that week."""
    monday = dt.date(2024, 5, 6)
    estimator = ServeEstimator()
    estimator.queue([_archive(monday, "Alice Smith", "Bob Jones")])
    for offset in range(0, TOURNAMENT_LAG_DAYS):
        absorbed = estimator.advance_to(monday + dt.timedelta(days=offset))
        assert absorbed == 0, f"absorbed a live tournament {offset} days in"
    assert estimator.advance_to(monday + dt.timedelta(days=TOURNAMENT_LAG_DAYS)) == 1


def test_no_estimate_exists_before_any_history_is_absorbed() -> None:
    estimator = ServeEstimator()
    estimator.queue([_archive(dt.date(2024, 1, 1), "Alice Smith", "Bob Jones")])
    assert estimator.estimate("ATP", "Smith A.", "Jones B.", dt.date(2024, 1, 3)) is None


def test_a_stronger_server_gets_a_higher_serve_probability() -> None:
    estimator = ServeEstimator(prior_serve_points=50.0)
    week = dt.date(2024, 1, 1)
    for index in range(30):
        estimator.queue([_archive(week + dt.timedelta(weeks=index),
                                  "Alice Smith", f"Foe Rivalx{index}",
                                  w_points=80, w_won=60, l_points=80, l_won=40)])
    estimator.advance_to(dt.date(2025, 1, 1))
    estimate = estimator.estimate("ATP", "Smith A.", "Rivalx0 F.", dt.date(2025, 1, 1))
    assert estimate is not None
    assert estimate.p_serve_a > estimate.p_serve_b


def test_the_estimate_is_antisymmetric_in_the_players() -> None:
    """Asking for A-versus-B and B-versus-A must give mirrored answers.

    Note what is deliberately NOT asserted: that the two serve probabilities sum to 1. They
    describe different service games, so for two strong servers they correctly sum to more
    than 1. The consistency Barnett-Clarke guarantees is within a service game, where the
    returner's probability is the complement of the server's by definition."""
    estimator = ServeEstimator(prior_serve_points=50.0)
    week = dt.date(2024, 1, 1)
    for index in range(20):
        estimator.queue([_archive(week + dt.timedelta(weeks=index), "Alice Smith", "Bob Jones",
                                  w_points=80, w_won=58, l_points=80, l_won=42)])
    estimator.advance_to(dt.date(2025, 1, 1))
    forward = estimator.estimate("ATP", "Smith A.", "Jones B.", dt.date(2025, 1, 1))
    reverse = estimator.estimate("ATP", "Jones B.", "Smith A.", dt.date(2025, 1, 1))
    assert forward is not None and reverse is not None
    assert forward.p_serve_a == pytest.approx(reverse.p_serve_b, abs=1e-12)
    assert forward.p_serve_b == pytest.approx(reverse.p_serve_a, abs=1e-12)


def test_shrinkage_keeps_a_thin_record_near_the_tour_average() -> None:
    """One freak match must not become a rating. With a strong prior the estimate stays
    close to the baseline, which is the whole defence against a five-point standard error
    being amplified fivefold by the match model."""
    estimator = ServeEstimator(prior_serve_points=2000.0)
    estimator.queue([_archive(dt.date(2024, 1, 1), "Alice Smith", "Bob Jones",
                              w_points=80, w_won=80, l_points=80, l_won=10)])
    estimator.advance_to(dt.date(2024, 3, 1))
    estimate = estimator.estimate("ATP", "Smith A.", "Jones B.", dt.date(2024, 3, 1))
    assert estimate is not None
    baseline = estimator.tour_serve_average("ATP")
    assert abs(estimate.p_serve_a - baseline) < 0.05, "one match should barely move it"


def test_retirements_are_excluded_from_the_serve_history() -> None:
    """A retirement inflates the opponent's serve line for reasons that are not skill."""
    estimator = ServeEstimator()
    estimator.queue([_archive(dt.date(2024, 1, 1), "Alice Smith", "Bob Jones",
                              score="6-1 2-0 RET")])
    assert estimator.advance_to(dt.date(2024, 3, 1)) == 0


def test_a_player_cannot_be_estimated_against_themselves() -> None:
    estimator = ServeEstimator()
    assert estimator.estimate("ATP", "Smith A.", "Smith A.", dt.date(2024, 1, 1)) is None


def test_absorbing_is_a_forward_walk_not_a_rescan() -> None:
    """Rebuilding the pending queue on every call made the full backtest quadratic and
    unusable; absorbing must consume the queue exactly once."""
    estimator = ServeEstimator()
    weeks = [dt.date(2024, 1, 1) + dt.timedelta(weeks=i) for i in range(10)]
    estimator.queue([_archive(week, f"P{i} One", f"Q{i} Two") for i, week in enumerate(weeks)])
    total = sum(estimator.advance_to(week + dt.timedelta(days=30)) for week in weeks)
    assert total == 10
    assert estimator.advance_to(dt.date(2030, 1, 1)) == 0, "nothing may be absorbed twice"
