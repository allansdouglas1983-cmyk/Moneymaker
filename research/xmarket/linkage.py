"""Cross-market feasibility audit — event linkage of derivative markets to Match-Odds
(STAGE3-0002 §5; audit code version xmarket-audit-v1).

Derivatives (COMBINED_TOTAL / HANDICAP) are linked to their Match-Odds sibling by
**eventId only**, never by display name. Linkage anomalies are made VISIBLE and counted,
never silently resolved: an event with more than one committed MO market, a derivative
whose event has no committed MO market, more than one derivative of the same role per
event (relisted / cancelled instances stay distinct), and a marketTime mismatch.

Audit-only: reads market DEFINITION identity fields (market_id, eventId, marketType,
marketTime). No price, no outcome. Import-quarantined from l5_decision / l5b_risk /
l6_broker. No latent-model equation.
"""
from __future__ import annotations

from dataclasses import dataclass

from research.xmarket.parsers import (
    PRIMARY_IDENTIFYING_GAME_HANDICAP,
    PRIMARY_IDENTIFYING_TOTAL_GAMES,
    PRIMARY_MATCH_ODDS,
    market_role,
)

# Linkage-level exclusion reasons — must match specs/programme/cross-market-audit-v1.yaml
NOT_LINKED_TO_MATCH_ODDS_EVENT = "NOT_LINKED_TO_MATCH_ODDS_EVENT"
AMBIGUOUS_EVENT_LINKAGE = "AMBIGUOUS_EVENT_LINKAGE"
MULTIPLE_MATCH_ODDS_FOR_EVENT_UNRESOLVED = "MULTIPLE_MATCH_ODDS_FOR_EVENT_UNRESOLVED"


class LinkageError(Exception):
    """A catalogue cannot be built deterministically (e.g. one market_id, two definitions)."""


@dataclass(frozen=True)
class MarketRef:
    """First-definition identity of one Betfair market. Outcome-free."""

    market_id: str
    event_id: str | None
    market_type: str | None
    market_time_ms: int | None
    event_name: str | None = None


@dataclass(frozen=True)
class LinkResult:
    """The identifying and auxiliary siblings linked to one committed MO market, plus any
    linkage anomalies (visible, never silently resolved)."""

    mo_market_id: str
    total_games_market_id: str | None
    game_handicap_market_id: str | None
    auxiliary_market_ids: tuple[str, ...]
    anomalies: tuple[str, ...]
    market_time_mismatch: bool


def build_catalogue(refs: list[MarketRef]) -> dict[str, MarketRef]:
    """Index refs by market_id. Duplicate packaging (the identical ref repeated) collapses
    to one entry; two DIFFERENT definitions for one market_id is a hard refusal. Distinct
    market_ids for the same event (relisted instances) stay distinct."""
    cat: dict[str, MarketRef] = {}
    for r in refs:
        prev = cat.get(r.market_id)
        if prev is None:
            cat[r.market_id] = r
        elif prev != r:
            raise LinkageError(
                f"market_id {r.market_id} has conflicting definitions: {prev} != {r}"
            )
    return cat


def mo_event_index(catalogue: dict[str, MarketRef],
                   committed_mo_ids: set[str]) -> dict[str, list[str]]:
    """Map eventId -> [committed MO market_ids], from the catalogue restricted to the
    committed MO universe (the F0 denominator B)."""
    idx: dict[str, list[str]] = {}
    for mid in committed_mo_ids:
        ref = catalogue.get(mid)
        if ref is None or ref.event_id is None:
            continue
        idx.setdefault(ref.event_id, []).append(mid)
    for ev in idx:
        idx[ev].sort()
    return idx


def link_mo(mo_market_id: str, catalogue: dict[str, MarketRef],
            mo_event_index: dict[str, list[str]]) -> LinkResult:
    """Link one committed MO market to its identifying and auxiliary siblings by eventId."""
    mo = catalogue.get(mo_market_id)
    if mo is None:
        raise LinkageError(f"MO market_id {mo_market_id} not in catalogue")
    anomalies: list[str] = []
    event_id = mo.event_id

    if event_id is not None and len(mo_event_index.get(event_id, [])) > 1:
        anomalies.append(MULTIPLE_MATCH_ODDS_FOR_EVENT_UNRESOLVED)

    # every OTHER market sharing this eventId is a sibling candidate
    siblings = [r for r in catalogue.values()
                if r.event_id is not None and r.event_id == event_id
                and r.market_id != mo_market_id]

    by_role: dict[str, list[MarketRef]] = {}
    for r in siblings:
        role = market_role(r.market_type) if isinstance(r.market_type, str) else "UNKNOWN_REQUIRES_REVIEW"
        by_role.setdefault(role, []).append(r)

    def _sole(role: str) -> str | None:
        cands = by_role.get(role, [])
        if len(cands) == 1:
            return cands[0].market_id
        if len(cands) > 1:
            anomalies.append(AMBIGUOUS_EVENT_LINKAGE)
        return None

    tg = _sole(PRIMARY_IDENTIFYING_TOTAL_GAMES)
    gh = _sole(PRIMARY_IDENTIFYING_GAME_HANDICAP)

    _identifying_or_mo = (PRIMARY_IDENTIFYING_TOTAL_GAMES, PRIMARY_IDENTIFYING_GAME_HANDICAP,
                          PRIMARY_MATCH_ODDS)
    auxiliary = tuple(sorted(
        r.market_id for r in siblings
        if isinstance(r.market_type, str)
        and market_role(r.market_type) not in _identifying_or_mo
    ))

    mismatch = False
    for linked in (tg, gh):
        if linked is not None:
            ref = catalogue[linked]
            if ref.market_time_ms != mo.market_time_ms:
                mismatch = True

    return LinkResult(
        mo_market_id=mo_market_id,
        total_games_market_id=tg,
        game_handicap_market_id=gh,
        auxiliary_market_ids=auxiliary,
        anomalies=tuple(dict.fromkeys(anomalies)),  # dedupe, preserve order
        market_time_mismatch=mismatch,
    )


def unlinked_derivatives(catalogue: dict[str, MarketRef],
                         mo_event_index: dict[str, list[str]]) -> list[tuple[str, str]]:
    """Every identifying derivative whose event has no committed MO market, tagged
    NOT_LINKED_TO_MATCH_ODDS_EVENT. Sorted for determinism."""
    out: list[tuple[str, str]] = []
    identifying = {PRIMARY_IDENTIFYING_TOTAL_GAMES, PRIMARY_IDENTIFYING_GAME_HANDICAP}
    for mid, ref in catalogue.items():
        if not isinstance(ref.market_type, str):
            continue
        if market_role(ref.market_type) not in identifying:
            continue
        if ref.event_id is None or ref.event_id not in mo_event_index:
            out.append((mid, NOT_LINKED_TO_MATCH_ODDS_EVENT))
    out.sort()
    return out
