"""Feature-set assembly and reproducible hashing (SPEC-024).

Feature builds are deterministic and identified by a ``feature_set_hash``: the same inputs
produce byte-identical canonical features and therefore the same hash (SPEC-024). The evidence
guards are **structural properties of the ``Feature`` type**, not conventions of a helper:
construction requires a :class:`~l3_features.build_context.FeatureBuildContext` supplied via
pydantic validation context, and the type re-runs the guards itself —

  * SPEC-020/023 — reject a feature not provably knowable before the context's boundary;
  * SPEC-022 — the boundary derives from the *explicit* build mode (live: scheduled start);
  * SPEC-021 — a reconciled-BSP value is rejected (``build_feature`` runtime assertion, plus
    the strict value-type union which no BSP object satisfies).

``build_feature`` remains the ergonomic path; direct ``Feature(...)`` construction without a
context raises :class:`~l3_features.knowledge_time.LeakageError`. (``model_construct``/
``model_copy`` are pydantic's documented no-validation escape hatches and remain out of scope,
as with every validator in this codebase.)

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

from pydantic import BaseModel, ConfigDict, ValidationInfo, model_validator

from l3_features.build_context import FeatureBuildContext
from l3_features.knowledge_time import (
    KnowledgeStamps,
    LeakageError,
    SourceProvenance,
    assert_knowable_before_off,
)
from l3_features.leakage import assert_no_bsp

FeatureValue = bool | int | Decimal | str | None


class Feature(BaseModel):
    """One knowledge-time-stamped feature value with its source provenance.

    The build-time leakage guards run inside validation, so they hold on *every* validating
    construction path — ``Feature(...)``, ``model_validate``, deserialisation — not only on
    ``build_feature``. A construction attempt without a build context is itself a leakage
    error: there is no unguarded way to mint a Feature.
    """

    # strict: never coerce across value types, so a float is rejected rather than silently
    # turned into a Decimal (which would defeat the no-float canonicalisation guarantee).
    model_config = ConfigDict(frozen=True, strict=True)

    name: str
    value: FeatureValue
    stamps: KnowledgeStamps
    source: SourceProvenance

    @model_validator(mode="before")
    @classmethod
    def _structural_guards(cls, data: Any, info: ValidationInfo) -> Any:
        # A frozen, already-guarded instance passes through: pydantic (2.13, strict mode)
        # re-validates nested model instances during e.g. FeatureSet assembly, and a Feature
        # can only exist because a guarded mint accepted it — its fields are frozen since.
        if isinstance(data, Feature):
            return data
        # Fresh mint from raw data: the build context is mandatory. LeakageError is not a
        # ValueError, so it propagates unwrapped (SPEC-020: an error, never a warning).
        context = info.context if isinstance(info.context, dict) else None
        build_context = context.get("build_context") if context is not None else None
        if not isinstance(build_context, FeatureBuildContext):
            name = data.get("name") if isinstance(data, dict) else None
            raise LeakageError(
                f"feature {name!r} constructed without a FeatureBuildContext; use "
                "build_feature(...) — the leakage guards are structural (SPEC-020/022/023)"
            )
        if isinstance(data, dict):
            raw_stamps = data.get("stamps")
            raw_source = data.get("source")
            stamps = (
                raw_stamps
                if isinstance(raw_stamps, KnowledgeStamps)
                else KnowledgeStamps.model_validate(raw_stamps)
            )
            source = (
                raw_source
                if isinstance(raw_source, SourceProvenance)
                else SourceProvenance.model_validate(raw_source)
            )
            assert_knowable_before_off(
                stamps, build_context.knowability_boundary, source=source
            )
        return data


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
    context: FeatureBuildContext,
) -> Feature:
    """The ergonomic feature-construction path (SPEC-020/021/022/023).

    ``value`` is typed ``object`` on purpose: the runtime BSP guard (SPEC-021) exists precisely
    to catch values the static type graph might not, so this path must accept an arbitrary value
    and reject it at runtime. Order: refuse a reconciled-BSP value (SPEC-021) first, then reject
    any value that is not an allowed feature scalar (no float — see module docstring), then let
    the ``Feature`` validator itself enforce knowability against the context's boundary
    (SPEC-020/022/023) — the guard the type also enforces on direct construction.
    """
    assert_no_bsp(value, field=name)
    if not (value is None or isinstance(value, (bool, int, Decimal, str))):
        raise TypeError(
            f"feature {name!r}: unsupported value type {type(value).__name__}; "
            "use bool/int/Decimal/str/None (no float)"
        )
    return Feature.model_validate(
        {"name": name, "value": value, "stamps": stamps, "source": source},
        context={"build_context": context},
    )
