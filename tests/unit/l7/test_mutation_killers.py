"""SPEC-080/082 mutation-hardening tests.

Each test here exists to kill a specific class of surviving mutant from the 2026-07-16
mutation baseline; together with the pnl/ledger restructures they drive l7_settle to zero
non-equivalent survivors.
"""
from __future__ import annotations

import dataclasses
from decimal import Decimal
from typing import get_type_hints

import pytest

from l7_settle import ledger as ledger_mod
from l7_settle import pnl as pnl_mod
from l7_settle import settlement as settlement_mod
from l7_settle.outcomes import MarketOutcome, MarketStatus, MatchedPosition, RunnerOutcome, RunnerResult
from l7_settle.settlement import MarketSettlement, settle_market

pytestmark = [pytest.mark.spec("SPEC-080"), pytest.mark.spec("SPEC-082")]


def test_public_annotations_resolve() -> None:
    # Under `from __future__ import annotations` a mutated annotation (e.g. `X | None` ->
    # `X + None`) is never evaluated at runtime and survives silently. Resolving the hints
    # evaluates every annotation expression, so any such mutant raises here.
    for cls in (RunnerOutcome, MarketOutcome, MatchedPosition, MarketSettlement):
        assert isinstance(get_type_hints(cls), dict)
    for fn in (
        pnl_mod.effective_odds,
        pnl_mod.position_pnl_minor,
        settlement_mod.settle_market,
        ledger_mod.SettlementLedger.apply,
        ledger_mod.SettlementLedger.current,
    ):
        assert isinstance(get_type_hints(fn), dict)


def test_matched_odds_of_exactly_one_is_rejected() -> None:
    # Odds are strictly > 1; the boundary itself must refuse (kills <= -> < at the guard).
    with pytest.raises(ValueError):
        MatchedPosition(runner_id=1, matched_stake_minor=1, matched_odds=Decimal("1"))


def test_matched_odds_below_one_is_rejected() -> None:
    # Sub-1 decimal odds are not a price (implied probability > 1); kills <= -> == at the
    # guard, which would accept everything except exactly 1.
    with pytest.raises(ValueError):
        MatchedPosition(runner_id=1, matched_stake_minor=1, matched_odds=Decimal("0.5"))


def test_zero_stake_is_permitted_and_negative_is_rejected() -> None:
    ok = MatchedPosition(runner_id=1, matched_stake_minor=0, matched_odds=Decimal("2.0"))
    assert ok.matched_stake_minor == 0
    with pytest.raises(ValueError):
        MatchedPosition(runner_id=1, matched_stake_minor=-1, matched_odds=Decimal("2.0"))


def test_outcome_types_are_frozen() -> None:
    # frozen=True is load-bearing (settlements/outcomes are immutable records); a
    # frozen=False mutant makes these assignments succeed.
    pos = MatchedPosition(runner_id=1, matched_stake_minor=1, matched_odds=Decimal("2.0"))
    runner = RunnerOutcome(RunnerResult.WINNER)
    market = MarketOutcome(market_status=MarketStatus.SETTLED, runners={})
    with pytest.raises(dataclasses.FrozenInstanceError):
        pos.matched_stake_minor = 2  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        runner.dead_heat_count = 3  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        market.market_status = MarketStatus.VOID  # type: ignore[misc]


def test_unknown_runner_result_raises_at_pnl_level() -> None:
    pos = MatchedPosition(runner_id=1, matched_stake_minor=100, matched_odds=Decimal("2.0"))
    with pytest.raises(ValueError):
        pnl_mod.position_pnl_minor(pos, RunnerOutcome(RunnerResult.UNKNOWN), MarketStatus.SETTLED)


def test_duplicate_ack_returns_the_stored_object_itself() -> None:
    # Idempotency means no new object is stored: the ledger returns THE existing record, not
    # an equal copy. Pinned by identity (kills an `is not` version-comparison mutant that
    # only misbehaves for non-interned large version ints, where it silently re-stores).
    ledger = ledger_mod.SettlementLedger()
    outcome = MarketOutcome(
        market_status=MarketStatus.SETTLED, runners={111: RunnerOutcome(RunnerResult.WINNER)}
    )

    def _mint(version: int) -> MarketSettlement:
        return settle_market(
            market_id="1.1",
            positions=[MatchedPosition(runner_id=111, matched_stake_minor=200, matched_odds=Decimal("3.0"))],
            outcome=outcome,
            commission_rate_effective=Decimal("0.02"),
            statement_reference="stmt-1",
            settlement_version=version,
        )

    # int("1000") defeats constant interning: the two version ints are equal but distinct
    # objects, so an identity-based version comparison misbehaves here.
    first = ledger.apply(_mint(1000))
    assert ledger.apply(_mint(int("1000"))) is first


def test_settle_market_default_flags() -> None:
    # settlement_version defaults to 1 and resettlement_flag to False; a flipped default
    # would let a first settlement masquerade as a resettlement or misnumber versioning.
    outcome = MarketOutcome(
        market_status=MarketStatus.SETTLED, runners={111: RunnerOutcome(RunnerResult.WINNER)}
    )
    s = settle_market(
        market_id="1.1",
        positions=[],
        outcome=outcome,
        commission_rate_effective=Decimal("0.02"),
        statement_reference="stmt-1",
    )
    assert s.settlement_version == 1
    assert s.resettlement_flag is False


def test_scenario_matrix_compares_runner_ids_by_value() -> None:
    # Runner ids arrive from JSON in production and are never small-int-cached; the matrix
    # must compare them by value, not identity. int("...") defeats constant interning here.
    rid = int("1000")
    outcome = MarketOutcome(
        market_status=MarketStatus.SETTLED,
        runners={1000: RunnerOutcome(RunnerResult.WINNER), 2000: RunnerOutcome(RunnerResult.LOSER)},
    )
    s = settle_market(
        market_id="1.1",
        positions=[MatchedPosition(runner_id=rid, matched_stake_minor=200, matched_odds=Decimal("3.0"))],
        outcome=outcome,
        commission_rate_effective=Decimal("0.02"),
        statement_reference="stmt-1",
    )
    assert s.gross_pnl_by_selection_scenario["1000"] == 400
    assert s.gross_pnl_by_selection_scenario["2000"] == -200


def test_commission_on_smallest_positive_net() -> None:
    # net = +1 minor unit at a 0.5 rate: commission = ROUND_HALF_UP(0.5) = 1. Kills the
    # guard-boundary mutant (`net_minor <= 0` -> `<= 1`, which would charge nothing) and
    # discriminates HALF_UP from HALF_EVEN at the commission rounding site too.
    outcome = MarketOutcome(
        market_status=MarketStatus.SETTLED,
        runners={111: RunnerOutcome(RunnerResult.WINNER), 222: RunnerOutcome(RunnerResult.LOSER)},
    )
    s = settle_market(
        market_id="1.1",
        positions=[
            MatchedPosition(runner_id=111, matched_stake_minor=201, matched_odds=Decimal("2.0")),
            MatchedPosition(runner_id=222, matched_stake_minor=200, matched_odds=Decimal("3.0")),
        ],
        outcome=outcome,
        commission_rate_effective=Decimal("0.5"),
        statement_reference="stmt-1",
    )
    assert s.actual_net_market_pnl == 1
    assert s.actual_commission == 1
    assert s.final_net_pnl == 0
