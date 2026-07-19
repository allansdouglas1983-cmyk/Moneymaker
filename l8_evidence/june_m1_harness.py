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
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol


class _WinnerOutcome(Protocol):
    """Anything carrying a market id and a winning Betfair selection id — both a governed
    :class:`~l8_evidence.tennis_outcomes.ExtractedMatchOutcome` and the immutable artifact's
    ``MinimalOutcome`` satisfy this, so the same join scores either."""

    @property
    def market_id(self) -> str: ...
    @property
    def winner_selection_id(self) -> int: ...


__all__ = [
    "FrozenPrediction",
    "ScoredRow",
    "HarnessJoinError",
    "score_market",
    "score_bundle",
    "m1_scorecard",
    "evaluate_m1_verdict",
]

_LN2 = math.log(2.0)
#: Frozen M1 bands (probability-m1.yaml numeric_bands_v1 + remediation_amendment_v1).
_CIL_PASS = 0.02          # |calibration-in-the-large| adequacy band
_CIL_HARM = 0.05          # catastrophic-transfer / harm boundary (NOT a widened PASS band)
_SLOPE_LO, _SLOPE_HI = 0.90, 1.10
_BRIER_LT = 0.25
#: M1 verdict severity, strictly increasing. The evaluator emits only PASS/CONTINUE/FAIL_HARM;
#: precedence is by POSITION in this tuple, never by a mutable integer code (a relabelled integer
#: lattice is mutation-equivalent — the ordering is pinned structurally instead, see
#: TestVerdictSeverityTruthTable). FAIL_FUTILITY is unreachable in M1 and is deliberately absent.
_M1_SEVERITY: tuple[str, ...] = ("PASS", "CONTINUE", "FAIL_HARM")


def evaluate_m1_verdict(scorecard: Mapping[str, object], *, min_support: int = 500) -> dict[str, object]:
    """Deterministic M1 verdict from a scorecard against the FROZEN probability-m1 bands +
    remediation_amendment_v1. No LLM decides this; it is a mechanical mapping (SPEC-093 spirit).

    PASS requires (overall + both supported tours): log loss < ln2, Brier < 0.25, slope in
    [0.90,1.10], and |cal-in-large| <= 0.02. CONTINUE if any adequacy item is merely in the
    (0.02, 0.05] cal band, or a required tour is unsupported (< min_support), or overall support
    is short. FAIL_HARM if |cal-in-large| > 0.05 anywhere supported, or a supported log loss >=
    ln2. Returns the verdict + the reasons (auditable)."""
    def _num(v: object) -> float:
        assert isinstance(v, (int, float))
        return float(v)

    overall = scorecard["overall"]
    assert isinstance(overall, Mapping)
    reasons: list[str] = []
    verdict = "PASS"

    def worse(v: str) -> None:
        # Escalate only: adopt v iff it is strictly more severe than the current verdict. Precedence
        # is by position in _M1_SEVERITY (no mutable integer codes). The equality case (v == verdict)
        # is a no-op: `>` holds only for a strictly-later position, and re-adopting the same verdict
        # would be an idempotent self-assignment anyway.
        nonlocal verdict
        if _M1_SEVERITY.index(v) > _M1_SEVERITY.index(verdict):
            verdict = v

    n_overall = int(_num(overall.get("n", 0)))
    if n_overall < min_support:
        worse("CONTINUE")
        reasons.append(f"overall support {n_overall} < {min_support}")

    def check(block: Mapping[str, object], label: str, required: bool) -> None:
        nonlocal verdict
        supported = bool(block.get("supported", False))
        if not supported:
            if required:
                worse("CONTINUE")
                reasons.append(f"{label} unsupported (< {min_support}) -> CONTINUE")
            return
        ll = _num(block["log_loss"])
        brier = _num(block["brier"])
        cil = abs(_num(block["cal_in_large"]))
        slope = _num(block["cal_slope"])
        if ll >= _LN2:
            worse("FAIL_HARM")
            reasons.append(f"{label} log_loss {ll} >= ln2")
        if brier >= _BRIER_LT:
            worse("FAIL_HARM")
            reasons.append(f"{label} brier {brier} >= {_BRIER_LT}")
        if cil > _CIL_HARM:
            worse("FAIL_HARM")
            reasons.append(f"{label} |cal_in_large| {cil} > {_CIL_HARM} (harm)")
        elif cil > _CIL_PASS:
            worse("CONTINUE")
            reasons.append(f"{label} |cal_in_large| {cil} in ({_CIL_PASS},{_CIL_HARM}] -> CONTINUE")
        if not (_SLOPE_LO <= slope <= _SLOPE_HI):
            worse("CONTINUE")
            reasons.append(f"{label} slope {slope} outside [{_SLOPE_LO},{_SLOPE_HI}]")

    check(overall, "overall", required=True)
    per_tour = scorecard["per_tour"]
    assert isinstance(per_tour, Mapping)
    for tour in ("ATP", "WTA"):
        block = per_tour[tour]
        assert isinstance(block, Mapping)
        check(block, tour, required=True)   # both tours required (amendment: neither carried by the other)

    return {"verdict": verdict, "reasons": reasons, "min_support": min_support}


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


def score_market(prediction: FrozenPrediction, outcome: _WinnerOutcome) -> ScoredRow:
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
    outcomes: Mapping[str, _WinnerOutcome],
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


#: The largest |argument| for which ``math.exp`` does not raise OverflowError: ``exp(log(float_max))``
#: is exactly representable (== float_max), and exp of anything larger raises. This is the EXACT
#: overflow threshold of the float type, not a tunable constant.
_MAX_EXP_ARG = math.log(sys.float_info.max)


def _sigmoid(z: float) -> float:
    """Overflow-safe logistic. Clamps the linear predictor to +/- the exact ``math.exp`` overflow
    threshold (``log(float_max)``) so an extreme probability (a valid FrozenPrediction input, e.g.
    p<=1e-12) cannot make ``math.exp`` overflow and crash the scorecard. The bound is the tightest
    value that is provably overflow-safe, so clamping never alters a well-conditioned fit."""
    z = max(-_MAX_EXP_ARG, min(_MAX_EXP_ARG, z))
    return 1.0 / (1.0 + math.exp(-z))


#: Frozen Newton-fit boundary parameters (founder round-3 §3). Pinned exactly by
#: TestFitPredicateBoundaries, so a mutated cap or epsilon is killed at the definition.
MAX_NEWTON_ITERATIONS = 60
DET_EPSILON = 1e-12
STEP_EPSILON = 1e-11


def iteration_allowed(iterations: int, maximum: int) -> bool:
    """True iff another Newton iteration may start: strictly below the cap. The loop counter
    starts at 0, only ever increments by exactly 1, and is never reassigned, so it cannot skip
    the cap; the predicate itself is total over ints and boundary-tested at 59/60/61."""
    return iterations < maximum


def hessian_is_singular(determinant: float) -> bool:
    """True iff the 2x2 information determinant has collapsed: at or BELOW ``DET_EPSILON``
    (the boundary value itself is singular). Boundary-tested at the epsilon and one ulp above."""
    return determinant <= DET_EPSILON


def step_has_converged(step_norm: float) -> bool:
    """True iff the Newton step norm ``|da| + |db|`` is strictly BELOW ``STEP_EPSILON``
    (the boundary value itself has NOT converged). Boundary-tested at the epsilon and one
    ulp below."""
    return step_norm < STEP_EPSILON


def _fit_slope(xs: Sequence[float], ys: Sequence[int]) -> tuple[float, int, str]:
    """Newton fit of the calibration slope. Returns (slope, iterations, status) where status is
    one of 'converged' | 'singular' | 'max_iterations'.

    The iteration count and exit status are RETAINED as first-class outputs so the optimiser's
    convergence behaviour is an observable of the M1 scorecard (SPEC-097): a degraded fit — one
    that takes a different number of iterations, exits by a different path, or fails to converge —
    cannot pass silently even when it lands on the same rounded slope. All three loop boundaries
    are the pure predicates above (directly boundary-tested); the numerical update is unchanged
    from the pre-diagnostics form (byte-identical coefficients)."""
    a, b = 0.0, 1.0
    iterations = 0
    status = "max_iterations"
    # `iterations` is LIVE in the loop condition (its initial 0 is read before the first step and
    # determines the reported count), so it is not a dead store. The cap is a non-binding safety
    # backstop: the fit provably exits via convergence or singularity first (fit_status is never
    # 'max_iterations'; TestOptimiserConvergenceDiagnostics pins this).
    while iteration_allowed(iterations, MAX_NEWTON_ITERATIONS):
        iterations += 1
        ga = gb = haa = hab = hbb = 0.0
        for x, y in zip(xs, ys):
            m = _sigmoid(a + b * x)
            ga += y - m
            gb += (y - m) * x
            w = m * (1 - m)
            haa += w
            hab += w * x
            hbb += w * x * x
        det = haa * hbb - hab * hab
        if hessian_is_singular(det):
            status = "singular"
            break
        da = (hbb * ga - hab * gb) / det
        db = (haa * gb - hab * ga) / det
        a += da
        b += db
        if step_has_converged(abs(da) + abs(db)):
            status = "converged"
            break
    return b, iterations, status


def _metrics(pairs: Sequence[tuple[float, int]]) -> dict[str, object]:
    """SPEC-097 proper scores + calibration-in-the-large + slope for (p, y) pairs, plus the
    calibration fit's convergence diagnostics (fit_iterations, fit_status)."""
    n = len(pairs)
    if n == 0:
        return {"n": 0}
    ll = sum(-math.log(_clamp(p if y == 1 else 1 - p)) for p, y in pairs) / n
    brier = sum((p - y) ** 2 for p, y in pairs) / n
    mp = sum(p for p, _ in pairs) / n
    my = sum(y for _, y in pairs) / n
    cil = _logit(my) - _logit(mp)
    xs = [_logit(p) for p, _ in pairs]
    ys = [y for _, y in pairs]
    b, iterations, status = _fit_slope(xs, ys)
    return {"n": n, "log_loss": round(ll, 6), "brier": round(brier, 6),
            "cal_in_large": round(cil, 6), "cal_slope": round(b, 6),
            "fit_iterations": iterations, "fit_status": status}


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
