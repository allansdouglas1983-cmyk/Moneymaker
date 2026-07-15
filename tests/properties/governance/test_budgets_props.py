"""SPEC-103 property: a debit on one budget never changes the other two."""
from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from governance.budgets import BudgetError, BudgetKind, SeparatedBudgets

pytestmark = pytest.mark.spec("SPEC-103")

_KIND = st.sampled_from(list(BudgetKind))
_AMOUNT = st.integers(min_value=1, max_value=1_000_000)
_BALANCE = st.integers(min_value=0, max_value=10**9)


@given(research=_BALANCE, bankroll=_BALANCE, experiment_loss=_BALANCE, kind=_KIND, amount=_AMOUNT)
def test_debit_leaves_other_budgets_unchanged(
    research: int, bankroll: int, experiment_loss: int, kind: BudgetKind, amount: int
) -> None:
    budgets = SeparatedBudgets.of(research=research, bankroll=bankroll, experiment_loss=experiment_loss)
    before = {k: budgets.balance(k) for k in BudgetKind}
    try:
        after = budgets.debit(kind, amount)
    except BudgetError:
        return  # overdraw refused -> no change at all
    for k in BudgetKind:
        if k is kind:
            assert after.balance(k) == before[k] - amount
        else:
            assert after.balance(k) == before[k]  # untouched: one budget cannot fund another
