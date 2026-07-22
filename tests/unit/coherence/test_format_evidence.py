"""STAGE3-0005 §11 — format-evidence policy (independent-of-price/outcome format resolution).

Synthetic-only. Format is established from tiered evidence; tier C may establish match length
ONLY; price/outcome sources are refused; there is no default-to-best-of-three.
"""
from __future__ import annotations

import pytest

from sport_tennis.coherence.formats import (
    FORMAT_UNRESOLVED,
    UNSUPPORTED_FORMAT,
    MatchFormat,
)
from sport_tennis.coherence.format_evidence import (
    FORMAT_EVIDENCE_CONFLICT,
    FORMAT_EVIDENCE_REFUSED,
    FORMAT_LENGTH_ONLY_BEST_OF_3,
    FORMAT_LENGTH_ONLY_BEST_OF_5,
    LENGTH_BEST_OF_3,
    LENGTH_BEST_OF_5,
    TIER_A,
    TIER_B,
    TIER_C,
    FormatEvidence,
    FormatEvidenceError,
    resolve_format,
)

_BO3 = MatchFormat.BO3_AD_TB7_ALL_SETS.value
_BO5 = MatchFormat.BO5_AD_TB10_FINAL_AT_6_6.value


def test_empty_evidence_is_unresolved() -> None:
    assert resolve_format(()) == FORMAT_UNRESOLVED


def test_tier_a_establishes_full_format() -> None:
    ev = (FormatEvidence(TIER_A, _BO3, "GOVERNED_COMPETITION_IDENTITY"),)
    assert resolve_format(ev) == _BO3


def test_tier_b_establishes_full_format() -> None:
    ev = (FormatEvidence(TIER_B, _BO5, "PRE_MATCH_EVENT_METADATA"),)
    assert resolve_format(ev) == _BO5


def test_unsupported_token_is_unsupported() -> None:
    ev = (FormatEvidence(TIER_A, "FAST4", "GOVERNED_COMPETITION_IDENTITY"),)
    assert resolve_format(ev) == UNSUPPORTED_FORMAT


def test_never_use_source_is_refused_even_with_valid_token() -> None:
    ev = (FormatEvidence(TIER_A, _BO3, "TOTAL_GAMES_PRICE"),)
    assert resolve_format(ev) == FORMAT_EVIDENCE_REFUSED


def test_never_use_source_poisons_whole_resolution() -> None:
    ev = (FormatEvidence(TIER_A, _BO3, "GOVERNED_COMPETITION_IDENTITY"),
          FormatEvidence(TIER_C, LENGTH_BEST_OF_3, "RESULT"))
    assert resolve_format(ev) == FORMAT_EVIDENCE_REFUSED


def test_tier_c_length_only_best_of_3() -> None:
    ev = (FormatEvidence(TIER_C, LENGTH_BEST_OF_3, "NUMBER_OF_SETS_SELECTIONS"),)
    assert resolve_format(ev) == FORMAT_LENGTH_ONLY_BEST_OF_3


def test_tier_c_length_only_best_of_5() -> None:
    ev = (FormatEvidence(TIER_C, LENGTH_BEST_OF_5, "SET_BETTING_SELECTIONS"),)
    assert resolve_format(ev) == FORMAT_LENGTH_ONLY_BEST_OF_5


def test_tier_c_cannot_establish_full_format_detail() -> None:
    # A tier-C source may NOT set the tiebreak/advantage detail; carrying a full format token
    # leaves the format unresolved (no A/B evidence present).
    ev = (FormatEvidence(TIER_C, _BO3, "SET_BETTING_SELECTIONS"),)
    assert resolve_format(ev) == FORMAT_UNRESOLVED


def test_tier_a_wins_over_tier_c_length() -> None:
    ev = (FormatEvidence(TIER_A, _BO5, "GOVERNED_COMPETITION_IDENTITY"),
          FormatEvidence(TIER_C, LENGTH_BEST_OF_5, "NUMBER_OF_SETS_SELECTIONS"))
    assert resolve_format(ev) == _BO5


def test_conflicting_full_formats_is_conflict() -> None:
    ev = (FormatEvidence(TIER_A, _BO3, "GOVERNED_COMPETITION_IDENTITY"),
          FormatEvidence(TIER_B, _BO5, "PRE_MATCH_EVENT_METADATA"))
    assert resolve_format(ev) == FORMAT_EVIDENCE_CONFLICT


def test_conflicting_lengths_is_conflict() -> None:
    ev = (FormatEvidence(TIER_C, LENGTH_BEST_OF_3, "SET_BETTING_SELECTIONS"),
          FormatEvidence(TIER_C, LENGTH_BEST_OF_5, "NUMBER_OF_SETS_SELECTIONS"))
    assert resolve_format(ev) == FORMAT_EVIDENCE_CONFLICT


def test_malformed_evidence_refused() -> None:
    with pytest.raises(FormatEvidenceError):
        resolve_format((FormatEvidence("Z", _BO3, "GOVERNED_COMPETITION_IDENTITY"),))
    with pytest.raises(FormatEvidenceError):
        resolve_format((FormatEvidence(TIER_A, "", "GOVERNED_COMPETITION_IDENTITY"),))
