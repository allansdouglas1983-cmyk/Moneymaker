"""SPEC-054 properties: single-position selection is deterministic; the second-position guard
dominates regardless of EV or fields.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from l5_decision.one_runner import (
    Candidate,
    SecondPositionError,
    MarketPositionLedger,
    select_market_position,
)

pytestmark = pytest.mark.spec("SPEC-054")

_EV = st.integers(min_value=-100, max_value=100).map(lambda n: Decimal(n) / Decimal(100))


@st.composite
def _candidates(draw: st.DrawFn) -> list[Candidate]:
    ids = draw(st.lists(st.integers(min_value=1, max_value=40), min_size=1, max_size=8, unique=True))
    return [Candidate(market_id="1.100", selection_id=i, conservative_ev=draw(_EV)) for i in ids]


@given(candidates=_candidates())
def test_chosen_maximises_ev_then_minimises_id(candidates: list[Candidate]) -> None:
    result = select_market_position(candidates)
    best_ev = max(c.conservative_ev for c in candidates)
    assert result.chosen.conservative_ev == best_ev
    tied_ids = [c.selection_id for c in candidates if c.conservative_ev == best_ev]
    assert result.chosen.selection_id == min(tied_ids)
    # Exactly one chosen; everything else recorded as rejected.
    assert len(result.rejected) == len(candidates) - 1


@given(candidates=_candidates(), data=st.data())
def test_selection_is_order_independent(candidates: list[Candidate], data: st.DataObject) -> None:
    shuffled = data.draw(st.permutations(candidates))
    assert select_market_position(candidates).chosen.selection_id == (
        select_market_position(list(shuffled)).chosen.selection_id
    )


@given(first=st.integers(min_value=1, max_value=40), second=st.integers(min_value=1, max_value=40))
def test_second_position_always_refused(first: int, second: int) -> None:
    # The guard dominates: once a market has a position, a second is refused regardless of the
    # second candidate's selection id (the ledger tracks positions, not EV).
    ledger = MarketPositionLedger()
    ledger.commit("1.100", first)
    with pytest.raises(SecondPositionError):
        ledger.commit("1.100", second)
