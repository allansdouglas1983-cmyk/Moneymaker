"""Stage 2E §4 — the OUTCOME-BLIND June M1 transfer scoring harness (SPEC-092, SPEC-097).

The join that turns a burned outcome into an M1 score is the one place a silent bug would
corrupt a non-recoverable holdout. This module isolates that join so it can be proven with
SYNTHETIC data BEFORE the real burn:

  * a :class:`FrozenPrediction` freezes, per market, the frozen affine-calibrated F2 probability
    on a DESIGNATED competitor (the lower governed competitor id) and the Betfair selection ids
    of BOTH competitors — everything needed to score, with NO outcome field;
  * :func:`score_market` maps a burned ``ExtractedMatchOutcome.winner_selection_id`` to y in
    {0,1} for the designated competitor, by SELECTION ID — so runner order/layout is irrelevant
    and an unknown/mismatched selection REFUSES rather than guessing;
  * :func:`m1_scorecard` computes the SPEC-097 proper scores + calibration on the scored rows.

The harness reads NO winner during construction. It is deterministic: outputs depend only on
the frozen bundle and the (later) outcome map, sorted by market id, never on iteration order.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from l8_evidence.tennis_outcomes import ExtractedMatchOutcome

__all__ = [
    "FrozenPrediction",
    "ScoredRow",
    "HarnessJoinError",
    "score_market",
    "score_bundle",
    "m1_scorecard",
]


class HarnessJoinError(RuntimeError):
    """A burned outcome could not be joined to its frozen prediction without ambiguity:
    a market-id mismatch, or a winner selection id that is neither designated competitor.
    Refuses rather than guessing (SPEC-038/092)."""


@dataclass(frozen=True)
class FrozenPrediction:
    """One market's frozen, outcome-blind M1 prediction (designated = the lower competitor).

    ``selection_id_designated`` / ``selection_id_other`` are the Betfair selection ids of the
    designated (lower governed competitor) and the other runner. ``p_cal_designated`` is the
    frozen affine-calibrated F2 probability that the DESIGNATED competitor wins; ``p_raw`` is the
    uncalibrated companion (retained separately, never consumed by calibration)."""

    market_id: str
    tour: str                       # "ATP" | "WTA"
    cohort: str                     # "STRICT" | "PRIMARY_ONLY_TIER"
    prior_band: str
    cluster_day: str                # UTC calendar day (correlation-cluster key)
    competitor_designated: str      # governed CompetitorId value (the lower id)
    competitor_other: str
    selection_id_designated: int
    selection_id_other: int
    p_raw_designated: float
    p_cal_designated: float

    def __post_init__(self) -> None:
        if not self.market_id:
            raise ValueError("market_id must be non-empty")
        if self.tour not in ("ATP", "WTA"):
            raise ValueError(f"tour must be ATP or WTA, got {self.tour!r}")
        if self.selection_id_designated == self.selection_id_other:
            raise ValueError("the two selection ids must differ")
        if self.competitor_designated == self.competitor_other:
            raise ValueError("the two competitor ids must differ")
        for name, p in (("p_raw_designated", self.p_raw_designated),
                        ("p_cal_designated", self.p_cal_designated)):
            if not isinstance(p, float) or not 0.0 < p < 1.0:
                raise ValueError(f"{name} must be a float in (0, 1), got {p!r}")


@dataclass(frozen=True)
class ScoredRow:
    """A joined, scored market: the designated competitor's calibrated probability and whether
    it actually won (y). Outcome-derived — exists only after the burn."""

    market_id: str
    tour: str
    cohort: str
    prior_band: str
    cluster_day: str
    p_cal_designated: float
    y_designated: int               # 1 iff the designated competitor won


def score_market(prediction: FrozenPrediction, outcome: ExtractedMatchOutcome) -> ScoredRow:
    """Join ONE burned outcome to its frozen prediction by market id + selection id.

    The winner is mapped to y for the DESIGNATED competitor purely by selection id — so the
    order runners appear in the stream cannot flip the result. A market-id mismatch, or a winner
    selection id that is neither of the two designated selections, REFUSES."""
    if outcome.market_id != prediction.market_id:
        raise HarnessJoinError(
            f"outcome market {outcome.market_id!r} != prediction market {prediction.market_id!r}"
        )
    winner = outcome.winner_selection_id
    if winner == prediction.selection_id_designated:
        y = 1
    elif winner == prediction.selection_id_other:
        y = 0
    else:
        raise HarnessJoinError(
            f"market {prediction.market_id}: winner selection {winner} is neither the designated "
            f"{prediction.selection_id_designated} nor the other {prediction.selection_id_other}"
        )
    return ScoredRow(
        market_id=prediction.market_id,
        tour=prediction.tour,
        cohort=prediction.cohort,
        prior_band=prediction.prior_band,
        cluster_day=prediction.cluster_day,
        p_cal_designated=prediction.p_cal_designated,
        y_designated=y,
    )


def score_bundle(
    predictions: Sequence[FrozenPrediction],
    outcomes: Mapping[str, ExtractedMatchOutcome],
) -> tuple[tuple[ScoredRow, ...], tuple[tuple[str, str], ...]]:
    """Score every frozen prediction against the burned outcome map.

    Deterministic: predictions are processed sorted by market id. Returns (scored_rows,
    exclusions) where exclusions is ((market_id, reason), ...) for markets whose outcome is
    absent or unjoinable — every prediction is accounted for exactly once (SPEC-038)."""
    seen: set[str] = set()
    for p in predictions:
        if p.market_id in seen:
            raise HarnessJoinError(f"duplicate frozen prediction for market {p.market_id}")
        seen.add(p.market_id)
    scored: list[ScoredRow] = []
    exclusions: list[tuple[str, str]] = []
    for p in sorted(predictions, key=lambda pr: pr.market_id):
        outcome = outcomes.get(p.market_id)
        if outcome is None:
            exclusions.append((p.market_id, "NO_OUTCOME_IN_ARTIFACT"))
            continue
        try:
            scored.append(score_market(p, outcome))
        except HarnessJoinError as exc:
            exclusions.append((p.market_id, f"UNJOINABLE:{exc}"))
    return tuple(scored), tuple(exclusions)


def _clamp(p: float) -> float:
    return min(max(p, 1e-12), 1 - 1e-12)


def _logit(p: float) -> float:
    p = _clamp(p)
    return math.log(p / (1 - p))


def _metrics(pairs: Sequence[tuple[float, int]]) -> dict[str, float]:
    """SPEC-097 proper scores + calibration-in-the-large + slope for (p, y) pairs."""
    n = len(pairs)
    if n == 0:
        return {"n": 0}
    ll = sum(-math.log(_clamp(p if y == 1 else 1 - p)) for p, y in pairs) / n
    brier = sum((p - y) ** 2 for p, y in pairs) / n
    mp = sum(p for p, _ in pairs) / n
    my = sum(y for _, y in pairs) / n
    cil = _logit(my) - _logit(mp)
    a, b = 0.0, 1.0
    xs = [_logit(p) for p, _ in pairs]
    ys = [y for _, y in pairs]
    for _ in range(60):
        ga = gb = haa = hab = hbb = 0.0
        for x, y in zip(xs, ys):
            m = 1 / (1 + math.exp(-(a + b * x)))
            ga += y - m
            gb += (y - m) * x
            w = m * (1 - m)
            haa += w
            hab += w * x
            hbb += w * x * x
        det = haa * hbb - hab * hab
        if det <= 1e-12:
            break
        da = (hbb * ga - hab * gb) / det
        db = (haa * gb - hab * ga) / det
        a += da
        b += db
        if abs(da) + abs(db) < 1e-11:
            break
    return {"n": n, "log_loss": round(ll, 6), "brier": round(brier, 6),
            "cal_in_large": round(cil, 6), "cal_slope": round(b, 6)}


def m1_scorecard(scored: Sequence[ScoredRow], *, min_support: int = 500) -> dict[str, object]:
    """The frozen M1 scorecard over scored rows (SPEC-097; deterministic).

    Overall + per-tour + prior-history cohorts; each carries a `supported` flag against
    `min_support` (the remediation_amendment_v1 rule — an unsupported subgroup is CONTINUE, never
    fabricated). No verdict is decided here; the SPEC-093 evaluator maps this to PASS/CONTINUE/
    FAIL against probability-m1.yaml. No LLM decides the gate."""
    def block(rows: Sequence[ScoredRow]) -> dict[str, object]:
        m = _metrics([(r.p_cal_designated, r.y_designated) for r in rows])
        return {**m, "supported": len(rows) >= min_support}

    rows = sorted(scored, key=lambda r: r.market_id)
    out: dict[str, object] = {
        "n_scored": len(rows),
        "min_support": min_support,
        "overall": block(rows),
        "per_tour": {t: block([r for r in rows if r.tour == t]) for t in ("ATP", "WTA")},
        "prior_history_cohorts": {
            b: block([r for r in rows if r.prior_band == b])
            for b in sorted({r.prior_band for r in rows})
        },
        "n_utc_day_clusters": len({r.cluster_day for r in rows}),
    }
    return out
