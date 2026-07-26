"""STAGE3-0006 §9 — keyword-only / positional signature contracts.

A ``*`` (keyword-only marker) -> ``/`` (positional-only marker) mutation is a behavioural
call-signature change, not an annotation change, and must be killed. These tests exercise the
signatures in a way the mutant breaks: they pass a parameter that the correct signature accepts
by keyword but the positional-only mutant would reject with TypeError.
"""
from __future__ import annotations

from sport_tennis.coherence.formats import MatchFormat, format_spec
from sport_tennis.coherence.scoring import check_normalized, set_distribution


def test_check_normalized_total_accepts_keyword() -> None:
    # Correct signature: def check_normalized(total, *, what=...). `total` is positional-or-keyword.
    # The `*`->`/` mutant makes `total` positional-only -> `total=` raises TypeError.
    check_normalized(total=1.0)
    check_normalized(total=1.0, what="pmf")


def test_set_distribution_spec_accepts_keyword() -> None:
    # Correct signature: def set_distribution(p_first, p_other, spec, *, is_final_set). `spec` is
    # positional-or-keyword; the `*`->`/` mutant makes p_first/p_other/spec positional-only.
    spec = format_spec(MatchFormat.BO3_AD_TB7_ALL_SETS)
    res = set_distribution(0.6, 0.55, spec=spec, is_final_set=False)
    assert abs(sum(res.games.values()) - 1.0) < 1e-9
