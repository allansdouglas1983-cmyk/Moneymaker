"""Reading Betfair Historical BASIC files.

BASIC is ``EX_LTP`` + ``EX_MARKET_DEF`` at one-minute intervals, and ``ltp`` is sent only
when it *changes* — so a naive reader that expects a price in every message silently
produces gaps. These tests pin that behaviour along with the two guards that matter more
than convenience: in-play observations are unreachable (hard prohibition, pre-off only), and
BSP is a settlement-time closing benchmark that must never be reachable from a pre-event
feature (SPEC-021).
"""
from __future__ import annotations

import bz2
import io
import json
import tarfile
import datetime as dt
from decimal import Decimal
from pathlib import Path

import pytest

from tennis_edge.betfair import (
    BspQuarantineError,
    InPlayRefusedError,
    MarketHistory,
    read_markets,
)

MARKET_ID = "1.198765432"
#: The scheduled off, as both an ISO string in the definition and epoch ms in the fixture.
#: These MUST be the same instant — the reader computes horizons from marketTime, so a
#: fixture where they disagree tests nothing it claims to.
OFF_ISO = "2025-06-15T14:00:00.000Z"
OFF_MS = int(dt.datetime.fromisoformat(OFF_ISO.replace("Z", "+00:00")).timestamp() * 1000)
A, B = 111, 222


def _definition(*, in_play: bool = False, status: str = "OPEN",
                bsp_reconciled: bool = False,
                runner_status: tuple[str, str] = ("ACTIVE", "ACTIVE")) -> dict:
    return {
        "marketTime": OFF_ISO,
        "marketType": "MATCH_ODDS",
        "eventName": "Alcaraz v Sinner",
        "eventId": "34567",
        "countryCode": "GB",
        "status": status,
        "inPlay": in_play,
        "bspReconciled": bsp_reconciled,
        "runners": [
            {"id": A, "name": "Carlos Alcaraz", "status": runner_status[0], "sortPriority": 1},
            {"id": B, "name": "Jannik Sinner", "status": runner_status[1], "sortPriority": 2},
        ],
    }


def _msg(pt: int, *, definition: dict | None = None,
         ltps: dict[int, float] | None = None) -> str:
    change: dict = {"id": MARKET_ID}
    if definition is not None:
        change["marketDefinition"] = definition
    if ltps:
        change["rc"] = [{"id": sid, "ltp": v} for sid, v in ltps.items()]
    return json.dumps({"op": "mcm", "clk": "AAA", "pt": pt, "mc": [change]})


def _write_jsonl(path: Path, lines: list[str]) -> Path:
    path.write_text("\n".join(lines) + "\n")
    return path


def _stream(minutes_before: list[int], prices: list[float]) -> list[str]:
    out = [_msg(OFF_MS - 3_600_000, definition=_definition())]
    for m, p in zip(minutes_before, prices):
        out.append(_msg(OFF_MS - m * 60_000, ltps={A: p, B: round(1 / (1 - 1 / p), 2)}))
    return out


# ------------------------------------------------------------------ container formats


def test_a_plain_jsonl_file_is_read(tmp_path: Path) -> None:
    path = _write_jsonl(tmp_path / "m.jsonl", _stream([30, 10], [2.0, 2.2]))
    (history,) = read_markets(path)
    assert history.market_id == MARKET_ID
    assert len(history.observations) == 4


def test_a_bz2_file_is_read(tmp_path: Path) -> None:
    path = tmp_path / "m.bz2"
    path.write_bytes(bz2.compress(("\n".join(_stream([30], [2.0])) + "\n").encode()))
    (history,) = read_markets(path)
    assert history.market_id == MARKET_ID


def test_a_tar_of_bz2_members_is_read(tmp_path: Path) -> None:
    """The shape Betfair actually ships: a .tar holding one .bz2 per market."""
    path = tmp_path / "bundle.tar"
    payload = bz2.compress(("\n".join(_stream([30], [2.0])) + "\n").encode())
    with tarfile.open(path, "w") as tar:
        info = tarfile.TarInfo("BASIC/2025/Jun/15/34567/1.198765432.bz2")
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
    (history,) = read_markets(path)
    assert history.market_id == MARKET_ID


def test_a_directory_is_walked(tmp_path: Path) -> None:
    root = tmp_path / "d"
    (root / "nested").mkdir(parents=True)
    _write_jsonl(root / "nested" / "m.jsonl", _stream([30], [2.0]))
    assert len(read_markets(root)) == 1


# ------------------------------------------------------------------ BASIC semantics


def test_the_definition_is_parsed(tmp_path: Path) -> None:
    path = _write_jsonl(tmp_path / "m.jsonl", _stream([30], [2.0]))
    (history,) = read_markets(path)
    assert history.market_type == "MATCH_ODDS"
    assert history.event_name == "Alcaraz v Sinner"
    assert [r.name for r in history.runners] == ["Carlos Alcaraz", "Jannik Sinner"]


def test_a_price_carries_forward_because_ltp_is_only_sent_on_change(tmp_path: Path) -> None:
    """The single most important BASIC quirk. A reader that does not carry the last price
    forward reports "no price" at horizons where the price simply had not moved."""
    path = _write_jsonl(tmp_path / "m.jsonl", _stream([30, 5], [2.0, 2.5]))
    (history,) = read_markets(path)
    assert history.ltp_at(A, seconds_before_off=1200) == Decimal("2.0")   # T-20m: unchanged
    assert history.ltp_at(A, seconds_before_off=60) == Decimal("2.5")     # T-1m: moved


def test_no_price_before_the_first_trade_is_none_not_a_guess(tmp_path: Path) -> None:
    path = _write_jsonl(tmp_path / "m.jsonl", _stream([10], [2.0]))
    (history,) = read_markets(path)
    assert history.ltp_at(A, seconds_before_off=1800) is None


def test_prices_land_on_the_canonical_ladder(tmp_path: Path) -> None:
    path = _write_jsonl(tmp_path / "m.jsonl", _stream([30], [2.0]))
    (history,) = read_markets(path)
    price = history.ltp_at(A, seconds_before_off=600)
    assert price is not None
    assert history.tick_at(A, seconds_before_off=600) is not None
    assert isinstance(price, Decimal), "prices are never floats (SPEC-053)"


def test_an_off_ladder_price_is_refused(tmp_path: Path) -> None:
    path = _write_jsonl(tmp_path / "m.jsonl", [
        _msg(OFF_MS - 3_600_000, definition=_definition()),
        _msg(OFF_MS - 600_000, ltps={A: 2.03}),      # not a valid Betfair tick
    ])
    with pytest.raises(ValueError, match="off-ladder"):
        read_markets(path)


# ------------------------------------------------------------------ pre-off only


def test_in_play_observations_are_dropped(tmp_path: Path) -> None:
    """Hard prohibition: pre-off only, every sport. In-play data is not merely unused —
    it must not be reachable."""
    path = _write_jsonl(tmp_path / "m.jsonl", [
        _msg(OFF_MS - 600_000, definition=_definition()),
        _msg(OFF_MS - 300_000, ltps={A: 2.0}),
        _msg(OFF_MS + 60_000, definition=_definition(in_play=True)),
        _msg(OFF_MS + 120_000, ltps={A: 8.0}),        # in-play: must never appear
    ])
    (history,) = read_markets(path)
    assert all(o.publish_time_ms <= OFF_MS for o in history.observations)
    assert Decimal("8.0") not in [o.price for o in history.observations]
    assert history.went_in_play is True


def test_asking_for_a_price_after_the_off_is_refused(tmp_path: Path) -> None:
    path = _write_jsonl(tmp_path / "m.jsonl", _stream([30], [2.0]))
    (history,) = read_markets(path)
    with pytest.raises(InPlayRefusedError):
        history.ltp_at(A, seconds_before_off=-60)


# ------------------------------------------------------------------ BSP quarantine


def test_bsp_is_not_reachable_from_the_price_path(tmp_path: Path) -> None:
    """BSP is a reconciled settlement-time closing benchmark. SPEC-021: it must not be
    reachable from any pre-event feature, and it joins only at grading time."""
    definition = _definition(bsp_reconciled=True, status="CLOSED", runner_status=("WINNER", "LOSER"))
    definition["runners"][0]["bsp"] = 2.14
    path = _write_jsonl(tmp_path / "m.jsonl", [
        _msg(OFF_MS - 600_000, definition=_definition()),
        _msg(OFF_MS - 300_000, ltps={A: 2.0}),
        _msg(OFF_MS + 600_000, definition=definition),
    ])
    (history,) = read_markets(path)
    assert not hasattr(history, "bsp"), "a history must not expose BSP as an attribute"
    with pytest.raises(BspQuarantineError, match="grading"):
        history.require_no_closing_benchmark()


def test_bsp_is_available_only_through_the_explicit_grading_channel(tmp_path: Path) -> None:
    definition = _definition(bsp_reconciled=True, status="CLOSED", runner_status=("WINNER", "LOSER"))
    definition["runners"][0]["bsp"] = 2.14
    definition["runners"][1]["bsp"] = 1.88
    path = _write_jsonl(tmp_path / "m.jsonl", [
        _msg(OFF_MS - 600_000, definition=_definition()),
        _msg(OFF_MS + 600_000, definition=definition),
    ])
    (history,) = read_markets(path)
    grading = history.grading_view()
    assert grading.bsp[A] == Decimal("2.14")
    assert grading.winner_selection_id == A


def test_a_market_with_no_settled_definition_has_no_grading_view(tmp_path: Path) -> None:
    path = _write_jsonl(tmp_path / "m.jsonl", _stream([30], [2.0]))
    (history,) = read_markets(path)
    assert history.grading_view() is None


# ------------------------------------------------------------------ selection & hygiene


def test_non_match_odds_markets_are_skipped(tmp_path: Path) -> None:
    definition = _definition()
    definition["marketType"] = "SET_BETTING"
    path = _write_jsonl(tmp_path / "m.jsonl", [
        _msg(OFF_MS - 600_000, definition=definition),
        _msg(OFF_MS - 300_000, ltps={A: 2.0}),
    ])
    assert read_markets(path) == ()


def test_a_removed_runner_is_recorded_not_dropped(tmp_path: Path) -> None:
    definition = _definition()
    definition["runners"][1]["status"] = "REMOVED"
    path = _write_jsonl(tmp_path / "m.jsonl", [_msg(OFF_MS - 600_000, definition=definition)])
    (history,) = read_markets(path)
    assert [r.status for r in history.runners] == ["ACTIVE", "REMOVED"]


def test_a_market_without_a_definition_is_skipped(tmp_path: Path) -> None:
    path = _write_jsonl(tmp_path / "m.jsonl", [_msg(OFF_MS - 600_000, ltps={A: 2.0})])
    assert read_markets(path) == ()


def test_a_malformed_line_is_refused_not_skipped(tmp_path: Path) -> None:
    path = _write_jsonl(tmp_path / "m.jsonl", [
        _msg(OFF_MS - 600_000, definition=_definition()),
        "{not json",
    ])
    with pytest.raises(ValueError, match="malformed"):
        read_markets(path)


def test_observations_are_chronological(tmp_path: Path) -> None:
    path = _write_jsonl(tmp_path / "m.jsonl", [
        _msg(OFF_MS - 600_000, definition=_definition()),
        _msg(OFF_MS - 120_000, ltps={A: 2.5}),
        _msg(OFF_MS - 300_000, ltps={A: 2.0}),      # out of order in the file
    ])
    (history,) = read_markets(path)
    times = [o.publish_time_ms for o in history.observations]
    assert times == sorted(times)


def test_two_markets_in_one_file_are_kept_apart(tmp_path: Path) -> None:
    other = json.dumps({"op": "mcm", "pt": OFF_MS - 600_000,
                        "mc": [{"id": "1.999", "marketDefinition": _definition()}]})
    path = _write_jsonl(tmp_path / "m.jsonl", [
        _msg(OFF_MS - 600_000, definition=_definition()), other,
    ])
    assert {h.market_id for h in read_markets(path)} == {MARKET_ID, "1.999"}


def test_history_is_hashable_and_frozen(tmp_path: Path) -> None:
    path = _write_jsonl(tmp_path / "m.jsonl", _stream([30], [2.0]))
    (history,) = read_markets(path)
    assert isinstance(history, MarketHistory)
    with pytest.raises(Exception):
        history.market_id = "nope"  # type: ignore[misc]


# ------------------------------------------------------------------ ADVANCED ladders


def _ladder_msg(pt: int, *, back: dict[int, list] | None = None,
                lay: dict[int, list] | None = None) -> str:
    """An ADVANCED runner-change message. batb/batl entries are [level, price, size]."""
    rc = []
    for sid in sorted({*(back or {}), *(lay or {})}):
        entry: dict = {"id": sid}
        if back and sid in back:
            entry["batb"] = back[sid]
        if lay and sid in lay:
            entry["batl"] = lay[sid]
        rc.append(entry)
    return json.dumps({"op": "mcm", "pt": pt, "mc": [{"id": MARKET_ID, "rc": rc}]})


def test_the_best_back_price_and_size_are_read(tmp_path: Path) -> None:
    """ADVANCED carries batb = best available TO BACK, as [level, price, size]. Level 0 is
    the best. This is a crossable price with depth — the thing BASIC cannot give."""
    path = _write_jsonl(tmp_path / "m.jsonl", [
        _msg(OFF_MS - 3_600_000, definition=_definition()),
        _ladder_msg(OFF_MS - 600_000,
                    back={A: [[0, 2.0, 180.0], [1, 1.99, 703.98]],
                          B: [[0, 2.02, 95.0]]}),
    ])
    (history,) = read_markets(path)
    level = history.best_back_at(A, seconds_before_off=300)
    assert level is not None
    assert level.price == Decimal("2.0") and level.size == Decimal("180.0")


def test_the_best_level_is_taken_regardless_of_message_order(tmp_path: Path) -> None:
    """Betfair does not guarantee level 0 comes first in the array."""
    path = _write_jsonl(tmp_path / "m.jsonl", [
        _msg(OFF_MS - 3_600_000, definition=_definition()),
        _ladder_msg(OFF_MS - 600_000, back={A: [[2, 1.9, 10.0], [0, 2.0, 180.0], [1, 1.95, 5.0]]}),
    ])
    (history,) = read_markets(path)
    level = history.best_back_at(A, seconds_before_off=300)
    assert level is not None and level.price == Decimal("2.0")


def test_a_ladder_carries_forward_like_a_price(tmp_path: Path) -> None:
    path = _write_jsonl(tmp_path / "m.jsonl", [
        _msg(OFF_MS - 3_600_000, definition=_definition()),
        _ladder_msg(OFF_MS - 1_800_000, back={A: [[0, 2.0, 180.0]]}),
        _ladder_msg(OFF_MS - 300_000, back={A: [[0, 2.5, 40.0]]}),
    ])
    (history,) = read_markets(path)
    early = history.best_back_at(A, seconds_before_off=900)
    late = history.best_back_at(A, seconds_before_off=60)
    assert early is not None and early.price == Decimal("2.0")
    assert late is not None and late.price == Decimal("2.5")


def test_an_emptied_ladder_removes_the_level(tmp_path: Path) -> None:
    """Betfair signals 'nothing available' with an empty array. Carrying the old price
    forward there would invent liquidity that no longer exists."""
    path = _write_jsonl(tmp_path / "m.jsonl", [
        _msg(OFF_MS - 3_600_000, definition=_definition()),
        _ladder_msg(OFF_MS - 1_800_000, back={A: [[0, 2.0, 180.0]]}),
        _ladder_msg(OFF_MS - 600_000, back={A: []}),
    ])
    (history,) = read_markets(path)
    assert history.best_back_at(A, seconds_before_off=300) is None


def test_a_zero_size_level_is_not_liquidity(tmp_path: Path) -> None:
    path = _write_jsonl(tmp_path / "m.jsonl", [
        _msg(OFF_MS - 3_600_000, definition=_definition()),
        _ladder_msg(OFF_MS - 600_000, back={A: [[0, 2.0, 0.0]]}),
    ])
    (history,) = read_markets(path)
    assert history.best_back_at(A, seconds_before_off=300) is None


def test_ladder_observations_stop_at_the_off(tmp_path: Path) -> None:
    path = _write_jsonl(tmp_path / "m.jsonl", [
        _msg(OFF_MS - 600_000, definition=_definition()),
        _ladder_msg(OFF_MS - 300_000, back={A: [[0, 2.0, 180.0]]}),
        _msg(OFF_MS + 60_000, definition=_definition(in_play=True)),
        _ladder_msg(OFF_MS + 120_000, back={A: [[0, 9.0, 500.0]]}),
    ])
    (history,) = read_markets(path)
    level = history.best_back_at(A, seconds_before_off=0)
    assert level is not None and level.price == Decimal("2.0")


def test_the_lay_side_is_read_too(tmp_path: Path) -> None:
    path = _write_jsonl(tmp_path / "m.jsonl", [
        _msg(OFF_MS - 3_600_000, definition=_definition()),
        _ladder_msg(OFF_MS - 600_000, back={A: [[0, 2.0, 180.0]]},
                    lay={A: [[0, 2.02, 60.0]]}),
    ])
    (history,) = read_markets(path)
    back = history.best_back_at(A, seconds_before_off=300)
    lay = history.best_lay_at(A, seconds_before_off=300)
    assert back is not None and lay is not None
    assert back.price < lay.price, "a healthy book has back below lay"


def test_a_zero_last_traded_price_means_no_trade_yet(tmp_path: Path) -> None:
    """ADVANCED sends ltp: 0.0 before anything has traded. It is a sentinel, not a price —
    0.0 implies infinite odds. Treating it as a price makes the whole market unreadable;
    treating it as a trade would invent one. It reads as absent."""
    path = _write_jsonl(tmp_path / "m.jsonl", [
        _msg(OFF_MS - 3_600_000, definition=_definition()),
        _msg(OFF_MS - 1_800_000, ltps={A: 0.0}),
        _msg(OFF_MS - 600_000, ltps={A: 2.0}),
    ])
    (history,) = read_markets(path)
    assert history.ltp_at(A, seconds_before_off=1200) is None, "no trade had happened yet"
    assert history.ltp_at(A, seconds_before_off=300) == Decimal("2.0")


def test_a_genuinely_off_ladder_price_is_still_refused(tmp_path: Path) -> None:
    """The sentinel carve-out must not become a general tolerance for bad prices."""
    path = _write_jsonl(tmp_path / "m.jsonl", [
        _msg(OFF_MS - 3_600_000, definition=_definition()),
        _msg(OFF_MS - 600_000, ltps={A: 2.03}),
    ])
    with pytest.raises(ValueError, match="off-ladder"):
        read_markets(path)


def test_an_absent_side_carries_forward_but_an_empty_one_clears(tmp_path: Path) -> None:
    """Betfair sends batb and batl as SEPARATE deltas. An absent key means 'unchanged';
    an empty array means 'cleared'. Treating absent as empty wipes the other side of the
    book on every one-sided update, and the market stops having a midpoint at all."""
    path = _write_jsonl(tmp_path / "m.jsonl", [
        _msg(OFF_MS - 3_600_000, definition=_definition()),
        _ladder_msg(OFF_MS - 1_800_000,
                    back={A: [[0, 2.0, 180.0]]}, lay={A: [[0, 2.02, 60.0]]}),
        _ladder_msg(OFF_MS - 900_000, back={A: [[0, 2.02, 90.0]]}),   # back only
    ])
    (history,) = read_markets(path)
    back = history.best_back_at(A, seconds_before_off=300)
    lay = history.best_lay_at(A, seconds_before_off=300)
    assert back is not None and back.price == Decimal("2.02"), "the new back applies"
    assert lay is not None and lay.price == Decimal("2.02"), "the lay was not wiped"


def test_an_explicitly_emptied_side_is_cleared_not_carried(tmp_path: Path) -> None:
    path = _write_jsonl(tmp_path / "m.jsonl", [
        _msg(OFF_MS - 3_600_000, definition=_definition()),
        _ladder_msg(OFF_MS - 1_800_000,
                    back={A: [[0, 2.0, 180.0]]}, lay={A: [[0, 2.02, 60.0]]}),
        _ladder_msg(OFF_MS - 900_000, lay={A: []}),
    ])
    (history,) = read_markets(path)
    assert history.best_back_at(A, seconds_before_off=300) is not None
    assert history.best_lay_at(A, seconds_before_off=300) is None


def test_one_selection_update_does_not_disturb_the_other(tmp_path: Path) -> None:
    path = _write_jsonl(tmp_path / "m.jsonl", [
        _msg(OFF_MS - 3_600_000, definition=_definition()),
        _ladder_msg(OFF_MS - 1_800_000, back={A: [[0, 2.0, 180.0]], B: [[0, 2.0, 95.0]]},
                    lay={A: [[0, 2.02, 60.0]], B: [[0, 2.02, 40.0]]}),
        _ladder_msg(OFF_MS - 900_000, back={A: [[0, 1.9, 200.0]]}),
    ])
    (history,) = read_markets(path)
    assert history.best_lay_at(B, seconds_before_off=300) is not None
    assert history.best_back_at(B, seconds_before_off=300).price == Decimal("2.0")


def test_traded_volume_is_captured_and_carries_forward(tmp_path: Path) -> None:
    """tv is cumulative matched volume on a selection. Volume imbalance is one of the few
    genuinely non-tennis signals available — how the money is actually distributed rather
    than what the displayed price says."""
    path = _write_jsonl(tmp_path / "m.jsonl", [
        _msg(OFF_MS - 3_600_000, definition=_definition()),
        json.dumps({"op": "mcm", "pt": OFF_MS - 1_800_000,
                    "mc": [{"id": MARKET_ID, "rc": [{"id": A, "tv": 1250.5}]}]}),
        json.dumps({"op": "mcm", "pt": OFF_MS - 600_000,
                    "mc": [{"id": MARKET_ID, "rc": [{"id": A, "ltp": 2.0}]}]}),
    ])
    (history,) = read_markets(path)
    assert history.traded_volume_at(A, seconds_before_off=1200) == Decimal("1250.5")
    assert history.traded_volume_at(A, seconds_before_off=300) == Decimal("1250.5")


def test_traded_volume_before_any_trade_is_none(tmp_path: Path) -> None:
    path = _write_jsonl(tmp_path / "m.jsonl", [
        _msg(OFF_MS - 3_600_000, definition=_definition()),
        json.dumps({"op": "mcm", "pt": OFF_MS - 600_000,
                    "mc": [{"id": MARKET_ID, "rc": [{"id": A, "tv": 100.0}]}]}),
    ])
    (history,) = read_markets(path)
    assert history.traded_volume_at(A, seconds_before_off=1800) is None
