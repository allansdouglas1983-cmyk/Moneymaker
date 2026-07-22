"""PROMOTED cross-market selection parsers (STAGE3-0004 §10). Production re-home of the
STAGE3-0002 audit parsers, hardened to the advice-critical bar and independent of
``research.xmarket``.

Deterministic, versioned. Preserves raw ``marketType`` (never renamed; unknown fails closed).
Type-specific selection parsing. The ``HANDICAP`` parser handles the double-line packing and
refuses any set-sized handicap (max |line| <= 3.0) as a game handicap. No probability, no
outcome, no fitted maths. Import-quarantined from execution and from ``research.xmarket``.
"""
from __future__ import annotations

from dataclasses import dataclass

PARSER_VERSION = "xmarket-contracts-parsers-v1"

PRIMARY_MATCH_ODDS = "PRIMARY_MATCH_ODDS"
PRIMARY_IDENTIFYING_TOTAL_GAMES = "PRIMARY_IDENTIFYING_TOTAL_GAMES"
PRIMARY_IDENTIFYING_GAME_HANDICAP = "PRIMARY_IDENTIFYING_GAME_HANDICAP"
AUXILIARY_SET_STRUCTURE = "AUXILIARY_SET_STRUCTURE"
AUXILIARY_OTHER = "AUXILIARY_OTHER"
UNSUPPORTED = "UNSUPPORTED"
UNKNOWN_REQUIRES_REVIEW = "UNKNOWN_REQUIRES_REVIEW"

_ROLE_BY_TYPE = {
    "MATCH_ODDS": PRIMARY_MATCH_ODDS,
    "COMBINED_TOTAL": PRIMARY_IDENTIFYING_TOTAL_GAMES,
    "HANDICAP": PRIMARY_IDENTIFYING_GAME_HANDICAP,
    "SET_WINNER": AUXILIARY_SET_STRUCTURE,
    "NUMBER_OF_SETS": AUXILIARY_SET_STRUCTURE,
    "PLAYER_A_WIN_A_SET": AUXILIARY_SET_STRUCTURE,
    "PLAYER_B_WIN_A_SET": AUXILIARY_SET_STRUCTURE,
    "SET_BETTING": AUXILIARY_OTHER,
    "SET_CORRECT_SCORE": AUXILIARY_OTHER,
    "TOURNAMENT_WINNER": UNSUPPORTED,
}

# A tennis set handicap has |line| <= 2.5; a game handicap only ever reaches 11.5/15.5. The
# boundary sits above the largest plausible set handicap and far below the smallest observed
# game handicap: no corpus market lands in the gap, so this never falsely refuses a real
# market and never lets a set handicap through.
_MAX_PLAUSIBLE_SET_HANDICAP = 3.0


class MarketParseError(Exception):
    """A market's structure cannot be parsed deterministically — refuse, never guess."""


def market_role(market_type: str) -> str:
    """Raw Betfair marketType -> audit role. Unlisted => review (fail closed). Never renamed."""
    if not isinstance(market_type, str) or not market_type:
        raise MarketParseError(f"marketType must be a non-empty string, got {market_type!r}")
    return _ROLE_BY_TYPE.get(market_type, UNKNOWN_REQUIRES_REVIEW)


@dataclass(frozen=True)
class TotalGamesLine:
    line: float
    over_runner_id: int
    under_runner_id: int


@dataclass(frozen=True)
class GameHandicapLine:
    line: float               # magnitude of the handicap in games (> 0)
    giver_runner_id: int      # the player at the negative handicap (concedes games)
    receiver_runner_id: int   # the player at the positive handicap (receives games)


def _runner_tuple(r: object) -> tuple[int, str, float | None]:
    if not isinstance(r, dict):
        raise MarketParseError(f"runner must be a mapping, got {type(r).__name__}")
    rid, name, hc = r.get("id"), r.get("name"), r.get("hc")
    if not isinstance(rid, int) or isinstance(rid, bool):
        raise MarketParseError(f"runner id must be int, got {rid!r}")
    if not isinstance(name, str) or not name:
        raise MarketParseError(f"runner name must be non-empty string, got {name!r}")
    if hc is not None and (not isinstance(hc, (int, float)) or isinstance(hc, bool)):
        raise MarketParseError(f"runner hc must be numeric or None, got {hc!r}")
    return rid, name, (float(hc) if hc is not None else None)


def parse_total_games(runners: object) -> tuple[TotalGamesLine, ...]:
    """COMBINED_TOTAL: pair Over/Under by exact line (hc). Missing side, non-Over/Under name,
    absent hc, or a duplicate side refuse."""
    if not isinstance(runners, list) or not runners:
        raise MarketParseError("Total Games market needs a non-empty runner list")
    overs: dict[float, int] = {}
    unders: dict[float, int] = {}
    for r in runners:
        rid, name, hc = _runner_tuple(r)
        if hc is None:
            raise MarketParseError(f"Total Games runner {name!r} has no line (hc)")
        side = name.strip().lower()
        if side == "over":
            if hc in overs:
                raise MarketParseError(f"duplicate Over line {hc}")
            overs[hc] = rid
        elif side == "under":
            if hc in unders:
                raise MarketParseError(f"duplicate Under line {hc}")
            unders[hc] = rid
        else:
            raise MarketParseError(f"Total Games runner name must be Over/Under, got {name!r}")
    unpaired = set(overs) ^ set(unders)
    if unpaired:
        raise MarketParseError(f"unpaired Over/Under lines: {sorted(unpaired)}")
    lines = sorted(set(overs) & set(unders))
    if not lines:
        raise MarketParseError("no complete Over+Under line")
    return tuple(TotalGamesLine(line=ln, over_runner_id=overs[ln], under_runner_id=unders[ln])
                 for ln in lines)


def parse_game_handicap(runners: object) -> tuple[GameHandicapLine, ...]:
    """HANDICAP: confirm a GAME handicap (max |line| unambiguously beyond a set handicap),
    then enumerate every priceable two-sided line in the double-line packing."""
    if not isinstance(runners, list) or not runners:
        raise MarketParseError("Handicap market needs a non-empty runner list")
    parsed = [_runner_tuple(r) for r in runners]
    if any(hc is None for _, _, hc in parsed):
        raise MarketParseError("Handicap runner has no line (hc)")

    names = {name for _, name, _ in parsed}
    if len(names) != 2:
        raise MarketParseError(f"must have exactly two distinct players, got {sorted(names)}")

    id_by_name: dict[str, int] = {}
    name_by_id: dict[int, str] = {}
    for rid, name, _ in parsed:
        if id_by_name.setdefault(name, rid) != rid:
            raise MarketParseError(f"player {name!r} maps to two ids")
        if name_by_id.setdefault(rid, name) != name:
            raise MarketParseError(f"runner id {rid} maps to two names")
    if len(id_by_name) != 2:
        raise MarketParseError(f"must have exactly two player ids, got {sorted(id_by_name.values())}")

    magnitudes = [abs(hc) for _, _, hc in parsed if hc is not None]
    if max(magnitudes) <= _MAX_PLAUSIBLE_SET_HANDICAP:
        raise MarketParseError(
            f"not unambiguously a GAME handicap (max |line| {max(magnitudes)} <= "
            f"{_MAX_PLAUSIBLE_SET_HANDICAP}); refusing as SET_HANDICAP_OR_OTHER"
        )

    present: set[tuple[int, float]] = set()
    for rid, _, hc in parsed:
        assert hc is not None
        if hc == 0.0:
            raise MarketParseError("zero line (no giver/receiver)")
        present.add((rid, hc))

    a_id, b_id = sorted(id_by_name.values())
    out: list[GameHandicapLine] = []
    seen: set[tuple[int, float]] = set()
    for gid, _, hc in parsed:
        assert hc is not None
        if hc >= 0.0:
            continue
        m = -hc
        other = b_id if gid == a_id else a_id
        if (other, m) not in present:
            raise MarketParseError(f"giver {gid} at -{m} has no opposite receiver at +{m}")
        key = (gid, m)
        if key in seen:
            raise MarketParseError(f"duplicate handicap line giver={gid} magnitude={m}")
        seen.add(key)
        out.append(GameHandicapLine(line=m, giver_runner_id=gid, receiver_runner_id=other))
    if not out:
        raise MarketParseError("no valid game-handicap line")
    out.sort(key=lambda ln: (ln.line, ln.giver_runner_id))
    return tuple(out)


def parse_match_odds(runners: object) -> tuple[int, int]:
    """MATCH_ODDS: exactly two player runners; return the two ids sorted."""
    if not isinstance(runners, list) or len(runners) != 2:
        n = len(runners) if isinstance(runners, list) else "?"
        raise MarketParseError(f"Match Odds needs exactly 2 runners, got {n}")
    a, b = (_runner_tuple(r) for r in runners)
    if a[0] == b[0]:
        raise MarketParseError("Match Odds runners share an id")
    lo, hi = sorted((a[0], b[0]))
    return lo, hi
