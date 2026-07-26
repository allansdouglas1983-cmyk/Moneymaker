"""Tests for the durability layer: head-to-head, retirement risk, workload, surface switch.

The properties that matter here are not "does it compute a number". They are:

- **nothing is learned from the future** — the eight-day tournament lag holds, and a match
  cannot inform a price on a day the estimator has not reached
- **absence stays absent** — a pair that has never met has no head-to-head feature, rather
  than a zero claiming they are even
- **the orientation is antisymmetric** — swapping the players negates every gap, which is
  what makes a leaked outcome visible as an asymmetry rather than hiding as a level
- **a walkover is not evidence of a matchup** — it was never played
"""
from __future__ import annotations

import datetime as dt

import pytest

from tennis_edge.durability import (
    DurabilityEstimator,
    MIN_H2H_MEETINGS,
    durability_features,
)
from tennis_edge.sackmann import Level, SackmannMatch, ServeLine


#: Sackmann writes "Given Surname"; Tennis-Data writes "Surname G.". The estimator absorbs
#: through the first mapping and is queried through the second, so a test name has to be
#: real enough to survive both — single letters parse to nothing in either.
ALPHA, ALPHA_TD = "Aaron Alpha", "Alpha A."
BRAVO, BRAVO_TD = "Brian Bravo", "Bravo B."
CHARLIE, CHARLIE_TD = "Colin Charlie", "Charlie C."
WINNER, WINNER_TD = "Walter Winner", "Winner W."


def match(winner: str, loser: str, *, date: dt.date, score: str = "6-4 6-4",
          minutes: int | None = 95, surface: str = "Hard", num: int = 1,
          tour: str = "ATP") -> SackmannMatch:
    blank = ServeLine(aces=None, double_faults=None, serve_points=None, first_in=None,
                      first_won=None, second_won=None, serve_games=None,
                      break_points_saved=None, break_points_faced=None)
    return SackmannMatch(
        tourney_id=f"t{date.year}", tourney_name="Test", tourney_date=date,
        level=Level.TOUR, surface=surface, round_name="R32", best_of=3, match_num=num,
        tour=tour, winner_id=winner, winner_name=winner, loser_id=loser, loser_name=loser,
        winner_rank=10, loser_rank=20, minutes=minutes, score=score,
        winner_serve=blank, loser_serve=blank, source_file="test.csv",
    )


def estimator_with(matches: list[SackmannMatch], *, through: dt.date) -> DurabilityEstimator:
    estimator = DurabilityEstimator()
    estimator.queue(matches)
    estimator.advance_to(through)
    return estimator


JAN = dt.date(2024, 1, 1)


class TestHeadToHead:
    def test_a_pair_that_has_never_met_has_no_feature(self) -> None:
        """Absence is a claim about what is known; zero is a claim about the world."""
        estimator = estimator_with([match(ALPHA, CHARLIE, date=JAN)], through=dt.date(2024, 3, 1))
        features = durability_features(estimator, "ATP", ALPHA_TD, BRAVO_TD,
                                       surface="Hard", when=dt.date(2024, 3, 1))
        assert "h2h_gap" not in features

    def test_one_meeting_is_not_enough(self) -> None:
        estimator = estimator_with([match(ALPHA, BRAVO, date=JAN)], through=dt.date(2024, 3, 1))
        assert estimator.head_to_head("ATP", ALPHA_TD, BRAVO_TD) is None

    def test_the_minimum_number_of_meetings_produces_a_feature(self) -> None:
        entries = [match(ALPHA, BRAVO, date=JAN, num=i) for i in range(MIN_H2H_MEETINGS)]
        estimator = estimator_with(entries, through=dt.date(2024, 3, 1))
        features = durability_features(estimator, "ATP", ALPHA_TD, BRAVO_TD,
                                       surface="Hard", when=dt.date(2024, 3, 1))
        assert features["h2h_gap"] > 0

    def test_the_record_is_read_from_either_side(self) -> None:
        entries = [match(ALPHA, BRAVO, date=JAN, num=1), match(ALPHA, BRAVO, date=JAN, num=2)]
        estimator = estimator_with(entries, through=dt.date(2024, 3, 1))
        assert estimator.head_to_head("ATP", ALPHA_TD, BRAVO_TD) == (2, 0)
        assert estimator.head_to_head("ATP", BRAVO_TD, ALPHA_TD) == (0, 2)

    def test_a_walkover_is_not_a_meeting(self) -> None:
        """It was never played, so it says nothing about how the two match up."""
        entries = [match(ALPHA, BRAVO, date=JAN, num=1, score="W/O"),
                   match(ALPHA, BRAVO, date=JAN, num=2, score="W/O")]
        estimator = estimator_with(entries, through=dt.date(2024, 3, 1))
        assert estimator.head_to_head("ATP", ALPHA_TD, BRAVO_TD) is None

    def test_a_retirement_is_a_meeting(self) -> None:
        """Unlike a walkover it was contested, and Betfair settled it."""
        entries = [match(ALPHA, BRAVO, date=JAN, num=1, score="6-4 2-1 RET"),
                   match(ALPHA, BRAVO, date=JAN, num=2, score="6-4 2-1 RET")]
        estimator = estimator_with(entries, through=dt.date(2024, 3, 1))
        assert estimator.head_to_head("ATP", ALPHA_TD, BRAVO_TD) == (2, 0)

    def test_the_two_tours_are_separate(self) -> None:
        entries = [match(ALPHA, BRAVO, date=JAN, num=i, tour="WTA") for i in range(3)]
        estimator = estimator_with(entries, through=dt.date(2024, 3, 1))
        assert estimator.head_to_head("ATP", ALPHA_TD, BRAVO_TD) is None
        assert estimator.head_to_head("WTA", ALPHA_TD, BRAVO_TD) == (3, 0)


class TestRetirementRisk:
    def test_a_player_who_never_retires_is_below_the_tour_baseline(self) -> None:
        entries = [match(ALPHA, f"Loser L{i}", date=JAN, num=i) for i in range(40)]
        entries += [match(WINNER, BRAVO, date=JAN, num=100 + i, score="6-1 1-0 RET")
                    for i in range(6)]
        estimator = estimator_with(entries, through=dt.date(2024, 3, 1))
        baseline = estimator.retirement_baseline("ATP")
        assert baseline > 0
        assert estimator.record("ATP", ALPHA_TD).retirement_rate(baseline=baseline) < baseline

    def test_only_the_retiring_player_is_charged(self) -> None:
        """The score marks the match; in this archive the retiring player always loses."""
        entries = [match(WINNER, BRAVO, date=JAN, num=i, score="6-1 1-0 RET") for i in range(20)]
        estimator = estimator_with(entries, through=dt.date(2024, 3, 1))
        assert estimator.record("ATP", BRAVO_TD).retirements == 20
        assert estimator.record("ATP", WINNER_TD).retirements == 0

    def test_an_unseen_player_gets_the_baseline_not_a_zero(self) -> None:
        """No history is not a claim of perfect durability."""
        estimator = estimator_with([match(ALPHA, BRAVO, date=JAN)], through=dt.date(2024, 3, 1))
        baseline = estimator.retirement_baseline("ATP")
        assert estimator.record("ATP", "Nobody N.").retirement_rate(baseline=baseline) == baseline


class TestWorkload:
    def test_minutes_inside_the_window_accumulate(self) -> None:
        when = dt.date(2024, 1, 20)
        entries = [match(ALPHA, BRAVO, date=dt.date(2024, 1, 8), minutes=120, num=1)]
        estimator = estimator_with(entries, through=when)
        features = durability_features(estimator, "ATP", ALPHA_TD, CHARLIE_TD, surface="Hard", when=when)
        assert features["workload_minutes_gap"] == pytest.approx(2.0)

    def test_minutes_outside_the_window_do_not(self) -> None:
        when = dt.date(2024, 3, 1)
        entries = [match(ALPHA, BRAVO, date=dt.date(2024, 1, 8), minutes=120, num=1)]
        estimator = estimator_with(entries, through=when)
        features = durability_features(estimator, "ATP", ALPHA_TD, CHARLIE_TD, surface="Hard", when=when)
        assert features["workload_minutes_gap"] == pytest.approx(0.0)

    def test_a_long_match_is_counted_separately(self) -> None:
        when = dt.date(2024, 1, 20)
        entries = [match(ALPHA, BRAVO, date=dt.date(2024, 1, 8), minutes=240, num=1)]
        estimator = estimator_with(entries, through=when)
        features = durability_features(estimator, "ATP", ALPHA_TD, CHARLIE_TD, surface="Hard", when=when)
        assert features["workload_long_gap"] == pytest.approx(1.0)


class TestSurfaceSwitch:
    def test_arriving_from_another_surface_is_flagged(self) -> None:
        when = dt.date(2024, 1, 20)
        entries = [match(ALPHA, BRAVO, date=dt.date(2024, 1, 8), surface="Clay", num=1)]
        estimator = estimator_with(entries, through=when)
        features = durability_features(estimator, "ATP", ALPHA_TD, CHARLIE_TD, surface="Grass", when=when)
        assert features["surface_switch_gap"] == pytest.approx(1.0)

    def test_staying_on_the_same_surface_is_not(self) -> None:
        when = dt.date(2024, 1, 20)
        entries = [match(ALPHA, BRAVO, date=dt.date(2024, 1, 8), surface="Grass", num=1)]
        estimator = estimator_with(entries, through=when)
        features = durability_features(estimator, "ATP", ALPHA_TD, CHARLIE_TD, surface="Grass", when=when)
        assert features["surface_switch_gap"] == pytest.approx(0.0)


class TestOrientationAndTime:
    def test_swapping_the_players_negates_every_gap(self) -> None:
        """Antisymmetry is what makes a leaked outcome show up rather than hide."""
        when = dt.date(2024, 3, 1)
        entries = [match(ALPHA, BRAVO, date=JAN, num=i) for i in range(3)]
        entries += [match("Xavier Xray", BRAVO, date=dt.date(2024, 2, 20), minutes=200, num=50)]
        estimator = estimator_with(entries, through=when)
        forward = durability_features(estimator, "ATP", ALPHA_TD, BRAVO_TD, surface="Clay", when=when)
        reverse = durability_features(estimator, "ATP", BRAVO_TD, ALPHA_TD, surface="Clay", when=when)
        assert set(forward) == set(reverse)
        for name in forward:
            assert forward[name] == pytest.approx(-reverse[name])

    def test_a_match_inside_the_lag_is_not_yet_visible(self) -> None:
        """The archive dates a match by the Monday of its week; without the lag a
        tournament's later rounds would inform its own earlier ones."""
        played = dt.date(2024, 1, 15)
        estimator = DurabilityEstimator()
        estimator.queue([match(ALPHA, BRAVO, date=played, num=i) for i in range(3)])
        estimator.advance_to(played + dt.timedelta(days=3))
        assert estimator.head_to_head("ATP", ALPHA_TD, BRAVO_TD) is None
        estimator.advance_to(played + dt.timedelta(days=9))
        assert estimator.head_to_head("ATP", ALPHA_TD, BRAVO_TD) == (3, 0)

    def test_advancing_backwards_is_refused(self) -> None:
        estimator = estimator_with([match(ALPHA, BRAVO, date=JAN)], through=dt.date(2024, 3, 1))
        with pytest.raises(ValueError, match="backwards"):
            estimator.advance_to(dt.date(2024, 1, 2))
