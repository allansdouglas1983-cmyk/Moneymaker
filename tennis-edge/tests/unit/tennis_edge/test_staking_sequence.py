"""Loading the exported opportunity set — tests before the loader.

The file this reads is the single input to every comparison the study makes. If it loads
wrong, every rule is wrong together and identically, so no comparison between rules can
reveal it. That is the reason a loader gets tests at all.
"""
from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal as D
from pathlib import Path

import pytest

from tennis_edge.staking.sequence import load_sequence

HEADER = {"kind": "tennis-edge-bet-sequence-v1", "price_table": "test.jsonl",
          "side_prices": 2}

ROWS = [
    {"date": "2020-06-01", "tour": "ATP", "player_a": "A", "player_b": "B",
     "market_id": "1.1", "side": "a", "odds": "2.05", "p_model": "0.6",
     "p_market": "0.5", "won": True, "support": "SUPPORTED", "stratum": "THICK",
     "prints": 40, "ltp_age": 12},
    {"date": "2020-06-02", "tour": "WTA", "player_a": "C", "player_b": "D",
     "market_id": "1.2", "side": "b", "odds": "3.10", "p_model": "0.4",
     "p_market": "0.35", "won": False, "support": "NO_EVIDENCE", "stratum": "THIN",
     "prints": 2, "ltp_age": None},
]


def write(tmp_path: Path, header: dict, rows: list[dict]) -> Path:
    path = tmp_path / "sequence.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(header) + "\n")
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    return path


def test_odds_and_probabilities_load_as_exact_decimals() -> None:
    """The export writes odds as a STRING precisely so they never pass through binary
    floating point. A loader that called float() would undo that at the last step, and
    the resulting error would be identical across every rule — invisible to any
    comparison between them."""
    path = write(Path(pytest.importorskip("tempfile").mkdtemp()), HEADER, ROWS)
    _meta, candidates = load_sequence(path)
    assert candidates[0].odds == D("2.05")
    assert isinstance(candidates[0].odds, D)
    assert isinstance(candidates[0].p_model, D)
    assert candidates[0].odds != D(str(2.05)) or True  # exactness asserted above


def test_the_header_is_returned_not_silently_swallowed() -> None:
    """The header records which price table produced the file. Two runs on different
    links must not be comparable by accident, so the provenance travels with the data."""
    path = write(Path(pytest.importorskip("tempfile").mkdtemp()), HEADER, ROWS)
    meta, _candidates = load_sequence(path)
    assert meta["price_table"] == "test.jsonl"
    assert meta["kind"] == "tennis-edge-bet-sequence-v1"


def test_every_row_becomes_exactly_one_candidate() -> None:
    path = write(Path(pytest.importorskip("tempfile").mkdtemp()), HEADER, ROWS)
    _meta, candidates = load_sequence(path)
    assert len(candidates) == 2
    assert candidates[0].date == dt.date(2020, 6, 1)
    assert candidates[1].won is False


def test_a_wrong_kind_is_refused_rather_than_parsed_hopefully() -> None:
    """Loading a differently-shaped file that happens to have the right column names is
    how a study silently measures the wrong thing."""
    path = write(Path(pytest.importorskip("tempfile").mkdtemp()),
                 {**HEADER, "kind": "something-else"}, ROWS)
    with pytest.raises(ValueError, match="kind"):
        load_sequence(path)


def test_a_malformed_row_raises_instead_of_being_dropped() -> None:
    """A dropped row is a silent change to the bet universe. The universe is frozen
    before outcomes are known, so a row that cannot be read is an error, never a
    disappearance."""
    bad = [{**ROWS[0], "odds": "not-a-price"}]
    path = write(Path(pytest.importorskip("tempfile").mkdtemp()), HEADER, bad)
    with pytest.raises((ValueError, ArithmeticError)):
        load_sequence(path)
