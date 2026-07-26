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
    SetBettingView,
    coherence_gap,
    dutch_return,
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
