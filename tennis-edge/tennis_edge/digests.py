"""Canonical digests. One serialisation, one hash, everywhere.

A digest is taken over sorted-key, separator-normalised JSON so the same content always
yields the same digest regardless of dict insertion order. Decimals serialise as their
exact string form; no float ever enters a digest.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

__all__ = ["canonical_json", "digest_of", "digest_bytes"]


def _default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (set, frozenset)):
        return sorted(str(v) for v in value)
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"{type(value).__name__} is not canonically serialisable")


def canonical_json(payload: Any) -> str:
    """Deterministic JSON: sorted keys, compact separators, exact Decimal strings."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_default)


def digest_of(payload: Any) -> str:
    """``sha256:<hex>`` over :func:`canonical_json` of ``payload``."""
    return digest_bytes(canonical_json(payload).encode("utf-8"))


def digest_bytes(raw: bytes) -> str:
    """``sha256:<hex>`` over raw bytes."""
    return "sha256:" + hashlib.sha256(raw).hexdigest()
