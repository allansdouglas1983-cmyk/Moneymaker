"""SPEC-102: real-money placement is impossible on a Delayed App Key."""
from __future__ import annotations

import dataclasses

import pytest

from governance.app_key import (
    DelayedAppKey,
    DelayedKeyRealMoneyError,
    LiveAppKey,
    RealMoneyPlacementAuthorization,
    authorize_real_money_placement,
)

pytestmark = pytest.mark.spec("SPEC-102")


def test_live_key_authorizes() -> None:
    auth = authorize_real_money_placement(LiveAppKey(key_id="live-1"))
    assert isinstance(auth, RealMoneyPlacementAuthorization)
    assert auth.live_key_id == "live-1"


def test_delayed_key_is_refused() -> None:
    with pytest.raises(DelayedKeyRealMoneyError):
        authorize_real_money_placement(DelayedAppKey(key_id="delayed-1"))


def test_direct_construction_from_delayed_key_is_refused() -> None:
    # Runtime backstop: the type barrier is also enforced at construction, not only by mypy.
    with pytest.raises(DelayedKeyRealMoneyError):
        RealMoneyPlacementAuthorization(live_key=DelayedAppKey(key_id="d"))  # type: ignore[arg-type]


def test_replace_with_delayed_key_is_refused() -> None:
    auth = authorize_real_money_placement(LiveAppKey(key_id="live"))
    with pytest.raises(DelayedKeyRealMoneyError):
        dataclasses.replace(auth, live_key=DelayedAppKey(key_id="d"))  # type: ignore[arg-type]
