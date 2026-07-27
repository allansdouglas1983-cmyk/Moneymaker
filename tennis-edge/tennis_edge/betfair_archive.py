"""Stream the eleven-year Betfair archive, and account for every file in it.

The archive is a 4 GB tar holding one ``.bz2`` per market — 1,114,614 of them, July 2015 to
2026. :func:`~tennis_edge.betfair.read_markets` accumulates every market it finds before
returning any of them, which is correct for a file or a day and impossible at this size.

So this streams: one member at a time, parsed by exactly the same code
(:func:`~tennis_edge.betfair.read_market_messages`), written out as it goes, nothing held.
Betfair ships one market per file, so a member is a natural unit and no market is ever split
across the boundary.

**Every member is accounted for.** ``markets_written`` on its own cannot distinguish "the
archive holds two hundred thousand Match Odds markets" from "the reader dropped ninety per
cent of them and nobody noticed". So each member lands under a named reason —
written, wrong market type, no definition, unreadable — and :attr:`ExtractStats.accounted`
must equal :attr:`ExtractStats.members_read`. A reason that is not in the sum is a row that
vanished, and the imbalance is the alarm.

**The extract knows where it came from.** The first line is a header naming the source
archive's digest, the market types requested and whether the run was truncated. Reading a
JSONL without that header is refused rather than guessed at. A derived file with no
provenance is precisely how a previous corpus was lost and then silently run without: the
cost of a header is one line, and the cost of not having one is an afternoon of numbers
about the wrong data.

A corrupt member costs one member. One bad file in 1.1 million must not end the stream.
"""
from __future__ import annotations

import bz2
import json
import tarfile
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from tennis_edge.betfair import (
    LtpObservation,
    MarketHistory,
    Runner,
    read_market_messages,
)

__all__ = [
    "EXTRACT_KIND",
    "ExtractStats",
    "iter_market_members",
    "extract_markets",
    "read_extract",
]

EXTRACT_KIND = "tennis-edge-betfair-extract-v1"

#: Default selection. Match Odds is what the model prices; the rest of the complex is what
#: the coherence solver needs, and is requested explicitly when that is what is wanted.
DEFAULT_MARKET_TYPES: tuple[str, ...] = ("MATCH_ODDS",)


@dataclass
class ExtractStats:
    """The exclusion funnel. Every member read lands under exactly one named reason."""

    members_read: int = 0
    markets_written: int = 0
    wrong_market_type: int = 0
    no_definition: int = 0
    unreadable: int = 0
    truncated: bool = False
    #: Market types seen and skipped, so "what else is in here" is answerable without a
    #: second full pass over four gigabytes.
    skipped_types: dict[str, int] = field(default_factory=dict)

    @property
    def accounted(self) -> int:
        """Members explained. Must equal :attr:`members_read`; a gap means a lost row."""
        return (self.markets_written + self.wrong_market_type + self.no_definition
                + self.unreadable)

    def report(self) -> str:
        top = ", ".join(f"{t}={n:,}" for t, n in
                        sorted(self.skipped_types.items(), key=lambda kv: -kv[1])[:8])
        return (
            f"members={self.members_read:,}  written={self.markets_written:,}  "
            f"wrong_type={self.wrong_market_type:,}  no_definition={self.no_definition:,}  "
            f"unreadable={self.unreadable:,}  "
            f"balanced={'yes' if self.accounted == self.members_read else 'NO'}"
            + (f"\n  skipped types: {top}" if top else "")
        )


def iter_market_members(
    archive: Path | str, *, include_unreadable: bool = False
) -> Iterator[tuple[str, bytes]]:
    """Yield ``(member_name, decompressed_bytes)`` for each market file, in archive order.

    Opened in stream mode (``r|``) rather than random-access: building an index of 1.1
    million members costs a gigabyte of memory and buys nothing, since every member is read
    exactly once and in order.

    A member that will not decompress is skipped, because one corrupt file in 1.1 million
    must cost one file and not the rest of the archive. ``include_unreadable=True`` yields
    it with empty bytes instead, which is what :func:`extract_markets` asks for — it has to
    *count* the damage, and a member that was silently skipped cannot be counted.
    """
    with tarfile.open(archive, "r|") as tar:
        for member in tar:
            if not member.isfile() or not member.name.endswith(".bz2"):
                continue
            handle = tar.extractfile(member)
            if handle is None:  # pragma: no cover - isfile() established this
                continue
            raw = handle.read()
            try:
                yield member.name, bz2.decompress(raw)
            except (OSError, ValueError, EOFError):
                if include_unreadable:
                    yield member.name, b""


def _messages(raw: bytes) -> Iterator[dict[str, object]]:
    for line in raw.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            continue
        if isinstance(message, dict):
            yield message


def _row(market: MarketHistory) -> dict[str, object]:
    """One market as a JSON row. Prices are strings so the Decimal survives the file."""
    return {
        "market_id": market.market_id,
        "event_id": market.event_id,
        "event_name": market.event_name,
        "market_type": market.market_type,
        "country_code": market.country_code,
        "market_time_ms": market.market_time_ms,
        "went_in_play": market.went_in_play,
        "runners": [
            {"id": r.selection_id, "name": r.name, "status": r.status,
             "sort": r.sort_priority}
            for r in market.runners
        ],
        # (publish_time_ms, selection_id, price). A list of triples rather than objects:
        # at forty million observations the key names are most of the file.
        "ltp": [[o.publish_time_ms, o.selection_id, str(o.price)]
                for o in market.observations],
    }


def extract_markets(
    archive: Path | str,
    out_path: Path | str,
    *,
    market_types: Sequence[str] = DEFAULT_MARKET_TYPES,
    source_digest: str = "",
    limit: int | None = None,
    progress_every: int = 0,
) -> ExtractStats:
    """Stream ``archive`` into a JSONL extract, one market per line, counting everything.

    ``limit`` caps markets written and marks the extract truncated in its header — a probe
    that looked complete would be quoted as though it covered the archive.
    """
    wanted = tuple(market_types)
    stats = ExtractStats()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", encoding="utf-8") as handle:
        header = {
            "kind": EXTRACT_KIND,
            "source": str(archive),
            "source_digest": source_digest,
            "market_types": list(wanted),
            "limit": limit,
            # Rewritten at the end once the answer is known; placed first so a reader hits
            # it before any data row.
            "truncated": False,
        }
        header_line = json.dumps(header)
        handle.write(header_line + "\n")

        for name, raw in iter_market_members(archive, include_unreadable=True):
            stats.members_read += 1
            if not raw:
                stats.unreadable += 1
                continue
            messages = list(_messages(raw))
            # Peek the types before parsing in full. read_market_messages filters on the
            # types it is given, so asking it for everything and classifying afterwards is
            # not available — `set(market_types)` would flatten any match-everything
            # sentinel to nothing. Peeking also means a market type nobody wants costs one
            # scan rather than a full accumulation.
            present = _market_types_in(messages)
            if not present:
                stats.no_definition += 1
                continue
            if not present & set(wanted):
                stats.wrong_market_type += 1
                for market_type in sorted(present):
                    stats.skipped_types[market_type] = (
                        stats.skipped_types.get(market_type, 0) + 1)
                continue
            histories = read_market_messages(messages, market_types=wanted)
            if not histories:
                stats.no_definition += 1
                continue
            for market in histories:
                handle.write(json.dumps(_row(market)) + "\n")
                stats.markets_written += 1
                if progress_every and stats.markets_written % progress_every == 0:
                    print(f"  {stats.markets_written:,} markets "
                          f"({stats.members_read:,} members) {name}", flush=True)
                if limit is not None and stats.markets_written >= limit:
                    stats.truncated = True
                    break
            if stats.truncated:
                break

    if stats.truncated:
        _rewrite_header(out, header_line, {**header, "truncated": True})
    return stats


def _market_types_in(messages: Sequence[dict[str, object]]) -> set[str]:
    """Market types named by any definition in this file, without accumulating prices."""
    found: set[str] = set()
    for message in messages:
        changes = message.get("mc")
        if not isinstance(changes, list):
            continue
        for change in changes:
            if not isinstance(change, dict):
                continue
            definition = change.get("marketDefinition")
            if isinstance(definition, dict):
                market_type = str(definition.get("marketType", ""))
                if market_type:
                    found.add(market_type)
    return found


def _rewrite_header(path: Path, old_line: str, header: dict[str, object]) -> None:
    """Replace the first line in place. Only the header changes; rows are untouched."""
    text = path.read_text(encoding="utf-8")
    assert text.startswith(old_line + "\n")
    path.write_text(json.dumps(header) + text[len(old_line):], encoding="utf-8")


def read_extract(path: Path | str) -> Iterable[MarketHistory]:
    """Rebuild :class:`MarketHistory` objects from an extract, one at a time.

    Refuses a file without the extract header. An unlabelled JSONL might be anything, and
    guessing is how a whole afternoon gets spent on the wrong corpus.
    """
    target = Path(path)
    with target.open(encoding="utf-8") as handle:
        first = handle.readline()
        try:
            header = json.loads(first)
        except ValueError as error:
            raise ValueError(f"{target} has no extract header") from error
        if not isinstance(header, dict) or header.get("kind") != EXTRACT_KIND:
            raise ValueError(
                f"{target} is not a {EXTRACT_KIND} extract; refusing to guess at its shape"
            )
        for line in handle:
            line = line.strip()
            if not line:
                continue
            yield _history(json.loads(line))


def _history(row: dict[str, object]) -> MarketHistory:
    # Row shapes come from _row() one function above, but the file in between makes them
    # `object` again. Narrowed explicitly rather than ignored: an extract written by an
    # older version is exactly the input that would otherwise fail somewhere unhelpful.
    raw_runners = row["runners"]
    raw_ltp = row["ltp"]
    if not isinstance(raw_runners, list) or not isinstance(raw_ltp, list):
        raise ValueError(f"malformed extract row for market {row.get('market_id')!r}")
    runners = tuple(
        Runner(selection_id=int(r["id"]), name=str(r["name"]), status=str(r["status"]),
               sort_priority=int(r["sort"]))
        for r in raw_runners
    )
    observations = tuple(
        LtpObservation(publish_time_ms=int(t), selection_id=int(sid),
                       price=Decimal(str(price)))
        for t, sid, price in raw_ltp
    )
    return MarketHistory(
        market_id=str(row["market_id"]),
        event_id=str(row["event_id"]),
        event_name=str(row["event_name"]),
        market_type=str(row["market_type"]),
        country_code=str(row["country_code"]),
        market_time_ms=int(str(row["market_time_ms"])),
        runners=runners,
        observations=observations,
        went_in_play=bool(row["went_in_play"]),
    )
