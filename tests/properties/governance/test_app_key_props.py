"""SPEC-102 property: no Delayed key, whatever its attributes, can authorize real money."""
from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from governance.app_key import (
    DelayedAppKey,
    DelayedKeyRealMoneyError,
    LiveAppKey,
    authorize_real_money_placement,
)

pytestmark = pytest.mark.spec("SPEC-102")


@given(key_id=st.text())
def test_no_delayed_key_authorizes(key_id: str) -> None:
    with pytest.raises(DelayedKeyRealMoneyError):
        authorize_real_money_placement(DelayedAppKey(key_id=key_id))


@given(key_id=st.text(min_size=1))
def test_every_live_key_authorizes(key_id: str) -> None:
    assert authorize_real_money_placement(LiveAppKey(key_id=key_id)).live_key_id == key_id
