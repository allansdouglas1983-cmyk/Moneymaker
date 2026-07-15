"""Derived book state produced by the L1 reducer (mutable during reduction)."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class RunnerDefinition:
    selection_id: int
    status: str | None = None
    adjustment_factor: Decimal | None = None
    sort_priority: int | None = None
    removal_date: str | None = None


@dataclass
class MarketDefinitionState:
    status: str | None = None
    in_play: bool | None = None
    version: int | None = None
    bet_delay: int | None = None
    number_of_active_runners: int | None = None
    runners: dict[int, RunnerDefinition] = field(default_factory=dict)


@dataclass
class RunnerBookState:
    selection_id: int
    batb: dict[int, tuple[Decimal, Decimal]] = field(default_factory=dict)
    batl: dict[int, tuple[Decimal, Decimal]] = field(default_factory=dict)
    atb: dict[Decimal, Decimal] = field(default_factory=dict)
    atl: dict[Decimal, Decimal] = field(default_factory=dict)
    ltp: Decimal | None = None
    tv: Decimal | None = None


@dataclass
class MarketBookState:
    market_id: str
    definition: MarketDefinitionState = field(default_factory=MarketDefinitionState)
    runners: dict[int, RunnerBookState] = field(default_factory=dict)
    publish_time: int | None = None


@dataclass
class MarketUniverseState:
    markets: dict[str, MarketBookState] = field(default_factory=dict)
