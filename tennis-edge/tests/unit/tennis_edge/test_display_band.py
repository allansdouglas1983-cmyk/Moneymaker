"""The execution-cost band the site displays with every edge (TE-0017 S6).

The displayed edge is a point; the adopted DR-TENNIS-MICROSTRUCTURE-001 standard requires
the band. This module converts the frozen per-stratum Roll spread into probability points
at the quoted odds, deterministically — the same numbers the golden vectors hold the
TypeScript port to.

The stratum key is the S5 staleness band, the only serve-time-knowable liquidity signal
in the system; a prediction with no knowable stratum takes the pooled conservative
fallback, never a claimed stratum.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from tennis_edge.display_band import ROLL_BAND_TABLE, band_spread, edge_band
from tennis_edge.upcoming import break_even_probability


class TestBandSpread:
    def test_a_known_stratum_takes_its_own_p75(self) -> None:
        for band in ("<60s", "60-600s", ">600s"):
            assert band_spread(band) == ROLL_BAND_TABLE[band]

    def test_an_unknown_stratum_takes_the_pooled_conservative_fallback(self) -> None:
        """Manual entries carry no LTP age. They get the pooled p90, never a claimed
        stratum — 'we do not know how thin this market is' costs more, not less."""
        assert band_spread(None) == ROLL_BAND_TABLE["pooled_p90"]

    def test_the_fallback_is_wider_than_every_knowable_stratum(self) -> None:
        """If unknown were ever cheaper than known, the display would reward not
        looking. Frozen property of the table, checked forever."""
        for band in ("<60s", "60-600s", ">600s"):
            assert ROLL_BAND_TABLE["pooled_p90"] > ROLL_BAND_TABLE[band]

    def test_a_name_outside_the_vocabulary_is_refused(self) -> None:
        with pytest.raises(KeyError):
            band_spread("weird-band")


class TestEdgeBand:
    def test_the_band_is_the_break_even_shift_at_half_spread(self) -> None:
        """The declared conversion: crossing costs half the Roll spread on the price, so
        the effective odds are O*exp(-s/2) and the band is how far break-even rises."""
        import math
        odds = Decimal("2.5")
        spread = 0.04
        effective = float(odds) * math.exp(-spread / 2.0)
        expected = (float(break_even_probability(Decimal(str(effective))))
                    - float(break_even_probability(odds)))
        assert edge_band(odds, spread) == pytest.approx(expected, abs=1e-15)

    def test_zero_spread_is_zero_band(self) -> None:
        assert edge_band(Decimal("3.0"), 0.0) == 0.0

    def test_the_band_is_positive_and_monotone_in_the_spread(self) -> None:
        narrow = edge_band(Decimal("2.0"), 0.02)
        wide = edge_band(Decimal("2.0"), 0.06)
        assert 0.0 < narrow < wide

    def test_negative_spread_and_unbettable_odds_are_refused(self) -> None:
        with pytest.raises(ValueError):
            edge_band(Decimal("2.0"), -0.01)
        with pytest.raises(ValueError):
            edge_band(Decimal("1.0"), 0.02)
