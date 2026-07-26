"""Tests for the per-horizon snapshot cache.

The cache is a derived artefact that experiments trust without re-deriving, so the tests
that matter are the ones about *refusing* — a cache built for different horizons, or in an
older schema, must not be read as though it answered the question being asked.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tennis_edge.snapshots import (
    HORIZONS,
    HorizonState,
    MarketSnapshot,
    load_snapshots,
    write_snapshots,
)


def state(horizon: int = 3_600, *, back_a: float = 2.0, lay_a: float = 2.02,
          back_b: float = 1.98, lay_b: float = 2.0) -> HorizonState:
    return HorizonState(
        horizon=horizon,
        back_a=back_a, back_b=back_b, lay_a=lay_a, lay_b=lay_b,
        size_back_a=100.0, size_back_b=50.0, size_lay_a=25.0, size_lay_b=75.0,
        volume_a=1000.0, volume_b=500.0,
    )


def snapshot(**overrides: object) -> MarketSnapshot:
    fields: dict[str, object] = {
        "market_id": "1.234", "event_name": "Smith A. v Jones B.",
        "match_date": "2026-06-15", "tour": "ATP", "surface": "Grass", "best_of": 3,
        "market_time_ms": 1_781_000_000_000, "won_a": 1,
        "player_a": "Smith A.", "player_b": "Jones B.",
        "states": (state(),),
    }
    fields.update(overrides)
    return MarketSnapshot(**fields)  # type: ignore[arg-type]


class TestRoundTrip:
    def test_a_written_cache_reads_back_identical(self, tmp_path: Path) -> None:
        original = [snapshot(), snapshot(market_id="1.235", player_a="Ray C.",
                                         player_b="Vale D.", won_a=0)]
        path = tmp_path / "cache.jsonl"
        write_snapshots(path, original, source="test", horizons=(3_600,))
        assert load_snapshots(path, horizons=(3_600,)) == original

    def test_the_corpus_names_survive(self, tmp_path: Path) -> None:
        """Downstream joins are by name; losing them would silently break every pairing."""
        path = tmp_path / "cache.jsonl"
        write_snapshots(path, [snapshot()], source="test", horizons=(3_600,))
        loaded = load_snapshots(path, horizons=(3_600,))
        assert (loaded[0].player_a, loaded[0].player_b) == ("Smith A.", "Jones B.")


class TestRefusals:
    def test_a_cache_built_for_other_horizons_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "cache.jsonl"
        write_snapshots(path, [snapshot()], source="test", horizons=(3_600,))
        with pytest.raises(ValueError, match="horizons"):
            load_snapshots(path, horizons=(600,))

    def test_an_older_schema_is_refused(self, tmp_path: Path) -> None:
        """A v1 cache has no player names, so reading it as v2 would join on nothing."""
        path = tmp_path / "cache.jsonl"
        path.write_text(json.dumps({
            "kind": "market-snapshot-cache-v1", "source": "old",
            "horizons": [3_600], "markets": 0,
        }) + "\n", encoding="utf-8")
        with pytest.raises(ValueError, match="not a snapshot cache"):
            load_snapshots(path, horizons=(3_600,))

    def test_an_empty_file_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "cache.jsonl"
        path.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="empty"):
            load_snapshots(path, horizons=HORIZONS)


class TestHorizonState:
    def test_the_midpoint_normalises_the_overround_away(self) -> None:
        """Both sides' midpoints must sum to one; a raw implied pair does not."""
        first = state()
        assert first.midpoint_a == pytest.approx(0.5, abs=0.01)

    def test_the_midpoint_moves_with_the_book(self) -> None:
        shorter = state(back_a=1.5, lay_a=1.52, back_b=2.9, lay_b=3.0)
        assert shorter.midpoint_a > 0.6

    def test_size_imbalance_is_a_share_of_both_sides(self) -> None:
        assert state().size_imbalance_a == pytest.approx(100.0 / 125.0)

    def test_volume_share_defaults_to_even_when_nothing_traded(self) -> None:
        """Zero volume is not evidence of a 50/50 split, but it is the only neutral value."""
        quiet = HorizonState(horizon=600, back_a=2.0, back_b=2.0, lay_a=2.02, lay_b=2.02,
                             size_back_a=1.0, size_back_b=1.0, size_lay_a=1.0,
                             size_lay_b=1.0, volume_a=0.0, volume_b=0.0)
        assert quiet.volume_share_a == 0.5

    def test_the_spread_is_measured_in_ticks_not_price(self) -> None:
        """Two ladder steps at 2.0 is 0.04 of price; the tick count is what is comparable."""
        assert state(back_a=2.0, lay_a=2.04).spread_ticks_a == 2


class TestLookup:
    def test_a_missing_horizon_returns_none(self) -> None:
        assert snapshot().at(120) is None

    def test_a_present_horizon_returns_its_state(self) -> None:
        found = snapshot().at(3_600)
        assert found is not None and found.horizon == 3_600
