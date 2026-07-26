"""Append-only evaluation ledger.

One line of JSON per match, never rewritten. The append-only property is what makes the
weekly job safe to re-run: a match already recorded is skipped, so a job that dies halfway
through, or fires twice, cannot double-count or silently revise a past decision.

Each row carries the **policy digest and the code commit that produced it**, alongside the
data vintage. That is the integrity claim of this whole exercise: the rule was committed to
git at a hash dated before these matches existed, and anyone can check that rather than
taking it on trust.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

from tennis_edge.metrics import brier, log_loss

__all__ = ["MIN_INTERPRETABLE_BETS", "LedgerRow", "Ledger", "Summary", "summarise"]

#: Below this many recommendations a return-per-unit figure is reported as a total only,
#: never as a percentage. A handful of bets can show any yield at all — two winners at 3.0
#: read as "+77% per unit", which is a number about sample size, not about edge. The same
#: floor guards the variant sweep in ``consensus.py`` for the same reason.
MIN_INTERPRETABLE_BETS = 200


@dataclass(frozen=True)
class LedgerRow:
    """One evaluated match. Outcome included: this is evaluation, not a pre-match record."""

    match_key: str
    match_date: str
    tour: str
    player_a: str
    player_b: str
    tier: str
    surface: str
    status: str
    book: str | None
    market_probability_a: float | None
    model_probability_a: float | None
    blended_probability_a: float | None
    quoted_odds: float | None
    side: str | None
    expected_value: float | None
    reason: str
    winner_is_a: bool
    policy_version: str
    policy_digest: str
    code_commit: str
    data_vintage: str
    recorded_utc: str

    def to_json(self) -> str:
        return json.dumps(self.__dict__, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, line: str) -> "LedgerRow":
        return cls(**json.loads(line))

    @property
    def realised_return(self) -> float | None:
        """Unit return of a recommendation at the recorded price, or None if none was made.

        Commission is charged on the win only, which is how an exchange bills it. This is a
        reporting figure on a notional unit; no stake exists and none is implied.
        """
        if self.quoted_odds is None or self.side is None:
            return None
        won = self.winner_is_a if self.side == "A" else not self.winner_is_a
        if not won:
            return -1.0
        from tennis_edge.policy import COMMISSION

        return (self.quoted_odds - 1.0) * (1.0 - COMMISSION)


def match_key(match_date: dt.date, tour: str, player_a: str, player_b: str) -> str:
    """Stable identity for a match. A pair can meet once per tour per day."""
    return f"{match_date.isoformat()}|{tour}|{player_a}|{player_b}"


class Ledger:
    """Append-only JSONL store. Reads are cheap; writes never modify an existing line."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._keys: set[str] | None = None

    @property
    def path(self) -> Path:
        return self._path

    def rows(self) -> Iterator[LedgerRow]:
        if not self._path.exists():
            return
        for line in self._path.read_text().splitlines():
            if line.strip():
                yield LedgerRow.from_json(line)

    def keys(self) -> set[str]:
        """Match keys already recorded. Cached, because the weekly job asks once per match."""
        if self._keys is None:
            self._keys = {row.match_key for row in self.rows()}
        return self._keys

    def contains(self, key: str) -> bool:
        return key in self.keys()

    def append(self, rows: Sequence[LedgerRow]) -> int:
        """Append rows whose keys are not already present. Returns how many were written."""
        known = self.keys()
        fresh = [r for r in rows if r.match_key not in known]
        if not fresh:
            return 0
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            for row in fresh:
                handle.write(row.to_json() + "\n")
                known.add(row.match_key)
        return len(fresh)


@dataclass(frozen=True)
class Summary:
    """What the ledger says so far."""

    rows: int
    scored: int
    market_log_loss: float | None
    market_brier: float | None
    model_log_loss: float | None
    blended_log_loss: float | None
    status_counts: dict[str, int]
    recommendations: int
    recommendation_return: float | None
    first_date: str | None
    last_date: str | None

    def report(self) -> str:
        lines = [
            f"ledger: {self.rows:,} matches"
            + (f", {self.first_date} to {self.last_date}" if self.first_date else ""),
            f"  scored against the market: {self.scored:,}",
        ]
        if self.market_log_loss is not None:
            lines.append(f"  market   log loss {self.market_log_loss:.5f}"
                         f"  brier {self.market_brier:.5f}")
        if self.blended_log_loss is not None:
            lines.append(f"  blended  log loss {self.blended_log_loss:.5f}")
        if self.model_log_loss is not None:
            lines.append(f"  model    log loss {self.model_log_loss:.5f}")
        lines.append("  statuses: " + ", ".join(
            f"{k}={v}" for k, v in sorted(self.status_counts.items())))
        if self.recommendations:
            assert self.recommendation_return is not None
            line = (f"  recommendations: {self.recommendations:,}, "
                    f"unit return {self.recommendation_return:+.2f}")
            if self.recommendations >= MIN_INTERPRETABLE_BETS:
                roi = 100.0 * self.recommendation_return / self.recommendations
                line += f" ({roi:+.2f}% per unit)"
            else:
                line += (f" (no rate shown: under {MIN_INTERPRETABLE_BETS} bets a "
                         f"percentage is noise, not a yield)")
            lines.append(line)
        else:
            lines.append("  recommendations: none")
        return "\n".join(lines)


def summarise(rows: Sequence[LedgerRow]) -> Summary:
    """Score the ledger. Model and market are scored on exactly the same matches."""
    statuses: dict[str, int] = {}
    for row in rows:
        statuses[row.status] = statuses.get(row.status, 0) + 1

    market: list[float] = []
    model: list[float] = []
    blended: list[float] = []
    outcomes: list[int] = []
    for row in rows:
        if row.market_probability_a is None or row.blended_probability_a is None:
            continue
        market.append(row.market_probability_a)
        blended.append(row.blended_probability_a)
        model.append(
            row.model_probability_a if row.model_probability_a is not None
            else row.market_probability_a
        )
        outcomes.append(1 if row.winner_is_a else 0)

    returns = [r.realised_return for r in rows if r.realised_return is not None]
    dates = sorted(r.match_date for r in rows)
    return Summary(
        rows=len(rows), scored=len(outcomes),
        market_log_loss=log_loss(market, outcomes) if outcomes else None,
        market_brier=brier(market, outcomes) if outcomes else None,
        model_log_loss=log_loss(model, outcomes) if outcomes else None,
        blended_log_loss=log_loss(blended, outcomes) if outcomes else None,
        status_counts=statuses,
        recommendations=len(returns),
        recommendation_return=math.fsum(returns) if returns else None,
        first_date=dates[0] if dates else None,
        last_date=dates[-1] if dates else None,
    )
