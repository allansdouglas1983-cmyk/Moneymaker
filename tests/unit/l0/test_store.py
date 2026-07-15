"""Unit tests for l0_raw.store.AppendOnlyLog (SPEC-001 append-only, SPEC-002 preserve all)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from l0_raw import store as store_mod
from l0_raw.store import AppendOnlyLog

pytestmark = [pytest.mark.spec("SPEC-001"), pytest.mark.spec("SPEC-002")]


def _log(tmp_path: Path) -> AppendOnlyLog:
    return AppendOnlyLog(tmp_path / "raw" / "log.l0")


def test_no_mutation_or_delete_api() -> None:
    # Append-only must be a property of the type, not a convention.
    for forbidden in ("update", "delete", "remove", "truncate", "overwrite", "__setitem__"):
        assert not hasattr(AppendOnlyLog, forbidden)


def test_read_returns_written_in_order(tmp_path: Path) -> None:
    log = _log(tmp_path)
    payloads = [b"a", b"bb", b"ccc"]
    for i, p in enumerate(payloads):
        log.append({"i": i}, p)
    got = list(log.read())
    assert [p for _, p in got] == payloads
    assert [m["i"] for m, _ in got] == [0, 1, 2]


def test_duplicates_are_preserved(tmp_path: Path) -> None:
    log = _log(tmp_path)
    for _ in range(3):
        log.append({"dup": True}, b"same")
    assert [p for _, p in log.read()] == [b"same", b"same", b"same"]


def test_out_of_order_is_preserved(tmp_path: Path) -> None:
    log = _log(tmp_path)
    seqs = [5, 2, 9, 1]  # deliberately not sorted; store must not reorder
    for s in seqs:
        log.append({"stream_clock": s}, b"x")
    assert [m["stream_clock"] for m, _ in log.read()] == seqs


def test_payload_stored_verbatim_all_byte_values(tmp_path: Path) -> None:
    log = _log(tmp_path)
    payload = bytes(range(256))
    log.append({"k": "v"}, payload)
    ((meta, got),) = list(log.read())
    assert got == payload
    assert meta["k"] == "v"


def test_corrupt_header_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.l0"
    path.write_bytes(b"NOT-A-VALID-HEADER" + b"\x00" * 8)
    with pytest.raises(ValueError):
        list(AppendOnlyLog(path).read())


def test_len_counts_records(tmp_path: Path) -> None:
    log = _log(tmp_path)
    meta: dict[str, Any] = {}
    for _ in range(4):
        log.append(meta, b"")
    assert len(log) == 4


def test_creation_fsyncs_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A new journal's directory entry must be made durable (SPEC-003 durability hardening).
    seen: list[Path] = []
    monkeypatch.setattr(store_mod, "_fsync_dir", seen.append)
    path = tmp_path / "sub" / "log.l0"
    AppendOnlyLog(path)
    assert seen == [path.parent]
