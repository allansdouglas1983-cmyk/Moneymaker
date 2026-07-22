"""STAGE3-0005 §9 — direct (fast) PMF tests on hand-built distributions.

Synthetic-only. Exercises Over/Under, Asian-handicap cover, push mass, half-line handling and
expectations directly on small normalized PMFs (no match DP), so the derived-market math is
pinned by fast, self-contained cases (also the fast mutation surface for pmf.py).
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from sport_tennis.coherence.pmf import (
    expected_margin,
    expected_total_games,
    handicap_cover,
    over_under,
)
from sport_tennis.coherence.scoring import CoherenceMathError

# total games in {20,21,22,23} with known masses
_TOT = {20: 0.1, 21: 0.2, 22: 0.3, 23: 0.4}
# margin A-B in {-2,-1,0,1,2}
_MAR = {-2: 0.1, -1: 0.2, 0: 0.15, 1: 0.25, 2: 0.3}


def test_over_under_half_line_partitions_exactly() -> None:
    ou = over_under(_TOT, Decimal("21.5"))
    assert ou.push == 0.0
    assert ou.over == pytest.approx(0.7)   # 22 + 23
    assert ou.under == pytest.approx(0.3)  # 20 + 21
    assert ou.over + ou.under == pytest.approx(1.0)


def test_over_under_integer_line_push() -> None:
    ou = over_under(_TOT, Decimal("22"))
    assert ou.push == pytest.approx(0.3)   # exactly 22
    assert ou.over == pytest.approx(0.4)   # 23
    assert ou.under == pytest.approx(0.3)  # 20 + 21
    assert ou.over + ou.under + ou.push == pytest.approx(1.0)


def test_over_monotone_decreasing_in_line() -> None:
    overs = [over_under(_TOT, Decimal(str(x))).over for x in ("19.5", "21.5", "22.5", "23.5")]
    assert overs == sorted(overs, reverse=True)


def test_handicap_half_line_no_push() -> None:
    hc = handicap_cover(_MAR, Decimal("-1.5"))
    assert hc.push == 0.0
    # A covers when margin - 1.5 > 0 -> margin >= 2 -> {2}
    assert hc.a_covers == pytest.approx(0.3)
    assert hc.b_covers == pytest.approx(0.7)
    assert hc.a_covers + hc.b_covers == pytest.approx(1.0)


def test_handicap_integer_line_push() -> None:
    hc = handicap_cover(_MAR, Decimal("-1"))
    # push when margin - 1 == 0 -> margin == 1
    assert hc.push == pytest.approx(0.25)
    assert hc.a_covers == pytest.approx(0.3)   # margin 2
    assert hc.b_covers == pytest.approx(0.45)  # margin -2,-1,0
    assert hc.a_covers + hc.b_covers + hc.push == pytest.approx(1.0)


def test_handicap_zero_line_is_sign_of_margin() -> None:
    hc = handicap_cover(_MAR, Decimal("0"))
    assert hc.a_covers == pytest.approx(0.55)  # margins 1,2
    assert hc.b_covers == pytest.approx(0.30)  # margins -2,-1
    assert hc.push == pytest.approx(0.15)      # margin 0


def test_expectations() -> None:
    assert expected_total_games(_TOT) == pytest.approx(20 * .1 + 21 * .2 + 22 * .3 + 23 * .4)
    assert expected_margin(_MAR) == pytest.approx(-2 * .1 - 1 * .2 + 0 * .15 + 1 * .25 + 2 * .3)


def test_bad_line_and_pmf_refused() -> None:
    with pytest.raises(CoherenceMathError):
        over_under(_TOT, Decimal("21.3"))
    with pytest.raises(CoherenceMathError):
        over_under({20: 0.5, 21: 0.3}, Decimal("20.5"))  # not normalized
    with pytest.raises(CoherenceMathError):
        handicap_cover({}, Decimal("0"))                  # empty


# --- STAGE3-0006 §5 mutation-hardening: the multiple-of-0.5 line guard (kill NotEq->Lt) ---

def test_line_guard_refuses_line_whose_double_rounds_down() -> None:
    # _validate_line checks `(line*2) != (line*2).to_integral_value()`. A NotEq->Lt mutant only
    # raises when line*2 is BELOW its rounded integral (fractional part > 0.5). A line whose doubled
    # value has fractional part < 0.5 (22.1 -> 44.2 -> rounds to 44) is >= the integral, so the `<`
    # mutant would wrongly ACCEPT it. The existing bad-line test uses 21.3 (42.6 -> rounds up to 43),
    # which `<` still refuses. Pin the complementary side.
    with pytest.raises(CoherenceMathError):
        over_under(_TOT, Decimal("22.1"))
    with pytest.raises(CoherenceMathError):
        handicap_cover(_MAR, Decimal("22.1"))
