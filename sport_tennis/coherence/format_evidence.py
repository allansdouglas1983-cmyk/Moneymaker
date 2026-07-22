"""CROSS_MARKET_COHERENCE_V1 — format-evidence policy (STAGE3-0005 §11).

SYNTHETIC-ONLY, deterministic. Format is established INDEPENDENTLY of prices and outcomes
(coherence-v1.yaml ``format_evidence_policy``). Evidence tiers:

  * Tier A — official governed competition identity / frozen competition-format lookup.
  * Tier B — lawful pre-match event metadata.
  * Tier C — SET_BETTING / NUMBER_OF_SETS selection structure: may establish ONLY best-of-3 vs
    best-of-5. It MUST NOT establish final-set tiebreak length, match-tiebreak replacement,
    advantage final set, or no-ad scoring.

Any evidence whose source is a Total-Games price, Handicap price, fitted parameter, realized
games, score, result or outcome is REFUSED — such a source can never establish format. There is
NO default-to-best-of-three. Import-quarantined from execution/pricing/V0/research.xmarket.
"""
from __future__ import annotations

from dataclasses import dataclass

from sport_tennis.coherence.formats import (
    FORMAT_UNRESOLVED,
    UNSUPPORTED_FORMAT,
    classify_format_token,
)

TIER_A = "A"
TIER_B = "B"
TIER_C = "C"
_TIERS = frozenset({TIER_A, TIER_B, TIER_C})

# Sources that may NEVER establish format (§11 never_use). Refused outright.
NEVER_USE_SOURCES = frozenset({
    "TOTAL_GAMES_PRICE", "HANDICAP_PRICE", "FITTED_PARAMETER", "REALIZED_GAMES",
    "SCORE", "RESULT", "OUTCOME",
})

# Tokens tier C is permitted to carry — match length ONLY.
LENGTH_BEST_OF_3 = "BEST_OF_3"
LENGTH_BEST_OF_5 = "BEST_OF_5"
_LENGTH_TOKENS = frozenset({LENGTH_BEST_OF_3, LENGTH_BEST_OF_5})

# Resolution statuses beyond a resolved MatchFormat value / formats.py statuses.
FORMAT_EVIDENCE_REFUSED = "FORMAT_EVIDENCE_REFUSED"          # a never_use source appeared
FORMAT_EVIDENCE_CONFLICT = "FORMAT_EVIDENCE_CONFLICT"        # A/B items disagree
FORMAT_LENGTH_ONLY_BEST_OF_3 = "FORMAT_LENGTH_ONLY_BEST_OF_3"
FORMAT_LENGTH_ONLY_BEST_OF_5 = "FORMAT_LENGTH_ONLY_BEST_OF_5"


class FormatEvidenceError(Exception):
    """Malformed format evidence — refuse, never guess."""


@dataclass(frozen=True)
class FormatEvidence:
    """One piece of format evidence. ``token`` is a MatchFormat value (tier A/B) or a length
    token (tier C); ``source`` names its provenance."""

    tier: str
    token: str
    source: str


def _length_only_status(token: str) -> str:
    return FORMAT_LENGTH_ONLY_BEST_OF_3 if token == LENGTH_BEST_OF_3 \
        else FORMAT_LENGTH_ONLY_BEST_OF_5


def resolve_format(evidence: tuple[FormatEvidence, ...]) -> str:
    """Resolve the match format from independent evidence. Returns a supported MatchFormat value,
    ``UNSUPPORTED_FORMAT``, ``FORMAT_UNRESOLVED``, a length-only status, ``FORMAT_EVIDENCE_CONFLICT``
    or ``FORMAT_EVIDENCE_REFUSED``. Never defaults to best-of-three."""
    if not evidence:
        return FORMAT_UNRESOLVED
    for e in evidence:
        if e.tier not in _TIERS:
            raise FormatEvidenceError(f"unknown evidence tier {e.tier!r}")
        if not isinstance(e.token, str) or not e.token:
            raise FormatEvidenceError("evidence token must be a non-empty string")

    # A single never_use source poisons the whole resolution — format may not derive from prices
    # or outcomes.
    if any(e.source in NEVER_USE_SOURCES for e in evidence):
        return FORMAT_EVIDENCE_REFUSED

    # Tier A/B may establish the full format. Tier C may NOT (it carries only length); a tier-C
    # item bearing a full format token is silently non-establishing for the detail it may not set.
    full: set[str] = set()
    unsupported = False
    for e in evidence:
        if e.tier in (TIER_A, TIER_B):
            resolved = classify_format_token(e.token)
            if resolved == UNSUPPORTED_FORMAT:
                unsupported = True
            elif resolved != FORMAT_UNRESOLVED:
                full.add(resolved)
    if len(full) > 1:
        return FORMAT_EVIDENCE_CONFLICT
    if len(full) == 1:
        return next(iter(full))
    if unsupported:
        return UNSUPPORTED_FORMAT

    # No A/B full format. Tier C may contribute length only, and only via a length token.
    lengths: set[str] = set()
    for e in evidence:
        if e.tier == TIER_C and e.token in _LENGTH_TOKENS:
            lengths.add(e.token)
    if len(lengths) > 1:
        return FORMAT_EVIDENCE_CONFLICT
    if len(lengths) == 1:
        return _length_only_status(next(iter(lengths)))
    return FORMAT_UNRESOLVED
