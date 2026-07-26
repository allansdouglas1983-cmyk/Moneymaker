"""Jeff Sackmann's match archive — per-match serve and return statistics.

Why this module exists: the Tennis-Data corpus has prices but no in-match detail, so every
feature we can build from it is a summary of *who beat whom*. That is exactly the
information a betting market prices first and best, which is why our rating layer measured
zero incremental value over the closing line. Serve and return counts are the first
genuinely different information we have — they are what the Barnett-Clarke/O'Malley
point-based models are built on.

**Provenance, and a correction worth recording.** ``JeffSackmann/tennis_atp`` and
``tennis_wta`` are no longer reachable on GitHub: Software Heritage's crawler recorded a
successful full archive of the ATP repo on 2026-05-08 and then ``not_found`` on 2026-06-16;
the WTA repo archived on 2025-01-03 and returned ``not_found`` on 2026-07-03. The data here
is restored from those Software Heritage archives, so ATP coverage runs to May 2026 and WTA
to the end of the 2024 season. That asymmetry is real and must be respected in any split.

**Licence.** CC BY-NC-SA 4.0 — attribution to Jeff Sackmann / Tennis Abstract, non-commercial
use only. Private research and a single user's own staking sit inside that; selling tips,
redistributing the data, or shipping it in a product does not. The files stay outside the
repository and are never committed.
"""
from __future__ import annotations

import csv
import datetime as dt
import os
from dataclasses import dataclass
from enum import Enum, unique
from pathlib import Path
from typing import Iterator, Sequence

__all__ = [
    "Level",
    "ServeLine",
    "SackmannMatch",
    "default_root",
    "available_files",
    "load_matches",
]


@unique
class Level(Enum):
    """Sackmann's ``tourney_level`` codes, plus the file family a row came from."""

    GRAND_SLAM = "G"
    MASTERS = "M"
    TOUR = "A"
    CHALLENGER = "C"
    ITF = "S"
    FINALS = "F"
    DAVIS_CUP = "D"
    OTHER = "?"

    @classmethod
    def parse(cls, raw: str) -> "Level":
        try:
            return cls(raw.strip().upper()[:1])
        except ValueError:
            return cls.OTHER


@dataclass(frozen=True)
class ServeLine:
    """One player's serve line for one match. Counts, not percentages.

    Percentages are derived on demand because the denominators differ and a ratio of two
    small counts is not a probability — a player who won 3 of 4 second serves has not got a
    75% second-serve skill, and shrinkage needs the raw counts to do its job.
    """

    aces: int | None
    double_faults: int | None
    serve_points: int | None
    first_in: int | None
    first_won: int | None
    second_won: int | None
    serve_games: int | None
    break_points_saved: int | None
    break_points_faced: int | None

    @property
    def complete(self) -> bool:
        """True when the fields the point model needs are all present and coherent."""
        if self.serve_points is None or self.first_in is None:
            return False
        if self.first_won is None or self.second_won is None:
            return False
        return self.serve_points > 0 and 0 <= self.first_in <= self.serve_points

    @property
    def serve_points_won(self) -> int | None:
        if self.first_won is None or self.second_won is None:
            return None
        return self.first_won + self.second_won

    @property
    def second_serve_points(self) -> int | None:
        """Second serves attempted, which by ATP convention includes double faults."""
        if self.serve_points is None or self.first_in is None:
            return None
        return self.serve_points - self.first_in


@dataclass(frozen=True)
class SackmannMatch:
    """One archive row, oriented winner/loser as the source stores it.

    Unlike :class:`tennis_edge.corpus.Match` this is *not* re-oriented, because nothing here
    is fed to a model directly — it is aggregated into per-player histories first, and an
    aggregate over a player's own matches cannot leak the result of a future one.
    """

    tourney_id: str
    tourney_name: str
    tourney_date: dt.date
    level: Level
    surface: str
    round_name: str
    best_of: int
    match_num: int
    tour: str
    winner_id: str
    winner_name: str
    loser_id: str
    loser_name: str
    winner_rank: int | None
    loser_rank: int | None
    minutes: int | None
    score: str
    winner_serve: ServeLine
    loser_serve: ServeLine
    source_file: str

    @property
    def has_serve_stats(self) -> bool:
        return self.winner_serve.complete and self.loser_serve.complete

    @property
    def retired(self) -> bool:
        """Sackmann encodes retirements and walkovers inside the score string."""
        upper = self.score.upper()
        return "RET" in upper or "W/O" in upper or "WO" == upper.strip() or "DEF" in upper


def default_root() -> Path:
    """Where the restored archives live. Never inside the repository."""
    configured = os.environ.get("TENNIS_EDGE_DATA")
    base = Path(configured) if configured else Path("/home/user/tennis_edge_data")
    return base / "sackmann"


def _int(value: str | None) -> int | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _date(value: str) -> dt.date | None:
    text = value.strip()
    if len(text) != 8 or not text.isdigit():
        return None
    try:
        return dt.date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    except ValueError:
        return None


def _serve_line(row: dict[str, str], prefix: str) -> ServeLine:
    return ServeLine(
        aces=_int(row.get(f"{prefix}_ace")),
        double_faults=_int(row.get(f"{prefix}_df")),
        serve_points=_int(row.get(f"{prefix}_svpt")),
        first_in=_int(row.get(f"{prefix}_1stIn")),
        first_won=_int(row.get(f"{prefix}_1stWon")),
        second_won=_int(row.get(f"{prefix}_2ndWon")),
        serve_games=_int(row.get(f"{prefix}_SvGms")),
        break_points_saved=_int(row.get(f"{prefix}_bpSaved")),
        break_points_faced=_int(row.get(f"{prefix}_bpFaced")),
    )


def available_files(
    root: Path | str | None = None, *, tours: Sequence[str] = ("atp", "wta"),
    families: Sequence[str] = ("main",),
) -> list[Path]:
    """Match files for the requested tours and file families.

    Families: ``main`` (tour-level main draw), ``qual_chall`` (tour qualifying + Challenger
    main draws), ``futures`` (ITF). The lower tiers matter: published operator figures put
    the achievable edge at roughly 9% yield in Challenger/ITF against about 2.4% on the main
    ATP tour, so a system that only ever sees the main tour is looking in the wrong place.
    """
    base = Path(root) if root is not None else default_root()
    found: list[Path] = []
    for tour in tours:
        directory = base / f"tennis_{tour}"
        if not directory.exists():
            continue
        for path in sorted(directory.glob(f"{tour}_matches_*.csv")):
            name = path.name
            if "qual_chall" in name or "qual_itf" in name:
                family = "qual_chall"
            elif "futures" in name:
                family = "futures"
            elif "doubles" in name or "amateur" in name:
                continue
            else:
                family = "main"
            if family in families:
                found.append(path)
    return found


def load_matches(
    root: Path | str | None = None,
    *,
    tours: Sequence[str] = ("atp", "wta"),
    families: Sequence[str] = ("main",),
    since: dt.date | None = None,
    require_serve_stats: bool = False,
) -> Iterator[SackmannMatch]:
    """Stream archive rows. Streaming because the full set is a few million rows.

    ``tourney_date`` is the Monday of the tournament week, not the match date — the archive
    has no per-match timestamp. Anything time-sensitive must therefore treat a whole
    tournament as one block, never split inside it.
    """
    for path in available_files(root, tours=tours, families=families):
        tour = "ATP" if path.name.startswith("atp") else "WTA"
        with path.open(newline="", encoding="utf-8", errors="replace") as handle:
            for row in csv.DictReader(handle):
                when = _date(row.get("tourney_date", ""))
                if when is None:
                    continue
                if since is not None and when < since:
                    continue
                winner = (row.get("winner_name") or "").strip()
                loser = (row.get("loser_name") or "").strip()
                if not winner or not loser or winner == loser:
                    continue
                match = SackmannMatch(
                    tourney_id=(row.get("tourney_id") or "").strip(),
                    tourney_name=(row.get("tourney_name") or "").strip(),
                    tourney_date=when,
                    level=Level.parse(row.get("tourney_level") or "?"),
                    surface=(row.get("surface") or "").strip(),
                    round_name=(row.get("round") or "").strip(),
                    best_of=_int(row.get("best_of")) or 3,
                    match_num=_int(row.get("match_num")) or 0,
                    tour=tour,
                    winner_id=(row.get("winner_id") or "").strip(),
                    winner_name=winner,
                    loser_id=(row.get("loser_id") or "").strip(),
                    loser_name=loser,
                    winner_rank=_int(row.get("winner_rank")),
                    loser_rank=_int(row.get("loser_rank")),
                    minutes=_int(row.get("minutes")),
                    score=(row.get("score") or "").strip(),
                    winner_serve=_serve_line(row, "w"),
                    loser_serve=_serve_line(row, "l"),
                    source_file=path.name,
                )
                if require_serve_stats and not match.has_serve_stats:
                    continue
                yield match
