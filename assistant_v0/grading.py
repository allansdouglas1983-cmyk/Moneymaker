"""PERSONAL_TENNIS_ASSISTANT_V0 — governed outcome append + probability grading.

Joins a governed sporting outcome (which competitor won) to an existing IMMUTABLE pre-match
record and scores the probabilities that were recorded BEFORE the match: log loss and Brier
for the market probability (the final V0 probability) and, separately and never merged, for
the F2-v1 diagnostic. The pre-match record is never rewritten — the outcome is a separate
append.

There is NO stake, EV, ROI, P&L, CLV or hypothetical bet anywhere in this module. V0 grades
probability quality only. A missing probability is an explicit EXCLUSION with a reason; it is
never substituted from the other view and never imputed.
"""
from __future__ import annotations

from assistant_v0.shadow_ledger import (
    PreMatchRecord,
    SettlementAppend,
    ShadowLedger,
    brier,
    log_loss,
)

WINNER_A = "A"
WINNER_B = "B"
_ALLOWED_WINNERS = (WINNER_A, WINNER_B)

# explicit exclusion reasons (a missing number is never invented)
NO_MARKET_PROBABILITY = "NO_MARKET_PROBABILITY"


class GradingError(Exception):
    """The settlement request is malformed (e.g. an unknown winner token)."""


def _label_for_a(winner: str) -> int:
    """1 when competitor A won, 0 when B won. Exact tokens only."""
    if winner not in _ALLOWED_WINNERS:
        raise GradingError(f"winner must be one of {_ALLOWED_WINNERS}, got {winner!r}")
    return 1 if winner == WINNER_A else 0


def _score(p_a: float | None, label: int) -> tuple[float | None, float | None]:
    """Proper scores of competitor A's probability against A's 0/1 label."""
    if p_a is None:
        return None, None
    return log_loss(p_a, label), brier(p_a, label)


def grade_settlement(rec: PreMatchRecord, *, winner: str) -> SettlementAppend:
    """Score one immutable pre-match record against the governed outcome. Pure; the record
    is read-only and is returned untouched."""
    label = _label_for_a(winner)
    market_ll, market_br = _score(rec.market_probability_a, label)
    model_ll, model_br = _score(rec.f2_probability_a, label)
    scored = market_ll is not None
    return SettlementAppend(
        record_id=rec.record_id,
        winner=winner,
        scored=scored,
        market_log_loss=market_ll,
        market_brier=market_br,
        model_log_loss=model_ll,
        model_brier=model_br,
        exclusion_reason=None if scored else NO_MARKET_PROBABILITY,
    )


def settle_in_ledger(ledger: ShadowLedger, *, record_id: str, winner: str) -> SettlementAppend:
    """Append the governed outcome + proper scores for ``record_id``. Append-only: an unknown
    or already-settled record is refused by the ledger, and the pre-match record is never
    modified."""
    rec = ledger.pre_match_by_id(record_id)
    if rec is None:
        from assistant_v0.shadow_ledger import ShadowLedgerError
        raise ShadowLedgerError(f"no pre-match record {record_id!r} to settle")
    app = grade_settlement(rec, winner=winner)
    ledger.append_settlement(app)
    return app


def _mean(values: list[float]) -> float | None:
    """Mean of the scored values, or None when nothing was scored (never a fabricated 0.0)."""
    return sum(values) / len(values) if values else None


def summarise_ledger(ledger: ShadowLedger) -> dict[str, object]:
    """Deterministic probability-quality summary over the whole ledger.

    Counts every pre-match record in the denominator, reports exclusions explicitly, and
    keeps the market and F2-diagnostic scores separate. No ROI/P&L/stake is computed."""
    pre = ledger.all_pre_match()
    market_ll: list[float] = []
    market_br: list[float] = []
    model_ll: list[float] = []
    model_br: list[float] = []
    exclusions: dict[str, int] = {}
    settled = 0
    for rec in pre:
        app = ledger.settlement_by_id(rec.record_id)
        if app is None:
            continue
        settled += 1
        if app.market_log_loss is not None and app.market_brier is not None:
            market_ll.append(app.market_log_loss)
            market_br.append(app.market_brier)
        if app.exclusion_reason is not None:
            exclusions[app.exclusion_reason] = exclusions.get(app.exclusion_reason, 0) + 1
        if app.model_log_loss is not None and app.model_brier is not None:
            model_ll.append(app.model_log_loss)
            model_br.append(app.model_brier)
    return {
        "pre_match_records": len(pre),
        "settled": settled,
        "scored": len(market_ll),
        "excluded": sum(exclusions.values()),
        "exclusions": dict(sorted(exclusions.items())),
        "market_log_loss_mean": _mean(market_ll),
        "market_brier_mean": _mean(market_br),
        "model_scored": len(model_ll),
        "model_log_loss_mean": _mean(model_ll),
        "model_brier_mean": _mean(model_br),
        "note": "probability quality only — no monetary quantity is computed or stored",
    }
