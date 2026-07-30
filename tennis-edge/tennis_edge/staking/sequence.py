"""Load the exported opportunity set into candidates the engine can replay.

This file is the single input to every comparison the study makes, which is exactly why
it is worth testing. If it loads wrong, every staking rule loads wrong TOGETHER and
IDENTICALLY — so no comparison between rules could ever reveal it, and the study would
produce a confidently wrong ranking.

Odds and probabilities arrive as exact Decimal. The exporter writes them as strings
specifically so they never pass through binary floating point; calling ``float()`` here
would undo that at the last step.

An unreadable row raises. The universe is frozen before outcomes are known, so a row that
cannot be parsed is an error with a knowledge-time, never a quiet disappearance.
"""
from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from tennis_edge.staking.engine import Candidate

__all__ = ["SEQUENCE_KIND", "load_sequence"]

SEQUENCE_KIND = "tennis-edge-bet-sequence-v1"


def _decimal(value: Any, field: str, line_number: int) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(
            f"line {line_number}: {field}={value!r} is not a valid exact number. "
            "Refusing rather than dropping the row: a dropped row is a silent change to "
            "the bet universe, and the universe is frozen before outcomes are known."
        ) from exc


def load_sequence(path: Path | str) -> tuple[dict[str, Any], list[Candidate]]:
    """Return ``(header, candidates)``.

    The header carries which price table and feature set produced the file. It is
    returned rather than swallowed so two runs on different links cannot be compared by
    accident — the provenance travels with the data or the comparison is not a comparison.
    """
    path = Path(path)
    candidates: list[Candidate] = []
    with path.open(encoding="utf-8") as handle:
        first = handle.readline()
        if not first:
            raise ValueError(f"{path} is empty")
        header = json.loads(first)
        if header.get("kind") != SEQUENCE_KIND:
            raise ValueError(
                f"{path} declares kind {header.get('kind')!r}, expected {SEQUENCE_KIND!r}. "
                "Refusing: a differently-shaped file with the right column names is how a "
                "study silently measures the wrong thing.")

        for line_number, line in enumerate(handle, start=2):
            if not line.strip():
                continue
            row = json.loads(line)
            candidates.append(Candidate(
                date=dt.date.fromisoformat(row["date"]),
                market_id=row["market_id"],
                side=row["side"],
                odds=_decimal(row["odds"], "odds", line_number),
                p_model=_decimal(row["p_model"], "p_model", line_number),
                p_market=_decimal(row["p_market"], "p_market", line_number),
                won=bool(row["won"]),
                support=row["support"],
                stratum=row["stratum"],
            ))
    return header, candidates
