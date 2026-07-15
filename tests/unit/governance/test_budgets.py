"""SPEC-103: three separate budgets; none can fund another."""
from __future__ import annotations

import pytest

from governance.budgets import BudgetAccount, BudgetError, BudgetKind, SeparatedBudgets

pytestmark = pytest.mark.spec("SPEC-103")


def _budgets() -> SeparatedBudgets:
    return SeparatedBudgets.of(research=10_000, bankroll=5_000, experiment_loss=2_000)


def test_no_transfer_api_exists() -> None:
    for forbidden in ("transfer", "move", "fund", "credit", "reallocate"):
        assert not hasattr(SeparatedBudgets, forbidden)


def test_debit_reduces_only_named_account() -> None:
    result = _budgets().debit(BudgetKind.BETTING_BANKROLL, 1_500)
    assert result.balance(BudgetKind.BETTING_BANKROLL) == 3_500
    assert result.balance(BudgetKind.RESEARCH_INFRASTRUCTURE) == 10_000
    assert result.balance(BudgetKind.MAX_EXPERIMENT_LOSS) == 2_000


def test_overdraw_is_refused() -> None:
    with pytest.raises(BudgetError):
        _budgets().debit(BudgetKind.MAX_EXPERIMENT_LOSS, 2_001)


def test_non_positive_debit_is_refused() -> None:
    with pytest.raises(BudgetError):
        _budgets().debit(BudgetKind.RESEARCH_INFRASTRUCTURE, 0)


def test_mismatched_account_kind_is_refused() -> None:
    # Raw constructor still enforces field/kind consistency (not only via .of()).
    with pytest.raises(BudgetError):
        SeparatedBudgets(
            research_infrastructure=BudgetAccount(BudgetKind.BETTING_BANKROLL, 1),  # wrong kind
            betting_bankroll=BudgetAccount(BudgetKind.BETTING_BANKROLL, 1),
            max_experiment_loss=BudgetAccount(BudgetKind.MAX_EXPERIMENT_LOSS, 1),
        )


def test_negative_balance_is_refused_by_raw_constructor() -> None:
    with pytest.raises(BudgetError):
        SeparatedBudgets(
            research_infrastructure=BudgetAccount(BudgetKind.RESEARCH_INFRASTRUCTURE, -1),
            betting_bankroll=BudgetAccount(BudgetKind.BETTING_BANKROLL, 1),
            max_experiment_loss=BudgetAccount(BudgetKind.MAX_EXPERIMENT_LOSS, 1),
        )
