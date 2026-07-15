"""Feature-set assembly and reproducible hashing (SPEC-024).

Feature builds are deterministic and identified by a ``feature_set_hash``: the same inputs
produce byte-identical canonical features and therefore the same hash (SPEC-024). ``build_feature``
is the single construction path and composes the evidence guards:

  * SPEC-021 — reject a reconciled-BSP value used as a feature input (runtime assertion);
  * SPEC-020/023 — reject a feature not provably knowable before the off.

Values are limited to ``bool | int | Decimal | str | None`` — **no float**, both to honour the
"Decimal, never float" rule for numeric quantities and to keep the canonical hash independent
of platform float formatting. Decimals are compared by numeric value, so ``12.5`` and ``12.50``
hash identically.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from l3_features.knowledge_time import (
    KnowledgeStamps,
    SourceProvenance,
    assert_knowable_before_off,
)
from l3_features.leakage import assert_no_bsp

FeatureValue = bool | int | Decimal | str | None


class Feature(BaseModel):
    """One knowledge-time-stamped feature value with its source provenance."""

    # strict: never coerce across value types, so a float is rejected rather than silently
    # turned into a Decimal (which would defeat the no-float canonicalisation guarantee).
    model_config = ConfigDict(frozen=True, strict=True)

    name: str
    value: FeatureValue
    stamps: KnowledgeStamps
    source: SourceProvenance


class FeatureSet(BaseModel):
    """An unordered collection of features whose hash does not depend on construction order."""

    model_config = ConfigDict(frozen=True, strict=True)

    features: tuple[Feature, ...]


def _canonical_value(value: FeatureValue) -> dict[str, Any]:
    """Type-tagged canonical form. Decimals are numeric-normalised, never scientific."""
    if value is None:
        return {"t": "null"}
    if isinstance(value, bool):  # before int — bool is a subclass of int
        return {"t": "bool", "v": value}
    if isinstance(value, Decimal):
        norm = value.normalize()
        if norm == 0:  # collapse -0 and 0.00 to a single canonical zero
            norm = Decimal(0)
        return {"t": "dec", "v": format(norm, "f")}
    if isinstance(value, int):
        return {"t": "int", "v": value}
    if isinstance(value, str):
        return {"t": "str", "v": value}
    raise TypeError(f"unsupported feature value type {type(value).__name__}")  # pragma: no cover


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _canonical_feature(feature: Feature) -> dict[str, Any]:
    stamps = feature.stamps
    source = feature.source
    return {
        "name": feature.name,
        "value": _canonical_value(feature.value),
        "stamps": {
            "event_time": stamps.event_time.isoformat(),
            "source_publication_time": stamps.source_publication_time.isoformat(),
            "provider_timestamp": stamps.provider_timestamp.isoformat(),
            "ingestion_receive_time": stamps.ingestion_receive_time.isoformat(),
            "first_usable_time": stamps.first_usable_time.isoformat(),
            "decision_time": _iso(stamps.decision_time),
            "correction_time": _iso(stamps.correction_time),
        },
        "source": {
            "source_id": source.source_id,
            "mode": source.mode.value,
            "true_publication_time": _iso(source.true_publication_time),
        },
    }


def canonical_feature_bytes(feature_set: FeatureSet) -> bytes:
    """Deterministic canonical serialisation; independent of feature construction order."""
    features = [_canonical_feature(f) for f in feature_set.features]
    # Sort by the fully-serialised feature so the ordering is total and order-independent even
    # if two features share a name.
    features.sort(key=lambda f: json.dumps(f, sort_keys=True, ensure_ascii=False))
    return json.dumps(
        {"features": features}, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def feature_set_hash(feature_set: FeatureSet) -> str:
    """sha256 of the canonical bytes — the reproducible feature-set identity (SPEC-024)."""
    return hashlib.sha256(canonical_feature_bytes(feature_set)).hexdigest()


def build_feature(
    name: str,
    value: object,
    stamps: KnowledgeStamps,
    source: SourceProvenance,
    market_off: datetime,
) -> Feature:
    """The single feature-construction path; applies every build-time evidence guard.

    ``value`` is typed ``object`` on purpose: the runtime BSP guard (SPEC-021) exists precisely
    to catch values the static type graph might not, so this path must accept an arbitrary value
    and reject it at runtime. Order matters: refuse a reconciled-BSP value (SPEC-021) first, then
    refuse a feature not provably knowable before the off (SPEC-020/023), then reject any value
    that is not an allowed feature scalar (no float — see module docstring).
    """
    assert_no_bsp(value, field=name)
    assert_knowable_before_off(stamps, market_off, source=source)
    if not (value is None or isinstance(value, (bool, int, Decimal, str))):
        raise TypeError(
            f"feature {name!r}: unsupported value type {type(value).__name__}; "
            "use bool/int/Decimal/str/None (no float)"
        )
    return Feature(name=name, value=value, stamps=stamps, source=source)
