"""Stage-2A properties: the pre-lockbox access guard cannot be made to leak an outcome
field, and its manifest is a deterministic, order-independent function of the safe
accesses (replay-provable). SPEC-092 data-layer completion; SPEC-021 discipline."""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from l8_evidence.outcome_fields import (
    ALL_CLASSIFIED_FIELDS,
    OutcomeFieldAccessError,
    OutcomeFieldClass,
    PreLockboxAccessRecorder,
    classify,
    is_pre_lockbox_safe,
)

pytestmark = [pytest.mark.spec("SPEC-092"), pytest.mark.spec("SPEC-021")]

_SAFE = [f for f in ALL_CLASSIFIED_FIELDS if classify(*f) is OutcomeFieldClass.SAFE_BEFORE_LOCKBOX]
_NONSAFE = [f for f in ALL_CLASSIFIED_FIELDS if classify(*f) is not OutcomeFieldClass.SAFE_BEFORE_LOCKBOX]


@given(accesses=st.lists(st.sampled_from(_SAFE), min_size=0, max_size=40))
@settings(max_examples=200)
def test_recorder_admits_exactly_the_safe_fields(accesses: list) -> None:
    rec = PreLockboxAccessRecorder()
    for lvl, fld in accesses:
        rec.record(lvl, fld)
    manifest = rec.manifest()
    # never any non-safe field; every manifest entry is safe and was requested
    assert all(a.field_class is OutcomeFieldClass.SAFE_BEFORE_LOCKBOX for a in manifest)
    assert {(a.level, a.field) for a in manifest} <= set(accesses)


@given(accesses=st.lists(st.sampled_from(_SAFE), min_size=1, max_size=40))
@settings(max_examples=200)
def test_manifest_digest_is_order_independent(accesses: list) -> None:
    rec_a = PreLockboxAccessRecorder()
    for lvl, fld in accesses:
        rec_a.record(lvl, fld)
    rec_b = PreLockboxAccessRecorder()
    for lvl, fld in reversed(accesses):
        rec_b.record(lvl, fld)
    assert rec_a.content_digest() == rec_b.content_digest()


@given(bad=st.sampled_from(_NONSAFE) if _NONSAFE else st.just(("runner", "status")))
@settings(max_examples=100)
def test_no_non_safe_field_can_ever_be_recorded(bad: tuple) -> None:
    rec = PreLockboxAccessRecorder()
    with pytest.raises(OutcomeFieldAccessError):
        rec.record(*bad)
    assert rec.manifest() == ()
    assert is_pre_lockbox_safe(*bad) is False
