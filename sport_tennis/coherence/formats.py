"""CROSS_MARKET_COHERENCE_V1 — immutable MatchFormat vocabulary (STAGE3-0005 §10).

SYNTHETIC-ONLY. This module defines the supported tennis match formats and their structural
parameters. It reads NO market prices and NO outcomes; format is supplied independently
(format-evidence policy, §11). Unknown formats are ``FORMAT_UNRESOLVED``; unsupported formats
are ``UNSUPPORTED_FORMAT`` — there is NO default-to-best-of-three.

Import-quarantined from execution, pricing, V0 and research.xmarket.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MatchFormat(Enum):
    """The immutable supported formats (§10). Do not default to best-of-three."""

    BO3_AD_TB7_ALL_SETS = "BO3_AD_TB7_ALL_SETS"
    BO3_AD_TB10_FINAL_AT_6_6 = "BO3_AD_TB10_FINAL_AT_6_6"
    BO5_AD_TB10_FINAL_AT_6_6 = "BO5_AD_TB10_FINAL_AT_6_6"
    BO3_AD_MATCH_TB10_REPLACES_DECIDER = "BO3_AD_MATCH_TB10_REPLACES_DECIDER"


# Structural statuses for unknown / unsupported formats (§10/§15).
FORMAT_UNRESOLVED = "FORMAT_UNRESOLVED"
UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"

# Explicitly-unsupported format tokens (§10).
UNSUPPORTED_FORMAT_TOKENS = frozenset({
    "NO_AD_SINGLES", "ADV_FINAL_SET_NO_TB", "FAST4", "UNKNOWN", "MIXED_OR_NONSTANDARD",
})


@dataclass(frozen=True)
class FormatSpec:
    """Structural parameters of a supported format. No prices, no outcomes."""

    fmt: MatchFormat
    sets_to_win: int                 # 2 (best of 3) or 3 (best of 5)
    ad_scoring: bool                 # advantage (deuce) games — all supported formats are AD
    tiebreak_target_normal_set: int  # 7-point tiebreak at 6-6 in a non-deciding set
    final_set_rule: str              # TB7_ALL_SETS | TB10_FINAL_AT_6_6 | MATCH_TB10_REPLACES_DECIDER
    match_tiebreak_games_credited_to_winner: int  # settlement games credited by a match-TB decider


# Frozen structural table. The `match_tiebreak_games_credited_to_winner` is a SYNTHETIC,
# explicitly-verified counting convention (STAGE3-0005 §9 "settlement counting is verified");
# it is NOT a claim about Betfair's real settlement (that is EXT-XMARKET-003 detail). A match
# tiebreak decider is scored as a single 1-0 "set" of one game to the winner here.
_SPECS = {
    MatchFormat.BO3_AD_TB7_ALL_SETS: FormatSpec(
        MatchFormat.BO3_AD_TB7_ALL_SETS, 2, True, 7, "TB7_ALL_SETS", 0),
    MatchFormat.BO3_AD_TB10_FINAL_AT_6_6: FormatSpec(
        MatchFormat.BO3_AD_TB10_FINAL_AT_6_6, 2, True, 7, "TB10_FINAL_AT_6_6", 0),
    MatchFormat.BO5_AD_TB10_FINAL_AT_6_6: FormatSpec(
        MatchFormat.BO5_AD_TB10_FINAL_AT_6_6, 3, True, 7, "TB10_FINAL_AT_6_6", 0),
    MatchFormat.BO3_AD_MATCH_TB10_REPLACES_DECIDER: FormatSpec(
        MatchFormat.BO3_AD_MATCH_TB10_REPLACES_DECIDER, 2, True, 7,
        "MATCH_TB10_REPLACES_DECIDER", 1),
}


def format_spec(fmt: MatchFormat) -> FormatSpec:
    return _SPECS[fmt]


def classify_format_token(token: str) -> str:
    """Map a raw format token to a MatchFormat name, ``UNSUPPORTED_FORMAT`` or
    ``FORMAT_UNRESOLVED``. Never defaults to best-of-three."""
    if not isinstance(token, str) or not token:
        return FORMAT_UNRESOLVED
    for f in MatchFormat:
        if f.value == token:
            return f.value
    if token in UNSUPPORTED_FORMAT_TOKENS:
        return UNSUPPORTED_FORMAT
    return FORMAT_UNRESOLVED
