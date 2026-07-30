"""The rule catalogue's defining identities — tests before the rules exist.

Every rule below is a verified formula from DR-TENNIS-STAKING-006-MATRIX. These tests pin
each rule's DEFINING identity — the one property that makes it that rule and not a
neighbour — so a later edit cannot quietly turn one candidate into another while keeping
its name (the exact failure the verification round caught in the literature).
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal as D

from tennis_edge.staking.engine import Candidate, DayState
from tennis_edge.staking.rules import (
    cppi,
    fixed_profit_net,
    flat,
    hb_cap,
    proportional,
    sqrt_profit,
    tipp,
    variance_ladder,
)

DAY = dt.date(2020, 6, 1)


def state(bank: int = 10_000, peak: int = 10_000) -> DayState:
    return DayState(opening_bank_pence=bank, peak_bank_pence=peak, floor_pence=0,
                    min_stake_pence=100, commission=D("0.02"), day_index=0,
                    bets_settled=0)


def bet(odds: str, market: str = "1.1") -> Candidate:
    return Candidate(date=DAY, market_id=market, side="a", odds=D(odds),
                     p_model=D("0.6"), p_market=D("0.5"), won=True,
                     support="SUPPORTED", stratum="THICK")


def test_flat_ignores_everything() -> None:
    rule = flat(100)
    assert rule([bet("1.50"), bet("6.00", "1.2")], state(500)) == [100, 100]
    assert rule([bet("2.00")], state(1_000_000)) == [100]


def test_proportional_stakes_a_fraction_of_the_morning_bank() -> None:
    rule = proportional(D("0.02"))
    assert rule([bet("2.00")], state(10_000)) == [200]
    assert rule([bet("2.00")], state(5_000)) == [100]


def test_cppi_stakes_the_multiple_of_the_cushion_and_zero_below_the_floor() -> None:
    """s = m*(W-F). The defining identity: the stake reads the CUSHION, not the bank."""
    rule = cppi(multiplier=D("0.5"), floor_pence=7_000)
    assert rule([bet("2.00")], state(10_000)) == [1_500]
    assert rule([bet("2.00")], state(7_000)) == [0], "at the floor the cushion is zero"
    assert rule([bet("2.00")], state(6_000)) == [0], "below the floor it never goes negative"


def test_tipp_floor_ratchets_with_the_high_water_mark() -> None:
    """F = max(F0, phi*HWM): the floor rises with the peak and NEVER falls back."""
    rule = tipp(multiplier=D("1"), base_floor_pence=7_000, ratchet=D("0.8"))
    # Peak 10,000: floor = max(7000, 8000) = 8000; cushion 2000.
    assert rule([bet("2.00")], state(10_000, peak=10_000)) == [2_000]
    # Peak grew to 15,000 while bank fell back: floor = 12,000 > bank -> no bet.
    assert rule([bet("2.00")], state(11_000, peak=15_000)) == [0]


def test_hb_cap_binds_the_base_rule_to_the_drawdown_budget() -> None:
    """stake <= W - (1-d_max)*HWM: the probability-one drawdown cap. At the HWM the cap
    is d_max*HWM; deep in drawdown it reaches zero before the bound is breached."""
    base = proportional(D("0.50"))
    rule = hb_cap(base, max_drawdown=D("0.30"))
    # At peak: base wants 5,000, cap allows 3,000.
    assert rule([bet("2.00")], state(10_000, peak=10_000)) == [3_000]
    # Bank 7,100 on peak 10,000: cap = 7,100-7,000 = 100.
    assert rule([bet("2.00")], state(7_100, peak=10_000)) == [100]
    # At the bound exactly: cap 0, whatever the base wants.
    assert rule([bet("2.00")], state(7_000, peak=10_000)) == [0]


def test_variance_ladder_equalises_per_bet_risk_across_odds() -> None:
    """k(O) proportional to 1/sqrt((O-1)(1-c)) — a longshot gets a smaller stake in exact
    proportion to its per-unit standard deviation, with the corrected closed form."""
    rule = variance_ladder(unit_pence=100)
    stakes = rule([bet("2.00", "1.1"), bet("5.00", "1.2")], state())
    # sd at 2.00 = sqrt(0.98); at 5.00 = sqrt(3.92) = 2*sqrt(0.98): exactly half the stake.
    assert stakes[0] == 2 * stakes[1]


def test_fixed_profit_net_targets_net_winnings_and_refuses_short_prices() -> None:
    """s = T/((O-1)(1-c)) wins T net. Above the coverage bound the stake would fall
    below the minimum — the rule abstains there, which the harness scores as SKIP."""
    rule = fixed_profit_net(target_pence=100)
    stakes = rule([bet("2.00")], state())
    assert stakes == [int(D(100) / (D("0.98")))]
    assert rule([bet("1.05")], state()) == [2_000], "short odds need a large stake"


def test_sqrt_profit_escalates_only_from_banked_profit() -> None:
    """u0 + sqrt(max(P,0)): the initial bank is never escalated — at or below the start
    bank the rule is exactly flat."""
    rule = sqrt_profit(base_pence=100, start_bank_pence=10_000)
    assert rule([bet("2.00")], state(10_000)) == [100]
    assert rule([bet("2.00")], state(9_000)) == [100], "drawdown never de-escalates below base"
    up = rule([bet("2.00")], state(12_500))[0]
    assert up == 100 + 50, "sqrt(2500 pence-profit) = 50p escalation"
