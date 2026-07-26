"""Cross-book consensus tests.

Two of these exist because the first version of this module got them wrong, and both errors
flattered the result: CLV was measured against the same consensus that selected the bet (so
every variant, including the losers, reported positive value), and "best variant" ranked on
raw ROI (so a 54-bet strategy betting into a panel *average* won a 45-variant sweep).
"""
from __future__ import annotations

import datetime as dt

import pytest

from tennis_edge.consensus import (
    ConsensusConfig,
    StrategyResult,
    VariantSweep,
    consensus_probabilities,
    evaluate,
    find_value_bets,
)
from tennis_edge.corpus import Completion, Match, OddsQuotes
from tennis_edge.devig import DevigMethod
from tennis_edge.metrics import BettingSummary


def _match(day: int, **odds: float | None) -> Match:
    return Match(
        match_date=dt.date(2024, 1, day), tour="ATP", tournament="T", location="L",
        tier="ATP250", court="Outdoor", surface="Hard", round_name="R1", best_of=3,
        player_a="A", player_b="B", winner_is_a=True,
        rank_a=1, rank_b=2, points_a=None, points_b=None,
        games_a=12, games_b=7, sets_a=2, sets_b=0, completion=Completion.COMPLETED,
        odds=OddsQuotes(**odds), source_file="test",
    )


def test_consensus_pools_in_logit_space_not_probability_space() -> None:
    """Averaging probabilities drags a consensus toward 0.5 and costs it resolution, which
    is the one thing a sharp market has that a model does not. Logit pooling preserves it,
    so the pooled value must sit off the arithmetic mean when the books disagree."""
    match = _match(1, pinnacle_a=1.5, pinnacle_b=2.6, b365_a=2.5, b365_b=1.55)
    pooled = consensus_probabilities(match, ("pinnacle", "b365"))
    assert pooled is not None
    single_a = consensus_probabilities(match, ("pinnacle",))
    single_b = consensus_probabilities(match, ("b365",))
    assert single_a is not None and single_b is not None
    arithmetic = (single_a[0] + single_b[0]) / 2.0
    assert pooled[0] != pytest.approx(arithmetic, abs=1e-9)
    assert sum(pooled) == pytest.approx(1.0, abs=1e-12)


def test_consensus_is_none_when_no_book_priced_the_match() -> None:
    assert consensus_probabilities(_match(1), ("pinnacle",)) is None


def test_a_book_inside_its_own_consensus_is_flagged() -> None:
    config = ConsensusConfig(consensus_books=("pinnacle", "b365"), target_book="b365")
    warning = config.circularity_warning()
    assert warning is not None and "inside its own consensus" in warning


def test_a_panel_aggregate_target_is_flagged_as_unattainable() -> None:
    """Max and Avg are statistics over a scraped panel, not counters you can bet at."""
    for book in ("max", "avg"):
        config = ConsensusConfig(consensus_books=("pinnacle",), target_book=book)
        warning = config.circularity_warning()
        assert warning is not None and "not a takeable price" in warning


def test_the_clean_pairing_carries_no_caveat() -> None:
    config = ConsensusConfig(consensus_books=("pinnacle",), target_book="b365")
    assert config.circularity_warning() is None
    assert config.independent and config.attainable


def test_clv_measured_against_a_consensus_book_is_refused() -> None:
    """The bug that made every variant look good: scoring value against the same number
    that picked the bet is a tautology, not a measurement."""
    config = ConsensusConfig(
        consensus_books=("pinnacle",), target_book="b365", clv_reference="pinnacle"
    )
    with pytest.raises(ValueError, match="circular"):
        evaluate([_match(1, pinnacle_a=2.0, pinnacle_b=2.0, b365_a=3.0, b365_b=1.4)], config)


def test_a_longer_price_than_the_consensus_qualifies() -> None:
    match = _match(1, pinnacle_a=2.0, pinnacle_b=2.0, b365_a=2.6, b365_b=1.5)
    bets = find_value_bets(match, ConsensusConfig())
    assert [b.side for b in bets] == ["A"]
    assert bets[0].edge > 0.0
    assert bets[0].struck_price < bets[0].quoted_price, "slippage must worsen the price"


def test_a_price_matching_the_consensus_does_not_qualify() -> None:
    match = _match(1, pinnacle_a=2.0, pinnacle_b=2.0, b365_a=1.95, b365_b=1.95)
    assert find_value_bets(match, ConsensusConfig()) == []


def test_commission_is_charged_on_an_exchange_target_but_not_a_bookmaker() -> None:
    assert ConsensusConfig(target_book="b365").effective_commission == 0.0
    assert ConsensusConfig(target_book="betfair").effective_commission > 0.0


def test_commission_makes_a_marginal_bet_stop_qualifying() -> None:
    """The edge must survive the cost of placing it, not merely exist before costs."""
    odds = dict(pinnacle_a=2.0, pinnacle_b=2.0, betfair_a=2.06, betfair_b=1.95)
    free = find_value_bets(_match(1, **odds),
                           ConsensusConfig(target_book="betfair", commission=0.0))
    charged = find_value_bets(_match(1, **odds),
                              ConsensusConfig(target_book="betfair", commission=0.20))
    assert len(free) > len(charged)


def test_price_band_and_tour_filters_are_applied() -> None:
    match = _match(1, pinnacle_a=2.0, pinnacle_b=2.0, b365_a=2.6, b365_b=1.5)
    assert find_value_bets(match, ConsensusConfig(min_price=3.0)) == []
    assert find_value_bets(match, ConsensusConfig(tours=frozenset({"WTA"}))) == []


def test_evaluate_refuses_a_window_with_no_qualifying_bets() -> None:
    match = _match(1, pinnacle_a=2.0, pinnacle_b=2.0, b365_a=1.9, b365_b=1.9)
    with pytest.raises(ValueError):
        evaluate([match], ConsensusConfig())


def _result(roi: float, bets: int, warning: str | None) -> StrategyResult:
    summary = BettingSummary(
        bets=bets, staked=float(bets), profit=roi * bets, roi=roi, mean_clv=None,
        max_drawdown=0.0, t_stat=0.0, roi_ci95=(roi, roi), bets_for_significance=None,
    )
    return StrategyResult(config=ConsensusConfig(), summary=summary, warning=warning)


def test_best_ignores_a_tiny_sample_however_good_it_looks() -> None:
    """The 54-bet, +98% ROI variant that won the first sweep must not be selectable."""
    sweep = VariantSweep()
    sweep.add(_result(0.99, 54, None))
    sweep.add(_result(0.03, 2000, None))
    best = sweep.best(min_bets=500)
    assert best is not None and best.summary.bets == 2000


def test_best_ignores_a_caveated_variant_by_default() -> None:
    sweep = VariantSweep()
    sweep.add(_result(0.50, 5000, "unattainable panel average"))
    sweep.add(_result(0.01, 5000, None))
    best = sweep.best(min_bets=500)
    assert best is not None and best.summary.roi == pytest.approx(0.01)


def test_a_variant_that_produced_no_bets_still_counts_as_a_trial() -> None:
    """Silently dropping empty variants would understate the trial count, which is exactly
    what the deflated Sharpe correction needs to be honest."""
    sweep = VariantSweep()
    sweep.add(_result(0.01, 1000, None))
    sweep.skip("some variant", "no qualifying bets")
    assert sweep.trials == 2


def test_proportional_devig_inflates_the_longshot_and_so_its_apparent_edge() -> None:
    """Margin sits disproportionately on longshots, so proportional removal credits the
    underdog with probability it does not have — and that surplus flows straight through
    into a larger apparent edge on the underdog side. This is the mechanism by which a
    de-vig choice invents value, which is why POWER is the default everywhere here."""
    match = _match(1, pinnacle_a=1.25, pinnacle_b=4.5, b365_a=1.28, b365_b=5.0)
    proportional = consensus_probabilities(match, ("pinnacle",), DevigMethod.PROPORTIONAL)
    power = consensus_probabilities(match, ("pinnacle",), DevigMethod.POWER)
    assert proportional is not None and power is not None
    assert proportional[1] > power[1], "proportional must overstate the longshot"

    def edge_on_b(method: DevigMethod) -> float:
        bets = find_value_bets(
            match, ConsensusConfig(method=method, min_edge=-1.0, apply_slippage=False)
        )
        return next(b.edge for b in bets if b.side == "B")

    assert edge_on_b(DevigMethod.PROPORTIONAL) > edge_on_b(DevigMethod.POWER)
