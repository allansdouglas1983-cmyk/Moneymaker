"""The replay engine's guarantees, written before the engine exists.

WHAT THIS HARNESS IS FOR. Staking rules cannot be chosen from theory, because expected
terminal wealth is W0 + sum(S_i * ev_i): a staking rule picks the weights S_i and can
never change any ev_i. Every rule is therefore optimal for some objective and the
objectives conflict, so the choice has to be made by replaying each rule over one real
sequence of settled bets and comparing what actually happened.

That makes the engine's mechanics load-bearing. Every test below pins a decision where a
plausible-looking alternative would silently flatter some rule and not others:

  * intra-day compounding would make a proportional rule look better purely from bet
    ordering inside a day, which is an artefact of the export, not of the strategy;
  * rounding a sub-minimum stake up rather than skipping it converts a carefully shrunk
    plan into a flat stake at several times the intended risk, and does it worst to the
    most conservative rules;
  * charging commission on turnover rather than on net winnings punishes high-turnover
    rules for a cost that does not exist;
  * float money accumulates a drift that differs per rule because the rules stake
    different amounts.

None of these is a staking rule. They are the measuring instrument, and the instrument
has to be neutral between the things it measures.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal as D

import pytest

from tennis_edge.staking.engine import (
    Candidate,
    EngineConfig,
    Halt,
    replay,
)

TODAY = dt.date(2020, 6, 1)
TOMORROW = dt.date(2020, 6, 2)


def candidate(
    date: dt.date = TODAY,
    market: str = "1.1",
    side: str = "a",
    odds: str = "2.00",
    p_model: str = "0.60",
    won: bool = True,
) -> Candidate:
    return Candidate(
        date=date,
        market_id=market,
        side=side,
        odds=D(odds),
        p_model=D(p_model),
        p_market=D("0.50"),
        won=won,
        support="SUPPORTED",
        stratum="THICK",
    )


def flat(pence: int):
    """A staking rule that always asks for the same stake. The measuring stick."""

    def rule(candidates, state):  # noqa: ARG001 — state unused by design
        return [pence for _ in candidates]

    return rule


def proportional(fraction: D):
    """Stake a fixed fraction of the bank the day opened on."""

    def rule(candidates, state):
        stake = int(state.opening_bank_pence * fraction)
        return [stake for _ in candidates]

    return rule


CONFIG = EngineConfig(
    start_bank_pence=10_000,
    floor_pence=0,
    min_stake_pence=100,
    commission=D("0.05"),
)


# --------------------------------------------------------------------------- settlement


def test_a_losing_bet_costs_exactly_its_stake_and_no_commission() -> None:
    """Commission is charged on net winnings per market. A losing market pays nothing —
    an engine that charges it on turnover would penalise every high-turnover rule for a
    cost that does not exist, and would do so in proportion to how much it staked."""
    path = replay([candidate(won=False)], flat(500), CONFIG)
    assert path.final_bank_pence == 10_000 - 500
    assert path.total_commission_pence == 0


def test_commission_is_charged_on_net_winnings_not_on_the_stake() -> None:
    """GBP 5 at 2.00 wins GBP 5 gross; 5% commission is 25p of the PROFIT, not 25p of
    the GBP 10 returned and not 25p of the GBP 5 staked."""
    path = replay([candidate(odds="2.00", won=True)], flat(500), CONFIG)
    assert path.total_commission_pence == 25
    assert path.final_bank_pence == 10_000 + 500 - 25


def test_settlement_rounds_against_the_bettor_in_both_directions() -> None:
    """Fractional pence exist in the arithmetic and not in the account. Gross profit is
    floored and commission is ceilinged, so the engine can never report a penny the
    exchange would not have paid. A rule that looks profitable only because rounding went
    its way is not a finding."""
    # 333p at 3.05: gross = 333 * 2.05 = 682.65p, floored to 682 (proves the floor);
    # commission = 682 * 0.05 = 34.10p, ceilinged to 35 (proves the ceiling).
    path = replay([candidate(odds="3.05", won=True)], flat(333), CONFIG)
    assert path.total_commission_pence == 35
    assert path.final_bank_pence == 10_000 + 682 - 35


def test_money_never_becomes_a_float() -> None:
    """Every ledger quantity is integer pence. Floats would accumulate a drift that
    differs between rules because the rules stake different amounts, which is a
    comparison artefact indistinguishable from a real difference."""
    path = replay([candidate(odds="1.37", won=True), candidate(market="1.2", won=False)],
                  flat(137), CONFIG)
    for row in path.rows:
        for value in (row.stake_pence, row.profit_pence, row.commission_pence,
                      row.closing_bank_pence):
            assert isinstance(value, int), f"{value!r} is not integer pence"
    assert isinstance(path.final_bank_pence, int)


# --------------------------------------------------------------------------- the day


def test_same_day_bets_are_all_sized_off_the_bank_the_day_opened_on() -> None:
    """THE most important mechanic here. Bets on the same day are placed before any of
    them settles, so none of them can be sized off another's winnings. An engine that
    compounds within the day makes a proportional rule's result depend on the arbitrary
    order rows happen to sit in the export file — an artefact of the data, reported as
    strategy performance."""
    day = [candidate(market="1.1", won=True), candidate(market="1.2", won=True)]
    path = replay(day, proportional(D("0.10")), CONFIG)
    assert len({row.stake_pence for row in path.rows}) == 1, "identical sizing within a day"
    assert path.rows[0].stake_pence == 1_000


def test_the_bank_compounds_between_days_but_not_within_one() -> None:
    day_one = [candidate(date=TODAY, market="1.1", odds="2.00", won=True)]
    day_two = [candidate(date=TOMORROW, market="1.2", odds="2.00", won=True)]
    path = replay(day_one + day_two, proportional(D("0.10")), CONFIG)
    assert path.rows[0].stake_pence == 1_000
    # Day one nets +1000 gross, -50 commission -> bank 10,950. Day two stakes 10% of that.
    assert path.rows[1].stake_pence == 1_095


def test_days_are_replayed_in_chronological_order_regardless_of_input_order() -> None:
    """The export is not guaranteed sorted, and a rule that reads bank state is
    order-sensitive by construction."""
    shuffled = [candidate(date=TOMORROW, market="1.2"), candidate(date=TODAY, market="1.1")]
    path = replay(shuffled, flat(500), CONFIG)
    assert [row.date for row in path.rows] == [TODAY, TOMORROW]


# --------------------------------------------------------------- granularity and floor


def test_a_stake_below_the_exchange_minimum_is_skipped_never_rounded_up() -> None:
    """Betfair's minimum is GBP 1.00 (verified: reduced from GBP 2 on 7 February 2022).
    Rounding 40p up to GBP 1 is a 150% increase in risk on that bet, applied silently.
    Across a card it turns a shrunk plan into a flat stake at several times the intended
    exposure — and it does the most damage to exactly the most conservative rules, which
    is the worst possible bias for a study comparing them."""
    path = replay([candidate()], flat(40), CONFIG)
    assert path.rows[0].stake_pence == 0
    assert path.rows[0].reason == "BELOW_MIN_STAKE"
    assert path.rows[0].requested_pence == 40, "the intention is recorded, so the skip is visible"
    assert path.final_bank_pence == 10_000


def test_the_floor_is_never_breached() -> None:
    """The floor is what keeps the programme alive to bet next week. A rule that would
    stake through it is truncated, not permitted."""
    config = EngineConfig(start_bank_pence=1_000, floor_pence=800,
                          min_stake_pence=100, commission=D("0.05"))
    path = replay([candidate(won=False)], flat(500), config)
    assert path.rows[0].stake_pence <= 200
    assert path.final_bank_pence >= config.floor_pence


def test_a_card_that_asks_for_more_than_the_stakeable_bank_scales_proportionally() -> None:
    """Four bets at once are not one bet four times. When the day's request exceeds what
    is available every stake shrinks by the same factor, so the RELATIVE sizing the rule
    asked for survives — otherwise the truncation silently becomes a different rule."""
    day = [candidate(market=f"1.{i}") for i in range(4)]
    config = EngineConfig(start_bank_pence=1_000, floor_pence=0,
                          min_stake_pence=100, commission=D("0.05"))
    path = replay(day, flat(400), config)
    staked = [row.stake_pence for row in path.rows]
    assert sum(staked) <= 1_000
    assert len(set(staked)) == 1, "equal requests must stay equal after scaling"
    assert all(row.reason == "SCALED_TO_BANK" for row in path.rows)


def test_the_engine_halts_when_it_cannot_fund_the_minimum_stake() -> None:
    """Ruin in this system is not 'bank reaches zero'. It is 'bank can no longer place
    the smallest legal bet', which happens strictly earlier and is the honest stopping
    condition on a lattice with a GBP 1 floor."""
    # GBP 1.50 bank, no floor: day one can fund the GBP 1 minimum, loses, and leaves 50p
    # — solvent, but no longer able to place the smallest legal bet.
    config = EngineConfig(start_bank_pence=150, floor_pence=0,
                          min_stake_pence=100, commission=D("0.05"))
    day = [candidate(date=TODAY, market="1.1", won=False),
           candidate(date=TOMORROW, market="1.2", won=True)]
    path = replay(day, flat(100), config)
    assert path.final_bank_pence == 50, "solvent, and still dead"
    assert path.halt is Halt.CANNOT_FUND_MINIMUM
    assert path.halted_on == TOMORROW
    assert len([r for r in path.rows if r.stake_pence > 0]) == 1, "no bet after the halt"


def test_nothing_after_the_halt_is_played_even_if_it_would_have_won() -> None:
    """A dead programme stays dead. An engine that merely skipped an unaffordable day and
    carried on would resurrect it the moment a cheaper day came along — and would credit
    a rule with winnings it could never have collected."""
    config = EngineConfig(start_bank_pence=150, floor_pence=0,
                          min_stake_pence=100, commission=D("0.05"))
    third = TOMORROW + dt.timedelta(days=1)
    day = [candidate(date=TODAY, market="1.1", won=False),
           candidate(date=TOMORROW, market="1.2", won=True),
           candidate(date=third, market="1.3", won=True)]
    path = replay(day, flat(100), config)
    assert path.halted_on == TOMORROW
    assert [r.date for r in path.rows] == [TODAY], "days after the halt are not played"
    assert path.final_bank_pence == 50


# --------------------------------------------------------------------------- integrity


def test_replay_is_deterministic() -> None:
    """Two rules are compared by the difference between their paths. If the engine is not
    bit-reproducible that difference contains engine noise, and no comparison is valid."""
    day = [candidate(market=f"1.{i}", won=bool(i % 2)) for i in range(8)]
    first = replay(day, proportional(D("0.05")), CONFIG)
    second = replay(day, proportional(D("0.05")), CONFIG)
    assert first.final_bank_pence == second.final_bank_pence
    assert [r.stake_pence for r in first.rows] == [r.stake_pence for r in second.rows]
    assert [r.closing_bank_pence for r in first.rows] == [r.closing_bank_pence
                                                          for r in second.rows]


def test_the_ledger_reconciles_to_the_final_bank() -> None:
    """The path is only evidence if it adds up. Start plus every profit equals the end,
    exactly, in integer pence."""
    day = [candidate(market=f"1.{i}", odds="2.50", won=bool(i % 3)) for i in range(9)]
    path = replay(day, flat(200), CONFIG)
    assert (CONFIG.start_bank_pence + sum(r.profit_pence for r in path.rows)
            == path.final_bank_pence)


def test_a_flat_rule_produces_an_additive_walk_and_a_proportional_rule_does_not() -> None:
    """The sanity anchor for the whole study. Flat staking is an additive random walk;
    proportional staking is multiplicative. If the engine cannot reproduce that
    distinction it is not measuring what the rules actually do."""
    wins = [candidate(date=TODAY + dt.timedelta(days=i), market=f"1.{i}",
                      odds="2.00", won=True) for i in range(4)]
    flat_path = replay(wins, flat(1_000), CONFIG)
    prop_path = replay(wins, proportional(D("0.10")), CONFIG)
    flat_steps = [r.profit_pence for r in flat_path.rows]
    prop_steps = [r.profit_pence for r in prop_path.rows]
    assert len(set(flat_steps)) == 1, "flat stakes give a constant step"
    assert prop_steps == sorted(prop_steps), "proportional steps grow with the bank"
    assert len(set(prop_steps)) == len(prop_steps), "and are strictly increasing"


def test_an_empty_sequence_is_not_a_crash_and_not_a_profit() -> None:
    path = replay([], flat(500), CONFIG)
    assert path.final_bank_pence == CONFIG.start_bank_pence
    assert path.rows == []
    assert path.halt is None


def test_the_engine_refuses_a_rule_that_asks_for_a_negative_stake() -> None:
    """A negative stake is a lay bet. Lay betting is prohibited platform-wide, so a rule
    that produces one is a defect and must not be silently clamped to zero — clamping
    would hide the bug and score the rule as though it had abstained."""
    def lays(candidates, state):  # noqa: ARG001
        return [-100 for _ in candidates]

    with pytest.raises(ValueError, match="negative stake"):
        replay([candidate()], lays, CONFIG)


def test_the_engine_refuses_a_rule_that_returns_the_wrong_number_of_stakes() -> None:
    """A rule returning fewer stakes than candidates has silently dropped a bet. That is
    a selection change wearing a staking rule's clothes."""
    def short(candidates, state):  # noqa: ARG001
        return []

    with pytest.raises(ValueError, match="one stake per candidate"):
        replay([candidate()], short, CONFIG)
