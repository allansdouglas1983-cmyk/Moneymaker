"""V0 release — property tests for grading and the market-only guarantee (Tier B).

Properties, not examples: proper scores behave as proper scores must, the final probability
is the market's under every admissible F2 view, and grading never invents a number.
"""
from __future__ import annotations

import math
from decimal import Decimal

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from assistant_v0 import grading as G
from assistant_v0 import manual_input as MI
from assistant_v0 import pipeline as P
from assistant_v0.shadow_ledger import PreMatchRecord

_probs = st.floats(min_value=1e-6, max_value=1 - 1e-6, allow_nan=False, allow_infinity=False)
_ratings = st.floats(min_value=800.0, max_value=2600.0, allow_nan=False, allow_infinity=False)
_counts = st.integers(min_value=5, max_value=500)


def _rec(p_market_a: float | None, p_f2_a: float | None = None) -> PreMatchRecord:
    return PreMatchRecord(
        record_id="r", snapshot_digest="sha256:s", tour="ATP",
        competitor_a="A", competitor_b="B",
        market_probability_a=p_market_a,
        market_probability_b=None if p_market_a is None else 1.0 - p_market_a,
        f2_probability_a=p_f2_a,
        f2_probability_b=None if p_f2_a is None else 1.0 - p_f2_a,
        status="MARKET_ONLY", reason_codes=(), data_digest="sha256:d",
        policy_digest="sha256:p", model_view_digest="sha256:m", created_at_ms=1)


# ------------------------------------------------------------------ proper-score properties
@settings(max_examples=150, deadline=None)
@given(p=_probs, winner=st.sampled_from(["A", "B"]))
def test_scores_are_non_negative_and_finite(p: float, winner: str) -> None:
    app = G.grade_settlement(_rec(p), winner=winner)
    assert app.market_log_loss is not None and app.market_brier is not None
    assert app.market_log_loss >= 0.0 and math.isfinite(app.market_log_loss)
    assert 0.0 <= app.market_brier <= 1.0


@settings(max_examples=150, deadline=None)
@given(p=_probs)
def test_confidence_in_the_winner_never_scores_worse(p: float) -> None:
    """Monotonicity: a probability closer to the realised outcome scores no worse."""
    better = min(p + (1 - p) / 2, 1 - 1e-9)
    a_lo = G.grade_settlement(_rec(p), winner="A")
    a_hi = G.grade_settlement(_rec(better), winner="A")
    assert a_hi.market_log_loss is not None and a_lo.market_log_loss is not None
    assert a_hi.market_log_loss <= a_lo.market_log_loss + 1e-12
    assert a_hi.market_brier is not None and a_lo.market_brier is not None
    assert a_hi.market_brier <= a_lo.market_brier + 1e-12


# The symmetry property is exact in real arithmetic, but the test itself must reconstruct
# (1 - p); near the unit boundary that subtraction loses most of its significant digits
# (catastrophic cancellation), so the property is stated over a numerically sane range. The
# extreme tails are still covered by the finiteness/non-negativity property above.
_symmetric_probs = st.floats(min_value=1e-3, max_value=1 - 1e-3,
                             allow_nan=False, allow_infinity=False)


@settings(max_examples=150, deadline=None)
@given(p=_symmetric_probs)
def test_winner_symmetry(p: float) -> None:
    """Scoring p for a win by A equals scoring (1-p) for a win by B."""
    a = G.grade_settlement(_rec(p), winner="A")
    b = G.grade_settlement(_rec(1.0 - p), winner="B")
    assert a.market_log_loss is not None and b.market_log_loss is not None
    assert a.market_log_loss == pytest.approx(b.market_log_loss, rel=1e-12)
    assert a.market_brier == pytest.approx(b.market_brier, rel=1e-12)


@settings(max_examples=100, deadline=None)
@given(p=_probs, winner=st.sampled_from(["A", "B"]))
def test_grading_is_deterministic(p: float, winner: str) -> None:
    assert G.grade_settlement(_rec(p), winner=winner) == G.grade_settlement(_rec(p),
                                                                           winner=winner)


@settings(max_examples=100, deadline=None)
@given(winner=st.sampled_from(["A", "B"]), p_f2=_probs)
def test_absent_market_probability_is_always_excluded_never_scored(winner: str,
                                                                   p_f2: float) -> None:
    """A missing market probability can never be substituted — not even from the F2 view."""
    app = G.grade_settlement(_rec(None, p_f2), winner=winner)
    assert app.scored is False
    assert app.market_log_loss is None and app.market_brier is None
    assert app.exclusion_reason == G.NO_MARKET_PROBABILITY


# ------------------------------------------------------------------ market-only guarantee
@settings(max_examples=120, deadline=None)
@given(rating_a=_ratings, rating_b=_ratings, n_a=_counts, n_b=_counts)
def test_final_probability_is_the_market_under_every_f2_view(
        rating_a: float, rating_b: float, n_a: int, n_b: int) -> None:
    """However confident F2 is, it never becomes (or perturbs) the final probability."""
    snap = MI.ManualMarketSnapshot(
        competitor_a="A", competitor_b="B", competitor_a_id=None, competitor_b_id=None,
        tour="ATP", scheduled_start_ms=2000, input_timestamp_ms=1000,
        source=MI.MANUAL_SOURCE,
        back_a=Decimal("1.90"), back_a_size=Decimal("50"),
        lay_a=Decimal("1.95"), lay_a_size=Decimal("40"),
        back_b=Decimal("2.04"), back_b_size=Decimal("30"),
        lay_b=Decimal("2.12"), lay_b_size=Decimal("20"),
        market_status="OPEN", in_play=False, market_id=None, event_id=None)
    market_only = P.assemble(snap, reference_time_ms=1000)

    def lookup(_tour: str, name: str) -> tuple[float, int] | None:
        return {"A": (rating_a, n_a), "B": (rating_b, n_b)}.get(name)

    with_f2 = P.assemble(snap, reference_time_ms=1000, rating_lookup=lookup)
    assert with_f2.final_probability_source == "MARKET"
    assert with_f2.final_probability_a == market_only.market_probability_a
    assert with_f2.market_probability_a == market_only.market_probability_a


@settings(max_examples=120, deadline=None)
@given(back_a=st.sampled_from(["1.5", "1.9", "2.5", "3.0"]),
       lay_gap=st.integers(min_value=1, max_value=3))
def test_market_probabilities_sum_to_one_when_available(back_a: str, lay_gap: int) -> None:
    """The governed market probabilities form a coherent two-outcome choice set."""
    from price_contracts.ladder import index_of, price_of
    ba = Decimal(back_a)
    la = price_of(index_of(ba) + lay_gap)
    bb = Decimal("2.0")
    lb = price_of(index_of(bb) + lay_gap)
    assume(ba < la and bb < lb)
    snap = MI.ManualMarketSnapshot(
        competitor_a="A", competitor_b="B", competitor_a_id=None, competitor_b_id=None,
        tour="ATP", scheduled_start_ms=2000, input_timestamp_ms=1000,
        source=MI.MANUAL_SOURCE,
        back_a=ba, back_a_size=Decimal("10"), lay_a=la, lay_a_size=Decimal("10"),
        back_b=bb, back_b_size=Decimal("10"), lay_b=lb, lay_b_size=Decimal("10"),
        market_status="OPEN", in_play=False, market_id=None, event_id=None)
    out = P.assemble(snap, reference_time_ms=1000)
    assert out.market_probability_a is not None and out.market_probability_b is not None
    assert out.market_probability_a + out.market_probability_b == pytest.approx(1.0, abs=1e-9)
