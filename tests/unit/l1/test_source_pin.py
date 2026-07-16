"""SPEC-012: changing reducer logic REQUIRES a version bump — mechanically enforced.

2026-07-16 retrospective audit: the requirement previously rested on developer discipline plus
two golden fixtures, which only trip when a change happens to alter those fixtures' output.
This pin turns ANY source change to the reducer into a failing test, forcing the change
through a conscious, reviewed decision: bump the reducer version (registering a new one and
keeping the old runnable), or explicitly re-pin here with rationale in the same commit.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from l1_reduce import mcm_v1

pytestmark = pytest.mark.spec("SPEC-012")

# sha256 of l1_reduce/mcm_v1.py exactly as reviewed for reducer-mcm-v1.
_PINNED_MCM_V1_SOURCE_SHA256 = "b032d9d9910918b1e82212cc65cbbc28ef9cc25561a75cfa25e63af9909becb1"


def test_reducer_source_change_requires_a_version_bump() -> None:
    source = Path(mcm_v1.__file__).read_bytes()
    assert hashlib.sha256(source).hexdigest() == _PINNED_MCM_V1_SOURCE_SHA256, (
        "l1_reduce/mcm_v1.py has changed. Changing reducer logic REQUIRES a version bump "
        "(SPEC-012): register a new reducer version (keep reducer-mcm-v1 runnable for replay), "
        "update the golden replay hashes if canonical output changed, and re-pin this hash in "
        "the same reviewed commit."
    )


def test_pinned_version_is_v1() -> None:
    assert mcm_v1.REDUCER_VERSION == "reducer-mcm-v1"
