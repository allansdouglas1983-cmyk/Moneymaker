"""The firing rule, parameterised — tests before the module.

WHY SELECTION IS SEPARATED FROM SIZING. Expected profit is sum(S_i * ev_i). A staking
rule chooses the weights S_i and cannot change any ev_i. Selection chooses WHICH ev_i
enter the sum at all, so it is the only lever that moves the per-bet expectation. Sizing
decides whether you survive long enough to collect whatever selection earns.

The two interact — a threshold that fires fewer bets makes each a larger share of a fixed
risk budget — so the study has to sweep both. That requires a firing rule with every knob
exposed and none of them hard-coded, which is what this module is. It is still measuring
apparatus: it makes no claim about which settings are right.

The properties below are the ones a sweep silently depends on. If thresholds were not
nested, "the best threshold" would not be a well-defined search; if commission did not
move break-even, the 2%-vs-5% comparison would be measuring nothing.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal as D

import pytest

from tennis_edge.staking.engine import Candidate
from tennis_edge.staking.selection import (
    ProbabilitySource,
    SelectionRule,
    break_even,
    edge_of,
)

DAY = dt.date(2020, 6, 1)


def candidate(odds: str = "2.00", p_model: str = "0.60", p_market: str = "0.50",
              support: str = "SUPPORTED", market: str = "1.1") -> Candidate:
    return Candidate(date=DAY, market_id=market, side="a", odds=D(odds),
                     p_model=D(p_model), p_market=D(p_market), won=True,
                     support=support, stratum="THICK")


# ------------------------------------------------------------------------- break-even


def test_break_even_is_the_exact_commission_aware_formula() -> None:
    """1/(1+(O-1)(1-c)). At 2.00 with 5% commission a winning GBP 1 returns 95p profit,
    so the bet needs to win 1/1.95 of the time, not half the time. Getting this wrong is
    invisible in a backtest that gets it wrong consistently."""
    assert break_even(D("2.00"), D("0.05")) == D(1) / D("1.95")
    assert break_even(D("2.00"), D("0")) == D("0.5")


def test_break_even_is_exact_arithmetic_never_float() -> None:
    """A firing threshold compared against a float-contaminated bar fires a different set
    of bets than the one declared, in a way no test of the strategy would reveal."""
    value = break_even(D("3.40"), D("0.05"))
    assert isinstance(value, D)
    with pytest.raises(TypeError):
        break_even(3.40, D("0.05"))  # type: ignore[arg-type]


def test_raising_commission_raises_the_bar_at_every_price() -> None:
    """The direction that made TE-0042 a strategy change and not a restatement."""
    for odds in ("1.30", "1.50", "2.00", "3.00", "5.00"):
        assert break_even(D(odds), D("0.05")) > break_even(D(odds), D("0.02"))


# -------------------------------------------------------------------------- the edge


def test_edge_is_measured_against_break_even_not_against_the_implied_price() -> None:
    """The naive edge p - 1/O ignores commission entirely and is systematically
    optimistic by roughly half a probability point at these prices."""
    c = D("0.05")
    naive = D("0.60") - D(1) / D("2.00")
    real = edge_of(candidate(odds="2.00", p_model="0.60"), c, ProbabilitySource.MODEL)
    assert real < naive


def test_the_market_source_and_the_model_source_select_differently() -> None:
    """The control reading in every measurement this project has published fires the same
    rule off the market's own de-vigged probability. If the two sources cannot be swapped
    the control does not exist."""
    c = D("0.05")
    tip = candidate(p_model="0.60", p_market="0.50")
    assert (edge_of(tip, c, ProbabilitySource.MODEL)
            != edge_of(tip, c, ProbabilitySource.MARKET))


# --------------------------------------------------------------------- the rule itself


def test_thresholds_are_nested_so_the_sweep_is_a_well_defined_search() -> None:
    """A higher minimum edge must fire a SUBSET of what a lower one fires. If that fails,
    'the best threshold' is not a search over nested sets and any sweep result is an
    artefact of which points happened to be sampled."""
    pool = [candidate(odds="2.00", p_model=str(D("0.50") + D(i) / 100), market=f"1.{i}")
            for i in range(1, 30)]
    loose = set(SelectionRule(min_edge=D("0.01")).fired(pool, D("0.05")))
    tight = set(SelectionRule(min_edge=D("0.05")).fired(pool, D("0.05")))
    assert tight <= loose
    assert len(tight) < len(loose), "the tighter threshold must actually bind"


def test_raising_commission_fires_strictly_fewer_bets_at_a_fixed_threshold() -> None:
    """Commission moves the bar, so it is a selection change and not only a settlement
    change. This is the property TE-0042 turned on."""
    pool = [candidate(odds="2.00", p_model=str(D("0.50") + D(i) / 200), market=f"1.{i}")
            for i in range(1, 40)]
    rule = SelectionRule(min_edge=D("0.02"))
    dear = set(rule.fired(pool, D("0.05")))
    cheap = set(rule.fired(pool, D("0.02")))
    assert dear < cheap


def test_the_odds_band_is_inclusive_at_both_ends() -> None:
    """Declared explicitly because a sweep over adjacent bands must partition the pool,
    not overlap it or leave gaps in it."""
    rule = SelectionRule(min_edge=D("0"), min_odds=D("2.00"), max_odds=D("3.00"))
    fired = rule.fired([candidate(odds="1.99", p_model="0.99", market="a"),
                        candidate(odds="2.00", p_model="0.99", market="b"),
                        candidate(odds="3.00", p_model="0.99", market="c"),
                        candidate(odds="3.01", p_model="0.99", market="d")], D("0.05"))
    assert [c.market_id for c in fired] == ["b", "c"]


def test_the_support_filter_selects_a_subset_and_never_invents_a_bet() -> None:
    """Restricting to fills the record supports must only ever REMOVE bets. A filter that
    changed which bets fire would confound the fill-evidence reading with a selection
    change, and the gap between the two readings is the whole point of measuring them."""
    pool = [candidate(support="SUPPORTED", market="1.1", p_model="0.70"),
            candidate(support="UNSUPPORTED", market="1.2", p_model="0.70"),
            candidate(support="NO_EVIDENCE", market="1.3", p_model="0.70")]
    everything = set(SelectionRule(min_edge=D("0.02")).fired(pool, D("0.05")))
    supported = set(SelectionRule(min_edge=D("0.02"),
                                  require_support=("SUPPORTED",)).fired(pool, D("0.05")))
    assert supported < everything
    assert all(c.support == "SUPPORTED" for c in supported)


def test_a_bet_exactly_on_the_threshold_does_not_fire() -> None:
    """Declared, because 'edge >= threshold' and 'edge > threshold' give different bet
    counts and the difference is not visible in any summary statistic. Strictly greater:
    a bet with exactly zero edge over the bar is not an opportunity."""
    odds, c = D("2.00"), D("0.05")
    exact = break_even(odds, c) + D("0.02")
    pool = [Candidate(date=DAY, market_id="1.1", side="a", odds=odds, p_model=exact,
                      p_market=D("0.5"), won=True, support="SUPPORTED", stratum="THICK")]
    assert SelectionRule(min_edge=D("0.02")).fired(pool, c) == []
    assert len(SelectionRule(min_edge=D("0.0199")).fired(pool, c)) == 1


def test_selection_never_reorders_or_duplicates_the_pool() -> None:
    """The engine replays in date order and settles each market once. A selection rule
    that duplicated a candidate would double an exposure; one that reordered would change
    nothing today but would silently matter the moment a rule reads its own history."""
    pool = [candidate(market=f"1.{i}", p_model="0.70") for i in range(6)]
    fired = SelectionRule(min_edge=D("0.02")).fired(pool, D("0.05"))
    assert [c.market_id for c in fired] == [c.market_id for c in pool]
    assert len({c.market_id for c in fired}) == len(fired)


def test_an_unfireable_pool_returns_empty_rather_than_relaxing_anything() -> None:
    """The refusal has to be reachable. A rule that quietly lowered its bar to produce a
    bet is a tipping engine, which SPEC-047 prohibits by name."""
    pool = [candidate(odds="1.20", p_model="0.10", market=f"1.{i}") for i in range(5)]
    assert SelectionRule(min_edge=D("0.02")).fired(pool, D("0.05")) == []
