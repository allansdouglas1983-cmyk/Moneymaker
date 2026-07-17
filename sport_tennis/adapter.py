"""Tennis :class:`~sport_core.adapter.SportAdapter` declaration (ADR 0017 S4).

Declares the tennis instantiation of the six seams the Phase-1 audit identified
(``docs/architecture/sport-agnostic-audit.md``): decision unit, correlation-cluster
key, event-start vocabulary, capability matrix, and closing-diagnostic taints.
No behavioural hooks attach here (settlement policy is SPEC-084, ``planned``; choice-set
construction/probability/model code is out of scope for this contracts-only slice).
"""
from __future__ import annotations

from sport_core.adapter import SportAdapter
from sport_core.capabilities import SportCapabilities
from sport_tennis.domain import SCHEMA_VERSION

__all__ = ["SCHEMA_VERSION", "TENNIS_CAPABILITIES", "TENNIS_ADAPTER"]


TENNIS_CAPABILITIES = SportCapabilities(
    supports_multi_runner=False,
    supports_binary=True,
    supports_bsp=False,
    supports_dead_heat=False,
    supports_reduction_factor=False,
    supports_retirements=True,
    supports_draw=False,
    supports_partial_settlement=False,
    supports_void_rules=True,
    supports_in_play=True,
    supports_pre_match_only=False,
)
"""Tennis Match Odds is binary (no multi-runner arity, no dead heats, no reduction
factors, no draw outcome), has no BSP (no reconciled starting-price benchmark
selected yet — DR-TENNIS-BENCHMARK-001 unresolved), supports retirements and void
handling, and Betfair turns tennis markets in-play (a market-structure fact, not a
trading permission: the platform's pre-off-only prohibition, CLAUDE.md, stands
regardless of this flag).
"""

TENNIS_ADAPTER = SportAdapter(
    sport_id="tennis",
    decision_unit="match",
    capabilities=TENNIS_CAPABILITIES,
    cluster_key_name="calendar_day_utc",
    event_start_name="scheduled_start",
    closing_diagnostic_taints=frozenset(),
    events_can_start_early=True,
)
"""``closing_diagnostic_taints`` is deliberately empty: tennis has no settlement-time
benchmark chosen yet (no BSP; final-midpoint/WAP/microprice are S8 future interfaces,
selection is evidence-driven per DR-TENNIS-BENCHMARK-001, ADR 0017 S8/S10). An empty
set is the documented "no benchmark yet" state (``sport_core.adapter.SportAdapter``
docstring), not an omission.
"""
