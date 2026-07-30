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
    # sd at 2.00 = sqrt(0.98); at 5.00 = sqrt(3.92) = 2*sqrt(0.98): half the stake,
    # up to one penny of ROUND_FLOOR quantisation (the sd is irrational, so the exact
    # 2:1 relation lives above the pence lattice, not on it).
    assert abs(stakes[0] - 2 * stakes[1]) <= 1
    assert stakes[0] > stakes[1]


def test_fixed_profit_net_targets_net_winnings_and_refuses_short_prices() -> None:
    """s = T/((O-1)(1-c)) wins T net. Above the coverage bound the stake would fall
    below the minimum — the rule abstains there, which the harness scores as SKIP."""
    rule = fixed_profit_net(target_pence=100)
    stakes = rule([bet("2.00")], state())
    assert stakes == [int(D(100) / (D("0.98")))]
    # 100 / (0.05 * 0.98) = 2040.8...p — the commission belongs in the denominator;
    # the naive 2,000 is FP-NAIVE, the control this rule must never collapse into.
    assert rule([bet("1.05")], state()) == [2_040], "short odds need a large stake"


def test_sqrt_profit_escalates_only_from_banked_profit() -> None:
    """u0 + sqrt(max(P,0)): the initial bank is never escalated — at or below the start
    bank the rule is exactly flat."""
    rule = sqrt_profit(base_pence=100, start_bank_pence=10_000)
    assert rule([bet("2.00")], state(10_000)) == [100]
    assert rule([bet("2.00")], state(9_000)) == [100], "drawdown never de-escalates below base"
    up = rule([bet("2.00")], state(12_500))[0]
    assert up == 100 + 50, "sqrt(2500 pence-profit) = 50p escalation"


def test_conservative_kelly_sizes_per_bet_from_bank_odds_and_probability() -> None:
    """The founder-requested allocator (registered by amendment): f_i = shrink * kelly of
    the live bank, per bet. Defining identities: stakes DIFFER across a card by odds and
    probability; they scale with the bank (compounding); a bet at or below break-even
    gets zero; and the shrink multiplies the fraction exactly."""
    from tennis_edge.staking.rules import conservative_kelly
    rule = conservative_kelly(shrink=D("0.5"), commission=D("0.02"))
    card = [bet("1.60", "1.1"), bet("2.40", "1.2"), bet("2.00", "1.3")]
    # p_model is 0.6 for all three. The stake tracks the EDGE, not the odds: at 1.60 the
    # break-even is 0.6297 > 0.60, so that bet has no edge and gets ZERO; at 2.40 the
    # edge (+0.178) dwarfs 2.00's (+0.095), so it carries the larger stake.
    stakes = rule(card, state(20_000))
    assert len(set(stakes)) == 3, "per-bet sizing: same probability, different odds, different stakes"
    assert stakes[0] == 0, "below break-even is not a small bet; it is no bet"
    assert stakes[1] > stakes[2] > 0, "the bigger edge carries the bigger stake"
    doubled = rule(card, state(40_000))
    # Exact doubling lives above the pence lattice: floor(2W*f) can exceed
    # 2*floor(W*f) by a penny. The compounding property is linear scaling to within
    # ROUND_FLOOR quantisation.
    for twice, once in zip(doubled, stakes, strict=True):
        assert abs(twice - 2 * once) <= 1, "stakes scale with the bank: compounding"
    hopeless = Candidate(date=DAY, market_id="1.9", side="a", odds=D("1.50"),
                         p_model=D("0.60"), p_market=D("0.5"), won=True,
                         support="SUPPORTED", stratum="THICK")
    # break-even at 1.50/2% is 0.6711 > 0.60: no edge, no stake.
    assert rule([hopeless], state(20_000)) == [0]


# ---------------------------------------------------------------------------
# TE-0047: the D7 conservative-bound allocator (matrix K-LCB), registered form.
# One test per registered metamorphic property; expectations hand-computed from the
# registration's exact formula at the frozen constants (c=0.02, delta_e=0.0249,
# d_max=0.30). Tests committed RED before the implementation exists.
# ---------------------------------------------------------------------------

def d7cand(odds: str, p: str, market: str = "1.1") -> Candidate:
    return Candidate(date=DAY, market_id=market, side="a", odds=D(odds),
                     p_model=D(p), p_market=D(p), won=True,
                     support="SUPPORTED", stratum="THICK")


def _d7() -> object:
    from tennis_edge.staking.rules import d7_conservative_bound
    return d7_conservative_bound(delta_e=D("0.0249"), commission=D("0.02"),
                                 max_drawdown=D("0.30"))


def test_d7_refuses_at_and_below_the_conservative_bound() -> None:
    """Property 1: e_c <= 0 -> stake 0 for every bank. The D7 'not yet' branch: a
    positive central edge smaller than the displacement is refused, not shrunk."""
    rule = _d7()
    # p=0.51 at 2.00: central e = +0.0098 > 0, but e_c = -0.0151 -> refuse.
    assert rule([d7cand("2.00", "0.51")], state(100_000, 100_000)) == [0]
    assert rule([d7cand("2.00", "0.51")], state(10**9, 10**9)) == [0]
    # Exactly at the bound (p = 1.0249/1.98): e_c = 0, and zero is not > 0.
    boundary = Candidate(date=DAY, market_id="1.1", side="a", odds=D("2.00"),
                         p_model=D("1.0249") / D("1.98"), p_market=D("0.5"),
                         won=True, support="SUPPORTED", stratum="THICK")
    assert rule([boundary], state(100_000, 100_000)) == [0]


def test_d7_exact_stake_and_bank_scaling() -> None:
    """Properties 3 + exact form: p=0.60 at 2.00 -> f = (0.6*1.98 - 1 - 0.0249)/0.98
    = 0.1631/0.98; on GBP 1,000 (HWM equal) that is floor(16642.85...) = 16642p, under
    a 30000p HB day budget. Doubling the bank doubles the stake within the 1p lattice."""
    rule = _d7()
    assert rule([d7cand("2.00", "0.60")], state(100_000, 100_000)) == [16_642]
    twice = rule([d7cand("2.00", "0.60")], state(200_000, 200_000))[0]
    assert abs(twice - 2 * 16_642) <= 1, "compounding: stakes scale with the bank"


def test_d7_delta_e_is_monotone_and_can_silence_the_card() -> None:
    """Property 2: a larger displacement never increases any stake; a displacement
    beyond every edge zeroes the whole card."""
    from tennis_edge.staking.rules import d7_conservative_bound
    tight = d7_conservative_bound(delta_e=D("0.05"), commission=D("0.02"),
                                  max_drawdown=D("0.30"))
    loose = _d7()
    card = [d7cand("2.00", "0.60"), d7cand("3.00", "0.45", "1.2")]
    st = state(100_000, 100_000)
    for a, b in zip(tight(card, st), loose(card, st), strict=True):
        assert a <= b
    everything = d7_conservative_bound(delta_e=D("5"), commission=D("0.02"),
                                       max_drawdown=D("0.30"))
    assert everything(card, st) == [0, 0]


def test_d7_monotone_in_odds_and_probability() -> None:
    """Properties 4 and 5: at fixed p the fraction never falls as odds lengthen; at
    fixed odds the stake never falls as p rises. And an odds so short the conservative
    edge dies is refused outright."""
    rule = _d7()
    st = state(100_000, 100_000)
    s3 = rule([d7cand("3.00", "0.40")], st)[0]
    s4 = rule([d7cand("4.00", "0.40")], st)[0]
    assert 0 < s3 < s4, "longer odds at fixed p carry the larger conservative fraction"
    assert rule([d7cand("2.50", "0.40")], st) == [0], "central edge -0.012: refused"
    p_lo = rule([d7cand("2.50", "0.50")], st)[0]
    p_hi = rule([d7cand("2.50", "0.55")], st)[0]
    assert 0 < p_lo < p_hi, "higher win chance at fixed odds carries the larger stake"


def test_d7_same_day_card_division() -> None:
    """Property 6: the perfectly-correlated card charge — doubling the card size halves
    each pre-cap stake within the 1p lattice."""
    rule = _d7()
    st = state(100_000, 100_000)
    alone = rule([d7cand("2.00", "0.60")], st)[0]
    pair = rule([d7cand("2.00", "0.60"), d7cand("2.00", "0.60", "1.2")], st)
    assert pair == [8_321, 8_321]
    assert abs(pair[0] - alone // 2) <= 1


def test_d7_hb_day_budget_bounds_the_card_pathwise() -> None:
    """Properties 7 + 8: the day's total stakes never exceed W - 0.70*HWM, so an
    all-lose day cannot take the bank below 70% of its high-water mark."""
    rule = _d7()
    st = state(100_000, 100_000)
    # Two huge-edge bets each wanting 43,406p against a 30,000p day budget: the walk
    # grants the budget to the first and refuses the second.
    card = [d7cand("5.00", "0.90"), d7cand("5.00", "0.90", "1.2")]
    stakes = rule(card, st)
    assert stakes == [30_000, 0]
    assert st.opening_bank_pence - sum(stakes) >= 70_000, "all-lose day floor holds"


def test_d7_zero_when_the_drawdown_bound_is_exhausted() -> None:
    """Property 7 tail: at 0.70*HWM >= W the cushion is spent — no stake, any edge."""
    rule = _d7()
    assert rule([d7cand("5.00", "0.90")], state(100_000, 150_000)) == [0]


def test_d7_refused_card_member_still_counts_in_the_correlation_charge() -> None:
    """Property 9: a selected bet below the conservative break-even stakes zero but
    still counts in k — it was selected, the correlation charge stands."""
    rule = _d7()
    st = state(100_000, 100_000)
    stakes = rule([d7cand("2.00", "0.60"), d7cand("2.00", "0.30", "1.2")], st)
    assert stakes == [8_321, 0], "k=2 division applies even though the second refuses"
