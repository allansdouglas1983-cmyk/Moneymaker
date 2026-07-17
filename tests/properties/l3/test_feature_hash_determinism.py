"""SPEC-024: feature-set hashing is deterministic and order-independent over generated sets.

Evidence-criticality does not require a property test, but reproducibility is naturally a
property: the same feature multiset MUST hash identically regardless of construction order,
and any change to a value MUST change the hash.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from l3_features.build_context import LiveBoundaryPolicy, BuildMode, FeatureBuildContext
from l3_features.feature_set import Feature, FeatureSet, build_feature, feature_set_hash
from l3_features.knowledge_time import (
    KnowledgeStamps,
    ProvenanceMode,
    SourceProvenance,
)

pytestmark = pytest.mark.spec("SPEC-024")

OFF = datetime(2026, 7, 15, 13, 0, 0, tzinfo=timezone.utc)

# Mechanical migration for the structural-guard API (2026-07-16 audit): same boundary as the
# old market_off=OFF argument.
CTX = FeatureBuildContext(boundary_policy=LiveBoundaryPolicy.SCHEDULED_START_FLOOR, mode=BuildMode.POST_HOC, scheduled_start=OFF - timedelta(seconds=300), actual_off=OFF)


def _stamps() -> KnowledgeStamps:
    fu = OFF - timedelta(seconds=60)
    return KnowledgeStamps(
        event_time=fu - timedelta(seconds=30),
        source_publication_time=fu - timedelta(seconds=30),
        provider_timestamp=fu - timedelta(seconds=30),
        ingestion_receive_time=fu,
        first_usable_time=fu,
    )


def _source() -> SourceProvenance:
    return SourceProvenance(source_id="s", mode=ProvenanceMode.LIVE_CAPTURED)


def _feat(name: str, cents: int) -> Feature:
    return build_feature(name, Decimal(cents) / Decimal(100), _stamps(), _source(), CTX)


_NAMES = st.text(alphabet="abcdefghijklmnop", min_size=1, max_size=6)
_VALUES = st.integers(min_value=-9999, max_value=9999)


@given(pairs=st.lists(st.tuples(_NAMES, _VALUES), min_size=1, max_size=8, unique_by=lambda p: p[0]))
def test_hash_is_order_independent(pairs: list[tuple[str, int]]) -> None:
    feats = [_feat(n, v) for n, v in pairs]
    forward = FeatureSet(features=tuple(feats))
    backward = FeatureSet(features=tuple(reversed(feats)))
    assert feature_set_hash(forward) == feature_set_hash(backward)


@given(
    pairs=st.lists(st.tuples(_NAMES, _VALUES), min_size=1, max_size=6, unique_by=lambda p: p[0]),
    bump=st.integers(min_value=1, max_value=50),
)
def test_changing_one_value_changes_hash(pairs: list[tuple[str, int]], bump: int) -> None:
    feats = [_feat(n, v) for n, v in pairs]
    base = feature_set_hash(FeatureSet(features=tuple(feats)))
    n0, v0 = pairs[0]
    mutated = [_feat(n0, v0 + bump)] + feats[1:]
    assert feature_set_hash(FeatureSet(features=tuple(mutated))) != base
