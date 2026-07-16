"""SPEC-033 property: ANY differing pair of horizon labels refuses; equal labels never do.

The guard must dominate over every label pair — this is a structural refusal, not a value
computation, so the property is exhaustive refusal/acceptance, not output variation.
"""
from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from l4_pricing.horizon import HorizonLabel, HorizonMismatch, require_horizon_match

pytestmark = pytest.mark.spec("SPEC-033")

_LABEL = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzT0123456789-", min_size=1, max_size=12
).filter(lambda s: s == s.strip())


@given(a=_LABEL, b=_LABEL)
def test_mismatch_refuses_and_match_accepts(a: str, b: str) -> None:
    model_label = HorizonLabel(a)
    request_label = HorizonLabel(b)
    if a == b:
        require_horizon_match(model_label, request_label)
    else:
        with pytest.raises(HorizonMismatch):
            require_horizon_match(model_label, request_label)


@given(a=_LABEL)
def test_label_round_trips_as_text(a: str) -> None:
    assert str(HorizonLabel(a)) == a
