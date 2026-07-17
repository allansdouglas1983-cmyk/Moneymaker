"""SportAdapter contract + registry (ADR 0017 S1).

An adapter is a frozen DECLARATION of one sport's instantiation of the six seams the
Phase-1 audit identified (docs/architecture/sport-agnostic-audit.md): decision unit,
correlation-cluster key, event-start vocabulary, settlement policy, closing-diagnostic
taints, and choice-set construction. This module carries the declaration surface; the
behavioural hooks (settlement policy, choice-set builders) attach in their own layers'
slices so no money-module logic moves in this one.

The Core never branches on ``sport_id`` — it reads ``capabilities`` (see
capabilities.py). ``decision_unit`` is validated against the governed closed set in
``l8_evidence.trial_ledger.PERMITTED_DECISION_UNITS`` (correction 0003): an adapter
cannot mint a unit the evidence ledger would refuse — future sports extend that set
by a governed change first, then declare an adapter.
"""
from __future__ import annotations

from dataclasses import dataclass

from l3_features.build_context import LiveBoundaryPolicy
from l8_evidence.trial_ledger import PERMITTED_DECISION_UNITS
from sport_core.capabilities import SportCapabilities

__all__ = [
    "AdapterRegistrationError",
    "SportAdapter",
    "SportAdapterRegistry",
]


class AdapterRegistrationError(ValueError):
    """A duplicate sport_id registration — adapters are declared once, never replaced."""


@dataclass(frozen=True)
class SportAdapter:
    """One sport's immutable declaration.

    ``cluster_key_name`` names the sport's shared-conditions correlation block
    (racing: ``meeting_day``; tennis: UTC calendar day) — the block-bootstrap and
    cross-fit fold unit. ``event_start_name`` names the sport's event-start concept
    (racing: "off"). ``closing_diagnostic_taints`` is the sport's set of
    settlement-time-benchmark taint markers that must never reach pre-event features
    (racing: reconciled BSP) — the l3 leakage-guard mechanism consumes these; an
    empty set means the sport has no settlement-time benchmark yet (tennis, until
    the benchmark research resolves).

    ``events_can_start_early`` (A1, conceptual audit F-01) is the sport's event-timing
    FACT: whether an event can begin before its scheduled start (racing: False — races
    are only ever delayed; tennis: True — matches are routinely brought forward). The
    knowability-boundary POLICY derives from this fact via :attr:`live_boundary_policy`
    and is never declared separately, so an early-start sport can never obtain the
    scheduled-start floor by construction.
    """

    sport_id: str
    decision_unit: str
    capabilities: SportCapabilities
    cluster_key_name: str
    event_start_name: str
    closing_diagnostic_taints: frozenset[str]
    events_can_start_early: bool

    @property
    def live_boundary_policy(self) -> LiveBoundaryPolicy:
        """The l3 knowability-boundary policy DERIVED from ``events_can_start_early``."""
        if self.events_can_start_early:
            return LiveBoundaryPolicy.OBSERVED_MARKET_STATE
        return LiveBoundaryPolicy.SCHEDULED_START_FLOOR

    def __post_init__(self) -> None:
        if not self.sport_id or not self.sport_id.strip():
            raise ValueError("sport_id must be non-empty")
        if self.decision_unit not in PERMITTED_DECISION_UNITS:
            raise ValueError(
                f"decision_unit {self.decision_unit!r} is not in the governed closed set "
                f"{sorted(PERMITTED_DECISION_UNITS)} (correction 0003); extend the set by a "
                "governed change before declaring the adapter"
            )
        if not self.cluster_key_name or not self.cluster_key_name.strip():
            raise ValueError("cluster_key_name must be non-empty")
        if not self.event_start_name or not self.event_start_name.strip():
            raise ValueError("event_start_name must be non-empty")


class SportAdapterRegistry:
    """Append-only adapter registry. No mutation, no replacement, no delete."""

    def __init__(self) -> None:
        self._adapters: dict[str, SportAdapter] = {}

    def register(self, adapter: SportAdapter) -> None:
        if adapter.sport_id in self._adapters:
            raise AdapterRegistrationError(
                f"sport_id {adapter.sport_id!r} is already registered; adapters are "
                "declared once and never replaced at runtime"
            )
        self._adapters[adapter.sport_id] = adapter

    def get(self, sport_id: str) -> SportAdapter:
        try:
            return self._adapters[sport_id]
        except KeyError:
            raise KeyError(f"no adapter registered for sport_id {sport_id!r}") from None

    def sport_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))
