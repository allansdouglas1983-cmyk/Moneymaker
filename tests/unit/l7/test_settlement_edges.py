"""SPEC-082 audit-gap edge cases: multi-runner settlement, ABANDONED, scenario matrix with
REMOVED runners, absent runners, and the SPEC-080 authoritative-field whitelist.

Added by the 2026-07-16 retrospective audit. All tests are additive; they pin behaviour the
implementation already specifies but no test previously exercised.
"""
from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest

from l7_settle.outcomes import MarketOutcome, MarketStatus, MatchedPosition, RunnerOutcome, RunnerResult
from l7_settle.settlement import MarketSettlement, SettlementBlocked, settle_market

pytestmark = [pytest.mark.spec("SPEC-080"), pytest.mark.spec("SPEC-082")]


def _pos(runner_id: int, stake: int, odds: str, rfs: tuple[str, ...] = ()) -> MatchedPosition:
    return MatchedPosition(
        runner_id=runner_id,
        matched_stake_minor=stake,
        matched_odds=Decimal(odds),
        applicable_reduction_factors=tuple(Decimal(r) for r in rfs),
    )


def _settle(
    positions: list[MatchedPosition],
    outcome: MarketOutcome,
    *,
    rate: str = "0.02",
    charges: int = 0,
) -> MarketSettlement:
    return settle_market(
        market_id="1.1",
        positions=positions,
        outcome=outcome,
        commission_rate_effective=Decimal(rate),
        transaction_charges_minor=charges,
        statement_reference="stmt-1",
    )


def _outcome(status: MarketStatus, runners: dict[int, RunnerOutcome]) -> MarketOutcome:
    return MarketOutcome(market_status=status, runners=runners)


def test_multi_runner_commission_is_on_net_not_per_order() -> None:
    # Winner on 111: 200 @ 3.0 -> +400. Loser on 222: 150 staked -> -150. Net = +250.
    # Commission on the NET market result: 2% of 250 = 5, final 245.
    # A per-order scheme would charge 8 on the winning order alone (400*2%) -> final 242. The
    # 245 != 242 distinction is exactly what SPEC-080 requires.
    outcome = _outcome(
        MarketStatus.SETTLED,
        {111: RunnerOutcome(RunnerResult.WINNER), 222: RunnerOutcome(RunnerResult.LOSER)},
    )
    s = _settle([_pos(111, 200, "3.0"), _pos(222, 150, "2.5")], outcome)
    assert s.actual_net_market_pnl == 250
    assert s.actual_commission == 5
    assert s.final_net_pnl == 245


def test_multi_runner_exact_zero_net_charges_no_commission() -> None:
    # +400 on the winner, -400 on a loser: an exact push. Commission on net <= 0 is zero,
    # and only the transaction charges remain.
    outcome = _outcome(
        MarketStatus.SETTLED,
        {111: RunnerOutcome(RunnerResult.WINNER), 222: RunnerOutcome(RunnerResult.LOSER)},
    )
    s = _settle([_pos(111, 200, "3.0"), _pos(222, 400, "2.0")], outcome, charges=7)
    assert s.actual_net_market_pnl == 0
    assert s.actual_commission == 0
    assert s.final_net_pnl == -7


def test_multi_runner_negative_net_charges_no_commission() -> None:
    outcome = _outcome(
        MarketStatus.SETTLED,
        {111: RunnerOutcome(RunnerResult.WINNER), 222: RunnerOutcome(RunnerResult.LOSER)},
    )
    s = _settle([_pos(111, 100, "3.0"), _pos(222, 500, "2.0")], outcome)
    assert s.actual_net_market_pnl == -300
    assert s.actual_commission == 0
    assert s.final_net_pnl == -300


def test_multi_runner_scenario_matrix_covers_every_competitor() -> None:
    # Positions on 111 (200 @ 3.0) and 222 (150 @ 2.5); 333 competed with no position.
    outcome = _outcome(
        MarketStatus.SETTLED,
        {
            111: RunnerOutcome(RunnerResult.WINNER),
            222: RunnerOutcome(RunnerResult.LOSER),
            333: RunnerOutcome(RunnerResult.LOSER),
        },
    )
    s = _settle([_pos(111, 200, "3.0"), _pos(222, 150, "2.5")], outcome)
    assert s.gross_pnl_by_selection_scenario == {
        "111": 400 - 150,  # 111 wins: back on 111 pays 400, back on 222 loses its 150 stake
        "222": -200 + 225,  # 222 wins: 150 @ 2.5 pays 225, back on 111 loses its 200 stake
        "333": -200 - 150,  # 333 wins: both backs lose
    }


def test_scenario_matrix_excludes_removed_runner_and_zeroes_its_position() -> None:
    # A REMOVED runner is never a hypothetical winner, and a position on it settles to zero
    # in every scenario.
    outcome = _outcome(
        MarketStatus.SETTLED,
        {
            111: RunnerOutcome(RunnerResult.WINNER),
            222: RunnerOutcome(RunnerResult.LOSER),
            333: RunnerOutcome(RunnerResult.REMOVED, reduction_factor=Decimal("0.25")),
        },
    )
    s = _settle([_pos(111, 200, "3.0"), _pos(333, 100, "2.0")], outcome)
    assert set(s.gross_pnl_by_selection_scenario) == {"111", "222"}
    assert s.gross_pnl_by_selection_scenario["111"] == 400  # 333 position contributes 0
    assert s.gross_pnl_by_selection_scenario["222"] == -200


def test_abandoned_market_is_all_zero_but_still_incurs_charges() -> None:
    # ABANDONED settles exactly like VOID: every position to zero, no commission, no scenario
    # matrix — but transaction charges were incurred at placement time and remain.
    outcome = _outcome(MarketStatus.ABANDONED, {111: RunnerOutcome(RunnerResult.VOID)})
    s = _settle([_pos(111, 200, "3.0")], outcome, charges=5)
    assert s.actual_net_market_pnl == 0
    assert s.actual_commission == 0
    assert s.transaction_charges == 5
    assert s.final_net_pnl == -5
    assert s.gross_pnl_by_selection_scenario == {}


def test_position_on_runner_absent_from_outcome_blocks_settlement() -> None:
    # A runner missing from the outcome map entirely (as opposed to explicitly UNKNOWN) must
    # also block: its state is not known.
    outcome = _outcome(MarketStatus.SETTLED, {111: RunnerOutcome(RunnerResult.WINNER)})
    with pytest.raises(SettlementBlocked):
        _settle([_pos(999, 200, "3.0")], outcome)


def test_multiple_orders_one_runner_different_odds() -> None:
    outcome = _outcome(MarketStatus.SETTLED, {111: RunnerOutcome(RunnerResult.WINNER)})
    s = _settle([_pos(111, 200, "3.0"), _pos(111, 100, "2.5")], outcome)
    assert s.actual_net_market_pnl == 400 + 150
    assert s.actual_commission == 11  # 2% of 550
    assert s.final_net_pnl == 539


def test_matched_position_field_whitelist() -> None:
    # Structural guard (stronger than a forbidden-name blacklist): the exact field set is
    # pinned, so ANY added field — whatever its name — forces a reviewed test change.
    assert {f.name for f in dataclasses.fields(MatchedPosition)} == {
        "runner_id",
        "matched_stake_minor",
        "matched_odds",
        "applicable_reduction_factors",
    }


def test_market_settlement_field_whitelist_matches_spec_080() -> None:
    assert {f.name for f in dataclasses.fields(MarketSettlement)} == {
        "market_id",
        "gross_pnl_by_selection_scenario",
        "actual_net_market_pnl",
        "commission_rate_effective",
        "actual_commission",
        "transaction_charges",
        "final_net_pnl",
        "statement_reference",
        "settlement_version",
        "resettlement_flag",
    }
