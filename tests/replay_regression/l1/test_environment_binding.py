"""SPEC-011 / SPECIFICATION.md §6.2: the four reproducibility digests are recorded.

§6.2: identical raw_manifest_digest + reducer_digest + config_digest + container_digest MUST
produce the same canonical output hash. 2026-07-16 retrospective audit: config_digest and
container_digest existed nowhere, so environment drift and logic regression were
indistinguishable. Every reduction now records all four, and same-environment stability is
asserted here; the digests are provenance metadata and MUST NOT enter the canonical bytes
(the golden replay hashes are pinned separately and must not move).
"""
from __future__ import annotations

import pytest

from l1_reduce.reducer import reduce

pytestmark = pytest.mark.spec("SPEC-011")

_EVENT = b'{"op":"mcm","pt":1752584400000,"mc":[]}'


def test_reduction_records_all_four_digests() -> None:
    result = reduce([_EVENT], "reducer-mcm-v1")
    assert result.reducer_digest
    assert result.raw_events_digest
    assert result.config_digest
    assert result.container_digest


def test_digests_and_hash_are_stable_within_one_environment() -> None:
    a = reduce([_EVENT], "reducer-mcm-v1")
    b = reduce([_EVENT], "reducer-mcm-v1")
    assert a.config_digest == b.config_digest
    assert a.container_digest == b.container_digest
    assert a.raw_events_digest == b.raw_events_digest
    assert a.canonical_hash == b.canonical_hash


def test_digests_do_not_enter_canonical_bytes() -> None:
    # The canonical payload identifies derived STATE; provenance digests ride alongside.
    # (If digests leaked into canonical_bytes, every environment change would silently move
    # the golden replay hashes.)
    result = reduce([_EVENT], "reducer-mcm-v1")
    assert result.container_digest.encode("ascii") not in result.canonical_bytes
    assert result.config_digest.encode("ascii") not in result.canonical_bytes
