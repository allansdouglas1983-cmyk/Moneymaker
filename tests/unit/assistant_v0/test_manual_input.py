"""STAGE3-0003 §6/§12 — V0 manual market-input contract (red tests first).

Deterministic, immutable manual snapshot for ONE upcoming tennis match. Canonical Betfair
tick validation; exact Decimal prices; malformed/crossed/missing-timestamp/future-timestamp
refuse; no scraping; no credentials. Immutable after construction.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from assistant_v0 import manual_input as MI


def _kw(**over: object) -> dict[str, object]:
    base: dict[str, object] = dict(
        competitor_a="A Player", competitor_b="B Player",
        competitor_a_id=None, competitor_b_id=None,
        tour="ATP", scheduled_start_ms=2000, input_timestamp_ms=1000,
        source="MANUAL_BETFAIR_UI",
        back_a=Decimal("1.90"), back_a_size=Decimal("50"),
        lay_a=Decimal("1.95"), lay_a_size=Decimal("40"),
        back_b=Decimal("2.05"), back_b_size=Decimal("30"),
        lay_b=Decimal("2.12"), lay_b_size=Decimal("20"),
        market_status="OPEN", in_play=False, market_id="1.234", event_id="E1",
    )
    base.update(over)
    return base


def _snap(**over: object) -> MI.ManualMarketSnapshot:
    return MI.ManualMarketSnapshot(**_kw(**over))  # type: ignore[arg-type]


def test_valid_snapshot_constructs() -> None:
    s = _snap()
    assert s.tour == "ATP" and s.source == "MANUAL_BETFAIR_UI"
    assert s.back_a == Decimal("1.90")


def test_snapshot_is_immutable() -> None:
    s = _snap()
    with pytest.raises(Exception):
        s.back_a = Decimal("2.0")  # type: ignore[misc]


def test_bad_source_refuses() -> None:
    with pytest.raises(MI.ManualInputError):
        _snap(source="SCRAPED")


def test_bad_tour_refuses() -> None:
    with pytest.raises(MI.ManualInputError):
        _snap(tour="MIXED")


def test_off_ladder_price_refuses() -> None:
    with pytest.raises(MI.ManualInputError):
        _snap(back_a=Decimal("1.901"))  # not a canonical Betfair tick


def test_float_price_refuses() -> None:
    with pytest.raises(MI.ManualInputError):
        _snap(back_a=1.90)  # float money is refused; Decimal required


def test_negative_size_refuses() -> None:
    with pytest.raises(MI.ManualInputError):
        _snap(back_a_size=Decimal("-1"))


def test_missing_timestamp_refuses() -> None:
    with pytest.raises(MI.ManualInputError):
        _snap(input_timestamp_ms=0)


def test_input_after_scheduled_start_refuses() -> None:
    # no retrospective input after the match begins; input must be pre-match
    with pytest.raises(MI.ManualInputError):
        _snap(input_timestamp_ms=2500, scheduled_start_ms=2000)


def test_unknown_market_status_refuses() -> None:
    with pytest.raises(MI.ManualInputError):
        _snap(market_status="WEIRD")


def test_suspended_and_in_play_are_recordable_valid_snapshots() -> None:
    # recording a suspended / in-play market is allowed; usability is judged downstream
    assert _snap(market_status="SUSPENDED").market_status == "SUSPENDED"
    assert _snap(in_play=True).in_play is True


def test_content_digest_is_deterministic() -> None:
    assert _snap().content_digest() == _snap().content_digest()
    assert _snap(back_a=Decimal("1.91")).content_digest() != _snap().content_digest()
