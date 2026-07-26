"""Tests for cross-market coherence between Match Odds and Set Betting.

These two markets are related by **identity, not by model**: for a best-of-three,
P(A wins the match) is exactly P(A wins 2-0) + P(A wins 2-1). Detecting a gap between them
needs no forecast, no rating and no opinion about tennis — only arithmetic. That makes it a
completely different kind of claim from everything else in this package, and the tests are
written to keep it that way: nothing here may depend on a model.

Two quantities, and they must not be confused. The **coherence gap** is measured on de-vigged
probabilities and says how much the two markets disagree. The **dutch condition** is measured
on the actual best-back prices and says whether that disagreement can be transacted. A gap is
common; a transactable one is the rare and valuable case, and reporting the first as though
it were the second is the obvious way this goes wrong.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from tennis_edge.xmarket import (
    Leg,
    align_sides,
    SetBettingView,
    coherence_gap,
    dutch_return,
    fillable_dutch,
    parse_set_runner,
)


class TestParsingRunners:
    def test_a_best_of_three_runner_parses(self) -> None:
        assert parse_set_runner("Bonzi 2-0") == ("Bonzi", 2, 0)

    def test_a_best_of_five_runner_parses(self) -> None:
        assert parse_set_runner("G Diallo 3-2") == ("G Diallo", 3, 2)

    def test_a_multi_word_name_keeps_its_spaces(self) -> None:
        assert parse_set_runner("Van De Zandschulp 2-1") == ("Van De Zandschulp", 2, 1)

    def test_a_runner_without_a_score_is_refused(self) -> None:
        assert parse_set_runner("Three Sets") is None

    def test_an_empty_name_is_refused(self) -> None:
        assert parse_set_runner("") is None

    def test_a_malformed_score_is_refused(self) -> None:
        assert parse_set_runner("Bonzi 2-x") is None


class TestCoherenceGap:
    def test_perfectly_coherent_markets_have_no_gap(self) -> None:
        view = SetBettingView(probability_a=0.60, probability_b=0.40)
        assert coherence_gap(match_odds_a=0.60, set_betting=view) == pytest.approx(0.0)

    def test_the_gap_is_signed_toward_match_odds(self) -> None:
        """Positive means Match Odds rates A higher than Set Betting does."""
        view = SetBettingView(probability_a=0.55, probability_b=0.45)
        assert coherence_gap(match_odds_a=0.60, set_betting=view) == pytest.approx(0.05)

    def test_the_gap_reverses_with_the_disagreement(self) -> None:
        view = SetBettingView(probability_a=0.65, probability_b=0.35)
        assert coherence_gap(match_odds_a=0.60, set_betting=view) == pytest.approx(-0.05)


class TestDutchReturn:
    """The transactable question: can the disagreement be locked in at real prices?"""

    def test_a_fair_pair_of_markets_returns_nothing(self) -> None:
        """Two coherent 2.0/2.0 books leave exactly nothing after staking both sides."""
        assert dutch_return(match_odds_back_a=Decimal("2.0"),
                            set_back_prices_b=(Decimal("4.0"), Decimal("4.0")),
                            commission=Decimal("0")) == pytest.approx(0.0)

    def test_a_genuinely_mispriced_pair_returns_a_profit(self) -> None:
        assert dutch_return(match_odds_back_a=Decimal("2.5"),
                            set_back_prices_b=(Decimal("5.0"), Decimal("5.0")),
                            commission=Decimal("0")) > 0.0

    def test_commission_reduces_the_return(self) -> None:
        """Charged on winnings, so it eats a thin lock — which is most of them."""
        gross = dutch_return(match_odds_back_a=Decimal("2.5"),
                             set_back_prices_b=(Decimal("5.0"), Decimal("5.0")),
                             commission=Decimal("0"))
        net = dutch_return(match_odds_back_a=Decimal("2.5"),
                           set_back_prices_b=(Decimal("5.0"), Decimal("5.0")),
                           commission=Decimal("0.02"))
        assert net < gross

    def test_an_overround_pair_returns_a_loss(self) -> None:
        assert dutch_return(match_odds_back_a=Decimal("1.8"),
                            set_back_prices_b=(Decimal("3.6"), Decimal("3.6")),
                            commission=Decimal("0.02")) < 0.0

    def test_a_missing_leg_is_refused(self) -> None:
        """A partial book cannot be dutched, and pretending otherwise invents a lock."""
        with pytest.raises(ValueError, match="at least one"):
            dutch_return(match_odds_back_a=Decimal("2.0"), set_back_prices_b=(),
                         commission=Decimal("0.02"))

    def test_odds_at_or_below_evens_are_refused(self) -> None:
        with pytest.raises(ValueError, match="above 1"):
            dutch_return(match_odds_back_a=Decimal("1.0"),
                         set_back_prices_b=(Decimal("4.0"),), commission=Decimal("0"))


class TestSetBettingView:
    def test_the_two_sides_sum_to_one(self) -> None:
        """De-vigged, so the view is a probability distribution and not a book."""
        view = SetBettingView(probability_a=0.6, probability_b=0.4)
        assert view.probability_a + view.probability_b == pytest.approx(1.0)

    def test_a_view_that_does_not_sum_to_one_is_refused(self) -> None:
        with pytest.raises(ValueError, match="sum to 1"):
            SetBettingView(probability_a=0.6, probability_b=0.6)


class TestSizeAwareness:
    """The correction that killed the first version of this scan.

    A best-back price is only real up to the size available behind it. Set Betting is thin,
    and a leg showing 1000.0 with two pounds behind it is not a price anyone can take — but
    it contributes 0.001 to the implied total, which is enough on its own to manufacture a
    six-hundred-percent "locked return". The first scan reported exactly that, and it was
    entirely an artefact of ignoring size.
    """

    def test_a_fillable_position_reports_its_limiting_stake(self) -> None:
        legs = (Leg(price=Decimal("2.0"), size=100.0),
                Leg(price=Decimal("4.0"), size=100.0),
                Leg(price=Decimal("4.0"), size=100.0))
        result = fillable_dutch(legs, commission=Decimal("0"))
        assert result is not None
        assert result.max_total_stake > 0.0

    def test_a_leg_with_no_size_makes_the_position_unfillable(self) -> None:
        legs = (Leg(price=Decimal("2.5"), size=100.0),
                Leg(price=Decimal("5.0"), size=0.0),
                Leg(price=Decimal("5.0"), size=100.0))
        assert fillable_dutch(legs, commission=Decimal("0")) is None

    def test_a_leg_below_the_minimum_size_makes_it_unfillable(self) -> None:
        legs = (Leg(price=Decimal("2.5"), size=100.0),
                Leg(price=Decimal("5.0"), size=1.0),
                Leg(price=Decimal("5.0"), size=100.0))
        assert fillable_dutch(legs, commission=Decimal("0"),
                              minimum_size=10.0) is None

    def test_the_stake_is_limited_by_the_thinnest_leg(self) -> None:
        """Doubling the thinnest leg's size must not more than double the position."""
        thin = fillable_dutch((Leg(price=Decimal("2.0"), size=1000.0),
                               Leg(price=Decimal("4.0"), size=20.0),
                               Leg(price=Decimal("4.0"), size=1000.0)),
                              commission=Decimal("0"))
        thick = fillable_dutch((Leg(price=Decimal("2.0"), size=1000.0),
                                Leg(price=Decimal("4.0"), size=40.0),
                                Leg(price=Decimal("4.0"), size=1000.0)),
                               commission=Decimal("0"))
        assert thin is not None and thick is not None
        assert thick.max_total_stake == pytest.approx(2 * thin.max_total_stake)

    def test_the_return_matches_the_price_only_calculation(self) -> None:
        """Size limits how much, never whether it is profitable."""
        legs = (Leg(price=Decimal("2.5"), size=500.0),
                Leg(price=Decimal("5.0"), size=500.0),
                Leg(price=Decimal("5.0"), size=500.0))
        result = fillable_dutch(legs, commission=Decimal("0.02"))
        assert result is not None
        assert result.unit_return == pytest.approx(dutch_return(
            match_odds_back_a=Decimal("2.5"),
            set_back_prices_b=(Decimal("5.0"), Decimal("5.0")),
            commission=Decimal("0.02")))


class TestSideAlignment:
    """The bug that produced a 380% "locked return" even after size was enforced.

    Match Odds lists its two runners in Betfair's order; Set Betting names them inside the
    runner strings. The first scan grouped set scores alphabetically and paired them with
    Match Odds by position, so whenever those two orders disagreed it backed one player on
    Match Odds *and* that same player's set scores — covering one outcome twice and leaving
    the other uncovered. That is not a dutch, it is an unhedged double, and it can report any
    number at all.

    Sides must be matched by name across the two markets, and a pair that cannot be matched
    must be refused rather than assumed aligned.
    """

    def test_sides_are_matched_by_name(self) -> None:
        assert align_sides(
            match_odds_names=("Zverev A.", "Alcaraz C."),
            set_betting_names=("Alcaraz C. 2-0", "Alcaraz C. 2-1",
                               "Zverev A. 2-0", "Zverev A. 2-1"),
        ) == ((2, 3), (0, 1))

    def test_alphabetical_order_is_not_assumed(self) -> None:
        """The Match Odds order here is the reverse of alphabetical — the failing case."""
        first, second = align_sides(
            match_odds_names=("Zverev A.", "Alcaraz C."),
            set_betting_names=("Alcaraz C. 2-0", "Alcaraz C. 2-1",
                               "Zverev A. 2-0", "Zverev A. 2-1"),
        )
        assert first != (0, 1)

    def test_a_name_that_does_not_appear_is_refused(self) -> None:
        assert align_sides(
            match_odds_names=("Zverev A.", "Sinner J."),
            set_betting_names=("Alcaraz C. 2-0", "Alcaraz C. 2-1",
                               "Zverev A. 2-0", "Zverev A. 2-1"),
        ) is None

    def test_an_unparseable_runner_is_refused(self) -> None:
        assert align_sides(
            match_odds_names=("A", "B"),
            set_betting_names=("A 2-0", "Three Sets"),
        ) is None

    def test_a_side_with_no_scores_is_refused(self) -> None:
        assert align_sides(
            match_odds_names=("A", "B"),
            set_betting_names=("A 2-0", "A 2-1"),
        ) is None
