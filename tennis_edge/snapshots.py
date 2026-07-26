"""Extract per-horizon market snapshots once, so experiments iterate in seconds.

Reading 20,482 compressed market files and replaying ~45 hours of one-second messages each
costs minutes. Every experiment that wanted a different question asked of the same prices
paid that cost again, which is a tax on trying things — and trying things is the whole job
at this stage.

This extracts what any price experiment actually needs — the two-sided book, the traded
volume and the outcome at a fixed set of horizons — into one compact JSONL. Downstream
experiments then load in under a second.

The cache is a **derived artefact, keyed by the corpus it came from**: it records the source
path, the horizons, and the count, and :func:`load_snapshots` refuses a cache built for
different horizons rather than silently answering a different question than the one asked.

No outcome-dependent field is ever written beyond the settled result itself, and the result
is written last and read only at scoring time — the same discipline as everywhere else.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from price_contracts.ladder import index_of
from tennis_edge.betfair import MarketHistory
from tennis_edge.exchange_link import LinkedMarket

__all__ = [
    "HORIZONS",
    "HorizonState",
    "MarketSnapshot",
    "extract_snapshots",
    "write_snapshots",
    "load_snapshots",
]

#: Seconds before the scheduled off. Spans market formation (24h) to just before the off.
HORIZONS: tuple[int, ...] = (86_400, 43_200, 21_600, 10_800, 3_600, 1_800, 600, 120)


@dataclass(frozen=True)
class HorizonState:
    """Both sides of the book for one market at one horizon."""

    horizon: int
    back_a: float
    back_b: float
    lay_a: float
    lay_b: float
    size_back_a: float
    size_back_b: float
    size_lay_a: float
    size_lay_b: float
    volume_a: float
    volume_b: float

    @property
    def midpoint_a(self) -> float:
        """Normalised midpoint probability for A — the estimator, not the tradeable price."""
        imp_a = (1.0 / self.back_a + 1.0 / self.lay_a) / 2.0
        imp_b = (1.0 / self.back_b + 1.0 / self.lay_b) / 2.0
        return imp_a / (imp_a + imp_b)

    @property
    def spread_ticks_a(self) -> int:
        from decimal import Decimal

        return index_of(Decimal(str(self.lay_a))) - index_of(Decimal(str(self.back_a)))

    @property
    def size_imbalance_a(self) -> float:
        """Back-side depth on A as a share of both sides. 0.5 is balanced."""
        total = self.size_back_a + self.size_lay_a
        return 0.5 if total <= 0 else self.size_back_a / total

    @property
    def volume_share_a(self) -> float:
        """Share of matched money that went on A. 0.5 when nothing has traded."""
        total = self.volume_a + self.volume_b
        return 0.5 if total <= 0 else self.volume_a / total


@dataclass(frozen=True)
class MarketSnapshot:
    """One market: its identity, its states, and its settled result.

    ``player_a``/``player_b`` are the **corpus** names the identity bridge resolved this
    market to, not the Betfair aliases. They are carried so a downstream experiment can join
    a snapshot back to a model's view of the same match by name instead of guessing from
    date and outcome, which on a busy day pairs the wrong two things — and a wrong pairing is
    indistinguishable from a wrong model.
    """

    market_id: str
    event_name: str
    match_date: str
    tour: str
    surface: str
    best_of: int
    market_time_ms: int
    won_a: int
    player_a: str
    player_b: str
    states: tuple[HorizonState, ...]

    def at(self, horizon: int) -> HorizonState | None:
        for state in self.states:
            if state.horizon == horizon:
                return state
        return None


def _state(history: MarketHistory, a: int, b: int, horizon: int) -> HorizonState | None:
    back_a = history.best_back_at(a, seconds_before_off=horizon)
    back_b = history.best_back_at(b, seconds_before_off=horizon)
    lay_a = history.best_lay_at(a, seconds_before_off=horizon)
    lay_b = history.best_lay_at(b, seconds_before_off=horizon)
    if back_a is None or back_b is None or lay_a is None or lay_b is None:
        return None
    volume_a = history.traded_volume_at(a, seconds_before_off=horizon)
    volume_b = history.traded_volume_at(b, seconds_before_off=horizon)
    return HorizonState(
        horizon=horizon,
        back_a=float(back_a.price), back_b=float(back_b.price),
        lay_a=float(lay_a.price), lay_b=float(lay_b.price),
        size_back_a=float(back_a.size), size_back_b=float(back_b.size),
        size_lay_a=float(lay_a.size), size_lay_b=float(lay_b.size),
        volume_a=float(volume_a or 0), volume_b=float(volume_b or 0),
    )


def extract_snapshots(
    linked: Sequence[LinkedMarket], *, horizons: Sequence[int] = HORIZONS
) -> list[MarketSnapshot]:
    """Pull every horizon state from already-linked markets."""
    out: list[MarketSnapshot] = []
    for row in linked:
        a = row.selection_for_player_a
        b = (row.quote.selection_b if a == row.quote.selection_a
             else row.quote.selection_a)
        states = tuple(
            state for state in
            (_state(row.market, a, b, horizon) for horizon in horizons)
            if state is not None
        )
        if not states:
            continue
        out.append(MarketSnapshot(
            market_id=row.market.market_id,
            event_name=row.market.event_name,
            match_date=row.match.match_date.isoformat(),
            tour=row.match.tour,
            surface=row.match.surface,
            best_of=row.match.best_of,
            market_time_ms=row.market.market_time_ms,
            won_a=1 if row.match.winner_is_a else 0,
            player_a=row.match.player_a,
            player_b=row.match.player_b,
            states=states,
        ))
    return out


def write_snapshots(
    path: Path | str, snapshots: Sequence[MarketSnapshot], *,
    source: str, horizons: Sequence[int] = HORIZONS,
) -> None:
    """Write the cache with a header recording what it was built from."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "kind": "market-snapshot-cache-v2",
            "source": source,
            "horizons": list(horizons),
            "markets": len(snapshots),
        }, sort_keys=True) + "\n")
        for snapshot in snapshots:
            handle.write(json.dumps(asdict(snapshot), sort_keys=True,
                                    separators=(",", ":")) + "\n")


def load_snapshots(
    path: Path | str, *, horizons: Sequence[int] = HORIZONS
) -> list[MarketSnapshot]:
    """Load a cache, refusing one built for different horizons.

    Silently answering with a cache built for a different horizon set would answer a
    different question than the one asked, and the mismatch would be invisible in the
    output.
    """
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError(f"empty snapshot cache: {path}")
    header = json.loads(lines[0])
    if header.get("kind") != "market-snapshot-cache-v2":
        raise ValueError(f"not a snapshot cache: {path}")
    if tuple(header.get("horizons", ())) != tuple(horizons):
        raise ValueError(
            f"cache was built for horizons {header.get('horizons')}, asked for "
            f"{list(horizons)} — rebuild rather than answering a different question"
        )
    out: list[MarketSnapshot] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        raw = json.loads(line)
        raw["states"] = tuple(HorizonState(**s) for s in raw["states"])
        out.append(MarketSnapshot(**raw))
    return out
