"""STAGE3-0006 §4/§7 — pin the governed format table + classify_format_token behaviour.

The _SPECS structural table (sets_to_win, ad_scoring, tiebreak target, final-set rule, credited
games) is consumed by the match/set DPs; pinning each field exactly here kills the data-value
mutants without needing the slow match suite. Also kills the classify_format_token comparison
mutants (a lexicographic >= would mis-resolve a low token; an identity `is` would fail to match a
non-interned token) and the signature `*`->`/` mutant.
"""
from __future__ import annotations

from sport_tennis.coherence.formats import (
    FORMAT_UNRESOLVED,
    FinalSetRule,
    MatchFormat,
    classify_format_token,
    format_spec,
    set_tiebreak_target,
)

# Exact expected structural parameters per format: (sets_to_win, ad, normal_tb, final_rule, credit)
_TABLE = {
    MatchFormat.BO3_AD_TB7_ALL_SETS: (2, True, 7, FinalSetRule.TB7_ALL_SETS, 0),
    MatchFormat.BO3_AD_TB10_FINAL_AT_6_6: (2, True, 7, FinalSetRule.TB10_FINAL_AT_6_6, 0),
    MatchFormat.BO5_AD_TB10_FINAL_AT_6_6: (3, True, 7, FinalSetRule.TB10_FINAL_AT_6_6, 0),
    MatchFormat.BO3_AD_MATCH_TB10_REPLACES_DECIDER: (2, True, 7,
                                                     FinalSetRule.MATCH_TB10_REPLACES_DECIDER, 1),
}


def test_format_table_exact_values() -> None:
    for fmt, (stw, ad, ntb, rule, credit) in _TABLE.items():
        spec = format_spec(fmt)
        assert spec.sets_to_win == stw, fmt
        assert spec.ad_scoring is ad, fmt
        assert spec.tiebreak_target_normal_set == ntb, fmt
        assert spec.final_set_rule is rule, fmt
        assert spec.match_tiebreak_games_credited_to_winner == credit, fmt


def test_set_tiebreak_target_accepts_keyword() -> None:
    # signature: def set_tiebreak_target(spec, *, is_final_set). The `*`->`/` mutant makes `spec`
    # positional-only; passing spec= by keyword must work under the correct signature.
    spec = format_spec(MatchFormat.BO3_AD_TB7_ALL_SETS)
    assert set_tiebreak_target(spec=spec, is_final_set=False) == 7


def test_classify_low_token_is_unresolved() -> None:
    # a token lexicographically below every format value: a `==`->`>=` mutant would wrongly return
    # the first format; the correct code returns FORMAT_UNRESOLVED.
    assert classify_format_token("AAA_NOT_A_FORMAT") == FORMAT_UNRESOLVED


def test_classify_non_interned_valid_token_resolves() -> None:
    # a value-equal but distinct (non-interned) string object built char-by-char at runtime: a
    # `==`->`is` mutant would fail the identity check and not resolve it; the correct `==` does.
    token = "".join(c for c in MatchFormat.BO3_AD_TB7_ALL_SETS.value)
    assert token is not MatchFormat.BO3_AD_TB7_ALL_SETS.value   # genuinely distinct object
    assert classify_format_token(token) == MatchFormat.BO3_AD_TB7_ALL_SETS.value
