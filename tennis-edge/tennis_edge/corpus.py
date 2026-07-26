"""The typed match corpus, read from Tennis-Data.co.uk vintage files.

One structural decision dominates this module. The provider stores every row
**winner-first** (`Winner`, `LRank`, `PSW`…), so the column layout itself encodes the
outcome. Any code that reads `Winner` as "player A" has already leaked the result into its
features. So the loader immediately re-orients each row into a neutral (`player_a`,
`player_b`) pair ordered by name, and records the outcome in exactly one place —
:attr:`Match.winner_is_a`. Every downstream consumer sees a symmetric row and has to be
told who won.

Odds are loaded and kept. They are **evaluation and execution data**: the benchmark to beat
and the price a bet is struck at. They are not model inputs — that separation is enforced by
the feature registry, not by pretending the columns do not exist. Refusing to load them (the
previous design) made honest backtesting impossible.
"""
from __future__ import annotations

import datetime as dt
import os
import re
from dataclasses import dataclass
from enum import Enum, unique
from pathlib import Path
from typing import Any, Iterator, Sequence

import openpyxl
import xlrd

__all__ = [
    "Completion",
    "OddsQuotes",
    "Match",
    "CorpusStats",
    "load_corpus",
    "default_vintage_root",
]

_DATE_FORMATS = ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d")

_COMPLETION_PREFIXES = (
    ("completed", "COMPLETED"),
    ("retired", "RETIRED"),
    ("walkover", "WALKOVER"),
    ("awarded", "AWARDED"),
    ("abandoned", "ABANDONED"),
    ("disqualified", "DISQUALIFIED"),
    ("cancelled", "CANCELLED"),
    ("sched", "SCHEDULED"),
    # Provider typos catalogued in the 2026-07-18 acceptance audit. Mapping them is not
    # "repairing history" — the intent is unambiguous and the alternative is silently
    # dropping real completed matches.
    ("rrtired", "RETIRED"),
    ("walkoer", "WALKOVER"),
)


@unique
class Completion(Enum):
    """How a match ended. Only COMPLETED rows may train a model."""

    COMPLETED = "COMPLETED"
    RETIRED = "RETIRED"
    WALKOVER = "WALKOVER"
    AWARDED = "AWARDED"
    ABANDONED = "ABANDONED"
    DISQUALIFIED = "DISQUALIFIED"
    CANCELLED = "CANCELLED"
    SCHEDULED = "SCHEDULED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class OddsQuotes:
    """Quoted decimal odds for the neutral (a, b) pair. Evaluation/execution only.

    ``None`` means the provider had no price, which is common in early years and for
    Betfair Exchange columns before ~2025. A missing price is never imputed.
    """

    b365_a: float | None = None
    b365_b: float | None = None
    pinnacle_a: float | None = None
    pinnacle_b: float | None = None
    max_a: float | None = None
    max_b: float | None = None
    avg_a: float | None = None
    avg_b: float | None = None
    betfair_a: float | None = None
    betfair_b: float | None = None

    def pair(self, book: str) -> tuple[float, float] | None:
        """Both sides of one book's price, or None unless both are present."""
        first = getattr(self, f"{book}_a")
        second = getattr(self, f"{book}_b")
        if first is None or second is None:
            return None
        return (float(first), float(second))


@dataclass(frozen=True)
class Match:
    """One match in neutral orientation. ``winner_is_a`` is the only outcome field."""

    match_date: dt.date
    tour: str
    tournament: str
    location: str
    tier: str
    court: str
    surface: str
    round_name: str
    best_of: int
    player_a: str
    player_b: str
    winner_is_a: bool
    rank_a: int | None
    rank_b: int | None
    points_a: int | None
    points_b: int | None
    games_a: int | None
    games_b: int | None
    sets_a: int | None
    sets_b: int | None
    completion: Completion
    odds: OddsQuotes
    source_file: str

    @property
    def completed(self) -> bool:
        return self.completion is Completion.COMPLETED

    @property
    def winner(self) -> str:
        return self.player_a if self.winner_is_a else self.player_b

    @property
    def loser(self) -> str:
        return self.player_b if self.winner_is_a else self.player_a

    @property
    def indoor(self) -> bool:
        return self.court.strip().lower() == "indoor"

    def key(self) -> tuple[dt.date, str, str, str]:
        """Identity for de-duplication: a pair can meet once per tour per day."""
        return (self.match_date, self.tour, self.player_a, self.player_b)


@dataclass(frozen=True)
class CorpusStats:
    """The exclusion funnel. Every dropped row is counted under a named reason."""

    files_read: int
    rows_seen: int
    rows_kept: int
    exclusions: dict[str, int]
    duplicates_dropped: int
    winner_conflicts: tuple[str, ...]

    def summary(self) -> str:
        parts = ", ".join(f"{k}={v}" for k, v in sorted(self.exclusions.items()))
        return (
            f"{self.rows_kept:,} kept of {self.rows_seen:,} rows in {self.files_read} files; "
            f"duplicates={self.duplicates_dropped}, conflicts={len(self.winner_conflicts)}"
            + (f"; exclusions: {parts}" if parts else "")
        )


#: Searched in order when ``TENNIS_EDGE_DATA`` is unset.
_DATA_CANDIDATES = (Path.home() / "tennis_edge_data", Path("/home/user/tennis_edge_data"))


def default_vintage_root() -> Path:
    """Where vintages live locally. Raw provider data never enters the repository.

    Tennis-Data is free to use, but a provider corpus is still someone else's work — it
    lives outside the repo so it is never redistributed by a push.
    """
    configured = os.environ.get("TENNIS_EDGE_DATA")
    if configured:
        return Path(configured)
    for candidate in _DATA_CANDIDATES:
        if (candidate / "tennis_data").exists():
            return candidate
    return _DATA_CANDIDATES[0]


def _iter_sheet(path: Path) -> Iterator[tuple[list[str], tuple[Any, ...]]]:
    if path.suffix == ".xlsx":
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        sheet = workbook.active
        if sheet is not None:
            rows = sheet.iter_rows(values_only=True)
            header = [str(c) if c is not None else "" for c in next(rows)]
            for row in rows:
                yield header, tuple(row)
        workbook.close()
        return
    book = xlrd.open_workbook(str(path))
    sheet = book.sheet_by_index(0)
    header = [str(c.value) for c in sheet.row(0)]
    for index in range(1, sheet.nrows):
        values: list[Any] = []
        for cell in sheet.row(index):
            if cell.ctype == xlrd.XL_CELL_DATE:
                values.append(dt.datetime(*xlrd.xldate_as_tuple(cell.value, book.datemode)))
            elif cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                values.append(None)
            else:
                values.append(cell.value)
        yield header, tuple(values)


def _parse_date(value: Any) -> dt.date | None:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        for fmt in _DATE_FORMATS:
            try:
                return dt.datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
    return None


def _completion(raw: Any) -> Completion:
    text = str(raw or "Completed").strip().lower()
    for prefix, label in _COMPLETION_PREFIXES:
        if text.startswith(prefix):
            return Completion(label)
    return Completion.UNKNOWN


def _price(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 1.0 else None


def _int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _games(cells: dict[str, Any], prefix: str) -> int | None:
    total = 0
    seen = False
    for setno in range(1, 6):
        value = _int(cells.get(f"{prefix}{setno}"))
        if value is not None:
            total += value
            seen = True
    return total if seen else None


def _tour_of(name: str) -> str:
    return "ATP" if name.lower().startswith("atp") else "WTA"


def load_corpus(
    vintage: Path | str | None = None,
    *,
    completed_only: bool = True,
    not_after: dt.date | None = None,
) -> tuple[tuple[Match, ...], CorpusStats]:
    """Load every match in a vintage, neutrally oriented and chronologically sorted.

    Duplicate pair-days collapse to one row. A pair-day whose two rows disagree on the
    winner is removed entirely and reported — a contradiction in the source is not something
    to resolve by preference.
    """
    root = Path(vintage) if vintage is not None else _latest_vintage(default_vintage_root())
    files = sorted(p for p in root.iterdir() if p.suffix in (".xls", ".xlsx"))
    if not files:
        raise FileNotFoundError(f"no Tennis-Data files under {root}")

    exclusions: dict[str, int] = {}
    by_key: dict[tuple[dt.date, str, str, str], Match] = {}
    conflicted: set[tuple[dt.date, str, str, str]] = set()
    conflicts: list[str] = []
    rows_seen = 0
    duplicates = 0

    def drop(reason: str) -> None:
        exclusions[reason] = exclusions.get(reason, 0) + 1

    for path in files:
        tour = _tour_of(path.name)
        for header, row in _iter_sheet(path):
            rows_seen += 1
            cells = {name: (row[i] if i < len(row) else None)
                     for i, name in enumerate(header) if name}
            match_date = _parse_date(cells.get("Date"))
            if match_date is None:
                if any(v is not None and str(v).strip() for v in row):
                    drop("unparseable_date")
                continue
            if not_after is not None and match_date > not_after:
                drop("after_boundary")
                continue
            winner = str(cells.get("Winner") or "").strip()
            loser = str(cells.get("Loser") or "").strip()
            if not winner or not loser:
                drop("missing_player")
                continue
            if winner == loser:
                drop("self_match")
                continue
            completion = _completion(cells.get("Comment"))
            if completion is Completion.UNKNOWN:
                drop("unknown_completion")
                continue
            if completed_only and completion is not Completion.COMPLETED:
                drop(f"not_completed_{completion.value.lower()}")
                continue

            # Neutral orientation: name order decides, never the outcome.
            winner_is_a = winner < loser
            player_a, player_b = (winner, loser) if winner_is_a else (loser, winner)

            def side(w_value: Any, l_value: Any) -> tuple[Any, Any]:
                return (w_value, l_value) if winner_is_a else (l_value, w_value)

            rank_a, rank_b = side(_int(cells.get("WRank")), _int(cells.get("LRank")))
            points_a, points_b = side(_int(cells.get("WPts")), _int(cells.get("LPts")))
            sets_a, sets_b = side(_int(cells.get("Wsets")), _int(cells.get("Lsets")))
            games_a, games_b = side(_games(cells, "W"), _games(cells, "L"))
            odds_pairs = {}
            for attr, column in (("b365", "B365"), ("pinnacle", "PS"), ("max", "Max"),
                                 ("avg", "Avg"), ("betfair", "BFE")):
                first, second = side(_price(cells.get(f"{column}W")),
                                     _price(cells.get(f"{column}L")))
                odds_pairs[f"{attr}_a"] = first
                odds_pairs[f"{attr}_b"] = second

            match = Match(
                match_date=match_date, tour=tour,
                tournament=str(cells.get("Tournament") or "").strip(),
                location=str(cells.get("Location") or "").strip(),
                tier=str(cells.get("Series") or cells.get("Tier") or "").strip(),
                court=str(cells.get("Court") or "").strip(),
                surface=str(cells.get("Surface") or "").strip(),
                round_name=str(cells.get("Round") or "").strip(),
                best_of=_int(cells.get("Best of")) or 3,
                player_a=player_a, player_b=player_b, winner_is_a=winner_is_a,
                rank_a=rank_a, rank_b=rank_b, points_a=points_a, points_b=points_b,
                games_a=games_a, games_b=games_b, sets_a=sets_a, sets_b=sets_b,
                completion=completion, odds=OddsQuotes(**odds_pairs),
                source_file=path.name,
            )
            key = match.key()
            if key in conflicted:
                drop("winner_conflict")
                continue
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = match
                continue
            if existing.winner_is_a != match.winner_is_a:
                del by_key[key]
                conflicted.add(key)
                conflicts.append(f"{tour}:{match_date.isoformat()}:{player_a}v{player_b}")
                drop("winner_conflict")
            else:
                duplicates += 1

    ordered = tuple(sorted(by_key.values(),
                           key=lambda m: (m.match_date, m.tour, m.player_a, m.player_b)))
    stats = CorpusStats(
        files_read=len(files), rows_seen=rows_seen, rows_kept=len(ordered),
        exclusions=exclusions, duplicates_dropped=duplicates,
        winner_conflicts=tuple(sorted(conflicts)),
    )
    return ordered, stats


def _latest_vintage(root: Path) -> Path:
    base = root / "tennis_data"
    if not base.exists():
        raise FileNotFoundError(
            f"no corpus at {base}; set TENNIS_EDGE_DATA or run the refresh command"
        )
    vintages = sorted(p for p in base.iterdir() if p.is_dir() and p.name.startswith("vintage-"))
    if not vintages:
        raise FileNotFoundError(f"no vintage directories under {base}")
    return vintages[-1]


def group_by_day(matches: Sequence[Match]) -> list[tuple[dt.date, list[Match]]]:
    """Chronological day batches — the unit for predict-then-update and for clustering.

    Ratings must be updated a whole day at a time, otherwise a match played earlier on the
    same day informs the prediction of a later one, which the live system could never do.
    """
    days: dict[dt.date, list[Match]] = {}
    for match in matches:
        days.setdefault(match.match_date, []).append(match)
    return [(day, days[day]) for day in sorted(days)]


_ODDS_COLUMN_RE = re.compile(r"^(B365|B&W|CB|EX|IW|LB|GB|PS|SB|SJ|UB|Max|Avg|BFE)[WL]$")


def is_odds_column(name: str) -> bool:
    """True for any provider odds column — used by the feature registry's ban list."""
    return bool(_ODDS_COLUMN_RE.match(name))
