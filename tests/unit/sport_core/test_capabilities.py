"""Sport core: capability matrix + adapter registry (ADR 0017 S1, founder-directed).

The Core's philosophical boundary: "any mutually exclusive Betfair market." The Core
never asks `if sport == ...`; it asks `capabilities.supports_*`. Adapters declare a
closed capability matrix; the registry refuses duplicates and runtime mutation.
"""
from __future__ import annotations

import dataclasses

import pytest

from sport_core.adapter import (
    AdapterRegistrationError,
    SportAdapter,
    SportAdapterRegistry,
)
from sport_core.capabilities import SportCapabilities

pytestmark = pytest.mark.spec("SPEC-091")


def _racing_caps() -> SportCapabilities:
    return SportCapabilities(
        supports_multi_runner=True,
        supports_binary=False,
        supports_bsp=True,
        supports_dead_heat=True,
        supports_reduction_factor=True,
        supports_retirements=False,
        supports_draw=False,
        supports_partial_settlement=True,
        supports_void_rules=True,
        supports_in_play=True,
        supports_pre_match_only=False,
    )


def _tennis_caps() -> SportCapabilities:
    return SportCapabilities(
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


def _adapter(
    sport_id: str = "horse_racing",
    decision_unit: str = "race",
    caps: SportCapabilities | None = None,
) -> SportAdapter:
    return SportAdapter(
        sport_id=sport_id,
        decision_unit=decision_unit,
        capabilities=caps if caps is not None else _racing_caps(),
        cluster_key_name="meeting_day",
        event_start_name="off",
        closing_diagnostic_taints=frozenset({"l8_evidence.reconciled_bsp:RECONCILED_BSP"}),
    )


# --- capability matrix -----------------------------------------------------------------------


def test_capabilities_is_frozen_and_all_fields_are_explicit_booleans() -> None:
    caps = _racing_caps()
    with pytest.raises(dataclasses.FrozenInstanceError):
        caps.supports_bsp = False  # type: ignore[misc]
    for field in dataclasses.fields(SportCapabilities):
        assert field.type in ("bool", bool), field.name
        assert field.default is dataclasses.MISSING, (
            f"{field.name} must have NO default — every adapter declares every "
            "capability explicitly; silence is not a capability statement"
        )


def test_capabilities_refuses_contradictory_arity() -> None:
    # A sport must support at least one market arity.
    with pytest.raises(ValueError):
        SportCapabilities(
            supports_multi_runner=False,
            supports_binary=False,
            supports_bsp=False,
            supports_dead_heat=False,
            supports_reduction_factor=False,
            supports_retirements=False,
            supports_draw=False,
            supports_partial_settlement=False,
            supports_void_rules=True,
            supports_in_play=False,
            supports_pre_match_only=True,
        )


def test_capabilities_refuses_bsp_without_multi_runner_reduction_coherence() -> None:
    # Reduction factors only exist where selections can be removed from a multi-runner
    # book; declaring reduction factors on a binary-only sport is a contradiction.
    with pytest.raises(ValueError):
        SportCapabilities(
            supports_multi_runner=False,
            supports_binary=True,
            supports_bsp=False,
            supports_dead_heat=False,
            supports_reduction_factor=True,
            supports_retirements=True,
            supports_draw=False,
            supports_partial_settlement=False,
            supports_void_rules=True,
            supports_in_play=True,
            supports_pre_match_only=False,
        )


def test_would_support_football_match_odds() -> None:
    # The founder's design test: 3-outcome (home/draw/away), no BSP, no dead heats,
    # abandonment voids. The matrix must express it without any new field.
    football = SportCapabilities(
        supports_multi_runner=True,
        supports_binary=False,
        supports_bsp=False,
        supports_dead_heat=False,
        supports_reduction_factor=False,
        supports_retirements=False,
        supports_draw=True,
        supports_partial_settlement=False,
        supports_void_rules=True,
        supports_in_play=True,
        supports_pre_match_only=False,
    )
    assert football.supports_draw and not football.supports_bsp


def test_would_support_binary_prediction_market() -> None:
    # The founder's second design test: pure binary, pre-match only, no sport events.
    binary = SportCapabilities(
        supports_multi_runner=False,
        supports_binary=True,
        supports_bsp=False,
        supports_dead_heat=False,
        supports_reduction_factor=False,
        supports_retirements=False,
        supports_draw=False,
        supports_partial_settlement=False,
        supports_void_rules=True,
        supports_in_play=False,
        supports_pre_match_only=True,
    )
    assert binary.supports_binary and binary.supports_pre_match_only


# --- adapter + registry ----------------------------------------------------------------------


def test_adapter_is_frozen_and_validates_decision_unit_against_ledger_vocabulary() -> None:
    adapter = _adapter()
    with pytest.raises(dataclasses.FrozenInstanceError):
        adapter.sport_id = "x"  # type: ignore[misc]
    with pytest.raises(ValueError):
        _adapter(decision_unit="runner")  # selections are never the unit of analysis


def test_adapter_decision_unit_must_be_in_the_governed_closed_set() -> None:
    # The adapter layer cannot mint decision units the governed trial-ledger set
    # (correction 0003) does not contain.
    with pytest.raises(ValueError):
        _adapter(sport_id="football", decision_unit="fixture")


def test_registry_refuses_duplicate_sport_and_has_no_mutation_api() -> None:
    registry = SportAdapterRegistry()
    registry.register(_adapter())
    with pytest.raises(AdapterRegistrationError):
        registry.register(_adapter())
    import inspect

    public = {
        n for n, _ in inspect.getmembers(SportAdapterRegistry, predicate=inspect.isfunction)
        if not n.startswith("_")
    }
    assert public == {"register", "get", "sport_ids"}


def test_core_asks_capabilities_never_sport_identity() -> None:
    # Structural guard: sport_core source must not branch on sport identity strings.
    import inspect

    import sport_core.adapter as adapter_mod
    import sport_core.capabilities as caps_mod

    for mod in (adapter_mod, caps_mod):
        source = inspect.getsource(mod)
        for forbidden in ('== "horse_racing"', '== "tennis"', "== 'horse_racing'", "== 'tennis'"):
            assert forbidden not in source


def test_tennis_and_racing_capability_declarations_differ_where_they_must() -> None:
    racing, tennis = _racing_caps(), _tennis_caps()
    assert racing.supports_bsp and not tennis.supports_bsp
    assert racing.supports_dead_heat and not tennis.supports_dead_heat
    assert racing.supports_reduction_factor and not tennis.supports_reduction_factor
    assert tennis.supports_retirements and not racing.supports_retirements
    assert racing.supports_multi_runner and tennis.supports_binary
