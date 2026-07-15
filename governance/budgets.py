"""SPEC-103: three separate budgets; none can fund another.

Research/infrastructure capital, betting bankroll, and maximum live-experimentation loss are
three separately tracked budgets. There is **no** transfer/credit API — only per-account
``debit`` — so one budget cannot fund another. Balances are exact integer minor units, never
float.
"""
from __future__ import annotations

from dataclasses import dataclass
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
class SeparatedBudgets:
    research_infrastructure: BudgetAccount
    betting_bankroll: BudgetAccount
    max_experiment_loss: BudgetAccount

    @classmethod
    def of(cls, *, research: int, bankroll: int, experiment_loss: int) -> SeparatedBudgets:
        for name, amount in (("research", research), ("bankroll", bankroll), ("experiment_loss", experiment_loss)):
            if amount < 0:
                raise BudgetError(f"initial {name} budget must be non-negative, got {amount}")
        return cls(
            research_infrastructure=BudgetAccount(BudgetKind.RESEARCH_INFRASTRUCTURE, research),
            betting_bankroll=BudgetAccount(BudgetKind.BETTING_BANKROLL, bankroll),
            max_experiment_loss=BudgetAccount(BudgetKind.MAX_EXPERIMENT_LOSS, experiment_loss),
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
        reduced = BudgetAccount(kind, current - amount_minor)
        # Only the named account changes; the other two are carried through unchanged, so no
        # budget can ever fund another.
        return SeparatedBudgets(
            research_infrastructure=reduced
            if kind is BudgetKind.RESEARCH_INFRASTRUCTURE
            else self.research_infrastructure,
            betting_bankroll=reduced if kind is BudgetKind.BETTING_BANKROLL else self.betting_bankroll,
            max_experiment_loss=reduced if kind is BudgetKind.MAX_EXPERIMENT_LOSS else self.max_experiment_loss,
        )
