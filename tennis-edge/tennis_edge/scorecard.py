"""The site grades its own served predictions (TE-0017 S6, reference implementation).

The predictions table is write-only until this exists, which means the full serving path —
TypeScript port, real user-entered prices, real staleness, real coverage — has never been
scored end to end. This module is the deterministic reference the deployment mirrors: the
weekly job exports results with :func:`grade_key` applied, the database joins them to the
last pre-match prediction per match, and settled rows append to a ledger that never
rewrites a prediction.

**Display-only by construction.** Nothing here feeds anything served: not MIN_EDGE, not
the staleness thresholds, not the model. The scorecard is monitoring with intervals,
explicitly non-gating — any future formal halt rule must meet the SPEC-096 anytime-valid
standard, and a single user's volume can gate nothing.

**The vintage policy is the clock's, never the result's.** Where several predictions exist
for one match (each price entry mints a new row), the graded one is the LAST row created
on or before the match date — declared here, before any outcome was seen. A row minted
after the match date is excluded from grading entirely.
"""
from __future__ import annotations

import datetime as dt
import math
import re
from enum import Enum, unique

from tennis_edge.serve_stats import sackmann_player_key, td_player_key

__all__ = ["GradeOutcome", "grade", "grade_key", "last_pre_match"]

#: A trailing abbreviated-initial token ("Alcaraz C.", "Pliskova Ka.") marks the
#: Tennis-Data name form; anything else is treated as a natural full name.
_TD_FORM = re.compile(r"\b[A-Z][a-z]?\.$")


@unique
class GradeOutcome(Enum):
    """Why a prediction did or did not settle. Every one is counted, never dropped."""

    GRADED = "GRADED"
    PENDING_RESULT = "PENDING_RESULT"
    UNMATCHED_NAME = "UNMATCHED_NAME"
    NOT_GRADEABLE = "NOT_GRADEABLE"


def grade_key(name: str) -> str | None:
    """One key both name forms converge to, or ``None`` — never a guess.

    "Carlos Alcaraz" (what the user types) and "Alcaraz C." (what the corpus stores) meet
    at ``(surname, first initial)`` through the same td-norm-v1 normalisation the identity
    bridge uses. The hard tail (double surnames, twins) may not converge; those grade as
    UNMATCHED_NAME, visible in the denominator rather than silently absent.
    """
    stripped = name.strip()
    if not stripped:
        return None
    key = (td_player_key(stripped) if _TD_FORM.search(stripped)
           else sackmann_player_key(stripped))
    return None if key is None else f"{key[0]} {key[1]}"


def last_pre_match(predictions: list[dict]) -> dict[str, dict]:
    """The one prediction per match_key the scorecard grades.

    Latest ``created_at`` whose date is on or before the match date. A post-match row
    knows too much and never grades; letting it compete would let a re-entry after the
    result quietly replace the honest pre-match opinion.
    """
    chosen: dict[str, dict] = {}
    for row in predictions:
        created = dt.datetime.fromisoformat(
            str(row["created_at"]).replace("Z", "+00:00"))
        if created.date() > dt.date.fromisoformat(str(row["match_date"])):
            continue
        key = str(row["match_key"])
        current = chosen.get(key)
        if current is None or str(row["created_at"]) > str(current["created_at"]):
            chosen[key] = row
    return chosen


def _log_loss(probability: float, won: bool) -> float:
    p = min(max(probability, 1e-12), 1.0 - 1e-12)
    return -math.log(p if won else 1.0 - p)


def grade(predictions: list[dict],
          results: list[dict]) -> tuple[list[dict], dict[GradeOutcome, int]]:
    """Settle the last pre-match prediction of every match a result exists for.

    Returns the settled rows and the typed exclusion counts. Deterministic: the same
    inputs produce the same rows, which is what lets the backfill replay prove the ledger
    was never rewritten. Input dicts are never mutated.
    """
    by_pair: dict[tuple[str, str, frozenset[str]], dict] = {}
    covered_days: set[tuple[str, str]] = set()
    for result in results:
        covered_days.add((str(result["match_date"]), str(result["tour"])))
        keys = frozenset(k for k in (result["key_a"], result["key_b"]) if k)
        if len(keys) == 2:
            by_pair[(str(result["match_date"]), str(result["tour"]), keys)] = result

    settled: list[dict] = []
    exclusions: dict[GradeOutcome, int] = {}

    def exclude(outcome: GradeOutcome) -> None:
        exclusions[outcome] = exclusions.get(outcome, 0) + 1

    for prediction in last_pre_match(predictions).values():
        key_a = grade_key(str(prediction["player_a"]))
        key_b = grade_key(str(prediction["player_b"]))
        if key_a is None or key_b is None:
            exclude(GradeOutcome.UNMATCHED_NAME)
            continue
        result = by_pair.get((str(prediction["match_date"]),
                              str(prediction["tour"]),
                              frozenset((key_a, key_b))))
        if result is None:
            # Results covering that day exist but this pair is not among them: a name
            # problem, not a timing one. The two must never be conflated — one is worth
            # chasing and the other resolves itself next week.
            day = (str(prediction["match_date"]), str(prediction["tour"]))
            exclude(GradeOutcome.UNMATCHED_NAME if day in covered_days
                    else GradeOutcome.PENDING_RESULT)
            continue
        winner_key = result.get("winner_key")
        if winner_key is None or str(result.get("completion")) in (
                "WALKOVER", "ABANDONED"):
            exclude(GradeOutcome.NOT_GRADEABLE)
            continue
        if winner_key not in (key_a, key_b):
            exclude(GradeOutcome.UNMATCHED_NAME)
            continue

        won_a = winner_key == key_a
        model_p = float(prediction["probability_a"])
        market_p = float(prediction["market_probability_a"])
        settled.append({
            "match_key": prediction["match_key"],
            "match_date": prediction["match_date"],
            "tour": prediction["tour"],
            "outcome": GradeOutcome.GRADED,
            "winner_side": "A" if won_a else "B",
            "completion": result["completion"],
            "model_log_loss": _log_loss(model_p, won_a),
            "market_log_loss": _log_loss(market_p, won_a),
        })
    return settled, exclusions
