"""Knowledge-time semantics and backfill provenance (SPEC-020, SPEC-023).

SPEC-020: a feature whose first-usable-time is not provably before the market off MUST be
rejected at build time with an *error*, not a warning.
SPEC-023: a backfilled source MUST declare its true publication time, and a backfill
first-seen timestamp MUST NOT confer earlier knowability than that publication time.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from l3_features.knowledge_time import (
    KnowledgeStamps,
    LeakageError,
    ProvenanceMode,
    SourceProvenance,
    assert_knowable_before_off,
)

pytestmark = pytest.mark.spec("SPEC-020")


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


class TestKnowableBeforeOff:
    def test_first_usable_strictly_before_off_is_accepted(self) -> None:
        assert_knowable_before_off(_stamps(_utc(-60)), OFF, source=_live_source())

    def test_first_usable_after_off_is_rejected(self) -> None:
        with pytest.raises(LeakageError):
            assert_knowable_before_off(_stamps(_utc(60)), OFF, source=_live_source())

    def test_first_usable_exactly_at_off_is_rejected(self) -> None:
        # "provably BEFORE" is strict — equality is not before.
        with pytest.raises(LeakageError):
            assert_knowable_before_off(_stamps(OFF), OFF, source=_live_source())

    def test_naive_off_boundary_is_rejected(self) -> None:
        naive_off = datetime(2026, 7, 15, 13, 0, 0)  # no tzinfo
        with pytest.raises(LeakageError):
            assert_knowable_before_off(_stamps(_utc(-60)), naive_off, source=_live_source())

    def test_rejection_is_error_not_warning(self, recwarn: pytest.WarningsRecorder) -> None:
        with pytest.raises(LeakageError):
            assert_knowable_before_off(_stamps(_utc(60)), OFF, source=_live_source())
        assert len(recwarn) == 0


class TestStampValidation:
    def test_naive_stamp_is_rejected(self) -> None:
        with pytest.raises((ValueError, LeakageError)):
            KnowledgeStamps(
                event_time=datetime(2026, 7, 15, 12, 0, 0),  # naive
                source_publication_time=_utc(-60),
                provider_timestamp=_utc(-60),
                ingestion_receive_time=_utc(-60),
                first_usable_time=_utc(-60),
            )

    def test_optional_decision_and_correction_default_none(self) -> None:
        s = _stamps(_utc(-60))
        assert s.decision_time is None
        assert s.correction_time is None

    def test_stamps_are_frozen(self) -> None:
        s = _stamps(_utc(-60))
        with pytest.raises((ValueError, TypeError)):
            s.first_usable_time = _utc(-10)

    def test_first_usable_before_ingestion_is_rejected(self) -> None:
        # A value cannot be usable before it was received — that is an unprovable claim.
        with pytest.raises(LeakageError):
            KnowledgeStamps(
                event_time=_utc(-120),
                source_publication_time=_utc(-120),
                provider_timestamp=_utc(-120),
                ingestion_receive_time=_utc(-60),
                first_usable_time=_utc(-90),  # earlier than ingestion
            )

    def test_first_usable_before_publication_is_rejected(self) -> None:
        # A value cannot be knowable before its provider published it.
        with pytest.raises(LeakageError):
            KnowledgeStamps(
                event_time=_utc(-120),
                source_publication_time=_utc(-60),
                provider_timestamp=_utc(-120),
                ingestion_receive_time=_utc(-90),
                first_usable_time=_utc(-90),  # earlier than publication (-60)
            )


@pytest.mark.spec("SPEC-023")
class TestBackfillProvenance:
    def test_backfilled_source_must_declare_true_publication_time(self) -> None:
        with pytest.raises(LeakageError):
            SourceProvenance(source_id="retro-ratings", mode=ProvenanceMode.BACKFILLED)

    def test_backfilled_source_with_publication_time_is_valid(self) -> None:
        src = SourceProvenance(
            source_id="retro-ratings",
            mode=ProvenanceMode.BACKFILLED,
            true_publication_time=_utc(-120),
        )
        assert src.true_publication_time == _utc(-120)

    def test_live_source_needs_no_publication_time(self) -> None:
        assert _live_source().true_publication_time is None

    def test_backfill_cannot_claim_knowability_before_true_publication(self) -> None:
        # first_usable_time earlier than the true publication time is a leakage claim:
        # backfill populating first_seen_ts does not make it knowable then (SPEC-023).
        src = SourceProvenance(
            source_id="retro-ratings",
            mode=ProvenanceMode.BACKFILLED,
            true_publication_time=_utc(-30),
        )
        with pytest.raises(LeakageError):
            assert_knowable_before_off(_stamps(_utc(-120)), OFF, source=src)

    def test_backfill_published_after_off_is_rejected(self) -> None:
        # A ratings file published after the race is never a pre-off feature.
        src = SourceProvenance(
            source_id="retro-ratings",
            mode=ProvenanceMode.BACKFILLED,
            true_publication_time=_utc(120),
        )
        with pytest.raises(LeakageError):
            assert_knowable_before_off(_stamps(_utc(130)), OFF, source=src)

    def test_backfill_published_before_off_and_consistent_is_accepted(self) -> None:
        src = SourceProvenance(
            source_id="retro-ratings",
            mode=ProvenanceMode.BACKFILLED,
            true_publication_time=_utc(-120),
        )
        assert_knowable_before_off(_stamps(_utc(-90)), OFF, source=src)
