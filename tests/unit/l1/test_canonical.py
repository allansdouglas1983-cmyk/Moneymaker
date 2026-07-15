"""Canonical serialisation determinism (SPEC-010 determinism, SPEC-011 canonical hash)."""
from __future__ import annotations

import json
from decimal import Decimal

import pytest

from l1_reduce.canonical import canonical_bytes, canonical_decimal, canonical_hash
from l1_reduce.mcm_v1 import REDUCER_VERSION
from l1_reduce.reducer import reduce

pytestmark = [pytest.mark.spec("SPEC-010"), pytest.mark.spec("SPEC-011")]


def _mcm(pt: int, mcs: list[dict[str, object]]) -> bytes:
    return json.dumps({"op": "mcm", "pt": pt, "mc": mcs}).encode("utf-8")


def test_canonical_decimal_has_no_scientific_notation() -> None:
    assert canonical_decimal(Decimal("3.45")) == "3.45"
    assert canonical_decimal(Decimal("100")) == "100"
    assert canonical_decimal(Decimal("0.10")) == "0.10"
    assert "E" not in canonical_decimal(Decimal("1000000000000"))


def test_canonical_bytes_are_deterministic() -> None:
    ev = _mcm(1000, [{"id": "1.1", "img": True, "rc": [{"id": 111, "batb": [[1, 3.5, 20], [0, 3.45, 10]]}]}])
    a = reduce([ev], REDUCER_VERSION).state
    b = reduce([ev], REDUCER_VERSION).state
    assert canonical_bytes(a) == canonical_bytes(b)
    assert canonical_hash(a) == canonical_hash(b)


def test_ladder_hash_independent_of_input_level_order() -> None:
    ev1 = _mcm(1000, [{"id": "1.1", "img": True, "rc": [{"id": 111, "batb": [[0, 3.45, 10], [1, 3.5, 20]]}]}])
    ev2 = _mcm(1000, [{"id": "1.1", "img": True, "rc": [{"id": 111, "batb": [[1, 3.5, 20], [0, 3.45, 10]]}]}])
    assert canonical_hash(reduce([ev1], REDUCER_VERSION).state) == canonical_hash(reduce([ev2], REDUCER_VERSION).state)
