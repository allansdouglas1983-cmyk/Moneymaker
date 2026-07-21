"""PERSONAL_TENNIS_ASSISTANT_V0 — frozen F2-v1 sporting DIAGNOSTIC (STAGE3-0003 §4).

F2-v1 is shown ONLY as a separate historical sporting estimate, labelled
``MODEL_DIAGNOSTIC_NOT_MARKET_PROVEN``. It never silently replaces the market probability,
never becomes the final decision probability, and is never represented as prospectively
confirmed. It is emitted only where the two competitors resolve to governed identities with
sufficient history in the frozen F2-v1 rating state; otherwise it is UNAVAILABLE with a
reason (``IDENTITY_UNRESOLVED`` / ``MODEL_HISTORY_INSUFFICIENT``) — never a fabricated
number. The probability itself comes from the governed ``elo_win_probability``; no LLM
estimates it.

F3 and DP1 remain retired and are not selectable here.
"""
from __future__ import annotations

from dataclasses import dataclass

from sport_tennis.elo_family import elo_win_probability

F2_LABEL = "MODEL_DIAGNOSTIC_NOT_MARKET_PROVEN"
MODEL_HISTORY_INSUFFICIENT = "MODEL_HISTORY_INSUFFICIENT"
IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"

# Minimum prior-match count per player for the F2 diagnostic to be shown (a data-quality
# floor, not a tuned threshold; below it the model view is MODEL_HISTORY_INSUFFICIENT).
DEFAULT_MIN_HISTORY = 5


@dataclass(frozen=True)
class F2Diagnostic:
    """The separate, labelled F2-v1 diagnostic view (never the final probability)."""

    available: bool
    p_a: float | None
    p_b: float | None
    history_count_a: int | None
    history_count_b: int | None
    label: str | None
    reason: str | None


def unavailable(reason: str) -> F2Diagnostic:
    return F2Diagnostic(available=False, p_a=None, p_b=None, history_count_a=None,
                        history_count_b=None, label=None, reason=reason)


def f2_view_from_ratings(rating_a: float, history_count_a: int,
                         rating_b: float, history_count_b: int, *,
                         min_history: int = DEFAULT_MIN_HISTORY) -> F2Diagnostic:
    """Emit the F2-v1 diagnostic from two resolved players' frozen ratings + history counts.
    Below the history floor it is UNAVAILABLE. The probability is the governed Elo win
    probability; it is always labelled and never final."""
    if history_count_a < min_history or history_count_b < min_history:
        return unavailable(MODEL_HISTORY_INSUFFICIENT)
    p_a = elo_win_probability(rating_a, rating_b)
    return F2Diagnostic(
        available=True, p_a=p_a, p_b=1.0 - p_a,
        history_count_a=history_count_a, history_count_b=history_count_b,
        label=F2_LABEL, reason=None,
    )
