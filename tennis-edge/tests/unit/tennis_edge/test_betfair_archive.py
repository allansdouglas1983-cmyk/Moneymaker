"""Streaming an eleven-year Betfair archive without holding it, and without losing count.

The archive is one ``.bz2`` per market inside a 4 GB tar — 1.1 million of them. Reading it
the way a single day is read would build 1.1 million accumulators before returning anything.
So it is streamed a market at a time, and these tests pin the two things that go wrong when
you stream: markets silently lost, and provenance silently absent.

Every file is accounted for. A tar member that is unreadable, or holds no market definition,
or holds a market type nobody asked for, is COUNTED under a named reason — because
``markets_written`` on its own cannot distinguish "the archive has 200 Match Odds markets"
from "the reader dropped 90% of them and nobody noticed".
"""
from __future__ import annotations

import bz2
import io
import json
import tarfile
from pathlib import Path

import pytest

from tennis_edge.betfair_archive import (
    ExtractStats,
    extract_markets,
    iter_market_members,
    read_extract,
)

OFF_MS = 1_700_000_000_000


def _message(market_id: str, *, market_type: str = "MATCH_ODDS",
             publish_time: int, ltp: list[tuple[int, str]] | None = None,
             definition: bool = True, in_play: bool = False) -> dict[str, object]:
    change: dict[str, object] = {"id": market_id}
    if definition:
        change["marketDefinition"] = {
            "marketType": market_type,
            "eventId": "99",
            "eventName": "Alpha v Beta",
            "countryCode": "GB",
            "marketTime": "2023-11-14T22:13:20.000Z",
            "inPlay": in_play,
            "status": "OPEN",
            "runners": [
                {"id": 1, "name": "Alpha", "status": "ACTIVE", "sortPriority": 1},
                {"id": 2, "name": "Beta", "status": "ACTIVE", "sortPriority": 2},
            ],
        }
    if ltp:
        change["rc"] = [{"id": sid, "ltp": float(price)} for sid, price in ltp]
    return {"op": "mcm", "pt": publish_time, "mc": [change]}


def _archive(tmp_path: Path, files: dict[str, list[dict[str, object]] | bytes]) -> Path:
    """A tar shaped like Betfair's: BASIC/YYYY/Mon/DD/eventId/marketId.bz2."""
    path = tmp_path / "data.tar"
    with tarfile.open(path, "w") as tar:
        for name, content in files.items():
            if isinstance(content, bytes):
                raw = content
            else:
                raw = bz2.compress(
                    "\n".join(json.dumps(m) for m in content).encode("utf-8")
                )
            info = tarfile.TarInfo(name=name)
            info.size = len(raw)
            tar.addfile(info, io.BytesIO(raw))
    return path


def _match_odds(market_id: str) -> list[dict[str, object]]:
    return [
        _message(market_id, publish_time=OFF_MS - 3_600_000, ltp=[(1, "2.0"), (2, "2.0")]),
        _message(market_id, publish_time=OFF_MS - 600_000, ltp=[(1, "3.0")],
                 definition=False),
        _message(market_id, publish_time=OFF_MS - 120_000, ltp=[(1, "3.2")],
                 definition=False),
    ]


class TestIterMarketMembers:
    def test_every_compressed_member_is_yielded_once(self, tmp_path: Path) -> None:
        archive = _archive(tmp_path, {
            "BASIC/2015/Jul/12/99/1.100.bz2": _match_odds("1.100"),
            "BASIC/2015/Jul/12/99/1.101.bz2": _match_odds("1.101"),
        })
        names = [name for name, _raw in iter_market_members(archive)]
        assert sorted(names) == ["BASIC/2015/Jul/12/99/1.100.bz2",
                                 "BASIC/2015/Jul/12/99/1.101.bz2"]

    def test_a_corrupt_member_does_not_end_the_stream(self, tmp_path: Path) -> None:
        """One bad file in 1.1 million must cost one file, not the other 1,099,999."""
        archive = _archive(tmp_path, {
            "BASIC/2015/Jul/12/99/1.100.bz2": b"this is not bzip2 data",
            "BASIC/2015/Jul/12/99/1.101.bz2": _match_odds("1.101"),
        })
        names = [name for name, _raw in iter_market_members(archive)]
        assert names == ["BASIC/2015/Jul/12/99/1.101.bz2"]


class TestExtractMarkets:
    def test_a_match_odds_market_round_trips_through_the_extract(self,
                                                                 tmp_path: Path) -> None:
        archive = _archive(tmp_path, {"BASIC/2015/Jul/12/99/1.100.bz2":
                                      _match_odds("1.100")})
        out = tmp_path / "extract.jsonl"
        extract_markets(archive, out)
        markets = list(read_extract(out))
        assert len(markets) == 1
        market = markets[0]
        assert market.market_id == "1.100"
        assert market.market_type == "MATCH_ODDS"
        assert market.event_name == "Alpha v Beta"
        assert [r.name for r in market.runners] == ["Alpha", "Beta"]
        assert market.market_time_ms == OFF_MS
        assert len(market.observations) == 4

    def test_the_price_read_back_matches_the_price_written(self, tmp_path: Path) -> None:
        """The whole extract is worthless if a price changes crossing the file."""
        archive = _archive(tmp_path, {"BASIC/2015/Jul/12/99/1.100.bz2":
                                      _match_odds("1.100")})
        out = tmp_path / "extract.jsonl"
        extract_markets(archive, out)
        market = next(iter(read_extract(out)))
        from decimal import Decimal
        assert market.ltp_at(1, seconds_before_off=600) == Decimal("3.0")
        assert market.ltp_at(1, seconds_before_off=120) == Decimal("3.2")
        assert market.ltp_at(2, seconds_before_off=600) == Decimal("2.0")

    def test_unwanted_market_types_are_counted_not_merely_skipped(self,
                                                                 tmp_path: Path) -> None:
        """A silent skip cannot be told apart from an archive that never had them."""
        archive = _archive(tmp_path, {
            "BASIC/2015/Jul/12/99/1.100.bz2": _match_odds("1.100"),
            "BASIC/2015/Jul/12/99/1.200.bz2": [
                _message("1.200", market_type="SET_BETTING",
                         publish_time=OFF_MS - 600_000, ltp=[(1, "2.0")])],
        })
        out = tmp_path / "extract.jsonl"
        stats = extract_markets(archive, out, market_types=("MATCH_ODDS",))
        assert stats.markets_written == 1
        assert stats.wrong_market_type == 1
        assert stats.members_read == 2

    def test_selecting_several_market_types_writes_all_of_them(self,
                                                               tmp_path: Path) -> None:
        """The cross-market complex is the point of having the archive at all."""
        archive = _archive(tmp_path, {
            "BASIC/2015/Jul/12/99/1.100.bz2": _match_odds("1.100"),
            "BASIC/2015/Jul/12/99/1.200.bz2": [
                _message("1.200", market_type="SET_BETTING",
                         publish_time=OFF_MS - 600_000, ltp=[(1, "2.0")])],
        })
        out = tmp_path / "extract.jsonl"
        stats = extract_markets(archive, out,
                                market_types=("MATCH_ODDS", "SET_BETTING"))
        assert stats.markets_written == 2
        assert stats.wrong_market_type == 0
        assert {m.market_type for m in read_extract(out)} == {"MATCH_ODDS", "SET_BETTING"}

    def test_a_member_with_no_market_definition_is_counted(self, tmp_path: Path) -> None:
        archive = _archive(tmp_path, {
            "BASIC/2015/Jul/12/99/1.100.bz2": [
                _message("1.100", publish_time=OFF_MS - 600_000,
                         ltp=[(1, "2.0")], definition=False)],
        })
        out = tmp_path / "extract.jsonl"
        stats = extract_markets(archive, out)
        assert stats.markets_written == 0
        assert stats.no_definition == 1

    def test_a_corrupt_member_is_counted_under_its_own_reason(self,
                                                              tmp_path: Path) -> None:
        archive = _archive(tmp_path, {
            "BASIC/2015/Jul/12/99/1.100.bz2": b"not bzip2",
            "BASIC/2015/Jul/12/99/1.101.bz2": _match_odds("1.101"),
        })
        out = tmp_path / "extract.jsonl"
        stats = extract_markets(archive, out)
        assert stats.markets_written == 1
        assert stats.unreadable == 1

    def test_the_funnel_balances(self, tmp_path: Path) -> None:
        """members_read equals everything that happened to a member. A reason that does not
        appear in this sum is a row that vanished."""
        archive = _archive(tmp_path, {
            "BASIC/2015/Jul/12/99/1.100.bz2": _match_odds("1.100"),
            "BASIC/2015/Jul/12/99/1.200.bz2": [
                _message("1.200", market_type="SET_BETTING",
                         publish_time=OFF_MS - 600_000, ltp=[(1, "2.0")])],
            "BASIC/2015/Jul/12/99/1.300.bz2": b"not bzip2",
            "BASIC/2015/Jul/12/99/1.400.bz2": [
                _message("1.400", publish_time=OFF_MS - 600_000, definition=False)],
        })
        out = tmp_path / "extract.jsonl"
        stats = extract_markets(archive, out)
        assert stats.members_read == 4
        assert stats.accounted == stats.members_read

    def test_in_play_markets_never_reach_the_extract_with_in_play_prices(
            self, tmp_path: Path) -> None:
        """Pre-off only is a hard prohibition of the programme, and an archive is exactly
        where an in-play price would sneak in unnoticed."""
        archive = _archive(tmp_path, {
            "BASIC/2015/Jul/12/99/1.100.bz2": [
                _message("1.100", publish_time=OFF_MS - 600_000, ltp=[(1, "3.0")]),
                _message("1.100", publish_time=OFF_MS + 60_000, ltp=[(1, "9.0")],
                         in_play=True),
            ],
        })
        out = tmp_path / "extract.jsonl"
        extract_markets(archive, out)
        for market in read_extract(out):
            assert all(o.publish_time_ms <= market.market_time_ms
                       for o in market.observations)

    def test_the_extract_records_the_archive_it_came_from(self, tmp_path: Path) -> None:
        """A derived file with no provenance is the failure that lost the last corpus: a
        future reader cannot tell what it is missing."""
        archive = _archive(tmp_path, {"BASIC/2015/Jul/12/99/1.100.bz2":
                                      _match_odds("1.100")})
        out = tmp_path / "extract.jsonl"
        extract_markets(archive, out, source_digest="sha256:abc123")
        header = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
        assert header["kind"] == "tennis-edge-betfair-extract-v1"
        assert header["source_digest"] == "sha256:abc123"
        assert header["market_types"] == ["MATCH_ODDS"]

    def test_reading_an_extract_without_a_header_is_refused(self,
                                                            tmp_path: Path) -> None:
        """An unlabelled JSONL might be anything. Guessing is how the wrong corpus gets
        used for an afternoon."""
        stray = tmp_path / "stray.jsonl"
        stray.write_text('{"market_id": "1.100"}\n', encoding="utf-8")
        with pytest.raises(ValueError):
            list(read_extract(stray))

    def test_a_limit_stops_early_and_says_so(self, tmp_path: Path) -> None:
        """Used for probes. A truncated extract that looked complete would be quoted as
        though it covered the archive."""
        archive = _archive(tmp_path, {
            f"BASIC/2015/Jul/12/99/1.{n}.bz2": _match_odds(f"1.{n}")
            for n in range(100, 105)
        })
        out = tmp_path / "extract.jsonl"
        stats = extract_markets(archive, out, limit=2)
        assert stats.markets_written == 2
        assert stats.truncated is True
        header = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
        assert header["truncated"] is True


class TestTruncatedArchive:
    """The archive that actually arrived stops mid-member at 94%.

    A 4 GB tar cut at a block boundary has no end-of-archive marker, and the reader hits
    "unexpected end of data" partway through. Three things must happen and none of them is
    "raise": the markets already read are kept, the stream stops cleanly at the damage, and
    the extract says on its face that its source was incomplete. Discarding 450,000 good
    markets because the last 6% is missing would be throwing away the evidence; keeping them
    without a label would be quoting an eleven-year result from nine years of data.
    """

    def _truncated(self, tmp_path: Path) -> Path:
        archive = _archive(tmp_path, {
            "BASIC/2015/Jul/12/99/1.100.bz2": _match_odds("1.100"),
            "BASIC/2015/Jul/12/99/1.101.bz2": _match_odds("1.101"),
            "BASIC/2015/Jul/12/99/1.102.bz2": _match_odds("1.102"),
        })
        # Cut inside the last member's data, on a block boundary, exactly as a half-finished
        # transfer does. The end-of-archive zero blocks go with it.
        raw = archive.read_bytes()
        cut = tmp_path / "truncated.tar"
        cut.write_bytes(raw[:len(raw) - 2048])
        return cut

    def test_markets_before_the_damage_are_kept(self, tmp_path: Path) -> None:
        out = tmp_path / "extract.jsonl"
        stats = extract_markets(self._truncated(tmp_path), out)
        assert stats.markets_written >= 1
        assert len(list(read_extract(out))) == stats.markets_written

    def test_the_stream_stops_cleanly_instead_of_raising(self, tmp_path: Path) -> None:
        names = [n for n, _raw in iter_market_members(self._truncated(tmp_path))]
        assert names  # got something before the damage
        assert len(names) < 3

    def test_the_damage_is_recorded_on_the_stats(self, tmp_path: Path) -> None:
        out = tmp_path / "extract.jsonl"
        stats = extract_markets(self._truncated(tmp_path), out)
        assert stats.source_truncated is True

    def test_the_damage_is_recorded_in_the_extract_header(self, tmp_path: Path) -> None:
        """Anyone reading this extract later must be able to see it is partial without
        knowing the story."""
        out = tmp_path / "extract.jsonl"
        extract_markets(self._truncated(tmp_path), out)
        header = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
        assert header["source_truncated"] is True

    def test_an_intact_archive_is_not_marked_truncated(self, tmp_path: Path) -> None:
        """The flag has to mean something, so it must be off for a whole archive."""
        archive = _archive(tmp_path, {"BASIC/2015/Jul/12/99/1.100.bz2":
                                      _match_odds("1.100")})
        out = tmp_path / "extract.jsonl"
        stats = extract_markets(archive, out)
        assert stats.source_truncated is False
        header = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
        assert header["source_truncated"] is False

    def test_the_funnel_still_balances_on_a_truncated_archive(self,
                                                              tmp_path: Path) -> None:
        out = tmp_path / "extract.jsonl"
        stats = extract_markets(self._truncated(tmp_path), out)
        assert stats.accounted == stats.members_read


class TestExtractStats:
    def test_accounted_sums_every_named_reason(self) -> None:
        stats = ExtractStats(members_read=10, markets_written=4, wrong_market_type=3,
                             no_definition=2, unreadable=1)
        assert stats.accounted == 10

    def test_a_reason_left_out_of_the_sum_shows_up_as_an_imbalance(self) -> None:
        stats = ExtractStats(members_read=10, markets_written=4, wrong_market_type=3,
                             no_definition=2, unreadable=0)
        assert stats.accounted != stats.members_read
