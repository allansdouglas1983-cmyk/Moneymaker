"""Betfair Historical BASIC reader — exchange prices, pre-off only.

Every measurement in this package so far has used **bookmaker closing prices**, which carry
a 4.4% overround and are a displayed line rather than a transactable one. Exchange prices
are the one genuinely untested case: no overround, commission charged on the net market
result instead, and a price someone will actually trade at. This module is what turns a
Betfair Historical download into that test.

**What BASIC is.** ``EX_LTP`` + ``EX_MARKET_DEF``, delivered at one-minute intervals, and
``ltp`` is sent **only when it changes** — it is not repeated in every message. A reader
that expects a price in every message reports "no price" at exactly the horizons where the
market was quiet, which is the opposite of the truth. :meth:`MarketHistory.ltp_at` therefore
carries the last observed price forward and returns ``None`` only genuinely before the first
trade.

BASIC carries no ladder and no traded volume, so it supports a *last-trade trace*, not a
quoted book. It cannot answer depth-aware execution questions (that needs ADVANCED or PRO)
and this module does not pretend otherwise.

**Two guards, both refusals rather than filters.**

* **Pre-off only.** A hard prohibition of the programme, every sport. In-play observations
  are dropped at parse time, and asking for a price at or after the off raises
  :class:`InPlayRefusedError` rather than returning something plausible.
* **BSP is quarantined.** Betfair Starting Price is a reconciled *settlement-time closing
  benchmark*. SPEC-021 requires it be unreachable from any pre-event feature and to join
  only at grading time. It is therefore not an attribute of a :class:`MarketHistory`; it
  exists only behind :meth:`MarketHistory.grading_view`, which returns ``None`` until the
  market has actually settled.

Prices are exact :class:`~decimal.Decimal` values on the canonical ladder, never floats
(SPEC-053). An off-ladder value is a defect in the input and is refused.
"""
from __future__ import annotations

import bz2
import json
import tarfile
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Sequence

from price_contracts.ladder import index_of, is_on_ladder

__all__ = [
    "BspQuarantineError",
    "InPlayRefusedError",
    "Runner",
    "LtpObservation",
    "LadderLevel",
    "LadderObservation",
    "VolumeObservation",
    "GradingView",
    "MarketHistory",
    "read_markets",
    "read_market_messages",
    "iter_messages",
]

#: v1 prices Match Odds only, and that stays the default. Set and game markets are a
#: different settlement policy and a different choice set, so they are never silently
#: treated as a match market — a caller that wants them must ask for them by name.
MARKET_TYPE = "MATCH_ODDS"

#: Types a cross-market reader may ask for. SET_BETTING is the useful companion to
#: MATCH_ODDS because the two are related by identity rather than by model: for a
#: best-of-three, P(A wins) is exactly P(A 2-0) + P(A 2-1). Any gap between them is the two
#: markets disagreeing with each other, which needs no forecast to detect.
CROSS_MARKET_TYPES = ("MATCH_ODDS", "SET_BETTING", "NUMBER_OF_SETS", "COMBINED_TOTAL",
                      "HANDICAP")


class InPlayRefusedError(RuntimeError):
    """An in-play price was requested. Pre-off only — this is not a tunable."""


class BspQuarantineError(RuntimeError):
    """A closing benchmark was reached from a pre-event path (SPEC-021)."""


@dataclass(frozen=True)
class Runner:
    """One selection as the market defined it."""

    selection_id: int
    name: str
    status: str
    sort_priority: int


@dataclass(frozen=True)
class LtpObservation:
    """One last-traded price, pre-off, on the canonical ladder."""

    publish_time_ms: int
    selection_id: int
    price: Decimal

    @property
    def tick_index(self) -> int:
        return index_of(self.price)


@dataclass(frozen=True)
class LadderLevel:
    """One side of the book: a price you could transact at, and how much is there."""

    price: Decimal
    size: Decimal

    @property
    def tick_index(self) -> int:
        return index_of(self.price)


@dataclass(frozen=True)
class VolumeObservation:
    """Cumulative matched volume on one selection at one instant (ADVANCED ``tv``).

    Where the money actually went, as opposed to what the displayed price says. It is one
    of the few signals available here that is not a restatement of the price itself.
    """

    publish_time_ms: int
    selection_id: int
    volume: Decimal


@dataclass(frozen=True)
class LadderObservation:
    """Best back/lay for one selection at one instant (ADVANCED ``batb``/``batl``).

    ``None`` on a side means the book was empty there. Betfair signals that with an empty
    array, and carrying the previous level forward would invent liquidity that no longer
    exists — the difference between a price you could have taken and one you could not.
    """

    publish_time_ms: int
    selection_id: int
    best_back: LadderLevel | None
    best_lay: LadderLevel | None


@dataclass(frozen=True)
class GradingView:
    """Settlement-time facts. Reachable only after the market closed, never from features.

    This type exists so that BSP has exactly one door, and that door is named after what it
    is for. Anything that holds a :class:`GradingView` is by construction doing grading, not
    building a feature.
    """

    market_id: str
    bsp: Mapping[int, Decimal]
    winner_selection_id: int | None
    runner_status: Mapping[int, str]


@dataclass(frozen=True)
class MarketHistory:
    """One market's pre-off last-trade trace, plus its definition.

    Deliberately does **not** carry BSP, settled results, or any in-play observation.
    """

    market_id: str
    event_id: str
    event_name: str
    market_type: str
    country_code: str
    #: Scheduled off, milliseconds since epoch. The live system knows this; it does not
    #: know the actual off (SPEC-022).
    market_time_ms: int
    runners: tuple[Runner, ...]
    observations: tuple[LtpObservation, ...]
    went_in_play: bool
    #: ADVANCED only. Empty for BASIC, which carries no ladder at all.
    ladders: tuple[LadderObservation, ...] = ()
    volumes: tuple[VolumeObservation, ...] = ()
    _grading: GradingView | None = None

    def ltp_at(self, selection_id: int, *, seconds_before_off: int) -> Decimal | None:
        """Last traded price at a horizon before the scheduled off.

        Carries the last observation forward, because BASIC sends ``ltp`` only when it
        changes — a quiet market still has a price. Returns ``None`` only when nothing has
        traded yet, which is a real state and never a guess.
        """
        if seconds_before_off < 0:
            raise InPlayRefusedError(
                f"seconds_before_off={seconds_before_off} is at or after the off; "
                "this platform is pre-off only and does not serve in-play prices"
            )
        cutoff = self.market_time_ms - seconds_before_off * 1000
        latest: Decimal | None = None
        for observation in self.observations:
            if observation.publish_time_ms > cutoff:
                break
            if observation.selection_id == selection_id:
                latest = observation.price
        return latest

    def tick_at(self, selection_id: int, *, seconds_before_off: int) -> int | None:
        """:meth:`ltp_at` as an integer ladder index (SPEC-053)."""
        price = self.ltp_at(selection_id, seconds_before_off=seconds_before_off)
        return None if price is None else index_of(price)

    def _ladder_at(
        self, selection_id: int, seconds_before_off: int
    ) -> LadderObservation | None:
        if seconds_before_off < 0:
            raise InPlayRefusedError(
                f"seconds_before_off={seconds_before_off} is at or after the off; "
                "this platform is pre-off only and does not serve in-play prices"
            )
        cutoff = self.market_time_ms - seconds_before_off * 1000
        latest: LadderObservation | None = None
        for observation in self.ladders:
            if observation.publish_time_ms > cutoff:
                break
            if observation.selection_id == selection_id:
                latest = observation
        return latest

    def best_back_at(
        self, selection_id: int, *, seconds_before_off: int
    ) -> LadderLevel | None:
        """Best price available **to back** at a horizon, with its size.

        This is the crossable price — what you could actually have taken — as distinct from
        :meth:`ltp_at`, which is a print of something that already happened and may not have
        been available to you.
        """
        observation = self._ladder_at(selection_id, seconds_before_off)
        return None if observation is None else observation.best_back

    def best_lay_at(
        self, selection_id: int, *, seconds_before_off: int
    ) -> LadderLevel | None:
        """Best price available to lay. Recorded for spread and book-health diagnostics;
        v1 never lays (hard prohibition)."""
        observation = self._ladder_at(selection_id, seconds_before_off)
        return None if observation is None else observation.best_lay

    def traded_volume_at(
        self, selection_id: int, *, seconds_before_off: int
    ) -> Decimal | None:
        """Cumulative matched volume at a horizon, carried forward. None before any trade."""
        if seconds_before_off < 0:
            raise InPlayRefusedError("pre-off only")
        cutoff = self.market_time_ms - seconds_before_off * 1000
        latest: Decimal | None = None
        for observation in self.volumes:
            if observation.publish_time_ms > cutoff:
                break
            if observation.selection_id == selection_id:
                latest = observation.volume
        return latest

    def grading_view(self) -> GradingView | None:
        """Settlement facts, or ``None`` if the market has not settled in this file."""
        return self._grading

    def require_no_closing_benchmark(self) -> None:
        """Assert this history carries no reconciled closing benchmark.

        The runtime half of SPEC-021's guard: a feature builder calls this to prove it is
        holding a pre-event object. It raises when settlement data is present, because at
        that point the object is a grading artefact and must not be treated as a feature
        source.
        """
        if self._grading is not None:
            raise BspQuarantineError(
                f"market {self.market_id} carries settlement data (BSP / runner results). "
                "A reconciled closing benchmark joins at grading time only and must not be "
                "reachable from a pre-event feature (SPEC-021)."
            )


def _best_level(raw: object, *, market_id: str) -> LadderLevel | None:
    """Level 0 of a batb/batl array, or ``None`` when the side is empty.

    Betfair does not guarantee level 0 appears first, so the level index is honoured rather
    than the array order. A zero-size level is not liquidity and reads as absent.
    """
    if not isinstance(raw, list) or not raw:
        return None
    best: LadderLevel | None = None
    best_index: int | None = None
    for entry in raw:
        if not isinstance(entry, list) or len(entry) < 3:
            continue
        level = int(entry[0])
        size = Decimal(str(entry[2]))
        if size <= 0:
            continue
        if best_index is None or level < best_index:
            best_index = level
            best = LadderLevel(
                price=_decimal_price(entry[1], market_id=market_id), size=size
            )
    return best


def _decimal_price(raw: object, *, market_id: str) -> Decimal:
    price = Decimal(str(raw))
    if not is_on_ladder(price):
        raise ValueError(
            f"market {market_id}: price {price} is off-ladder. Betfair prices are always "
            "on the canonical ladder; an off-ladder value means the input is corrupt or "
            "is not a Betfair exchange price."
        )
    return price


def _open_stream(path: Path) -> Iterator[str]:
    if path.suffix == ".bz2":
        yield from bz2.decompress(path.read_bytes()).decode("utf-8").splitlines()
    else:
        yield from path.read_text(encoding="utf-8", errors="replace").splitlines()


def iter_messages(path: Path | str) -> Iterator[dict[str, object]]:
    """Yield every market-change message from a file, archive or directory tree.

    Handles the shapes Betfair actually ships: a ``.tar`` holding one ``.bz2`` per market,
    a bare ``.bz2``, a plain JSON-lines file, or a directory of any of those.
    """
    target = Path(path)
    if target.is_dir():
        for child in sorted(target.rglob("*")):
            if child.is_file():
                yield from iter_messages(child)
        return

    if tarfile.is_tarfile(target):
        with tarfile.open(target) as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                handle = tar.extractfile(member)
                if handle is None:  # pragma: no cover - isfile() established this
                    continue
                raw = handle.read()
                if member.name.endswith(".bz2"):
                    raw = bz2.decompress(raw)
                for line in raw.decode("utf-8", errors="replace").splitlines():
                    yield from _parse_line(line, source=member.name)
        return

    for line in _open_stream(target):
        yield from _parse_line(line, source=str(target))


def _parse_line(line: str, *, source: str) -> Iterator[dict[str, object]]:
    stripped = line.strip()
    if not stripped:
        return
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed message in {source}: {exc}") from exc
    if isinstance(payload, dict):
        yield payload


@dataclass
class _Accumulator:
    """Mutable per-market state while streaming. Never escapes this module."""

    definition: dict[str, object] | None = None
    observations: list[LtpObservation] | None = None
    ladders: list[LadderObservation] | None = None
    volumes: list[VolumeObservation] | None = None
    #: Running best back/lay per selection, so a one-sided delta carries the other side.
    book: dict[int, tuple["LadderLevel | None", "LadderLevel | None"]] | None = None
    went_in_play: bool = False
    settled: dict[str, object] | None = None

    def __post_init__(self) -> None:
        if self.observations is None:
            self.observations = []
        if self.ladders is None:
            self.ladders = []
        if self.book is None:
            self.book = {}
        if self.volumes is None:
            self.volumes = []


def _market_time_ms(definition: Mapping[str, object]) -> int:
    import datetime as dt

    raw = str(definition.get("marketTime", ""))
    parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return int(parsed.timestamp() * 1000)


def read_markets(
    path: Path | str, *, market_types: Sequence[str] = (MARKET_TYPE,)
) -> tuple[MarketHistory, ...]:
    """Read every Match Odds market under ``path`` into a pre-off history.

    In-play observations are dropped as they are read, so they are never present to be
    filtered later. Settlement data is routed to a :class:`GradingView` and kept off the
    history itself.

    Holds every market it finds in memory. That is right for a file or a day; the eleven-year
    archive is 1.1 million markets and does not fit, which is what
    :func:`read_market_messages` exists for.
    """
    return read_market_messages(iter_messages(path), market_types=market_types)


def read_market_messages(
    messages: Iterable[Mapping[str, object]],
    *,
    market_types: Sequence[str] = (MARKET_TYPE,),
) -> tuple[MarketHistory, ...]:
    """:func:`read_markets` over an already-open message stream.

    Identical accumulation, identical guarantees — this is the same function body, with the
    source of messages lifted out so a caller streaming a large archive can hand it one
    market's messages at a time and never hold the whole archive. Extracted rather than
    reimplemented on purpose: a second copy of the in-play drop or the BSP quarantine is a
    second place for them to be wrong.
    """
    wanted = set(market_types)
    accumulators: dict[str, _Accumulator] = {}

    for message in messages:
        publish_time = message.get("pt")
        changes = message.get("mc")
        if not isinstance(changes, list):
            continue
        for change in changes:
            if not isinstance(change, dict):
                continue
            market_id = str(change.get("id", ""))
            if not market_id:
                continue
            state = accumulators.setdefault(market_id, _Accumulator())

            definition = change.get("marketDefinition")
            if isinstance(definition, dict):
                if bool(definition.get("inPlay")):
                    state.went_in_play = True
                if str(definition.get("status", "")).upper() == "CLOSED":
                    state.settled = definition
                elif not state.went_in_play:
                    state.definition = definition
                if state.definition is None:
                    state.definition = definition

            if state.went_in_play or not isinstance(publish_time, int):
                continue
            for runner_change in change.get("rc", ()) or ():
                if not isinstance(runner_change, dict) or "id" not in runner_change:
                    continue
                if "batb" in runner_change or "batl" in runner_change:
                    assert state.ladders is not None
                    assert state.book is not None
                    selection = int(runner_change["id"])
                    back, lay = state.book.get(selection, (None, None))
                    # Betfair sends batb and batl as SEPARATE deltas. An ABSENT key means
                    # unchanged and must carry forward; an EMPTY ARRAY means the side was
                    # cleared. Conflating them wipes half the book on every one-sided
                    # update, and the market stops having a midpoint at all.
                    if "batb" in runner_change:
                        back = _best_level(runner_change["batb"], market_id=market_id)
                    if "batl" in runner_change:
                        lay = _best_level(runner_change["batl"], market_id=market_id)
                    state.book[selection] = (back, lay)
                    state.ladders.append(
                        LadderObservation(
                            publish_time_ms=publish_time,
                            selection_id=selection,
                            best_back=back,
                            best_lay=lay,
                        )
                    )
                # ltp == 0 is ADVANCED's "nothing has traded yet" sentinel, not a price.
                # 0.0 implies infinite odds; it is absence, and absence is what it reads as.
                if runner_change.get("tv") is not None:
                    assert state.volumes is not None
                    state.volumes.append(VolumeObservation(
                        publish_time_ms=publish_time,
                        selection_id=int(runner_change["id"]),
                        volume=Decimal(str(runner_change["tv"])),
                    ))
                if not runner_change.get("ltp"):
                    continue
                assert state.observations is not None
                state.observations.append(
                    LtpObservation(
                        publish_time_ms=publish_time,
                        selection_id=int(runner_change["id"]),
                        price=_decimal_price(runner_change["ltp"], market_id=market_id),
                    )
                )

    histories: list[MarketHistory] = []
    for market_id, state in accumulators.items():
        definition = state.definition
        if definition is None:
            continue
        if str(definition.get("marketType", "")) not in wanted:
            continue
        off_ms = _market_time_ms(definition)
        assert state.observations is not None
        assert state.ladders is not None
        assert state.volumes is not None
        pre_off = tuple(sorted(
            (o for o in state.observations if o.publish_time_ms <= off_ms),
            key=lambda o: (o.publish_time_ms, o.selection_id),
        ))
        histories.append(
            MarketHistory(
                market_id=market_id,
                event_id=str(definition.get("eventId", "")),
                event_name=str(definition.get("eventName", "")),
                market_type=str(definition.get("marketType", "")),
                country_code=str(definition.get("countryCode", "")),
                market_time_ms=off_ms,
                runners=_runners(definition),
                observations=pre_off,
                went_in_play=state.went_in_play,
                volumes=tuple(sorted(
                    (v for v in state.volumes if v.publish_time_ms <= off_ms),
                    key=lambda v: (v.publish_time_ms, v.selection_id),
                )),
                ladders=tuple(sorted(
                    (rung for rung in state.ladders if rung.publish_time_ms <= off_ms),
                    key=lambda rung: (rung.publish_time_ms, rung.selection_id),
                )),
                _grading=_grading_view(market_id, state.settled),
            )
        )
    return tuple(histories)


def _runners(definition: Mapping[str, object]) -> tuple[Runner, ...]:
    raw = definition.get("runners")
    if not isinstance(raw, Sequence):
        return ()
    return tuple(
        Runner(
            selection_id=int(entry["id"]),
            name=str(entry.get("name", "")),
            status=str(entry.get("status", "")),
            sort_priority=int(entry.get("sortPriority", 0)),
        )
        for entry in raw
        if isinstance(entry, dict) and "id" in entry
    )


def _grading_view(market_id: str, settled: Mapping[str, object] | None) -> GradingView | None:
    if settled is None:
        return None
    bsp: dict[int, Decimal] = {}
    status: dict[int, str] = {}
    winner: int | None = None
    raw = settled.get("runners")
    if isinstance(raw, Sequence):
        for entry in raw:
            if not isinstance(entry, dict) or "id" not in entry:
                continue
            selection_id = int(entry["id"])
            status[selection_id] = str(entry.get("status", ""))
            if entry.get("bsp") is not None:
                bsp[selection_id] = Decimal(str(entry["bsp"]))
            if str(entry.get("status", "")).upper() == "WINNER":
                winner = selection_id
    return GradingView(
        market_id=market_id, bsp=bsp, winner_selection_id=winner, runner_status=status
    )
