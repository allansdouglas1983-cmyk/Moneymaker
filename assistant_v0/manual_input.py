"""PERSONAL_TENNIS_ASSISTANT_V0 — manual market-input contract (STAGE3-0003 §6).

A deterministic, immutable snapshot of one upcoming tennis match's Match-Odds book, entered
by hand from the Betfair UI (source ``MANUAL_BETFAIR_UI``). Prices are exact ``Decimal`` and
validated against the canonical Betfair ladder (``price_contracts.ladder``). Malformed
prices/sizes, a missing timestamp, a future/after-start timestamp, a bad source token, and
an unknown market status all REFUSE at construction (``ManualInputError``). The snapshot is
frozen — immutable after submission; there is no retrospective mutation.

Recording a SUSPENDED or in-play market is allowed (it is a fact about the book); whether
the market is USABLE for a probability is judged downstream (``market_probability``).

No scraping, no credentials, no network. Import-quarantined from execution layers.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal

from price_contracts.ladder import is_on_ladder

MANUAL_SOURCE = "MANUAL_BETFAIR_UI"
_ALLOWED_TOURS = {"ATP", "WTA"}
_ALLOWED_STATUSES = {"OPEN", "SUSPENDED", "CLOSED", "INACTIVE"}


class ManualInputError(Exception):
    """The manual snapshot is malformed and is refused at construction."""


def _check_price(name: str, value: object) -> None:
    if not isinstance(value, Decimal):
        raise ManualInputError(f"{name} must be an exact Decimal, got {type(value).__name__}")
    if not is_on_ladder(value):
        raise ManualInputError(f"{name} {value} is not a canonical Betfair ladder price")


def _check_size(name: str, value: object) -> None:
    if not isinstance(value, Decimal):
        raise ManualInputError(f"{name} must be an exact Decimal, got {type(value).__name__}")
    if value < 0:
        raise ManualInputError(f"{name} must be non-negative, got {value}")


@dataclass(frozen=True)
class ManualMarketSnapshot:
    """One immutable manual Match-Odds snapshot for an upcoming tennis match (§6)."""

    competitor_a: str
    competitor_b: str
    competitor_a_id: str | None
    competitor_b_id: str | None
    tour: str
    scheduled_start_ms: int
    input_timestamp_ms: int
    source: str
    back_a: Decimal
    back_a_size: Decimal
    lay_a: Decimal
    lay_a_size: Decimal
    back_b: Decimal
    back_b_size: Decimal
    lay_b: Decimal
    lay_b_size: Decimal
    market_status: str
    in_play: bool
    market_id: str | None
    event_id: str | None

    def __post_init__(self) -> None:
        if self.source != MANUAL_SOURCE:
            raise ManualInputError(f"source must be {MANUAL_SOURCE!r}, got {self.source!r}")
        if self.tour not in _ALLOWED_TOURS:
            raise ManualInputError(f"tour must be one of {sorted(_ALLOWED_TOURS)}, got {self.tour!r}")
        if self.market_status not in _ALLOWED_STATUSES:
            raise ManualInputError(f"unknown market_status {self.market_status!r}")
        if not isinstance(self.competitor_a, str) or not self.competitor_a:
            raise ManualInputError("competitor_a must be a non-empty string")
        if not isinstance(self.competitor_b, str) or not self.competitor_b:
            raise ManualInputError("competitor_b must be a non-empty string")
        for nm, v in (("back_a", self.back_a), ("lay_a", self.lay_a),
                      ("back_b", self.back_b), ("lay_b", self.lay_b)):
            _check_price(nm, v)
        for nm, v in (("back_a_size", self.back_a_size), ("lay_a_size", self.lay_a_size),
                      ("back_b_size", self.back_b_size), ("lay_b_size", self.lay_b_size)):
            _check_size(nm, v)
        if not isinstance(self.input_timestamp_ms, int) or self.input_timestamp_ms <= 0:
            raise ManualInputError("input_timestamp_ms is required (positive int)")
        if not isinstance(self.scheduled_start_ms, int) or self.scheduled_start_ms <= 0:
            raise ManualInputError("scheduled_start_ms is required (positive int)")
        # no retrospective input after the match begins; a pre-match snapshot only
        if self.input_timestamp_ms > self.scheduled_start_ms:
            raise ManualInputError(
                f"input_timestamp_ms {self.input_timestamp_ms} is after scheduled start "
                f"{self.scheduled_start_ms} (no retrospective/future input)"
            )

    def content_digest(self) -> str:
        payload = {
            "competitor_a": self.competitor_a, "competitor_b": self.competitor_b,
            "competitor_a_id": self.competitor_a_id, "competitor_b_id": self.competitor_b_id,
            "tour": self.tour, "scheduled_start_ms": self.scheduled_start_ms,
            "input_timestamp_ms": self.input_timestamp_ms, "source": self.source,
            "back_a": str(self.back_a), "back_a_size": str(self.back_a_size),
            "lay_a": str(self.lay_a), "lay_a_size": str(self.lay_a_size),
            "back_b": str(self.back_b), "back_b_size": str(self.back_b_size),
            "lay_b": str(self.lay_b), "lay_b_size": str(self.lay_b_size),
            "market_status": self.market_status, "in_play": self.in_play,
            "market_id": self.market_id, "event_id": self.event_id,
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()
