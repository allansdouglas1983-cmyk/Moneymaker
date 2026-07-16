"""SPEC-103: budget separation is nominal-typed, not label-only.

2026-07-16 retrospective audit, finding A6: the three budgets were separated by a
runtime-checked enum label on one shared class — a mismatched-kind swap type-checked cleanly
under mypy --strict. The strengthened contract adds a nominal subclass per budget, typed into
SeparatedBudgets' fields, so the swap is now BOTH a mypy error and a runtime BudgetError
(the same two-layer pattern SPEC-102 uses).
"""
from __future__ import annotations

import pytest

from governance.budgets import (
    BettingBankrollAccount,
    BudgetAccount,
    BudgetError,
    BudgetKind,
    MaxExperimentLossAccount,
    ResearchInfrastructureAccount,
    SeparatedBudgets,
)

pytestmark = pytest.mark.spec("SPEC-103")


def test_nominal_account_types_exist_and_pin_their_kind() -> None:
    research = ResearchInfrastructureAccount(balance_minor=10)
    bankroll = BettingBankrollAccount(balance_minor=5)
    experiment = MaxExperimentLossAccount(balance_minor=2)
    assert research.kind is BudgetKind.RESEARCH_INFRASTRUCTURE
    assert bankroll.kind is BudgetKind.BETTING_BANKROLL
    assert experiment.kind is BudgetKind.MAX_EXPERIMENT_LOSS
    for account in (research, bankroll, experiment):
        assert isinstance(account, BudgetAccount)


def test_kind_cannot_be_overridden_at_construction() -> None:
    with pytest.raises(TypeError):
        ResearchInfrastructureAccount(  # type: ignore[call-arg]
            kind=BudgetKind.BETTING_BANKROLL, balance_minor=1
        )


def test_wrong_nominal_type_in_field_is_refused_at_runtime() -> None:
    # mypy --strict also rejects this construction (arg-type); the ignore below is
    # load-bearing under warn-unused-ignores — if the nominal typing ever weakens, mypy
    # flags the ignore as unnecessary and CI fails.
    with pytest.raises(BudgetError):
        SeparatedBudgets(
            research_infrastructure=BettingBankrollAccount(balance_minor=1),  # type: ignore[arg-type]
            betting_bankroll=BettingBankrollAccount(balance_minor=1),
            max_experiment_loss=MaxExperimentLossAccount(balance_minor=1),
        )


def test_base_account_with_matching_kind_is_refused() -> None:
    # Label-matching is no longer sufficient: the nominal type itself is required.
    with pytest.raises(BudgetError):
        SeparatedBudgets(
            research_infrastructure=BudgetAccount(  # type: ignore[arg-type]
                BudgetKind.RESEARCH_INFRASTRUCTURE, 1
            ),
            betting_bankroll=BettingBankrollAccount(balance_minor=1),
            max_experiment_loss=MaxExperimentLossAccount(balance_minor=1),
        )


def test_of_and_debit_mint_nominal_types() -> None:
    budgets = SeparatedBudgets.of(research=10, bankroll=5, experiment_loss=2)
    assert isinstance(budgets.research_infrastructure, ResearchInfrastructureAccount)
    assert isinstance(budgets.betting_bankroll, BettingBankrollAccount)
    assert isinstance(budgets.max_experiment_loss, MaxExperimentLossAccount)
    after = budgets.debit(BudgetKind.BETTING_BANKROLL, 1)
    assert isinstance(after.betting_bankroll, BettingBankrollAccount)
    assert after.balance(BudgetKind.BETTING_BANKROLL) == 4
    assert isinstance(after.research_infrastructure, ResearchInfrastructureAccount)
    assert isinstance(after.max_experiment_loss, MaxExperimentLossAccount)
