"""PERSONAL_TENNIS_ASSISTANT_V0 — frozen F2-v1 rating-state READER.

This module builds NO model and fits nothing. It reads a local JSON snapshot of the FROZEN
F2-v1 rating state (supplied by the founder from the frozen F2-v1 evidence) and exposes it
as the pipeline's ``RatingLookup``: ``(tour, display_name) -> (rating, prior_match_count)``
or ``None`` when the identity does not resolve. ATP and WTA are separate namespaces, never
pooled. A malformed store REFUSES at load rather than guessing, and an unresolved player is
reported as unresolved (the pipeline maps that to ``IDENTITY_UNRESOLVED``) — never imputed.

The F2-v1 view this feeds is a labelled DIAGNOSTIC and is never the final V0 probability.
No network, no credentials, no writes: loading a store never mutates it.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from assistant_v0.pipeline import RatingLookup

RATING_STATE_VERSION_KEY = "rating_state_version"
EXPECTED_STATE_VERSION = "F2_V1_FROZEN"


class RatingStoreError(Exception):
    """The rating store is missing or malformed and is refused at load."""


def _validate(payload: object) -> dict[str, dict[str, tuple[float, int]]]:
    if not isinstance(payload, dict):
        raise RatingStoreError("rating store must be a JSON object")
    if payload.get(RATING_STATE_VERSION_KEY) != EXPECTED_STATE_VERSION:
        raise RatingStoreError(
            f"{RATING_STATE_VERSION_KEY} must be {EXPECTED_STATE_VERSION!r}, got "
            f"{payload.get(RATING_STATE_VERSION_KEY)!r}")
    players = payload.get("players")
    if not isinstance(players, dict):
        raise RatingStoreError("rating store must carry a 'players' mapping")

    parsed: dict[str, dict[str, tuple[float, int]]] = {}
    for tour, entries in players.items():
        if not isinstance(tour, str) or not isinstance(entries, dict):
            raise RatingStoreError(f"tour {tour!r} must map to an object of players")
        by_name: dict[str, tuple[float, int]] = {}
        for name, rec in entries.items():
            if not isinstance(name, str) or not name:
                raise RatingStoreError(f"player name {name!r} must be a non-empty string")
            if not isinstance(rec, dict):
                raise RatingStoreError(f"player {name!r} must map to an object")
            rating, matches = rec.get("rating"), rec.get("matches")
            if isinstance(rating, bool) or not isinstance(rating, (int, float)):
                raise RatingStoreError(f"player {name!r} rating must be numeric, got {rating!r}")
            if isinstance(matches, bool) or not isinstance(matches, int):
                raise RatingStoreError(f"player {name!r} matches must be an int, got {matches!r}")
            if matches < 0:
                raise RatingStoreError(f"player {name!r} matches must be >= 0, got {matches}")
            by_name[name] = (float(rating), matches)
        parsed[tour] = by_name
    return parsed


def load_rating_lookup(path: Path | str) -> RatingLookup:
    """Load a frozen F2-v1 rating snapshot and return a pure ``RatingLookup``."""
    p = Path(path)
    if not p.exists():
        raise RatingStoreError(f"rating store not found: {p}")
    try:
        payload = json.loads(p.read_text())
    except json.JSONDecodeError as exc:
        raise RatingStoreError(f"rating store is not valid JSON: {exc}") from exc
    table = _validate(payload)

    def lookup(tour: str, name: str) -> tuple[float, int] | None:
        return table.get(tour, {}).get(name)

    return lookup


def rating_state_digest(path: Path | str) -> str:
    """Content digest of the rating state, recorded alongside any F2 diagnostic it feeds."""
    p = Path(path)
    if not p.exists():
        raise RatingStoreError(f"rating store not found: {p}")
    return "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()
