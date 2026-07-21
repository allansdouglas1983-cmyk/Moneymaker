"""Cross-market feasibility audit — orchestrator + audit-only data contract (STAGE3-0002
§9-§16; audit code version xmarket-audit-v1).

Ties the catalogue + the frozen F0 anchor + as-of reconstruction into a per-MO-market
:class:`MarketAuditRecord` that carries NO outcome / winner / settlement / P&L / BSP /
close / ROI / CLV / EV field (§16 — structurally impossible below), and aggregates the
feasibility observables the founder directive asks for. Every number here is outcome-blind
and pre-off: reconstruction reads only stream state at/before the F0 decision timestamp.

Audit-only. Import-quarantined from l5_decision / l5b_risk / l6_broker. No latent model.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

from research.xmarket import reconstruct as recon
from research.xmarket.linkage import LinkResult, MarketRef, link_mo
from research.xmarket.parsers import (
    MarketParseError,
    PRIMARY_IDENTIFYING_GAME_HANDICAP,
    PRIMARY_IDENTIFYING_TOTAL_GAMES,
)

AUDIT_CODE_VERSION = "xmarket-audit-v1"

TOUR_UNRESOLVED = "TOUR_UNRESOLVED"
# extra funnel reasons for a linked-but-absent identifying sibling
TOTAL_GAMES_ABSENT = "TOTAL_GAMES_ABSENT"
GAME_HANDICAP_ABSENT = "GAME_HANDICAP_ABSENT"
MALFORMED_SELECTION_STRUCTURE = "MALFORMED_SELECTION_STRUCTURE"

MessageProvider = Callable[[str], Iterable[Mapping[str, Any]]]


# ------------------------------------------------------------------ data contract (§16)
@dataclass(frozen=True)
class DerivativeAudit:
    """Outcome-blind audit of one identifying derivative at the F0 timestamp."""

    role: str
    linked_market_id: str
    exclusion_reason: str | None            # None => usable at F0
    quote_age_seconds: float | None
    two_sided_line_count: int
    lines_offered: int                      # §10 line richness
    min_spread_ticks: int | None
    min_spread_bps: float | None
    best_back_size_max: float | None
    best_lay_size_max: float | None
    traded_volume_total: float
    pre_cutoff_update_count: int            # §12 independent-update observable


@dataclass(frozen=True)
class MarketAuditRecord:
    """Per-MO-market audit record. NO outcome/winner/settlement/P&L/BSP/close/ROI/CLV/EV
    field is representable — this is the §16 audit-only data contract."""

    mo_market_id: str
    event_id: str | None
    tour: str
    calendar_day: str | None
    cohort: str
    commit_pt_ms: int
    total_games: DerivativeAudit | None
    game_handicap: DerivativeAudit | None
    auxiliary_market_ids: tuple[str, ...]
    linkage_anomalies: tuple[str, ...]


# ------------------------------------------------------------------------- one market
def _count_pre_cutoff_updates(messages: Iterable[Mapping[str, Any]], market_id: str,
                              cutoff_ms: int) -> int:
    n = 0
    for msg in messages:
        pt = msg.get("pt")
        if not isinstance(pt, int) or pt > cutoff_ms:
            continue
        for mc in msg.get("mc") or []:
            if mc.get("id") == market_id and mc.get("rc"):
                n += 1
                break
    return n


def _lines_offered(snap: recon.AsOfSnapshot) -> int:
    """Count distinct priced lines in the reconstructed selections (§10 line richness).
    The snapshot carries (id, hc) selections but not Over/Under names, so line richness is
    the count of distinct hc lines present. Refuses if no line is priced."""
    distinct_lines = {q.line for q in snap.quotes if q.line is not None}
    if not distinct_lines:
        raise MarketParseError("no priced line in reconstructed snapshot")
    return len(distinct_lines)


def _audit_derivative(role: str, market_id: str, commit_pt_ms: int,
                      messages: list[Mapping[str, Any]]) -> DerivativeAudit:
    try:
        snap = recon.reconstruct_as_of(messages, market_id, commit_pt_ms)
    except recon.ReconstructionRefusal as r:
        return DerivativeAudit(role, market_id, r.reason, None, 0, 0, None, None,
                               None, None, 0.0, 0)
    reason = recon.book_exclusion_reason(snap)
    bq = recon.book_quality(snap)
    updates = _count_pre_cutoff_updates(messages, market_id, commit_pt_ms)
    try:
        lines = _lines_offered(snap)
    except MarketParseError:
        reason = reason or MALFORMED_SELECTION_STRUCTURE
        lines = 0
    return DerivativeAudit(
        role=role, linked_market_id=market_id, exclusion_reason=reason,
        quote_age_seconds=recon.quote_age_seconds(snap),
        two_sided_line_count=bq.two_sided_line_count, lines_offered=lines,
        min_spread_ticks=bq.min_spread_ticks, min_spread_bps=bq.min_spread_bps,
        best_back_size_max=bq.best_back_size_max, best_lay_size_max=bq.best_lay_size_max,
        traded_volume_total=bq.traded_volume_total, pre_cutoff_update_count=updates,
    )


def audit_one_market(mo_market_id: str, commit_pt_ms: int, cohort: str, tour: str,
                     calendar_day: str | None, catalogue: dict[str, MarketRef],
                     mo_index: dict[str, list[str]],
                     message_provider: MessageProvider) -> MarketAuditRecord:
    """Produce the audit record for one committed MO market: link siblings, reconstruct the
    identifying derivatives as-of F0, and summarise them outcome-blind."""
    link: LinkResult = link_mo(mo_market_id, catalogue, mo_index)
    mo = catalogue[mo_market_id]

    def _for(role: str, mid: str | None) -> DerivativeAudit | None:
        if mid is None:
            return None
        return _audit_derivative(role, mid, commit_pt_ms, list(message_provider(mid)))

    return MarketAuditRecord(
        mo_market_id=mo_market_id, event_id=mo.event_id,
        tour=tour or TOUR_UNRESOLVED, calendar_day=calendar_day, cohort=cohort,
        commit_pt_ms=commit_pt_ms,
        total_games=_for(PRIMARY_IDENTIFYING_TOTAL_GAMES, link.total_games_market_id),
        game_handicap=_for(PRIMARY_IDENTIFYING_GAME_HANDICAP, link.game_handicap_market_id),
        auxiliary_market_ids=link.auxiliary_market_ids,
        linkage_anomalies=link.anomalies,
    )


# --------------------------------------------------------------------- usability helpers
def derivative_usable(d: DerivativeAudit | None, cutoff_s: float) -> bool:
    return (d is not None and d.exclusion_reason is None
            and d.quote_age_seconds is not None and d.quote_age_seconds <= cutoff_s)


def record_has_identifying(rec: MarketAuditRecord, cutoff_s: float) -> bool:
    return derivative_usable(rec.total_games, cutoff_s) or derivative_usable(rec.game_handicap, cutoff_s)


# ---------------------------------------------------------------- aggregation (§9-§15)
def n_primary_identifying(records: list[MarketAuditRecord],
                          cutoffs_s: list[float]) -> dict[float, dict[str, int]]:
    """N_PRIMARY_IDENTIFYING per quote-age cutoff, broken down by TOTAL, cohort, tour."""
    out: dict[float, dict[str, int]] = {}
    for cut in cutoffs_s:
        c: Counter[str] = Counter()
        for rec in records:
            if record_has_identifying(rec, cut):
                c["TOTAL"] += 1
                c[rec.cohort] += 1
                c[rec.tour] += 1
        out[cut] = dict(c)
    return out


def refusal_funnel(records: list[MarketAuditRecord]) -> dict[str, int]:
    """Every counted refusal across linkage anomalies, absent siblings, and derivative
    book exclusions."""
    c: Counter[str] = Counter()
    for rec in records:
        for a in rec.linkage_anomalies:
            c[a] += 1
        if rec.total_games is None:
            c[TOTAL_GAMES_ABSENT] += 1
        elif rec.total_games.exclusion_reason is not None:
            c[rec.total_games.exclusion_reason] += 1
        if rec.game_handicap is None:
            c[GAME_HANDICAP_ABSENT] += 1
        elif rec.game_handicap.exclusion_reason is not None:
            c[rec.game_handicap.exclusion_reason] += 1
    return dict(c)


@dataclass(frozen=True)
class IndependentUpdateStatus:
    usable_derivatives: int
    usable_with_independent_volume: int
    usable_with_multiple_updates: int
    verdict: str


def independent_update_status(records: list[MarketAuditRecord],
                              cutoff_s: float) -> IndependentUpdateStatus:
    """§12 secondary observable: do usable identifying derivatives carry their OWN updates
    and traded volume? This is NOT the redundancy verdict (that requires the MO co-timing
    join in research.xmarket.redundancy) — it is only a coarse self-quote observable."""
    usable = 0
    with_vol = 0
    with_updates = 0
    for rec in records:
        for d in (rec.total_games, rec.game_handicap):
            if derivative_usable(d, cutoff_s):
                assert d is not None
                usable += 1
                if d.traded_volume_total > 0:
                    with_vol += 1
                if d.pre_cutoff_update_count > 1:
                    with_updates += 1
    verdict = "SELF_QUOTES_PRESENT"
    if usable == 0 or with_vol * 2 < usable:
        verdict = "LIMITED_SELF_QUOTES"
    return IndependentUpdateStatus(usable, with_vol, with_updates, verdict)


def spread_tick_sensitivity(records: list[MarketAuditRecord], cutoff_s: float,
                            max_ticks_grid: list[int]) -> dict[int, int]:
    """§13 one-tick / book-interval sensitivity: how N_PRIMARY_IDENTIFYING shrinks as we
    require the identifying book's min spread to be within k ticks. Monotone in k."""
    out: dict[int, int] = {}
    for k in max_ticks_grid:
        n = 0
        for rec in records:
            ok = False
            for d in (rec.total_games, rec.game_handicap):
                if derivative_usable(d, cutoff_s) and d is not None \
                        and d.min_spread_ticks is not None and d.min_spread_ticks <= k:
                    ok = True
            n += 1 if ok else 0
        out[k] = n
    return out


def coverage_comparison(records: list[MarketAuditRecord], cutoff_s: float) -> dict[str, Any]:
    """§15 selection-bias: covered vs uncovered MO markets by outcome-blind cohort/tour."""
    by_cohort: dict[str, dict[str, int]] = {}
    by_tour: dict[str, dict[str, int]] = {}
    covered_total = 0
    for rec in records:
        covered = record_has_identifying(rec, cutoff_s)
        covered_total += 1 if covered else 0
        for table, key in ((by_cohort, rec.cohort), (by_tour, rec.tour)):
            slot = table.setdefault(key, {"covered": 0, "denominator": 0})
            slot["denominator"] += 1
            if covered:
                slot["covered"] += 1
    return {
        "by_cohort": by_cohort, "by_tour": by_tour,
        "overall": {"covered": covered_total, "denominator": len(records)},
    }
