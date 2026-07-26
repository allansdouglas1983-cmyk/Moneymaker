"""One command, end to end: fixtures in, a ranked view of today's matches out.

This is the product. Everything else in the package is a component of it, and until now
there was no single thing that ran the whole chain — fixtures, state, model, policy, ledger —
so what existed was a collection of parts that each worked.

    fixtures -> live state -> residual model -> frozen policy -> ledger -> this view

**What the status means, and why it is not a tip.** The v2 policy produces a status per
fixture. `BET_CANDIDATE` is structurally unreachable: SPEC-109 keeps it behind a
module-private activation token that gates P1, P2 and T1 must pass before the founder can
turn on. Until then a candidate-shaped opportunity surfaces as
``BET_CANDIDATE_DISABLED`` — the numbers are shown, the recommendation is withheld, and the
withholding is a property of the code rather than a promise in a document.

That is not decoration. TE-0007 measured the model's exchange performance as undecided at the
available power, and the exchange is the only venue that cannot limit an account. A system
that printed "BET" off an undecided measurement would be converting a statistical non-result
into a financial instruction.

**Every run appends to the prospective ledger.** A prediction that is not recorded before the
result is not evidence, and a ledger written after the fact is worth nothing. Rows carry the
model digest, the policy digest and the state date, so months later any line can be traced to
the exact rule and rating state that produced it.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

from tennis_edge.fixtures import FixtureSource
from tennis_edge.live_state import StateSnapshot, live_features
from tennis_edge.policy_v2 import COMMISSION, MIN_EDGE, WATCH_EDGE
from tennis_edge.residual_model import ResidualModel
from tennis_edge.upcoming import Fixture, UpcomingPrediction, price_fixture

__all__ = [
    "TipStatus",
    "TodayRow",
    "assess",
    "render",
]


#: The governed status vocabulary, SPEC-109. ``BET_CANDIDATE`` is deliberately absent from
#: this module: it cannot be produced here at all, which is what "structurally unreachable"
#: means. Adding it would be a governance change, not a code change.
class TipStatus:
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    MARKET_UNAVAILABLE = "MARKET_UNAVAILABLE"
    MODEL_VIEW_ONLY = "MODEL_VIEW_ONLY"
    LEAN = "LEAN"
    NO_BET = "NO_BET"
    BET_CANDIDATE_DISABLED = "BET_CANDIDATE_DISABLED"


@dataclass(frozen=True)
class TodayRow:
    """One fixture assessed, with everything a ledger row or a screen needs."""

    fixture: Fixture
    source: FixtureSource
    prediction: UpcomingPrediction
    status: str
    best_side: str
    best_edge: float
    reasons: tuple[str, ...]

    @property
    def sort_key(self) -> tuple[int, float]:
        """Most interesting first: candidates above leans above everything else."""
        rank = {TipStatus.BET_CANDIDATE_DISABLED: 0, TipStatus.LEAN: 1}.get(self.status, 2)
        return (rank, -self.best_edge)


def _reasons(row_features: Mapping[str, float], prediction: UpcomingPrediction,
             stale_days: int) -> tuple[str, ...]:
    """Deterministic reason codes from the numeric core. No causal language, no invention.

    Every code is a sign or threshold statement about a number already computed. Nothing
    here explains *why* a player is better; it says only which input pushed the price.
    """
    found: list[str] = []
    if not row_features:
        found.append("INSUFFICIENT_DATA")
    if stale_days > 14:
        found.append("STALE_STATE")
    pyramid = row_features.get("pyramid_elo_gap")
    if pyramid is not None and abs(pyramid) > 0.25:
        found.append("RATING_ADVANTAGE" if pyramid > 0 else "RATING_DISADVANTAGE")
    point = row_features.get("point_model_residual")
    if point is not None and abs(point) > 0.35:
        found.append("SERVE_MODEL_DISAGREES")
    if row_features.get("pyramid_workload_gap", 0.0) >= 2.0:
        found.append("HEAVY_RECENT_WORKLOAD")
    gap = prediction.probability_a - prediction.market_probability_a
    found.append("MARKET_DISAGREEMENT" if abs(gap) > 0.03 else "MARKET_AGREEMENT")
    if max(prediction.edge_a, prediction.edge_b) >= MIN_EDGE:
        found.append("PRICE_ABOVE_CONSERVATIVE_FAIR")
    found.append("TIPPING_GATE_DISABLED")
    return tuple(found)


def assess(
    fixtures: Sequence[tuple[Fixture, FixtureSource, Mapping[str, Any]]],
    *,
    snapshot: StateSnapshot | None,
    model: ResidualModel,
    today: dt.date | None = None,
    commission: Decimal = Decimal(str(COMMISSION)),
) -> list[TodayRow]:
    """Run every fixture through the chain and rank what comes out.

    A fixture the state cannot support becomes ``INSUFFICIENT_DATA`` rather than being priced
    at the market and presented as though the model had an opinion. That distinction is the
    whole reason the feature map is allowed to come back empty.
    """
    when = today or dt.date.today()
    stale = 0 if snapshot is None else snapshot.days_old(when)
    rows: list[TodayRow] = []

    for fixture, source, entry in fixtures:
        features: dict[str, float] = {
            k: float(v) for k, v in (entry.get("features") or {}).items()
        }
        if not features and snapshot is not None:
            implied_a = 1.0 / float(fixture.odds_a)
            implied_b = 1.0 / float(fixture.odds_b)
            features = live_features(
                snapshot, fixture.tour, fixture.player_a, fixture.player_b,
                surface=fixture.surface, best_of=fixture.best_of,
                market_probability=implied_a / (implied_a + implied_b),
                match_date=fixture.date,
                rank_a=entry.get("rank_a"), rank_b=entry.get("rank_b"),
            )
        prediction = price_fixture(fixture, features, model, commission=commission)

        best_edge = max(prediction.edge_a, prediction.edge_b)
        best_side = "A" if prediction.edge_a >= prediction.edge_b else "B"
        if not features:
            status = TipStatus.INSUFFICIENT_DATA
        elif best_edge >= MIN_EDGE:
            # The only place a candidate can appear, and it appears disabled. There is no
            # branch in this module that produces BET_CANDIDATE.
            status = TipStatus.BET_CANDIDATE_DISABLED
        elif best_edge >= WATCH_EDGE:
            status = TipStatus.LEAN
        else:
            status = TipStatus.NO_BET
        rows.append(TodayRow(
            fixture=fixture, source=source, prediction=prediction, status=status,
            best_side=best_side, best_edge=best_edge,
            reasons=_reasons(features, prediction, stale),
        ))

    return sorted(rows, key=lambda r: r.sort_key)


def render(rows: Sequence[TodayRow], *, model: ResidualModel,
           snapshot: StateSnapshot | None, today: dt.date) -> str:
    """The screen. Ordered most interesting first, with the banner impossible to miss."""
    lines = [
        "=" * 78,
        f"  TENNIS EDGE — {today}    RESEARCH / SHADOW ONLY, NO STAKE AUTHORISED",
        "=" * 78,
        f"  model  {model.digest[:27]}...  trained through {model.trained_through}",
    ]
    if snapshot is None:
        lines.append("  state  MISSING — fixtures priced at the market only")
    else:
        age = snapshot.days_old(today)
        flag = "  STALE, rebuild with `state`" if age > 14 else ""
        lines.append(f"  state  {snapshot.as_of} ({age}d old){flag}")
    lines.append("")

    if not rows:
        lines.append("  no fixtures")
        return "\n".join(lines)

    for row in rows:
        fixture, prediction = row.fixture, row.prediction
        side = fixture.player_a if row.best_side == "A" else fixture.player_b
        odds = fixture.odds_a if row.best_side == "A" else fixture.odds_b
        lines += [
            f"  [{row.status}]  {fixture.date} {fixture.tour}  "
            f"{fixture.player_a} v {fixture.player_b}",
            f"      market {prediction.market_probability_a:.3f} / "
            f"{prediction.market_probability_b:.3f}"
            f"     model {prediction.probability_a:.3f} / "
            f"{prediction.probability_b:.3f}",
            f"      fair   {prediction.fair_odds_a} / {prediction.fair_odds_b}"
            f"        quoted {fixture.odds_a} / {fixture.odds_b}",
            f"      best   {side} at {odds}, edge {row.best_edge:+.4f} "
            f"over the commission-aware break-even",
            f"      why    {', '.join(row.reasons)}",
            "",
        ]

    counts: dict[str, int] = {}
    for row in rows:
        counts[row.status] = counts.get(row.status, 0) + 1
    lines += [
        "-" * 78,
        "  " + "   ".join(f"{k}={v}" for k, v in sorted(counts.items())),
        "",
        "  BET_CANDIDATE is structurally unreachable until gates P1, P2 and T1 pass and",
        "  the founder activates T2 (SPEC-109). Nothing above authorises a stake, and the",
        "  model's exchange performance is undecided at the available power (TE-0007).",
    ]
    return "\n".join(lines)
