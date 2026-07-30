"""STK-HARNESS-V1 mechanics the engine does not yet have — tests before implementation.

Protocol: docs/research/findings/DR-TENNIS-STAKING-006-PROTOCOL.md. The existing engine
(tennis_edge.staking.engine) already guarantees morning-bank sizing, skip-not-round-up,
net-winnings commission and integer pence. The head-to-head needs four more mechanics,
each pinned here because a plausible alternative silently favours some rules:

  * STRESS SCENARIOS by win-payout haircut (protocol §4): shift the mean without
    inventing or flipping a single outcome, preserving max-loss = stake so every floor
    proof stays valid in the counterfactual world.
  * DAY-LEVEL RESERVATION (§1.6): sequential deterministic reservation in canonical
    order — NOT proportional rescaling — because floor guarantees are proved under
    "sum of same-day stakes <= day budget" and rescaling breaks the skip rule.
  * ABSORBING RUIN STATES (§5): DEAD_FLOOR (founder floor breach, the primary
    definition) and SILENT_DEATH (the rule switched itself off) — both first-class
    outputs, never inferred afterwards from a wealth series.
  * PAIRED RESAMPLING (§3.4): the same resampled day sequence replayed through every
    rule, so cross-rule differences isolate the staking policy.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal as D

import pytest

from tennis_edge.staking.engine import Candidate
from tennis_edge.staking.harness import (
    HarnessConfig,
    Ruin,
    day_sequence_draws,
    haircut_factor,
    replay_run,
)

DAY = dt.date(2020, 6, 1)


def candidate(date: dt.date = DAY, market: str = "1.1", odds: str = "2.00",
              won: bool = True) -> Candidate:
    return Candidate(date=date, market_id=market, side="a", odds=D(odds),
                     p_model=D("0.60"), p_market=D("0.50"), won=won,
                     support="SUPPORTED", stratum="THICK")


def flat(pence: int):
    def rule(candidates, state):  # noqa: ARG001
        return [pence for _ in candidates]
    return rule


CONFIG = HarnessConfig(
    start_bank_pence=10_000,
    founder_floor_pence=7_000,
    min_stake_pence=100,
    commission=D("0.02"),
    silent_death_days=30,
)


# ------------------------------------------------------------------ stress scenarios


def test_haircut_solves_the_exact_mean_shift_identity() -> None:
    """h = -delta * n / sum(b_i over winners), exact Decimal (protocol §4.3). With two
    bets, one winner at net odds b=0.98, shifting the mean by -0.10 over n=2 needs
    h = 0.2/0.98."""
    bets = [candidate(market="1.1", won=True), candidate(market="1.2", won=False)]
    h = haircut_factor(bets, D("-0.10"), commission=D("0.02"))
    assert h == D("0.2") / D("0.98")


def test_zero_shift_is_exactly_no_haircut_and_positive_shift_is_refused() -> None:
    """The scenario axis only degrades payouts. A negative haircut would improve the
    world silently — that is a different study and it is refused, not clamped."""
    bets = [candidate(won=True)]
    assert haircut_factor(bets, D("0"), commission=D("0.02")) == 0
    with pytest.raises(ValueError, match="degrad"):
        haircut_factor(bets, D("0.05"), commission=D("0.02"))


def test_haircut_touches_only_winning_payouts_never_losses() -> None:
    """A loss never exceeds the stake in any scenario — the property every floor proof
    depends on (protocol §4.4). The losing bet's cash flow must be identical across
    scenarios."""
    bets = [candidate(date=DAY, market="1.1", won=True),
            candidate(date=DAY + dt.timedelta(days=1), market="1.2", won=False)]
    base = replay_run(bets, flat(1_000), CONFIG, haircut=D("0"))
    stressed = replay_run(bets, flat(1_000), CONFIG, haircut=D("0.5"))
    assert base.rows[1].profit_pence == stressed.rows[1].profit_pence == -1_000
    assert stressed.rows[0].profit_pence < base.rows[0].profit_pence


# ------------------------------------------------------------ day-level reservation


def test_reservation_is_sequential_in_canonical_order_not_proportional() -> None:
    """Protocol §1.6: each bet takes min(stake, remaining) in canonical order; a grant
    below the minimum is a SKIP_RESERVE. Proportional rescaling — what the plain engine
    does — would shrink every stake a little instead, and floor guarantees are proved
    under sequential reservation."""
    day = [candidate(market=f"1.{i}") for i in range(3)]
    config = HarnessConfig(start_bank_pence=2_500, founder_floor_pence=0,
                           min_stake_pence=100, commission=D("0.02"),
                           silent_death_days=30)
    path = replay_run(day, flat(1_000), config, haircut=D("0"))
    stakes = [r.stake_pence for r in path.rows]
    reasons = [r.reason for r in path.rows]
    assert stakes == [1_000, 1_000, 500], "first-come reservation, remainder to the last"
    assert reasons[2] == "CLAMP_RESERVE"


def test_a_reservation_grant_below_the_minimum_is_skipped() -> None:
    day = [candidate(market=f"1.{i}") for i in range(3)]
    config = HarnessConfig(start_bank_pence=2_050, founder_floor_pence=0,
                           min_stake_pence=100, commission=D("0.02"),
                           silent_death_days=30)
    path = replay_run(day, flat(1_000), config, haircut=D("0"))
    assert [r.stake_pence for r in path.rows] == [1_000, 1_000, 0]
    assert path.rows[2].reason == "SKIP_RESERVE"


# ------------------------------------------------------------------ absorbing states


def test_breaching_the_founder_floor_absorbs_the_path() -> None:
    """DEAD_FLOOR is the PRIMARY ruin definition (§5 R2): end-of-day bank below the
    founder floor freezes wealth at the breach value and no later day is played."""
    days = [candidate(date=DAY, market="1.1", won=False),
            candidate(date=DAY + dt.timedelta(days=1), market="1.2", won=True)]
    config = HarnessConfig(start_bank_pence=10_000, founder_floor_pence=9_500,
                           min_stake_pence=100, commission=D("0.02"),
                           silent_death_days=30)
    path = replay_run(days, flat(1_000), config, haircut=D("0"))
    assert path.ruin is Ruin.DEAD_FLOOR
    assert path.final_bank_pence == 9_000, "frozen at breach value"
    assert len(path.rows) == 1, "the winning day after death is never played"


def test_a_rule_that_stops_betting_gets_the_silent_death_flag() -> None:
    """A rule demanding below the minimum on every eligible bet for the configured run
    of days has switched itself off (§5 R3). Non-absorbing — but flagged, because a
    rule that stops betting stops buying evidence."""
    days = [candidate(date=DAY + dt.timedelta(days=i), market=f"1.{i}", won=True)
            for i in range(35)]
    path = replay_run(days, flat(50), CONFIG, haircut=D("0"))
    assert path.silent_death_onset is not None
    assert path.silent_death_onset == DAY + dt.timedelta(days=29)
    assert path.ruin is None, "silent death is a flag, not an absorption"


# ------------------------------------------------------------------ paired draws


def test_draws_are_deterministic_and_shared_across_rules() -> None:
    """§3.4: the SAME resampled day sequence must drive every rule, and the same seed
    must reproduce the same draws — otherwise cross-rule differences contain draw noise
    and nothing isolates the staking policy."""
    days = sorted({DAY + dt.timedelta(days=i) for i in range(10)})
    first = day_sequence_draws(days, draws=5, seed=20260730)
    second = day_sequence_draws(days, draws=5, seed=20260730)
    assert first == second, "same seed, same draws, byte-for-byte"
    assert len(first) == 5
    assert all(len(draw) == len(days) for draw in first), "each draw is a full-length path"
    assert all(day in days for draw in first for day in draw)


def test_different_seeds_give_different_draws() -> None:
    days = sorted({DAY + dt.timedelta(days=i) for i in range(10)})
    assert (day_sequence_draws(days, draws=3, seed=1)
            != day_sequence_draws(days, draws=3, seed=2))
