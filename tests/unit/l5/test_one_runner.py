"""One runner per market (SPEC-054).

v1 MUST refuse a second position in a market. If several candidates clear the threshold, choose
the highest conservative net EV with an explicit deterministic tie-break, record every rejected
candidate, and never inspect the outcome or a future market move.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from l5_decision.one_runner import (
    Candidate,
    SecondPositionError,
    MarketPositionLedger,
    select_market_position,
)

pytestmark = pytest.mark.spec("SPEC-054")


def _c(selection_id: int, ev: str, market: str = "1.100") -> Candidate:
    return Candidate(market_id=market, selection_id=selection_id, conservative_ev=Decimal(ev))


class TestSelection:
    def test_highest_conservative_ev_chosen(self) -> None:
        result = select_market_position([_c(11, "0.01"), _c(22, "0.05"), _c(33, "0.02")])
        assert result.chosen.selection_id == 22
        assert {r.selection_id for r in result.rejected} == {11, 33}

    def test_deterministic_tie_break_lowest_selection_id(self) -> None:
        result = select_market_position([_c(33, "0.04"), _c(11, "0.04"), _c(22, "0.04")])
        assert result.chosen.selection_id == 11
        assert {r.selection_id for r in result.rejected} == {22, 33}

    def test_selection_is_order_independent(self) -> None:
        a = select_market_position([_c(11, "0.01"), _c(22, "0.05"), _c(33, "0.02")])
        b = select_market_position([_c(33, "0.02"), _c(22, "0.05"), _c(11, "0.01")])
        assert a.chosen.selection_id == b.chosen.selection_id == 22

    def test_single_candidate(self) -> None:
        result = select_market_position([_c(11, "0.01")])
        assert result.chosen.selection_id == 11
        assert result.rejected == []

    def test_empty_candidates_rejected(self) -> None:
        with pytest.raises(ValueError):
            select_market_position([])

    def test_candidates_must_share_market(self) -> None:
        with pytest.raises(ValueError):
            select_market_position([_c(11, "0.01", "1.100"), _c(22, "0.02", "1.200")])

    def test_duplicate_selection_rejected(self) -> None:
        with pytest.raises(ValueError):
            select_market_position([_c(11, "0.01"), _c(11, "0.02")])


class TestLedgerRefusesSecondPosition:
    def test_second_position_same_market_refused(self) -> None:
        ledger = MarketPositionLedger()
        ledger.commit("1.100", 11)
        with pytest.raises(SecondPositionError):
            ledger.commit("1.100", 22)

    def test_different_markets_allowed(self) -> None:
        ledger = MarketPositionLedger()
        ledger.commit("1.100", 11)
        ledger.commit("1.200", 22)  # no raise
        assert ledger.has_position("1.100")
        assert ledger.has_position("1.200")

    def test_re_committing_same_selection_still_refused(self) -> None:
        # Even the identical selection is a second placement attempt — refuse it.
        ledger = MarketPositionLedger()
        ledger.commit("1.100", 11)
        with pytest.raises(SecondPositionError):
            ledger.commit("1.100", 11)
