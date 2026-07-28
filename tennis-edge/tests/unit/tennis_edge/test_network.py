"""Common opponents and local intransitivity — what a scalar rating cannot represent.

DR-TENNIS-FORECAST-LIT-001 returned exactly one genuinely new feature family with published
evidence: relational structure in the player graph. Clegg and Cartlidge (2025) report that
bookmakers are weakest where a local matchup neighbourhood is **cyclic** rather than
hierarchical — A beats B, B beats C, C beats A — because a rating is a single number on a
line and a line cannot hold a cycle. They find subset profitability there under Bonferroni
control, while their model still loses to the market overall.

Two quantities, both computed from matches strictly before the priced one under the same
eight-day tournament lag used everywhere else:

``common_opponent_gap`` — of the opponents both players have faced, how much better A did
than B against the same people. This is a genuinely different estimate from Elo: it weights
only shared opponents, so it survives when two players inhabit different parts of the draw
and their ratings were earned against disjoint fields.

``intransitivity`` — how much those shared opponents *disagree* about who is stronger. Near
zero when every common opponent points the same way (a hierarchy the rating already
captures); large when they contradict each other (a cycle it cannot).

The pair is symmetric by design: the gap flips sign under a swap, intransitivity does not.
That asymmetry test is the cheap way to catch a leaked outcome.
"""
from __future__ import annotations

import datetime as dt

import pytest

from tennis_edge.network import (
    MIN_COMMON_OPPONENTS,
    NetworkEstimator,
    network_features,
)
from tennis_edge.sackmann import Level, SackmannMatch, ServeLine

FULL = {"A": "Aaron Alpha", "B": "Bruno Beta", "C": "Carl Gamma", "D": "Dan Delta",
        "E": "Ed Epsilon", "F": "Frank Zeta", "G": "Greg Eta"}
TD = {"A": "Alpha A.", "B": "Beta B.", "C": "Gamma C.", "D": "Delta D.",
      "E": "Epsilon E.", "F": "Zeta F.", "G": "Eta G."}

DAY = dt.date(2019, 6, 3)
LAGGED = DAY + dt.timedelta(days=20)  # comfortably past the 8-day tournament lag


def _match(winner: str, loser: str, *, when: dt.date = DAY,
           tour: str = "ATP", num: int = 1) -> SackmannMatch:
    blank = ServeLine(aces=None, double_faults=None, serve_points=None,
                      first_in=None, first_won=None, second_won=None,
                      serve_games=None, break_points_saved=None,
                      break_points_faced=None)
    return SackmannMatch(
        tourney_id=f"t-{when.isoformat()}-{num}", tourney_name="Test Open",
        tourney_date=when, level=Level.TOUR, surface="Hard", round_name="R32",
        best_of=3, match_num=num, tour=tour,
        winner_id=f"w{winner}", winner_name=FULL[winner],
        loser_id=f"l{loser}", loser_name=FULL[loser],
        winner_rank=None, loser_rank=None, minutes=90, score="6-4 6-4",
        winner_serve=blank, loser_serve=blank, source_file="test",
    )


def _fed(matches: list[SackmannMatch], *, upto: dt.date = LAGGED) -> NetworkEstimator:
    estimator = NetworkEstimator()
    estimator.queue(matches)
    estimator.advance_to(upto)
    return estimator


class TestCommonOpponentGap:
    def test_a_beating_the_same_opponents_b_lost_to_is_a_positive_gap(self) -> None:
        est = _fed([
            _match("A", "C", num=1), _match("A", "D", num=2),
            _match("C", "B", num=3), _match("D", "B", num=4),
        ])
        f = network_features(est, "ATP", TD["A"], TD["B"], when=LAGGED)
        assert f["common_opponent_gap"] > 0

    def test_the_gap_flips_sign_when_the_players_swap(self) -> None:
        """Antisymmetry. A feature that does not flip is reading something about the row
        rather than about the pair, which is how a leaked outcome shows up."""
        est = _fed([
            _match("A", "C", num=1), _match("A", "D", num=2),
            _match("C", "B", num=3), _match("D", "B", num=4),
        ])
        ab = network_features(est, "ATP", TD["A"], TD["B"], when=LAGGED)
        ba = network_features(est, "ATP", TD["B"], TD["A"], when=LAGGED)
        assert ab["common_opponent_gap"] == pytest.approx(-ba["common_opponent_gap"])

    def test_too_few_common_opponents_yields_no_feature_at_all(self) -> None:
        """Absent, not zero. Zero claims the pair is even; absence claims nothing, and the
        rest of this package makes the same distinction."""
        est = _fed([_match("A", "C", num=1), _match("C", "B", num=2)])
        f = network_features(est, "ATP", TD["A"], TD["B"], when=LAGGED)
        assert "common_opponent_gap" not in f
        assert "intransitivity" not in f

    def test_opponents_faced_by_only_one_player_are_not_common(self) -> None:
        """The whole point of the feature is the shared sub-graph. Counting an opponent only
        one player met would make this a worse Elo."""
        est = _fed([
            _match("A", "C", num=1), _match("A", "D", num=2), _match("A", "E", num=3),
            _match("C", "B", num=4), _match("D", "B", num=5),
        ])
        f = network_features(est, "ATP", TD["A"], TD["B"], when=LAGGED)
        assert f["common_opponents"] == 2.0  # C and D, never E


class TestIntransitivity:
    def test_agreeing_opponents_give_near_zero_intransitivity(self) -> None:
        """Every common opponent points the same way: a hierarchy, which the rating
        already represents."""
        est = _fed([
            _match("A", "C", num=1), _match("A", "D", num=2), _match("A", "E", num=3),
            _match("C", "B", num=4), _match("D", "B", num=5), _match("E", "B", num=6),
        ])
        f = network_features(est, "ATP", TD["A"], TD["B"], when=LAGGED)
        assert f["intransitivity"] == pytest.approx(0.0, abs=1e-9)

    def test_contradicting_opponents_give_high_intransitivity(self) -> None:
        """C says A is stronger, D says B is. That is the cycle a scalar cannot hold."""
        est = _fed([
            _match("A", "C", num=1), _match("C", "B", num=2),   # C -> A stronger
            _match("B", "D", num=3), _match("D", "A", num=4),   # D -> B stronger
        ])
        f = network_features(est, "ATP", TD["A"], TD["B"], when=LAGGED)
        assert f["intransitivity"] > 0.5

    def test_intransitivity_is_symmetric_under_a_swap(self) -> None:
        """It measures disagreement, which has no direction. If it flipped it would be
        smuggling the gap in twice."""
        est = _fed([
            _match("A", "C", num=1), _match("C", "B", num=2),
            _match("B", "D", num=3), _match("D", "A", num=4),
        ])
        ab = network_features(est, "ATP", TD["A"], TD["B"], when=LAGGED)
        ba = network_features(est, "ATP", TD["B"], TD["A"], when=LAGGED)
        assert ab["intransitivity"] == pytest.approx(ba["intransitivity"])


class TestKnowledgeTime:
    def test_a_match_inside_the_lag_window_is_not_yet_visible(self) -> None:
        """The archive dates a match by the Monday of its week, so without the lag a
        tournament's later rounds inform its own earlier ones."""
        est = NetworkEstimator()
        est.queue([
            _match("A", "C", num=1), _match("A", "D", num=2),
            _match("C", "B", num=3), _match("D", "B", num=4),
        ])
        est.advance_to(DAY + dt.timedelta(days=2))  # inside the 8-day lag
        assert network_features(est, "ATP", TD["A"], TD["B"], when=DAY) == {}

    def test_advancing_backwards_is_refused(self) -> None:
        est = _fed([_match("A", "C")])
        with pytest.raises(ValueError):
            est.advance_to(DAY - dt.timedelta(days=30))

    def test_tours_do_not_share_a_graph(self) -> None:
        """ATP and WTA are separate namespaces everywhere else in this package; a shared
        surname would otherwise link two different people's results."""
        est = _fed([
            _match("A", "C", num=1, tour="ATP"), _match("A", "D", num=2, tour="ATP"),
            _match("C", "B", num=3, tour="WTA"), _match("D", "B", num=4, tour="WTA"),
        ])
        assert network_features(est, "ATP", TD["A"], TD["B"], when=LAGGED) == {}


class TestShapeAndScale:
    def test_the_gap_is_bounded_and_finite_on_a_perfect_sweep(self) -> None:
        """A 100%-vs-0% record on shared opponents must not produce an infinite logit."""
        est = _fed([
            _match("A", "C", num=1), _match("A", "D", num=2), _match("A", "E", num=3),
            _match("C", "B", num=4), _match("D", "B", num=5), _match("E", "B", num=6),
        ])
        f = network_features(est, "ATP", TD["A"], TD["B"], when=LAGGED)
        assert abs(f["common_opponent_gap"]) < 10.0

    def test_more_shared_evidence_does_not_shrink_the_gap(self) -> None:
        """Shrinkage toward even must weaken with evidence, not strengthen — otherwise the
        feature says the opposite of what more data means."""
        few = _fed([
            _match("A", "C", num=1), _match("A", "D", num=2),
            _match("C", "B", num=3), _match("D", "B", num=4),
        ])
        many = _fed([
            _match("A", "C", num=1), _match("A", "D", num=2), _match("A", "E", num=3),
            _match("A", "F", num=7), _match("A", "G", num=8),
            _match("C", "B", num=4), _match("D", "B", num=5), _match("E", "B", num=6),
            _match("F", "B", num=9), _match("G", "B", num=10),
        ])
        assert (many_gap := network_features(many, "ATP", TD["A"], TD["B"],
                                             when=LAGGED)["common_opponent_gap"]) > 0
        assert many_gap > network_features(few, "ATP", TD["A"], TD["B"],
                                           when=LAGGED)["common_opponent_gap"]

    def test_the_minimum_is_a_declared_constant_not_a_magic_number(self) -> None:
        assert isinstance(MIN_COMMON_OPPONENTS, int) and MIN_COMMON_OPPONENTS >= 2
