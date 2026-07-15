"""Idempotent, versioned settlement ledger (SPEC-082).

A duplicate acknowledgement adds no exposure; a resettlement (higher version + flag) supersedes;
a conflicting same-version or a stale version is refused.
"""
from __future__ import annotations

from l7_settle.settlement import MarketSettlement


class SettlementConflict(Exception):
    """Raised on a conflicting or stale settlement for a market."""


class SettlementLedger:
    def __init__(self) -> None:
        self._by_market: dict[str, MarketSettlement] = {}

    def apply(self, settlement: MarketSettlement) -> MarketSettlement:
        existing = self._by_market.get(settlement.market_id)
        if existing is None:
            self._by_market[settlement.market_id] = settlement
            return settlement
        if settlement.settlement_version == existing.settlement_version:
            if settlement != existing:
                raise SettlementConflict(
                    f"{settlement.market_id}: conflicting settlement at version {settlement.settlement_version}"
                )
            return existing  # duplicate acknowledgement — idempotent, no double exposure
        if settlement.settlement_version < existing.settlement_version:
            raise SettlementConflict(
                f"{settlement.market_id}: stale version {settlement.settlement_version} "
                f"< {existing.settlement_version}"
            )
        if not settlement.resettlement_flag:
            raise SettlementConflict(
                f"{settlement.market_id}: version {settlement.settlement_version} supersedes "
                f"{existing.settlement_version} but resettlement_flag is not set"
            )
        self._by_market[settlement.market_id] = settlement
        return settlement

    def current(self, market_id: str) -> MarketSettlement | None:
        return self._by_market.get(market_id)
