"""STAGE3-0006 §5.4/§5.5/§5.10 — tiebreak service sequence, tail-server seam, deuce-tail fallback.

Pins the pure service-sequence seam (exhaustive vs the independent reference, with input
refusal), the explicit tail-server-pair helper that replaces the opaque n0 arithmetic, and the
guarded deuce-tail resolver — so serve-inversion, parity/pair-arithmetic, n0, comparison and
epsilon-fallback mutants are all killed rather than surviving on a coincidental grid.
"""
from __future__ import annotations

import pytest

from sport_tennis.coherence import reference as R
from sport_tennis.coherence.scoring import (
    CoherenceMathError,
    _deuce_tail_first_win,
    point_win_prob_for_first,
    tiebreak_server_is_first,
    tiebreak_tail_servers,
)


# ------------------------------------------------------------ point-win path (kills serve flip)
def test_point_win_prob_matches_independent_reference_serve() -> None:
    # The first player wins point n with p_first when they serve it, else (1-p_other). Pinned
    # against the INDEPENDENT reference serve order, so a serve-assignment inversion (AddNot on
    # _server_is_first) is killed even though the tiebreak WIN probability is flip-invariant.
    pf, po = 0.7, 0.4
    for n in range(1, 30):
        expected = pf if R.ref_tiebreak_server_is_first(n) else (1.0 - po)
        assert point_win_prob_for_first(n, pf, po) == expected


# --------------------------------------------------------------- §5.4 service sequence
def test_serve_order_exhaustive_matches_independent_reference() -> None:
    for n in range(1, 45):
        assert tiebreak_server_is_first(n) == R.ref_tiebreak_server_is_first(n)


def test_serve_order_point_one_is_first() -> None:
    assert tiebreak_server_is_first(1) is True


def test_serve_order_refuses_nonpositive() -> None:
    for bad in (0, -1, -7):
        with pytest.raises(CoherenceMathError):
            tiebreak_server_is_first(bad)


def test_serve_order_refuses_non_integer_and_bool() -> None:
    for bad in (1.5, "3", True, False):
        with pytest.raises(CoherenceMathError):
            tiebreak_server_is_first(bad)  # type: ignore[arg-type]


# --------------------------------------------------------------- §5.5 tail-server pair
@pytest.mark.parametrize("target,expected", [(7, (True, False)), (10, (False, True))])
def test_tail_servers_pinned(target: int, expected: tuple[bool, bool]) -> None:
    assert tiebreak_tail_servers(target) == expected


def test_tail_servers_consistent_with_service_sequence() -> None:
    # the tail pair is exactly the servers of the two points at (target-1, target-1)
    for target in (7, 10):
        n0 = 2 * (target - 1) + 1
        assert tiebreak_tail_servers(target) == (
            tiebreak_server_is_first(n0), tiebreak_server_is_first(n0 + 1))


def test_tail_servers_bad_target_refused() -> None:
    for bad in (5, 6, 8, 0):
        with pytest.raises(CoherenceMathError):
            tiebreak_tail_servers(bad)


# --------------------------------------------------------------- §5.10 deuce-tail fallback
def test_deuce_tail_normal_ratio() -> None:
    x, y = 0.7, 0.4
    ff, oo = x * y, (1.0 - x) * (1.0 - y)
    assert _deuce_tail_first_win(x, y) == pytest.approx(ff / (ff + oo), abs=1e-15)


def test_deuce_tail_symmetric_half() -> None:
    assert _deuce_tail_first_win(0.5, 0.5) == pytest.approx(0.5, abs=1e-15)


def test_deuce_tail_fallback_distinguishable_from_ratio() -> None:
    # Near-degenerate tail mass underflow: ff+oo < _EPS AND the ratio is NOT 0.5, so the guarded
    # 0.5 fallback is observably different from ff/(ff+oo). Kills negative-eps, altered-comparison,
    # altered-denominator and altered-fallback-value mutants.
    x, y = 1.0 - 3e-14, 1e-14
    ff, oo = x * y, (1.0 - x) * (1.0 - y)
    assert 0.0 < ff + oo < 1e-12
    assert ff / (ff + oo) == pytest.approx(0.25, abs=0.05)   # the ratio is ~0.25, not 0.5
    assert _deuce_tail_first_win(x, y) == 0.5                # the guard returns exactly 0.5


def test_deuce_tail_denominator_shape() -> None:
    # ff/(ff+oo) differs from ff/(ff-oo) and ff*(ff+oo): pin the exact denominator form.
    x, y = 0.8, 0.3
    ff, oo = x * y, (1.0 - x) * (1.0 - y)
    got = _deuce_tail_first_win(x, y)
    assert got == pytest.approx(ff / (ff + oo), abs=1e-15)
    assert got != pytest.approx(ff / (ff - oo), abs=1e-9)
    assert got != pytest.approx(ff * (ff + oo), abs=1e-9)
