"""ADR 0017 S3 — settlement-policy seam (audit slice S3, governed surface C8).

The seam lets a sport adapter name its settlement policy WITHOUT moving, renaming or
re-implementing anything in racing settlement. Two invariants dominate:

* **Racing behaviour is byte-identical.** The racing policy is pure delegation to the
  existing ``l7_settle.settlement.settle_market`` — same module path, same enums, same
  results object, same exceptions. The pinned mutation survivors
  (specs/mutation-survivors.yaml) key off those stable paths; this seam must not
  perturb them (audit C8).
* **Tennis still refuses everything.** The tennis policy raises the SPEC-084
  ``SettlementPolicyPendingError`` for every input — the whole-matrix refusal from
  ``l7_settle.tennis_rules`` reached through the seam, not bypassed by it.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from l7_settle.outcomes import (
    MarketOutcome,
    MarketStatus,
    MatchedPosition,
    RunnerOutcome,
    RunnerResult,
)
from l7_settle.policy import (
    RACING_SETTLEMENT_POLICY,
    SETTLEMENT_POLICIES,
    TENNIS_SETTLEMENT_POLICY,
    PolicyRegistrationError,
    RacingSettlementPolicy,
    SettlementPolicy,
    SettlementPolicyRegistry,
    TennisSettlementPolicy,
)
from l7_settle.settlement import SettlementBlocked, settle_market
from l7_settle.tennis_rules import SettlementPolicyPendingError

pytestmark = pytest.mark.spec("SPEC-080")

_COMMISSION = Decimal("0.02")


def _positions() -> tuple[MatchedPosition, ...]:
    return (
        MatchedPosition(runner_id=1, matched_stake_minor=200, matched_odds=Decimal("3.5")),
        MatchedPosition(runner_id=2, matched_stake_minor=300, matched_odds=Decimal("4.0")),
    )


def _outcome(status: MarketStatus = MarketStatus.SETTLED) -> MarketOutcome:
    return MarketOutcome(
        market_status=status,
        runners={
            1: RunnerOutcome(result=RunnerResult.WINNER),
            2: RunnerOutcome(result=RunnerResult.LOSER),
        },
    )


def _settle_kwargs(status: MarketStatus = MarketStatus.SETTLED) -> dict[str, object]:
    return {
        "market_id": "1.234",
        "positions": _positions(),
        "outcome": _outcome(status),
        "commission_rate_effective": _COMMISSION,
        "transaction_charges_minor": 7,
        "statement_reference": "stmt-1",
        "settlement_version": 2,
        "resettlement_flag": False,
    }


# --- racing policy: pure delegation, byte-identical -------------------------------------------


def test_racing_policy_result_is_identical_to_direct_settle_market() -> None:
    direct = settle_market(**_settle_kwargs())  # type: ignore[arg-type]
    via_policy = RACING_SETTLEMENT_POLICY.settle(**_settle_kwargs())  # type: ignore[arg-type]
    assert via_policy == direct


def test_racing_policy_void_market_is_identical_to_direct_settle_market() -> None:
    direct = settle_market(**_settle_kwargs(MarketStatus.VOID))  # type: ignore[arg-type]
    via_policy = RACING_SETTLEMENT_POLICY.settle(**_settle_kwargs(MarketStatus.VOID))  # type: ignore[arg-type]
    assert via_policy == direct


def test_racing_policy_propagates_settlement_blocked_unchanged() -> None:
    with pytest.raises(SettlementBlocked):
        RACING_SETTLEMENT_POLICY.settle(**_settle_kwargs(MarketStatus.UNKNOWN))  # type: ignore[arg-type]


def test_racing_policy_identity() -> None:
    assert RACING_SETTLEMENT_POLICY.sport_id == "horse_racing"
    assert RACING_SETTLEMENT_POLICY.policy_version
    assert isinstance(RACING_SETTLEMENT_POLICY, RacingSettlementPolicy)


# --- tennis policy: the SPEC-084 whole-matrix refusal reached through the seam -----------------


def test_tennis_policy_refuses_every_settlement() -> None:
    with pytest.raises(SettlementPolicyPendingError):
        TENNIS_SETTLEMENT_POLICY.settle(**_settle_kwargs())  # type: ignore[arg-type]


def test_tennis_policy_refusal_cites_spec_084() -> None:
    with pytest.raises(SettlementPolicyPendingError, match="SPEC-084"):
        TENNIS_SETTLEMENT_POLICY.settle(**_settle_kwargs())  # type: ignore[arg-type]
    assert isinstance(TENNIS_SETTLEMENT_POLICY, TennisSettlementPolicy)
    assert TENNIS_SETTLEMENT_POLICY.sport_id == "tennis"


# --- protocol + registry ------------------------------------------------------------------------


def test_both_policies_satisfy_the_runtime_checkable_protocol() -> None:
    assert isinstance(RACING_SETTLEMENT_POLICY, SettlementPolicy)
    assert isinstance(TENNIS_SETTLEMENT_POLICY, SettlementPolicy)
    assert not isinstance(object(), SettlementPolicy)


def test_default_registry_contains_exactly_racing_and_tennis() -> None:
    assert SETTLEMENT_POLICIES.sport_ids() == ("horse_racing", "tennis")
    assert SETTLEMENT_POLICIES.get("horse_racing") is RACING_SETTLEMENT_POLICY
    assert SETTLEMENT_POLICIES.get("tennis") is TENNIS_SETTLEMENT_POLICY


def test_registry_refuses_duplicates_and_unknown_sport() -> None:
    registry = SettlementPolicyRegistry()
    registry.register(RACING_SETTLEMENT_POLICY)
    with pytest.raises(PolicyRegistrationError):
        registry.register(RACING_SETTLEMENT_POLICY)
    with pytest.raises(KeyError):
        registry.get("football")


def test_registry_has_no_mutation_api() -> None:
    import inspect

    public = {
        n
        for n, _ in inspect.getmembers(SettlementPolicyRegistry, predicate=inspect.isfunction)
        if not n.startswith("_")
    }
    assert public == {"register", "get", "sport_ids"}


# --- C8 stability: the seam moves nothing --------------------------------------------------------


def test_racing_settlement_paths_and_enums_are_unmoved() -> None:
    # Pinned mutation survivors (specs/mutation-survivors.yaml) key off these exact
    # module paths and enum members; the seam must not move or alias-away any of them.
    from l7_settle.settlement import MarketSettlement, settle_market  # noqa: F401

    assert settle_market.__module__ == "l7_settle.settlement"
    assert MarketSettlement.__module__ == "l7_settle.settlement"
    assert MarketStatus.__module__ == "l7_settle.outcomes"
    assert {m.name for m in MarketStatus} == {"SETTLED", "VOID", "ABANDONED", "UNKNOWN"}
    assert {m.name for m in RunnerResult} == {"WINNER", "LOSER", "REMOVED", "VOID", "UNKNOWN"}
