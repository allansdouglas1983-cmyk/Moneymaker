"""One runner per market (SPEC-054).

v1 refuses a second position in a market: commission is charged on the **net market result**,
so multi-position attribution is path-dependent. Two mechanisms:

* :func:`select_market_position` — given the candidates in one market that cleared the decision
  threshold, choose exactly one by **highest conservative net EV**, breaking ties by lowest
  ``selection_id`` (an explicit, deterministic tie-break that never inspects the outcome or a
  future market move), and record every rejected candidate.
* :class:`MarketPositionLedger` — a hard guard that refuses committing a second position to a
  market that already holds one, regardless of the second candidate's fields.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class SecondPositionError(RuntimeError):
    """Raised when a second position is attempted in a market that already holds one (SPEC-054)."""


class Candidate(BaseModel):
    """A runner that cleared the decision threshold, with its conservative net EV."""

    model_config = ConfigDict(frozen=True, strict=True)

    market_id: str
    selection_id: int
    conservative_ev: Decimal


@dataclass(frozen=True)
class MarketSelection:
    """The single chosen position and every candidate rejected in its favour."""

    chosen: Candidate
    rejected: list[Candidate] = field(default_factory=list)


def select_market_position(candidates: list[Candidate]) -> MarketSelection:
    """Choose exactly one position for a single market (SPEC-054).

    Deterministic: maximise ``conservative_ev``, then minimise ``selection_id``. Never looks at
    anything but the candidates' declared EVs and ids. Raises ``ValueError`` for an empty set,
    candidates spanning multiple markets, or duplicate selection ids.
    """
    if not candidates:
        raise ValueError("no candidates to select from")
    markets = {c.market_id for c in candidates}
    if len(markets) != 1:
        raise ValueError(f"candidates span multiple markets: {sorted(markets)}")
    ids = [c.selection_id for c in candidates]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate selection_id among candidates")

    # Highest EV, then lowest selection_id. Sorting key is total and outcome-independent.
    chosen = min(candidates, key=lambda c: (-c.conservative_ev, c.selection_id))
    rejected = [c for c in candidates if c.selection_id != chosen.selection_id]
    return MarketSelection(chosen=chosen, rejected=rejected)


class MarketPositionLedger:
    """Tracks the at-most-one committed position per market and refuses a second (SPEC-054)."""

    def __init__(self) -> None:
        self._positions: dict[str, int] = {}

    def has_position(self, market_id: str) -> bool:
        return market_id in self._positions

    def committed_selection(self, market_id: str) -> int | None:
        return self._positions.get(market_id)

    def commit(self, market_id: str, selection_id: int) -> None:
        """Record a position. Raises :class:`SecondPositionError` if the market already has one —
        including a repeat of the identical selection (still a second placement attempt)."""
        if market_id in self._positions:
            raise SecondPositionError(
                f"market {market_id} already holds a position on selection "
                f"{self._positions[market_id]}; v1 refuses a second position (SPEC-054)"
            )
        self._positions[market_id] = selection_id
