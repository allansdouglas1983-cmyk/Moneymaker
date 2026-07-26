"""Tests for exact-cover arbitrage across every market on one match.

TE-0009 tested one market pair. This is the complete version: Match Odds, Set Betting and
Number of Sets are all **partitions of the same outcome space** — the final set score. Any
selection of runners whose outcome sets are disjoint and together cover everything is a
guaranteed position, whichever markets those runners came from.

That matters because a two-market check can only find a mispricing that shows up between
those two books. Searching every cover finds the cheapest way to buy the whole space, which
is the strongest form of the question and the one that cannot be improved on by adding
another pair.

The tests are about the two ways an exact cover lies: a selection that misses an outcome
(unhedged, and it will look profitable exactly when it is riskiest) and one that covers an
outcome twice (paid for twice, so it understates the return and hides nothing dangerous but
is still wrong).
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from tennis_edge.cover import (
    best_cover,
    covered_outcomes,
    outcome_space,
)
from tennis_edge.xmarket import Leg


class TestOutcomeSpace:
    def test_best_of_three_has_four_outcomes(self) -> None:
        assert outcome_space(3) == {("A", 2, 0), ("A", 2, 1), ("B", 2, 0), ("B", 2, 1)}

    def test_best_of_five_has_six_outcomes(self) -> None:
        assert len(outcome_space(5)) == 6

    def test_an_unsupported_format_is_refused(self) -> None:
        with pytest.raises(ValueError, match="best_of"):
            outcome_space(4)


class TestCoveredOutcomes:
    def test_match_odds_covers_a_whole_side(self) -> None:
        assert covered_outcomes("MATCH_ODDS", "A", sides=("A", "B"), best_of=3) == {
            ("A", 2, 0), ("A", 2, 1)}

    def test_set_betting_covers_one_scoreline(self) -> None:
        assert covered_outcomes("SET_BETTING", "A 2-1", sides=("A", "B"),
                                best_of=3) == {("A", 2, 1)}

    def test_number_of_sets_covers_both_players_at_that_length(self) -> None:
        assert covered_outcomes("NUMBER_OF_SETS", "Three Sets", sides=("A", "B"),
                                best_of=3) == {("A", 2, 1), ("B", 2, 1)}

    def test_number_of_sets_scales_to_best_of_five(self) -> None:
        assert covered_outcomes("NUMBER_OF_SETS", "Five Sets", sides=("A", "B"),
                                best_of=5) == {("A", 3, 2), ("B", 3, 2)}

    def test_a_length_impossible_in_the_format_is_refused(self) -> None:
        """"Five Sets" on a best-of-three is a market mismatch, not an empty cover."""
        assert covered_outcomes("NUMBER_OF_SETS", "Five Sets", sides=("A", "B"),
                                best_of=3) is None

    def test_an_unknown_market_type_is_refused(self) -> None:
        assert covered_outcomes("HANDICAP", "A -2.5", sides=("A", "B"), best_of=3) is None

    def test_an_unrecognised_runner_is_refused(self) -> None:
        assert covered_outcomes("NUMBER_OF_SETS", "Some Sets", sides=("A", "B"),
                                best_of=3) is None


def leg(price: str, size: float = 1000.0) -> Leg:
    return Leg(price=Decimal(price), size=size)


class TestBestCover:
    def test_it_finds_the_two_leg_match_odds_cover(self) -> None:
        space = outcome_space(3)
        candidates = [
            (frozenset({("A", 2, 0), ("A", 2, 1)}), leg("2.0")),
            (frozenset({("B", 2, 0), ("B", 2, 1)}), leg("2.0")),
        ]
        found = best_cover(candidates, space, commission=Decimal("0"))
        assert found is not None
        assert len(found.legs) == 2

    def test_it_prefers_the_cheaper_cover_across_markets(self) -> None:
        """The point of searching: the best cover need not come from one market."""
        space = outcome_space(3)
        candidates = [
            (frozenset({("A", 2, 0), ("A", 2, 1)}), leg("2.0")),
            (frozenset({("B", 2, 0), ("B", 2, 1)}), leg("2.0")),
            (frozenset({("B", 2, 0)}), leg("10.0")),
            (frozenset({("B", 2, 1)}), leg("10.0")),
        ]
        found = best_cover(candidates, space, commission=Decimal("0"))
        assert found is not None
        assert found.unit_return > 0.0

    def test_an_incomplete_candidate_set_yields_nothing(self) -> None:
        """Missing an outcome must return None, never a partial cover."""
        space = outcome_space(3)
        candidates = [(frozenset({("A", 2, 0), ("A", 2, 1)}), leg("2.0"))]
        assert best_cover(candidates, space, commission=Decimal("0")) is None

    def test_overlapping_runners_are_never_combined(self) -> None:
        """Two runners covering the same outcome would be paid for twice."""
        space = outcome_space(3)
        candidates = [
            (frozenset({("A", 2, 0), ("A", 2, 1)}), leg("2.0")),
            (frozenset({("A", 2, 0), ("B", 2, 0)}), leg("2.0")),
            (frozenset({("B", 2, 0), ("B", 2, 1)}), leg("2.0")),
        ]
        found = best_cover(candidates, space, commission=Decimal("0"))
        assert found is not None
        chosen = [outcomes for outcomes, _leg in found.legs]
        assert sum(len(c) for c in chosen) == len(space)

    def test_commission_reduces_the_return(self) -> None:
        space = outcome_space(3)
        candidates = [
            (frozenset({("A", 2, 0), ("A", 2, 1)}), leg("2.5")),
            (frozenset({("B", 2, 0), ("B", 2, 1)}), leg("2.5")),
        ]
        gross = best_cover(candidates, space, commission=Decimal("0"))
        net = best_cover(candidates, space, commission=Decimal("0.02"))
        assert gross is not None and net is not None
        assert net.unit_return < gross.unit_return

    def test_a_thin_leg_disqualifies_the_cover_that_uses_it(self) -> None:
        """Size decides whether a position exists — the TE-0009 correction, kept."""
        space = outcome_space(3)
        candidates = [
            (frozenset({("A", 2, 0), ("A", 2, 1)}), leg("2.0")),
            (frozenset({("B", 2, 0), ("B", 2, 1)}), leg("2.0", size=1.0)),
        ]
        assert best_cover(candidates, space, commission=Decimal("0"),
                          minimum_size=10.0) is None

    def test_it_reports_the_stake_the_thinnest_leg_allows(self) -> None:
        space = outcome_space(3)
        candidates = [
            (frozenset({("A", 2, 0), ("A", 2, 1)}), leg("2.0", size=50.0)),
            (frozenset({("B", 2, 0), ("B", 2, 1)}), leg("2.0", size=1000.0)),
        ]
        found = best_cover(candidates, space, commission=Decimal("0"))
        assert found is not None
        assert found.max_total_stake == pytest.approx(100.0)
