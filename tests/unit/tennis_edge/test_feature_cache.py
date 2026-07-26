"""Tests for the feature cache.

Building features walks the whole Sackmann archive day by day and takes about ten minutes.
Every experiment that wanted the same features paid it again, which is a tax on trying
things — and four re-runs of one experiment in a single session is what made that tax
visible.

A cache is only safe if it can prove it describes the inputs it is being used for, so the
tests are almost entirely about **refusal**: a cache built from a different corpus vintage,
a different archive, or a different feature-set version must not be silently returned in
place of one that was never built.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from tennis_edge.feature_cache import (
    FEATURE_SET_VERSION,
    CacheKey,
    FeatureRow,
    load_cache,
    write_cache,
)


def key(**overrides: str) -> CacheKey:
    fields: dict[str, str] = {
        "feature_set_version": FEATURE_SET_VERSION,
        "corpus_vintage": "vintage-2026-07-25",
        "corpus_manifest_digest": "sha256:aaaa",
        "archive_digest": "sha256:bbbb",
    }
    fields.update(overrides)
    return CacheKey(**fields)  # type: ignore[arg-type]


def rows() -> list[FeatureRow]:
    return [
        FeatureRow(date=dt.date(2020, 3, 1), tour="ATP", player_a="Smith A.",
                   player_b="Jones B.", market_logit=0.25,
                   features={"rank_gap": 1.5, "pyramid_elo_gap": -0.25}, won=1,
                   odds_a={"pinnacle": 1.8}, odds_b={"pinnacle": 2.1}),
        FeatureRow(date=dt.date(2020, 3, 2), tour="WTA", player_a="Ray C.",
                   player_b="Vale D.", market_logit=-0.5,
                   features={"rank_gap": -2.0}, won=0,
                   odds_a={}, odds_b={"max": 1.6}),
    ]


class TestRoundTrip:
    def test_a_written_cache_reads_back_identical(self, tmp_path: Path) -> None:
        path = tmp_path / "features.jsonl"
        write_cache(path, rows(), key=key())
        assert load_cache(path, key=key()) == rows()

    def test_feature_dicts_survive_exactly(self, tmp_path: Path) -> None:
        """Floats are the whole payload; a lossy round trip would move every result."""
        path = tmp_path / "features.jsonl"
        write_cache(path, rows(), key=key())
        loaded = load_cache(path, key=key())
        assert loaded is not None
        assert loaded[0].features == {"rank_gap": 1.5, "pyramid_elo_gap": -0.25}

    def test_a_row_missing_a_feature_stays_missing(self, tmp_path: Path) -> None:
        """Absence is a claim about knowledge; filling it in would be a different one."""
        path = tmp_path / "features.jsonl"
        write_cache(path, rows(), key=key())
        loaded = load_cache(path, key=key())
        assert loaded is not None
        assert "pyramid_elo_gap" not in loaded[1].features

    def test_an_empty_odds_map_is_preserved(self, tmp_path: Path) -> None:
        path = tmp_path / "features.jsonl"
        write_cache(path, rows(), key=key())
        loaded = load_cache(path, key=key())
        assert loaded is not None and loaded[1].odds_a == {}


class TestRefusals:
    """A stale cache is worse than no cache: it answers a question nobody asked."""

    def test_a_different_feature_set_version_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "features.jsonl"
        write_cache(path, rows(), key=key(feature_set_version="something-else"))
        assert load_cache(path, key=key()) is None

    def test_a_different_corpus_vintage_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "features.jsonl"
        write_cache(path, rows(), key=key(corpus_vintage="vintage-2020-01-01"))
        assert load_cache(path, key=key()) is None

    def test_a_changed_corpus_manifest_is_refused(self, tmp_path: Path) -> None:
        """Same vintage directory, different contents — the dangerous case."""
        path = tmp_path / "features.jsonl"
        write_cache(path, rows(), key=key(corpus_manifest_digest="sha256:cccc"))
        assert load_cache(path, key=key()) is None

    def test_a_changed_archive_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "features.jsonl"
        write_cache(path, rows(), key=key(archive_digest="sha256:dddd"))
        assert load_cache(path, key=key()) is None

    def test_a_missing_file_is_a_miss_not_an_error(self, tmp_path: Path) -> None:
        """A cold cache is the normal first run, not a failure."""
        assert load_cache(tmp_path / "absent.jsonl", key=key()) is None

    def test_a_truncated_cache_is_refused(self, tmp_path: Path) -> None:
        """A run killed mid-write leaves a file whose row count is short."""
        path = tmp_path / "features.jsonl"
        write_cache(path, rows(), key=key())
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
        with pytest.raises(ValueError, match="truncated"):
            load_cache(path, key=key())

    def test_a_foreign_file_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "features.jsonl"
        path.write_text(json.dumps({"kind": "something-else"}) + "\n", encoding="utf-8")
        with pytest.raises(ValueError, match="not a feature cache"):
            load_cache(path, key=key())


class TestKey:
    def test_the_key_is_order_independent_and_stable(self) -> None:
        """Two keys with the same values must compare equal however they were built."""
        assert key() == CacheKey(
            corpus_vintage="vintage-2026-07-25",
            feature_set_version=FEATURE_SET_VERSION,
            archive_digest="sha256:bbbb",
            corpus_manifest_digest="sha256:aaaa",
        )

    def test_the_version_is_a_declared_constant(self) -> None:
        """Bumping it is how a feature change invalidates every cache, so it is pinned."""
        assert isinstance(FEATURE_SET_VERSION, str) and FEATURE_SET_VERSION
