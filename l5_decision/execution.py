"""Crossing execution policy only in v1 — ``taker-v1`` (SPEC-052).

v1 crosses the spread and is genuinely taker-only. A plain marketable limit order can partially
match and leave a remainder **resting** in the market — a passive order that would smuggle maker
execution into the taker-only Gates 2/3. So a ``taker-v1`` order is pinned:

* ``time_in_force = FILL_OR_KILL``
* ``min_fill_size`` = the **full** intended stake (no partial that could rest)
* ``persistence_type = LAPSE`` always
* a ``market_version`` on **every** order (the guard; if the version has incremented the order
  lapses rather than matching into a changed market — enforced at the broker, SPEC-072)
* back only (v1 hard prohibition on lay/hedge)

Passive posting is unreachable: there is no maker constructor, and every non-``LAPSE``
persistence, non-``FILL_OR_KILL`` time-in-force, or ``min_fill_size`` below the stake is refused.
Stakes are **integer minor units**, never float.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, model_validator

from l5_decision.ladder import is_valid_index


class Side(str, Enum):
    BACK = "BACK"
    LAY = "LAY"  # representable so it can be explicitly refused in v1, never constructed


class TimeInForce(str, Enum):
    FILL_OR_KILL = "FILL_OR_KILL"
    GOOD_TILL_CANCELLED = "GOOD_TILL_CANCELLED"  # a resting/passive TIF — refused in taker-v1


class PersistenceType(str, Enum):
    LAPSE = "LAPSE"
    PERSIST = "PERSIST"  # passive — refused
    MARKET_ON_CLOSE = "MARKET_ON_CLOSE"  # passive — refused


class TakerV1Order(BaseModel):
    """A fully-pinned taker-v1 order. Any field that would permit a resting remainder, passive
    posting, or a lay is rejected at construction (SPEC-052)."""

    model_config = ConfigDict(frozen=True, strict=True)

    market_id: str
    selection_id: int
    side: Side
    stake_minor: int
    min_fill_size_minor: int
    worst_acceptable_tick: int
    time_in_force: TimeInForce
    persistence_type: PersistenceType
    market_version: int

    @model_validator(mode="after")
    def _enforce_taker_v1(self) -> TakerV1Order:
        if self.side is not Side.BACK:
            raise ValueError("v1 is back-only; lay/hedge is refused (SPEC-052)")
        if self.stake_minor <= 0:
            raise ValueError(f"stake_minor must be positive, got {self.stake_minor}")
        if self.time_in_force is not TimeInForce.FILL_OR_KILL:
            raise ValueError("taker-v1 requires timeInForce=FILL_OR_KILL (SPEC-052)")
        if self.persistence_type is not PersistenceType.LAPSE:
            raise ValueError("taker-v1 requires persistenceType=LAPSE; passive posting is unreachable (SPEC-052)")
        if self.min_fill_size_minor != self.stake_minor:
            raise ValueError(
                "taker-v1 requires minFillSize == full stake so no remainder can rest "
                f"(stake={self.stake_minor}, minFill={self.min_fill_size_minor}) (SPEC-052)"
            )
        if not is_valid_index(self.worst_acceptable_tick):
            raise ValueError(f"worst_acceptable_tick {self.worst_acceptable_tick!r} is not a valid ladder index")
        return self


def taker_v1(
    *,
    market_id: str,
    selection_id: int,
    stake_minor: int,
    worst_acceptable_tick: int,
    market_version: int,
) -> TakerV1Order:
    """Build a taker-v1 order with the policy fields fixed, so a caller cannot misconfigure them.

    ``worst_acceptable_tick`` is the worst acceptable price bound (best-price execution may
    improve it); ``market_version`` is the guard carried on the order.
    """
    return TakerV1Order(
        market_id=market_id,
        selection_id=selection_id,
        side=Side.BACK,
        stake_minor=stake_minor,
        min_fill_size_minor=stake_minor,
        worst_acceptable_tick=worst_acceptable_tick,
        time_in_force=TimeInForce.FILL_OR_KILL,
        persistence_type=PersistenceType.LAPSE,
        market_version=market_version,
    )
