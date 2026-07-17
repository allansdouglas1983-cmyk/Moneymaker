"""Settlement-policy seam (ADR 0017, audit slice S3; governed surface C8).

A sport adapter names its settlement policy here; the Core settles through the seam
without asking which sport it is. Two design constraints dominate:

* **Racing behaviour is byte-identical.** :class:`RacingSettlementPolicy` is PURE
  DELEGATION to the existing :func:`l7_settle.settlement.settle_market` — same module
  path, same enums, same result object, same exceptions. Nothing in racing settlement
  moved, and the pinned mutation survivors (specs/mutation-survivors.yaml) keep keying
  off the original ``l7_settle.settlement`` / ``l7_settle.outcomes`` paths.
* **Tennis still refuses everything.** :class:`TennisSettlementPolicy` raises the
  SPEC-084 :class:`~l7_settle.tennis_rules.SettlementPolicyPendingError` for every
  input: the whole-matrix refusal is reached THROUGH the seam, never bypassed by it.
  When the founder-approved policy matrix activates (its own governed slice), the
  tennis policy gains a real implementation and this refusal disappears with it —
  whole, never partially.

The ``settle`` signature is the existing sport-agnostic settlement vocabulary
(positions, outcome, effective commission, transaction charges, statement reference,
settlement version) — nothing racing-specific appears in the seam itself; racing's
reduction factors and dead heats live inside ``MatchedPosition``/``RunnerOutcome``
where they always did.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable

from l7_settle.outcomes import MarketOutcome, MatchedPosition
from l7_settle.settlement import MarketSettlement, settle_market
from l7_settle.tennis_rules import SettlementPolicyPendingError

__all__ = [
    "SettlementPolicy",
    "RacingSettlementPolicy",
    "TennisSettlementPolicy",
    "PolicyRegistrationError",
    "SettlementPolicyRegistry",
    "RACING_SETTLEMENT_POLICY",
    "TENNIS_SETTLEMENT_POLICY",
    "SETTLEMENT_POLICIES",
]


@runtime_checkable
class SettlementPolicy(Protocol):
    """One sport's market-settlement entry point. Deterministic tested code only —
    no LLM may implement or back a settlement policy (CLAUDE.md rule 3), and a policy
    with no approved rules must refuse (never guess) exactly as the tennis policy does.
    """

    @property
    def sport_id(self) -> str: ...

    @property
    def policy_version(self) -> str: ...

    def settle(
        self,
        *,
        market_id: str,
        positions: Sequence[MatchedPosition],
        outcome: MarketOutcome,
        commission_rate_effective: Decimal,
        transaction_charges_minor: int,
        statement_reference: str,
        settlement_version: int,
        resettlement_flag: bool,
    ) -> MarketSettlement: ...


@dataclass(frozen=True)
class RacingSettlementPolicy:
    """Pure delegation to :func:`l7_settle.settlement.settle_market`. No logic lives
    here — adding any would fork racing settlement behaviour behind the seam."""

    sport_id: str = "horse_racing"
    policy_version: str = "racing-settlement-v1"

    def settle(
        self,
        *,
        market_id: str,
        positions: Sequence[MatchedPosition],
        outcome: MarketOutcome,
        commission_rate_effective: Decimal,
        transaction_charges_minor: int,
        statement_reference: str,
        settlement_version: int,
        resettlement_flag: bool,
    ) -> MarketSettlement:
        return settle_market(
            market_id=market_id,
            positions=positions,
            outcome=outcome,
            commission_rate_effective=commission_rate_effective,
            transaction_charges_minor=transaction_charges_minor,
            statement_reference=statement_reference,
            settlement_version=settlement_version,
            resettlement_flag=resettlement_flag,
        )


@dataclass(frozen=True)
class TennisSettlementPolicy:
    """Refuses every settlement: the SPEC-084 outcome-to-settlement policy matrix is
    not yet founder-approved (DR-TENNIS-SETTLEMENT-001 unresolved). See
    :mod:`l7_settle.tennis_rules` — the matrix activates whole, never partially."""

    sport_id: str = "tennis"
    policy_version: str = "tennis-settlement-policy-pending"

    def settle(
        self,
        *,
        market_id: str,
        positions: Sequence[MatchedPosition],
        outcome: MarketOutcome,
        commission_rate_effective: Decimal,
        transaction_charges_minor: int,
        statement_reference: str,
        settlement_version: int,
        resettlement_flag: bool,
    ) -> MarketSettlement:
        # Guard dominance: the refusal legitimately ignores every input except the
        # market being named — no field may influence a pending policy's behaviour.
        del positions, outcome, commission_rate_effective, transaction_charges_minor
        del statement_reference, settlement_version, resettlement_flag
        raise SettlementPolicyPendingError(
            f"{market_id}: tennis settlement is PENDING_EXCHANGE_RULES_VERIFICATION "
            "(SPEC-084, DR-TENNIS-SETTLEMENT-001 unresolved) — no deterministic "
            "outcome-to-settlement mapping is approved; the policy matrix activates "
            "whole, never partially (l7_settle.tennis_rules)."
        )


class PolicyRegistrationError(ValueError):
    """A duplicate sport_id registration — policies are declared once, never replaced."""


class SettlementPolicyRegistry:
    """Append-only policy registry. No mutation, no replacement, no delete."""

    def __init__(self) -> None:
        self._policies: dict[str, SettlementPolicy] = {}

    def register(self, policy: SettlementPolicy) -> None:
        if policy.sport_id in self._policies:
            raise PolicyRegistrationError(
                f"sport_id {policy.sport_id!r} already has a settlement policy; "
                "policies are declared once and never replaced at runtime"
            )
        self._policies[policy.sport_id] = policy

    def get(self, sport_id: str) -> SettlementPolicy:
        try:
            return self._policies[sport_id]
        except KeyError:
            raise KeyError(f"no settlement policy registered for sport_id {sport_id!r}") from None

    def sport_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._policies))


RACING_SETTLEMENT_POLICY = RacingSettlementPolicy()
TENNIS_SETTLEMENT_POLICY = TennisSettlementPolicy()

SETTLEMENT_POLICIES = SettlementPolicyRegistry()
SETTLEMENT_POLICIES.register(RACING_SETTLEMENT_POLICY)
SETTLEMENT_POLICIES.register(TENNIS_SETTLEMENT_POLICY)
