"""STAGE3-0002 §3 — corpus reader (red tests first).

Thin, deterministic reader over the bz2 ADVANCED corpus. Tests write a tiny synthetic bz2
so they are hermetic (no dependency on the real corpus).
"""
from __future__ import annotations

import bz2
import json
from pathlib import Path

import pytest

from research.xmarket import corpus as C
from research.xmarket.linkage import MarketRef


def _write_market(tmp: Path, event_id: str, market_id: str, market_type: str) -> Path:
    d = tmp / "2026" / "Jun" / "3" / event_id
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{market_id}.bz2"
    md = {"pt": 100, "mc": [{"id": market_id, "marketDefinition": {
        "marketType": market_type, "eventId": event_id, "eventName": "A v B",
        "marketTime": "2026-06-03T12:00:00.000Z", "status": "OPEN", "inPlay": False,
        "eventTypeId": "2", "runners": [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]}}]}
    delta = {"pt": 200, "mc": [{"id": market_id, "rc": [
        {"id": 1, "hc": 0.0, "batb": [[0, 1.9, 10.0]], "ltp": 0.0, "tv": 0.0}]}]}
    with bz2.open(p, "wt") as fh:
        fh.write(json.dumps(md) + "\n")
        fh.write(json.dumps(delta) + "\n")
    return p


def test_market_id_from_filename(tmp_path: Path) -> None:
    p = _write_market(tmp_path, "E1", "1.234", "MATCH_ODDS")
    assert C.market_id_from_path(p) == "1.234"


def test_read_first_definition_returns_marketref(tmp_path: Path) -> None:
    p = _write_market(tmp_path, "E1", "1.234", "COMBINED_TOTAL")
    ref = C.read_first_definition(p)
    assert isinstance(ref, MarketRef)
    assert ref.market_id == "1.234"
    assert ref.event_id == "E1"
    assert ref.market_type == "COMBINED_TOTAL"
    assert ref.market_time_ms == 1780488000000  # 2026-06-03T12:00:00Z in ms


def test_iter_market_files_finds_all_bz2(tmp_path: Path) -> None:
    _write_market(tmp_path, "E1", "1.1", "MATCH_ODDS")
    _write_market(tmp_path, "E1", "1.2", "COMBINED_TOTAL")
    _write_market(tmp_path, "E2", "1.3", "HANDICAP")
    found = sorted(mid for mid, _ in C.iter_market_files(tmp_path))
    assert found == ["1.1", "1.2", "1.3"]


def test_iter_messages_yields_in_file_order(tmp_path: Path) -> None:
    p = _write_market(tmp_path, "E1", "1.234", "MATCH_ODDS")
    msgs = list(C.iter_messages(p))
    assert [m["pt"] for m in msgs] == [100, 200]


def test_build_catalogue_from_corpus_is_deterministic(tmp_path: Path) -> None:
    _write_market(tmp_path, "E1", "1.1", "MATCH_ODDS")
    _write_market(tmp_path, "E1", "1.2", "COMBINED_TOTAL")
    cat_a = C.build_corpus_catalogue(tmp_path)
    cat_b = C.build_corpus_catalogue(tmp_path)
    assert cat_a == cat_b
    assert set(cat_a) == {"1.1", "1.2"}


def test_missing_market_time_is_none_not_error(tmp_path: Path) -> None:
    d = tmp_path / "2026" / "Jun" / "3" / "E1"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "1.9.bz2"
    md = {"pt": 100, "mc": [{"id": "1.9", "marketDefinition": {
        "marketType": "MATCH_ODDS", "eventId": "E1", "status": "OPEN"}}]}
    with bz2.open(p, "wt") as fh:
        fh.write(json.dumps(md) + "\n")
    ref = C.read_first_definition(p)
    assert ref.market_time_ms is None


def test_file_without_definition_refuses(tmp_path: Path) -> None:
    d = tmp_path / "2026" / "Jun" / "3" / "E1"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "1.8.bz2"
    with bz2.open(p, "wt") as fh:
        fh.write(json.dumps({"pt": 100, "mc": [{"id": "1.8", "rc": []}]}) + "\n")
    with pytest.raises(C.CorpusReadError):
        C.read_first_definition(p)
