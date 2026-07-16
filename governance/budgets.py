"""SPEC-103: three separate budgets; none can fund another.

Research/infrastructure capital, betting bankroll, and maximum live-experimentation loss are
three separately tracked budgets. There is **no** transfer/credit API — only per-account
``debit`` — so one budget cannot fund another. Balances are exact integer minor units, never
float.

Separation is enforced in two layers (the SPEC-102 pattern; 2026-07-16 audit finding A6):
each budget has a **nominal account type** typed into ``SeparatedBudgets``' fields, so wiring
the wrong account into a field is a ``mypy --strict`` error; and ``__post_init__`` re-checks
the exact runtime type, so the invariant survives dynamically-typed call sites too.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BudgetKind(Enum):
    RESEARCH_INFRASTRUCTURE = "research_infrastructure"
    BETTING_BANKROLL = "betting_bankroll"
    MAX_EXPERIMENT_LOSS = "max_experiment_loss"


class BudgetError(Exception):
    """Raised on an invalid budget operation (overdraw, non-positive amount, negative funding)."""


@dataclass(frozen=True)
class BudgetAccount:
    kind: BudgetKind
    balance_minor: int


@dataclass(frozen=True)
class ResearchInfrastructureAccount(BudgetAccount):
    """Research & infrastructure capital — nominal type; kind is pinned, not a parameter."""

    kind: BudgetKind = field(default=BudgetKind.RESEARCH_INFRASTRUCTURE, init=False)


@dataclass(frozen=True)
class BettingBankrollAccount(BudgetAccount):
    """Betting bankroll — nominal type; kind is pinned, not a parameter."""

    kind: BudgetKind = field(default=BudgetKind.BETTING_BANKROLL, init=False)


@dataclass(frozen=True)
class MaxExperimentLossAccount(BudgetAccount):
    """Maximum live-experimentation loss — nominal type; kind is pinned, not a parameter."""

    kind: BudgetKind = field(default=BudgetKind.MAX_EXPERIMENT_LOSS, init=False)


@dataclass(frozen=True)
class SeparatedBudgets:
    research_infrastructure: ResearchInfrastructureAccount
    betting_bankroll: BettingBankrollAccount
    max_experiment_loss: MaxExperimentLossAccount

    def __post_init__(self) -> None:
        # Runtime backstop behind the nominal field types (defence in depth): the EXACT
        # account type is required — a base account with a matching kind label, or a further
        # subclass, is refused. Non-negativity holds via the raw constructor too.
        for account, expected in (
            (self.research_infrastructure, ResearchInfrastructureAccount),
            (self.betting_bankroll, BettingBankrollAccount),
            (self.max_experiment_loss, MaxExperimentLossAccount),
        ):
            if type(account) is not expected:
                raise BudgetError(
                    f"budget field requires {expected.__name__}, got {type(account).__name__}"
                )
            if account.balance_minor < 0:
                raise BudgetError(
                    f"{account.kind.value} balance must be non-negative, got {account.balance_minor}"
                )

    @classmethod
    def of(cls, *, research: int, bankroll: int, experiment_loss: int) -> SeparatedBudgets:
        for name, amount in (("research", research), ("bankroll", bankroll), ("experiment_loss", experiment_loss)):
            if amount < 0:
                raise BudgetError(f"initial {name} budget must be non-negative, got {amount}")
        return cls(
            research_infrastructure=ResearchInfrastructureAccount(balance_minor=research),
            betting_bankroll=BettingBankrollAccount(balance_minor=bankroll),
            max_experiment_loss=MaxExperimentLossAccount(balance_minor=experiment_loss),
        )

    def _account(self, kind: BudgetKind) -> BudgetAccount:
        if kind is BudgetKind.RESEARCH_INFRASTRUCTURE:
            return self.research_infrastructure
        if kind is BudgetKind.BETTING_BANKROLL:
            return self.betting_bankroll
        return self.max_experiment_loss

    def balance(self, kind: BudgetKind) -> int:
        return self._account(kind).balance_minor

    def debit(self, kind: BudgetKind, amount_minor: int) -> SeparatedBudgets:
        if amount_minor <= 0:
            raise BudgetError(f"debit amount must be positive, got {amount_minor}")
        current = self.balance(kind)
        if amount_minor > current:
            raise BudgetError(f"{kind.value} has {current}, cannot debit {amount_minor}")
        new_balance = current - amount_minor
        # Only the named account changes; the other two are carried through unchanged, so no
        # budget can ever fund another.
        if kind is BudgetKind.RESEARCH_INFRASTRUCTURE:
            return SeparatedBudgets(
                research_infrastructure=ResearchInfrastructureAccount(balance_minor=new_balance),
                betting_bankroll=self.betting_bankroll,
                max_experiment_loss=self.max_experiment_loss,
            )
        if kind is BudgetKind.BETTING_BANKROLL:
            return SeparatedBudgets(
                research_infrastructure=self.research_infrastructure,
                betting_bankroll=BettingBankrollAccount(balance_minor=new_balance),
                max_experiment_loss=self.max_experiment_loss,
            )
        return SeparatedBudgets(
            research_infrastructure=self.research_infrastructure,
            betting_bankroll=self.betting_bankroll,
            max_experiment_loss=MaxExperimentLossAccount(balance_minor=new_balance),
        )
