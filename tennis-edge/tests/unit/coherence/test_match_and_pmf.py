"""STAGE3-0005 §12/§16 — match + derived-market production vs independent reference agreement.

Synthetic-only. Production ``match_distribution`` must agree with the independently-structured
``ref_match`` (top-down recursion + independent set/tiebreak references) to 1e-9 over a governed
grid; a discrepancy is STOP_MATH_INTEGRITY. Plus properties on the match distribution and the
Over/Under and Asian-handicap derived quantities (normalization, push semantics, monotonicity,
physical player-relabel symmetry).
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from sport_tennis.coherence import reference as R
from sport_tennis.coherence.formats import MatchFormat
from sport_tennis.coherence.match import match_distribution
from sport_tennis.coherence.pmf import (
    expected_margin,
    expected_total_games,
    handicap_cover,
    over_under,
)
from sport_tennis.coherence.scoring import CoherenceMathError

_ALL_FORMATS = list(MatchFormat)
_TOL = 1e-9


def _pmf_close(a: dict[int, float], b: dict[int, float]) -> None:
    keys = set(a) | set(b)
    for k in keys:
        assert a.get(k, 0.0) == pytest.approx(b.get(k, 0.0), abs=_TOL), f"PMF mismatch at {k}"


# --------------------------------------------------------- production == reference (§2.5)
@pytest.mark.parametrize("fmt", _ALL_FORMATS)
@pytest.mark.parametrize("a_first", [True, False])
def test_match_production_equals_reference(fmt: MatchFormat, a_first: bool) -> None:
    for pa in (0.55, 0.62, 0.70):
        for pb in (0.58, 0.66):
            prod = match_distribution(pa, pb, fmt, a_serves_first_match=a_first)
            win, tot, mar = R.ref_match(pa, pb, fmt, a_serves_first_match=a_first)
            assert prod.match_win_a == pytest.approx(win, abs=_TOL)
            _pmf_close(prod.total_games_pmf, tot)
            _pmf_close(prod.margin_pmf, mar)


# ------------------------------------------------------------------ match properties
@pytest.mark.parametrize("fmt", _ALL_FORMATS)
def test_match_pmfs_normalize(fmt: MatchFormat) -> None:
    md = match_distribution(0.61, 0.59, fmt, a_serves_first_match=True)
    assert sum(md.total_games_pmf.values()) == pytest.approx(1.0, abs=_TOL)
    assert sum(md.margin_pmf.values()) == pytest.approx(1.0, abs=_TOL)
    assert 0.0 <= md.match_win_a <= 1.0


def test_match_win_increases_with_own_serve() -> None:
    fmt = MatchFormat.BO3_AD_TB7_ALL_SETS
    lo = match_distribution(0.58, 0.62, fmt, a_serves_first_match=True).match_win_a
    hi = match_distribution(0.66, 0.62, fmt, a_serves_first_match=True).match_win_a
    assert hi > lo


def test_match_win_decreases_with_opponent_serve() -> None:
    fmt = MatchFormat.BO3_AD_TB7_ALL_SETS
    lo = match_distribution(0.62, 0.58, fmt, a_serves_first_match=True).match_win_a
    hi = match_distribution(0.62, 0.66, fmt, a_serves_first_match=True).match_win_a
    assert hi < lo


@pytest.mark.parametrize("fmt", _ALL_FORMATS)
@pytest.mark.parametrize("a_first", [True, False])
def test_match_symmetric_players_half(fmt: MatchFormat, a_first: bool) -> None:
    md = match_distribution(0.6, 0.6, fmt, a_serves_first_match=a_first)
    assert md.match_win_a == pytest.approx(0.5, abs=_TOL)


@pytest.mark.parametrize("fmt", _ALL_FORMATS)
def test_match_physical_relabel_symmetry(fmt: MatchFormat) -> None:
    # Relabel the two physical players but keep the SAME player serving the match's first game:
    # original A (2nd arg in the swap) still serves first. Win-prob complements, totals are
    # identical (same physical match), margins negate.
    orig = match_distribution(0.63, 0.57, fmt, a_serves_first_match=True)
    swap = match_distribution(0.57, 0.63, fmt, a_serves_first_match=False)
    assert swap.match_win_a == pytest.approx(1.0 - orig.match_win_a, abs=_TOL)
    _pmf_close(swap.total_games_pmf, orig.total_games_pmf)
    _pmf_close(swap.margin_pmf, {-m: pr for m, pr in orig.margin_pmf.items()})


# ------------------------------------------------------------------ Over/Under (§9)
def _totals() -> dict[int, float]:
    return match_distribution(0.62, 0.58, MatchFormat.BO3_AD_TB7_ALL_SETS,
                              a_serves_first_match=True).total_games_pmf


def test_over_under_half_line_has_no_push_and_sums_to_one() -> None:
    ou = over_under(_totals(), Decimal("21.5"))
    assert ou.push == 0.0
    assert ou.over + ou.under + ou.push == pytest.approx(1.0, abs=_TOL)


def test_over_under_integer_line_carries_push() -> None:
    tot = _totals()
    line = Decimal("22")
    ou = over_under(tot, line)
    assert ou.push == pytest.approx(tot.get(22, 0.0), abs=_TOL)
    assert ou.over + ou.under + ou.push == pytest.approx(1.0, abs=_TOL)


def test_over_probability_monotone_decreasing_in_line() -> None:
    tot = _totals()
    lines = [Decimal("18.5"), Decimal("20.5"), Decimal("22.5"), Decimal("24.5")]
    overs = [over_under(tot, ln).over for ln in lines]
    assert overs == sorted(overs, reverse=True)


def test_over_under_bad_line_refused() -> None:
    with pytest.raises(CoherenceMathError):
        over_under(_totals(), Decimal("21.3"))
    with pytest.raises(CoherenceMathError):
        over_under(_totals(), 21.5)  # type: ignore[arg-type]


# --------------------------------------------------------------- Asian handicap (§9)
def _margins() -> dict[int, float]:
    return match_distribution(0.64, 0.56, MatchFormat.BO3_AD_TB7_ALL_SETS,
                              a_serves_first_match=True).margin_pmf


def test_handicap_half_line_no_push_and_complements() -> None:
    hc = handicap_cover(_margins(), Decimal("-3.5"))
    assert hc.push == 0.0
    assert hc.a_covers + hc.b_covers == pytest.approx(1.0, abs=_TOL)


def test_handicap_integer_line_carries_push() -> None:
    mar = _margins()
    hc = handicap_cover(mar, Decimal("-4"))
    # push == P(margin == 4): A wins by exactly 4, +(-4) == 0
    assert hc.push == pytest.approx(mar.get(4, 0.0), abs=_TOL)
    assert hc.a_covers + hc.b_covers + hc.push == pytest.approx(1.0, abs=_TOL)


def test_handicap_zero_line_matches_margin_sign() -> None:
    mar = _margins()
    hc = handicap_cover(mar, Decimal("0"))
    assert hc.a_covers == pytest.approx(sum(pr for m, pr in mar.items() if m > 0), abs=_TOL)
    assert hc.b_covers == pytest.approx(sum(pr for m, pr in mar.items() if m < 0), abs=_TOL)
    assert hc.push == pytest.approx(mar.get(0, 0.0), abs=_TOL)


def test_handicap_a_cover_monotone_in_line() -> None:
    mar = _margins()
    # A giving up more games (more negative handicap) can only lower A's cover probability.
    lines = [Decimal("-6.5"), Decimal("-4.5"), Decimal("-2.5"), Decimal("-0.5")]
    covers = [handicap_cover(mar, ln).a_covers for ln in lines]
    assert covers == sorted(covers)


# ------------------------------------------------------------------ expectations
def test_expected_total_and_margin_consistent() -> None:
    md = match_distribution(0.62, 0.58, MatchFormat.BO3_AD_TB7_ALL_SETS,
                            a_serves_first_match=True)
    et = expected_total_games(md.total_games_pmf)
    em = expected_margin(md.margin_pmf)
    assert et > 0
    # stronger server A should have a positive expected game margin
    assert em > 0
