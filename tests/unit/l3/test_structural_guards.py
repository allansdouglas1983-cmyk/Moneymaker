"""SPEC-020/022/023: the leakage guards are structural properties of the ``Feature`` type,
not conventions of one helper function.

2026-07-16 retrospective audit, FINDING-1/2: ``build_feature`` applied the guards but nothing
stopped direct ``Feature(...)`` construction from skipping every one of them, and the explicit
build mode (SPEC-022) was wired to nothing. These tests pin the strengthened contract:
construction requires a ``FeatureBuildContext``, and the knowability boundary comes from that
context (post-hoc: the actual off when known; live: the scheduled start — the only boundary a
live builder may know).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from l3_features.build_context import LiveBoundaryPolicy, BuildMode, FeatureBuildContext
from l3_features.feature_set import Feature, build_feature
from l3_features.knowledge_time import (
    KnowledgeStamps,
    LeakageError,
    ProvenanceMode,
    SourceProvenance,
)

pytestmark = [pytest.mark.spec("SPEC-020"), pytest.mark.spec("SPEC-022"), pytest.mark.spec("SPEC-023")]


def _utc(offset_s: int) -> datetime:
    return datetime(2026, 7, 15, 13, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=offset_s)


OFF = _utc(0)


def _stamps(first_usable: datetime) -> KnowledgeStamps:
    base = first_usable - timedelta(seconds=30)
    return KnowledgeStamps(
        event_time=base,
        source_publication_time=base,
        provider_timestamp=base,
        ingestion_receive_time=first_usable,
        first_usable_time=first_usable,
    )


def _live_source() -> SourceProvenance:
    return SourceProvenance(source_id="ratings-feed", mode=ProvenanceMode.LIVE_CAPTURED)


def _post_hoc_context() -> FeatureBuildContext:
    return FeatureBuildContext(boundary_policy=LiveBoundaryPolicy.SCHEDULED_START_FLOOR, mode=BuildMode.POST_HOC, scheduled_start=_utc(-300), actual_off=OFF)


class TestConstructionIsSealed:
    def test_direct_construction_without_context_is_rejected(self) -> None:
        # Even a perfectly clean feature may not be built outside the guarded path.
        with pytest.raises(LeakageError):
            Feature(
                name="rating",
                value=Decimal("1"),
                stamps=_stamps(_utc(-60)),
                source=_live_source(),
            )

    def test_direct_construction_cannot_smuggle_a_post_off_feature(self) -> None:
        # The audit's demonstrated bypass: first usable five minutes AFTER the off, accepted
        # silently by direct construction. Now rejected regardless of construction path.
        with pytest.raises(LeakageError):
            Feature(
                name="late",
                value=Decimal("1"),
                stamps=_stamps(_utc(300)),
                source=_live_source(),
            )

    def test_model_validate_with_context_still_runs_the_leak_guard(self) -> None:
        # Supplying the context does not waive the guard — it supplies the boundary for it.
        with pytest.raises(LeakageError):
            Feature.model_validate(
                {
                    "name": "late",
                    "value": Decimal("1"),
                    "stamps": _stamps(_utc(60)),
                    "source": _live_source(),
                },
                context={"build_context": _post_hoc_context()},
            )

    def test_backfill_cross_check_is_structural(self) -> None:
        # Backfilled source whose first_usable_time precedes its declared true publication
        # time (SPEC-023) is rejected even via direct context-bearing validation.
        backfilled = SourceProvenance(
            source_id="ratings-archive",
            mode=ProvenanceMode.BACKFILLED,
            true_publication_time=_utc(-10),
        )
        with pytest.raises(LeakageError):
            Feature.model_validate(
                {
                    "name": "rating",
                    "value": Decimal("1"),
                    "stamps": _stamps(_utc(-60)),
                    "source": backfilled,
                },
                context={"build_context": _post_hoc_context()},
            )


class TestBuildFeatureUsesTheContextBoundary:
    def test_post_hoc_boundary_is_actual_off(self) -> None:
        ctx = _post_hoc_context()
        ok = build_feature("rating", Decimal("1"), _stamps(_utc(-60)), _live_source(), ctx)
        assert ok.value == Decimal("1")
        with pytest.raises(LeakageError):
            build_feature("late", Decimal("1"), _stamps(_utc(60)), _live_source(), ctx)

    def test_post_hoc_without_actual_off_falls_back_to_scheduled_start(self) -> None:
        ctx = FeatureBuildContext(boundary_policy=LiveBoundaryPolicy.SCHEDULED_START_FLOOR, mode=BuildMode.POST_HOC, scheduled_start=OFF)
        with pytest.raises(LeakageError):
            build_feature("late", Decimal("1"), _stamps(_utc(60)), _live_source(), ctx)

    def test_live_boundary_is_scheduled_start(self) -> None:
        # SPEC-022: a live builder knows only the scheduled start; the mode is explicit and
        # the boundary follows from it.
        ctx = FeatureBuildContext(boundary_policy=LiveBoundaryPolicy.SCHEDULED_START_FLOOR, mode=BuildMode.LIVE, scheduled_start=OFF)
        ok = build_feature("early", Decimal("1"), _stamps(_utc(-60)), _live_source(), ctx)
        assert ok.name == "early"
        with pytest.raises(LeakageError):
            build_feature("late", Decimal("1"), _stamps(_utc(60)), _live_source(), ctx)

    def test_float_value_is_rejected(self) -> None:
        # FINDING-4: the no-float path previously had no covering test.
        with pytest.raises(TypeError):
            build_feature("bad", 3.14, _stamps(_utc(-60)), _live_source(), _post_hoc_context())
