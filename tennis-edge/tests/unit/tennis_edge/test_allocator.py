"""The bank allocator's guarantees. Every one of these is a property somebody could
otherwise quietly break while 'improving' the staking rule."""
from __future__ import annotations

from decimal import Decimal as D

import pytest

from tennis_edge.allocator import (
    AllocationPolicy,
    Tip,
    allocate,
    break_even,
    kelly_fraction,
)

FAV = Tip("fav", D("1.80"), D("0.60"))
DOG = Tip("dog", D("6.00"), D("0.19"))
LIVE = AllocationPolicy(kelly_fraction=D("0.33"))


def test_lambda_zero_reproduces_the_flat_rule_exactly() -> None:
    """SPEC-060 mandates a fixed minimum stake. The allocator must be installable
    WITHOUT changing behaviour, so that activating it is a separate, deliberate act."""
    for a in allocate([FAV, DOG], D(1000), D(1000), AllocationPolicy()):
        assert a.stake == 0


def test_a_longshot_gets_a_smaller_fraction_than_a_favourite_at_the_same_edge() -> None:
    """The odds-dependence that makes this an allocator rather than a flat stake. At an
    identical edge the longshot is the more dangerous bet: the loss branch is far more
    likely, so Kelly stakes it smaller. This falls out of f = p - (1-p)/b; no separate
    rule is needed, and if it ever stops holding the formula has been broken."""
    c = D("0.05")
    edge = D("0.03")
    fav = kelly_fraction(D("1.80"), break_even(D("1.80"), c) + edge, c)
    dog = kelly_fraction(D("6.00"), break_even(D("6.00"), c) + edge, c)
    assert dog < fav


def test_no_edge_is_refused_and_never_staked() -> None:
    """A bet whose conservative probability sits below break-even is not a small bet.
    It is not a bet."""
    hopeless = Tip("hopeless", D("2.00"), D("0.40"))
    result = allocate([hopeless], D(1000), D(1000), LIVE)[0]
    assert result.stake == 0
    assert result.reason == "NO_EDGE"


def test_a_stake_below_the_exchange_minimum_is_skipped_not_rounded_up() -> None:
    """THE most important guarantee here. Rounding GBP 1.30 up to the GBP 2 minimum is a
    54% increase in risk on that bet, applied silently and systematically. Do that across
    a card and a carefully shrunk plan becomes a flat stake at several times the intended
    exposure — while still reporting itself as risk-managed."""
    result = allocate([FAV], D(100), D(100), LIVE)[0]
    assert result.stake == 0
    assert result.reason == "BELOW_MIN_STAKE"
    assert result.fraction > 0, "the intended fraction is still reported, so the skip is visible"


def test_the_daily_cap_scales_the_whole_card_proportionally() -> None:
    """Four simultaneous bets are not one bet four times. When the day's total breaches
    the cap every stake shrinks by the same factor, so the relative sizing the model
    asked for survives."""
    tips = [Tip(f"t{i}", D("2.00"), D("0.62")) for i in range(6)]
    result = allocate(tips, D(5000), D(5000), LIVE)
    live = [a for a in result if a.stake > 0]
    assert len(live) == 6
    stakeable = D(5000) - D(5000) * LIVE.reserve_floor
    assert sum(a.stake for a in live) <= stakeable * LIVE.max_daily + D("0.06")
    assert len({a.stake for a in live}) == 1, "identical tips must get identical stakes"


def test_no_single_bet_exceeds_the_single_cap_however_good_it_looks() -> None:
    """A probability estimate that is simply wrong is the failure this cap exists for."""
    certain = Tip("certain", D("2.00"), D("0.95"))
    result = allocate([certain], D(10000), D(10000), LIVE)[0]
    stakeable = D(10000) - D(10000) * LIVE.reserve_floor
    assert result.stake <= stakeable * LIVE.max_single


def test_a_drawdown_halves_exposure_without_anyone_intervening() -> None:
    """A drawdown is evidence the edge estimate may be optimistic. Kelly is famously
    unforgiving of overbetting, so exposure falls automatically rather than waiting for
    a human to notice a bad run."""
    # A modest edge, deliberately: at a large one both cases pin to max_single and the
    # brake is invisible behind the cap.
    tips = [Tip("t", D("2.00"), D("0.54"))]
    at_peak = allocate(tips, D(5000), D(5000), LIVE)[0]
    drawn = allocate(tips, D(5000), D(10000), LIVE)[0]
    assert at_peak.fraction < LIVE.max_single, "guard: the cap must not be what is binding"
    assert drawn.fraction == pytest.approx(at_peak.fraction / 2, rel=D("0.01"))


def test_the_reserve_floor_stops_betting_rather_than_betting_the_last_pound() -> None:
    """What keeps the system alive to bet next week."""
    result = allocate([FAV], D(100), D(1000), LIVE)
    assert all(a.stake == 0 for a in result)
    assert all(a.reason == "RESERVE_FLOOR_REACHED" for a in result)


def test_stakes_scale_with_the_bank_in_both_directions() -> None:
    """The whole point: the bank drives the stake. Double the bank, double the stake;
    halve it and the stake halves. That is what a flat stake cannot do."""
    tips = [Tip("t", D("2.00"), D("0.62"))]
    small = allocate(tips, D(1000), D(1000), LIVE)[0].stake
    large = allocate(tips, D(2000), D(2000), LIVE)[0].stake
    assert large == pytest.approx(small * 2, rel=D("0.01"))


def test_commission_lowers_the_fraction() -> None:
    """Commission is charged on winnings, so it shrinks the payoff branch and therefore
    the growth-optimal stake. A rule ignoring it overbets."""
    cheap = kelly_fraction(D("2.00"), D("0.60"), D("0.02"))
    dear = kelly_fraction(D("2.00"), D("0.60"), D("0.05"))
    assert dear < cheap
