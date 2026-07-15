"""Reducer versioning & registry (SPEC-012)."""
from __future__ import annotations

import json

import pytest

from l1_reduce import reducer as red
from l1_reduce.mcm_v1 import REDUCER_VERSION

pytestmark = pytest.mark.spec("SPEC-012")


def _event() -> bytes:
    return json.dumps({"op": "mcm", "pt": 1, "mc": [{"id": "1.1", "img": True, "rc": [{"id": 111, "ltp": 2.0}]}]}).encode(
        "utf-8"
    )


def test_known_version_is_registered() -> None:
    assert REDUCER_VERSION in red.available_versions()


def test_unknown_version_is_refused() -> None:
    with pytest.raises(red.UnknownReducerVersion):
        red.reduce([_event()], "reducer-does-not-exist")


def test_result_records_version_and_digests() -> None:
    result = red.reduce([_event()], REDUCER_VERSION)
    assert result.reducer_version == REDUCER_VERSION
    assert result.reducer_digest  # immutable logic-identity string, recorded with the artefact
    assert result.raw_events_digest  # digest of the L0 inputs
    assert result.canonical_hash


def test_reducer_version_string_is_stable() -> None:
    # The version string is an immutable identifier, not a moving target.
    assert REDUCER_VERSION == "reducer-mcm-v1"
