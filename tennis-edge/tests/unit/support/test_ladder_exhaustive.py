"""SPEC-053: exhaustive round-trip over the entire 350-tick ladder.

Added by the 2026-07-16 retrospective audit. The spec states exactness in absolute terms
("Round-trip index->decimal->index MUST be exact") over a small, finite, fully enumerable
domain — sampled property tests are a lower verification bar than the requirement's own
language, so every tick is checked, not a sample.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from price_contracts.ladder import LADDER, index_of, price_of

pytestmark = pytest.mark.spec("SPEC-053")


def test_ladder_has_exactly_350_ticks() -> None:
    assert len(LADDER) == 350


def test_every_tick_round_trips_exactly() -> None:
    for i in range(len(LADDER)):
        p = price_of(i)
        assert isinstance(p, Decimal)
        assert index_of(p) == i
        assert price_of(index_of(p)) == p


def test_every_adjacent_pair_is_strictly_increasing() -> None:
    for i in range(len(LADDER) - 1):
        assert price_of(i) < price_of(i + 1)


def test_band_boundaries_are_exact() -> None:
    # Canonical band endpoints (SPEC-053, verbatim from the manifest).
    assert price_of(0) == Decimal("1.01")
    assert index_of(Decimal("2.00")) == 99
    assert index_of(Decimal("3.00")) == 149
    assert index_of(Decimal("4.00")) == 169
    assert index_of(Decimal("6.00")) == 189
    assert index_of(Decimal("10.0")) == 209
    assert index_of(Decimal("20.0")) == 229
    assert index_of(Decimal("30.0")) == 239
    assert index_of(Decimal("50.0")) == 249
    assert index_of(Decimal("100")) == 259
    assert index_of(Decimal("1000")) == 349
