"""Append-only raw event log (SPEC-001 append-only/verbatim, SPEC-002 keep everything).

A magic-prefixed file of length-framed records: ``>II`` (metadata length, payload length)
followed by deterministic metadata JSON and the payload **bytes verbatim**. The type exposes
only ``append`` and ``read`` — there is no update or delete, so append-only is a property of
the type, not a convention.
"""
from __future__ import annotations

import json
import os
import struct
from pathlib import Path
from typing import Any, Iterator

_MAGIC = b"L0RAW1\n"
_HEADER = struct.Struct(">II")


class AppendOnlyLog:
    def __init__(self, path: Path) -> None:
        self._path = path
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as handle:
                handle.write(_MAGIC)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, metadata: dict[str, Any], payload: bytes) -> None:
        """Durably append one framed record. Never mutates existing records."""
        meta_bytes = json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("utf-8")
        frame = _HEADER.pack(len(meta_bytes), len(payload)) + meta_bytes + payload
        with self._path.open("ab") as handle:
            handle.write(frame)
            handle.flush()
            os.fsync(handle.fileno())

    def read(self) -> Iterator[tuple[dict[str, Any], bytes]]:
        """Yield ``(metadata, payload)`` frames in write order."""
        data = self._path.read_bytes()
        if not data.startswith(_MAGIC):
            raise ValueError(f"{self._path}: not an L0 raw log (bad magic header)")
        pos = len(_MAGIC)
        end = len(data)
        while pos < end:
            if pos + _HEADER.size > end:
                raise ValueError(f"{self._path}: truncated frame header at byte {pos}")
            meta_len, payload_len = _HEADER.unpack(data[pos : pos + _HEADER.size])
            pos += _HEADER.size
            if pos + meta_len + payload_len > end:
                raise ValueError(f"{self._path}: truncated frame body at byte {pos}")
            metadata: dict[str, Any] = json.loads(data[pos : pos + meta_len])
            pos += meta_len
            payload = data[pos : pos + payload_len]
            pos += payload_len
            yield metadata, payload

    def __len__(self) -> int:
        return sum(1 for _ in self.read())
