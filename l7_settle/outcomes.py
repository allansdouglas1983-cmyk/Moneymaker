"""Settlement input contracts and outcome enums (SPEC-080/082).

Money types: stakes are exact integer minor units; odds and reduction factors are exact
``Decimal``. There is deliberately **no** per-order commission field (SPEC-080).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class MarketStatus(Enum):
    SETTLED = "SETTLED"
    VOID = "VOID"
    ABANDONED = "ABANDONED"
    UNKNOWN = "UNKNOWN"


class RunnerResult(Enum):
    WINNER = "WINNER"
    LOSER = "LOSER"
    REMOVED = "REMOVED"
    VOID = "VOID"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RunnerOutcome:
    result: RunnerResult
    dead_heat_count: int = 1
    reduction_factor: Decimal | None = None

    def __post_init__(self) -> None:
        if self.dead_heat_count < 1:
            raise ValueError(f"dead_heat_count must be >= 1, got {self.dead_heat_count}")


@dataclass(frozen=True)
class MarketOutcome:
    market_status: MarketStatus
    runners: dict[int, RunnerOutcome] = field(default_factory=dict)


@dataclass(frozen=True)
class MatchedPosition:
    runner_id: int
    matched_stake_minor: int
    matched_odds: Decimal
    applicable_reduction_factors: tuple[Decimal, ...] = ()

    def __post_init__(self) -> None:
        if self.matched_stake_minor < 0:
            raise ValueError(f"matched_stake_minor must be non-negative, got {self.matched_stake_minor}")
        if self.matched_odds <= 1:
            raise ValueError(f"matched_odds must be > 1, got {self.matched_odds}")
