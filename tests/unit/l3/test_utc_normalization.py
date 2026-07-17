"""SPEC-024: equal instants hash identically regardless of UTC-offset representation.

2026-07-16 retrospective audit, FINDING-3: timestamps were checked for tz-awareness but not
normalised to UTC, so the same instant written as ``13:00+00:00`` and ``14:00+01:00`` produced
two different feature-set hashes. The type rule is "Timestamps: UTC" — aware datetimes are
normalised to UTC at the model boundary; naive datetimes remain rejected.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from l3_features.build_context import LiveBoundaryPolicy, BuildMode, FeatureBuildContext
from l3_features.feature_set import FeatureSet, build_feature, feature_set_hash
from l3_features.knowledge_time import (
    KnowledgeStamps,
    LeakageError,
    ProvenanceMode,
    SourceProvenance,
)

pytestmark = [pytest.mark.spec("SPEC-020"), pytest.mark.spec("SPEC-024")]

_CET = timezone(timedelta(hours=1))


def _utc(offset_s: int) -> datetime:
    return datetime(2026, 7, 15, 13, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=offset_s)


OFF = _utc(0)


def _stamps_in(tz: timezone) -> KnowledgeStamps:
    base = _utc(-90).astimezone(tz)
    usable = _utc(-60).astimezone(tz)
    return KnowledgeStamps(
        event_time=base,
        source_publication_time=base,
        provider_timestamp=base,
        ingestion_receive_time=usable,
        first_usable_time=usable,
    )


def _source() -> SourceProvenance:
    return SourceProvenance(source_id="ratings-feed", mode=ProvenanceMode.LIVE_CAPTURED)


def _ctx() -> FeatureBuildContext:
    return FeatureBuildContext(boundary_policy=LiveBoundaryPolicy.SCHEDULED_START_FLOOR, mode=BuildMode.POST_HOC, scheduled_start=_utc(-300), actual_off=OFF)


def test_equal_instants_hash_identically_across_offsets() -> None:
    # The audit's demonstrated divergence: same instants, +00:00 vs +01:00 representation.
    f_utc = build_feature("rating", Decimal("1"), _stamps_in(timezone.utc), _source(), _ctx())
    f_cet = build_feature("rating", Decimal("1"), _stamps_in(_CET), _source(), _ctx())
    assert feature_set_hash(FeatureSet(features=(f_utc,))) == feature_set_hash(
        FeatureSet(features=(f_cet,))
    )


def test_stamps_are_stored_in_utc() -> None:
    stamps = _stamps_in(_CET)
    assert stamps.event_time.utcoffset() == timedelta(0)
    assert stamps.first_usable_time.utcoffset() == timedelta(0)
    assert stamps.event_time == _utc(-90)  # same instant, UTC representation


def test_source_publication_time_is_stored_in_utc() -> None:
    src = SourceProvenance(
        source_id="ratings-archive",
        mode=ProvenanceMode.BACKFILLED,
        true_publication_time=_utc(-120).astimezone(_CET),
    )
    assert src.true_publication_time is not None
    assert src.true_publication_time.utcoffset() == timedelta(0)


def test_build_context_times_are_stored_in_utc() -> None:
    ctx = FeatureBuildContext(boundary_policy=LiveBoundaryPolicy.SCHEDULED_START_FLOOR, 
        mode=BuildMode.POST_HOC,
        scheduled_start=_utc(-300).astimezone(_CET),
        actual_off=OFF.astimezone(_CET),
    )
    assert ctx.scheduled_start is not None
    assert ctx.scheduled_start.utcoffset() == timedelta(0)
    assert ctx.actual_off is not None
    assert ctx.actual_off.utcoffset() == timedelta(0)


def test_naive_datetimes_remain_rejected() -> None:
    naive = datetime(2026, 7, 15, 12, 59, 0)
    with pytest.raises(LeakageError):
        KnowledgeStamps(
            event_time=naive,
            source_publication_time=naive,
            provider_timestamp=naive,
            ingestion_receive_time=naive,
            first_usable_time=naive,
        )
    with pytest.raises(ValueError):
        FeatureBuildContext(boundary_policy=LiveBoundaryPolicy.SCHEDULED_START_FLOOR, mode=BuildMode.POST_HOC, scheduled_start=naive)
