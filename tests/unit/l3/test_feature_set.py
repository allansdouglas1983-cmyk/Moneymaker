"""Feature-set hash reproducibility and build-time guard integration (SPEC-024).

Feature builds are deterministic and identified by ``feature_set_hash``. Same inputs + same
hash MUST produce identical features. ``build_feature`` composes the SPEC-020/021/023 guards.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from l3_features.build_context import BuildMode, FeatureBuildContext
from l3_features.feature_set import (
    Feature,
    FeatureSet,
    build_feature,
    canonical_feature_bytes,
    feature_set_hash,
)
from l3_features.knowledge_time import (
    KnowledgeStamps,
    ProvenanceMode,
    SourceProvenance,
)
from l3_features.leakage import BSPLeakageError
from l8_evidence.reconciled_bsp import ReconciledBSP

pytestmark = pytest.mark.spec("SPEC-024")


def _utc(offset_s: int) -> datetime:
    return datetime(2026, 7, 15, 13, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=offset_s)


OFF = _utc(0)

# Mechanical migration for the structural-guard API (2026-07-16 audit): build_feature now takes
# the explicit build context; the boundary (actual_off=OFF) is identical to the old market_off.
CTX = FeatureBuildContext(mode=BuildMode.POST_HOC, scheduled_start=_utc(-300), actual_off=OFF)


def _stamps(first_usable: datetime) -> KnowledgeStamps:
    base = first_usable - timedelta(seconds=30)
    return KnowledgeStamps(
        event_time=base,
        source_publication_time=base,
        provider_timestamp=base,
        ingestion_receive_time=first_usable,
        first_usable_time=first_usable,
    )


def _source() -> SourceProvenance:
    return SourceProvenance(source_id="ratings-feed", mode=ProvenanceMode.LIVE_CAPTURED)


def _feature(name: str, value: object) -> Feature:
    return build_feature(
        name=name,
        value=value,
        stamps=_stamps(_utc(-60)),
        source=_source(),
        context=CTX,
    )


class TestReproducibility:
    def test_same_inputs_same_hash(self) -> None:
        fs1 = FeatureSet(features=(_feature("rating", Decimal("12.5")), _feature("draw", 3)))
        fs2 = FeatureSet(features=(_feature("rating", Decimal("12.5")), _feature("draw", 3)))
        assert feature_set_hash(fs1) == feature_set_hash(fs2)
        assert canonical_feature_bytes(fs1) == canonical_feature_bytes(fs2)

    def test_hash_independent_of_feature_order(self) -> None:
        a = _feature("rating", Decimal("12.5"))
        b = _feature("draw", 3)
        assert feature_set_hash(FeatureSet(features=(a, b))) == feature_set_hash(
            FeatureSet(features=(b, a))
        )

    def test_different_value_changes_hash(self) -> None:
        fs1 = FeatureSet(features=(_feature("rating", Decimal("12.5")),))
        fs2 = FeatureSet(features=(_feature("rating", Decimal("12.6")),))
        assert feature_set_hash(fs1) != feature_set_hash(fs2)

    def test_different_first_usable_time_changes_hash(self) -> None:
        f1 = build_feature("rating", Decimal("1"), _stamps(_utc(-60)), _source(), CTX)
        f2 = build_feature("rating", Decimal("1"), _stamps(_utc(-90)), _source(), CTX)
        assert feature_set_hash(FeatureSet(features=(f1,))) != feature_set_hash(
            FeatureSet(features=(f2,))
        )

    def test_decimal_value_hash_ignores_trailing_zero_representation(self) -> None:
        # Decimal("12.5") and Decimal("12.50") are equal numbers; canonical form must agree.
        fs1 = FeatureSet(features=(_feature("rating", Decimal("12.5")),))
        fs2 = FeatureSet(features=(_feature("rating", Decimal("12.50")),))
        assert feature_set_hash(fs1) == feature_set_hash(fs2)

    def test_signed_zero_hashes_identically(self) -> None:
        fs_pos = FeatureSet(features=(_feature("bias", Decimal("0")),))
        fs_neg = FeatureSet(features=(_feature("bias", Decimal("-0")),))
        assert feature_set_hash(fs_pos) == feature_set_hash(fs_neg)

    def test_hash_order_independent_with_duplicate_names(self) -> None:
        # Two features share a name but differ in value; the total-order sort must make the set
        # hash order-independent even then (the collision-handling path).
        a = _feature("rating", Decimal("1"))
        b = _feature("rating", Decimal("2"))
        assert feature_set_hash(FeatureSet(features=(a, b))) == feature_set_hash(
            FeatureSet(features=(b, a))
        )


class TestBuildGuards:
    def test_build_rejects_reconciled_bsp_value(self) -> None:
        with pytest.raises(BSPLeakageError):
            build_feature(
                "fav_bsp",
                ReconciledBSP(selection_id=111, bsp=Decimal("4.2")),
                _stamps(_utc(-60)),
                _source(),
                CTX,
            )

    def test_build_rejects_unknowable_feature(self) -> None:
        from l3_features.knowledge_time import LeakageError

        with pytest.raises(LeakageError):
            build_feature("late", Decimal("1"), _stamps(_utc(60)), _source(), CTX)

    def test_build_mode_enum_available(self) -> None:
        # POST_HOC vs LIVE both exist and are distinct (used by callers building features).
        assert {BuildMode.LIVE, BuildMode.POST_HOC} <= set(BuildMode)
        assert len({BuildMode.LIVE, BuildMode.POST_HOC}) == 2

    def test_feature_is_frozen(self) -> None:
        f = _feature("rating", Decimal("1"))
        with pytest.raises((ValueError, TypeError)):
            f.name = "other"
