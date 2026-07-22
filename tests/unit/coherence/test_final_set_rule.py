"""STAGE3-0006 §5.3 — final-set rule identity & ordering as a governed closed vocabulary.

The final-set rule must be a governed enum, not an unconstrained string. These tests pin the
closed member set, the per-format assignment, and the two pure resolver seams
(set_tiebreak_target, is_match_tiebreak_decider) that replace the raw `== "..."` comparisons —
killing identity/lexicographic/foreign-string mutants.
"""
from __future__ import annotations

import pytest

from sport_tennis.coherence.formats import (
    FinalSetRule,
    MatchFormat,
    format_spec,
    is_match_tiebreak_decider,
    set_tiebreak_target,
)

_EXPECTED = {
    MatchFormat.BO3_AD_TB7_ALL_SETS: FinalSetRule.TB7_ALL_SETS,
    MatchFormat.BO3_AD_TB10_FINAL_AT_6_6: FinalSetRule.TB10_FINAL_AT_6_6,
    MatchFormat.BO5_AD_TB10_FINAL_AT_6_6: FinalSetRule.TB10_FINAL_AT_6_6,
    MatchFormat.BO3_AD_MATCH_TB10_REPLACES_DECIDER: FinalSetRule.MATCH_TB10_REPLACES_DECIDER,
}


def test_final_set_rule_is_closed_vocabulary() -> None:
    assert {r.name for r in FinalSetRule} == {
        "TB7_ALL_SETS", "TB10_FINAL_AT_6_6", "MATCH_TB10_REPLACES_DECIDER"}


@pytest.mark.parametrize("fmt,rule", list(_EXPECTED.items()), ids=lambda v: getattr(v, "name", v))
def test_each_format_has_the_governed_rule(fmt: MatchFormat, rule: FinalSetRule) -> None:
    spec = format_spec(fmt)
    assert spec.final_set_rule is rule
    assert isinstance(spec.final_set_rule, FinalSetRule)


def test_set_tiebreak_target_only_ten_for_tb10_final_set() -> None:
    for fmt in MatchFormat:
        spec = format_spec(fmt)
        assert set_tiebreak_target(spec, is_final_set=False) == 7           # normal set always 7
        expected_final = 10 if spec.final_set_rule is FinalSetRule.TB10_FINAL_AT_6_6 else 7
        assert set_tiebreak_target(spec, is_final_set=True) == expected_final


def test_is_match_tiebreak_decider_only_for_that_format() -> None:
    for fmt in MatchFormat:
        spec = format_spec(fmt)
        expected = spec.final_set_rule is FinalSetRule.MATCH_TB10_REPLACES_DECIDER
        assert is_match_tiebreak_decider(spec) is expected


def test_final_set_rule_not_ordered_and_not_string() -> None:
    # An enum member is a singleton (== and is coincide, killing the Eq->Is mutant) and is NOT
    # comparable by <= (killing the lexicographic mutant) and never equals a raw string.
    a = FinalSetRule.TB10_FINAL_AT_6_6
    assert (a == FinalSetRule.TB10_FINAL_AT_6_6) is (a is FinalSetRule.TB10_FINAL_AT_6_6)
    assert a != "TB10_FINAL_AT_6_6"
    with pytest.raises(TypeError):
        _ = a <= FinalSetRule.TB7_ALL_SETS  # type: ignore[operator]
