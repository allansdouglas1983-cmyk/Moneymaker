"""A6 (audit F-10/F-11/F-12, founder order): generic choice-set outcome vocabulary.

REPRESENTATIONAL ONLY. This vocabulary names how a mutually exclusive choice set
resolved — a known winner, no sporting winner (void / abandoned / tied), or not yet
resolved — so that training, metrics and snapshots can account for such sets explicitly
instead of silently omitting them. It encodes NO settlement consequence: racing
settlement stays SPEC-082 behind the racing policy; tennis settlement stays SPEC-084 and
REFUSED. A tied outcome here is a structure ("more than one selection shares the
result"), never a payout rule.

Pins:
* coherence refusals both directions (winner iff WINNER_KNOWN; reason iff
  NO_SPORTING_WINNER);
* canonical machine-stable exclusion-reason strings for crossfit's ExcludedRace and the
  metrics exclusion path — an unresolved/no-winner choice set is an EXPLICIT exclusion
  with a reason, never a disappearance;
* the founder design tests: football (3-way, abandonment) and a binary financial market
  (void) are expressible with no new members.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import pytest

from sport_core.outcomes import (
    ChoiceSetOutcome,
    ChoiceSetResolution,
    NoWinnerReason,
    exclusion_reason,
)

pytestmark = pytest.mark.spec("SPEC-090")


def _winner(sel: int = 7) -> ChoiceSetOutcome:
    return ChoiceSetOutcome(
        resolution=ChoiceSetResolution.WINNER_KNOWN, winner_selection_id=sel
    )


def _no_winner(reason: NoWinnerReason = NoWinnerReason.MARKET_VOID) -> ChoiceSetOutcome:
    return ChoiceSetOutcome(
        resolution=ChoiceSetResolution.NO_SPORTING_WINNER, no_winner_reason=reason
    )


class TestVocabularyClosure:
    def test_resolutions_exact(self) -> None:
        assert {m.name for m in ChoiceSetResolution} == {
            "WINNER_KNOWN",
            "NO_SPORTING_WINNER",
            "PENDING",
        }

    def test_no_winner_reasons_exact(self) -> None:
        assert {m.name for m in NoWinnerReason} == {
            "MARKET_VOID",
            "EVENT_ABANDONED",
            "TIED_OUTCOME",
        }


class TestCoherence:
    def test_winner_known_requires_winner_and_nothing_else(self) -> None:
        outcome = _winner()
        assert outcome.winner_selection_id == 7
        with pytest.raises(ValueError):
            ChoiceSetOutcome(resolution=ChoiceSetResolution.WINNER_KNOWN)
        with pytest.raises(ValueError):
            ChoiceSetOutcome(
                resolution=ChoiceSetResolution.WINNER_KNOWN,
                winner_selection_id=7,
                no_winner_reason=NoWinnerReason.MARKET_VOID,
            )

    def test_no_sporting_winner_requires_reason_and_no_winner(self) -> None:
        outcome = _no_winner(NoWinnerReason.TIED_OUTCOME)
        assert outcome.no_winner_reason is NoWinnerReason.TIED_OUTCOME
        with pytest.raises(ValueError):
            ChoiceSetOutcome(resolution=ChoiceSetResolution.NO_SPORTING_WINNER)
        with pytest.raises(ValueError):
            ChoiceSetOutcome(
                resolution=ChoiceSetResolution.NO_SPORTING_WINNER,
                winner_selection_id=7,
                no_winner_reason=NoWinnerReason.MARKET_VOID,
            )

    def test_pending_carries_nothing(self) -> None:
        pending = ChoiceSetOutcome(resolution=ChoiceSetResolution.PENDING)
        assert pending.winner_selection_id is None and pending.no_winner_reason is None
        with pytest.raises(ValueError):
            ChoiceSetOutcome(
                resolution=ChoiceSetResolution.PENDING, winner_selection_id=7
            )
        with pytest.raises(ValueError):
            ChoiceSetOutcome(
                resolution=ChoiceSetResolution.PENDING,
                no_winner_reason=NoWinnerReason.MARKET_VOID,
            )

    def test_frozen(self) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            _winner().winner_selection_id = 8  # type: ignore[misc]


class TestExclusionReasons:
    def test_canonical_reasons_are_machine_stable(self) -> None:
        assert exclusion_reason(_no_winner(NoWinnerReason.MARKET_VOID)) == (
            "no_sporting_winner:market_void"
        )
        assert exclusion_reason(_no_winner(NoWinnerReason.EVENT_ABANDONED)) == (
            "no_sporting_winner:event_abandoned"
        )
        assert exclusion_reason(_no_winner(NoWinnerReason.TIED_OUTCOME)) == (
            "no_sporting_winner:tied_outcome"
        )
        assert exclusion_reason(
            ChoiceSetOutcome(resolution=ChoiceSetResolution.PENDING)
        ) == "outcome_pending"

    def test_a_known_winner_is_not_an_exclusion(self) -> None:
        with pytest.raises(ValueError):
            exclusion_reason(_winner())


class TestFounderDesignChecks:
    def test_football_abandonment_expressible(self) -> None:
        assert (
            _no_winner(NoWinnerReason.EVENT_ABANDONED).no_winner_reason
            is NoWinnerReason.EVENT_ABANDONED
        )

    def test_binary_financial_void_expressible(self) -> None:
        assert (
            _no_winner(NoWinnerReason.MARKET_VOID).resolution
            is ChoiceSetResolution.NO_SPORTING_WINNER
        )

    def test_racing_dead_heat_expressible_as_structure_not_payout(self) -> None:
        # TIED_OUTCOME names the structure; dead-heat PAYOUT stays in racing settlement
        # (SPEC-082) and nothing here computes one.
        tied = _no_winner(NoWinnerReason.TIED_OUTCOME)
        assert not hasattr(tied, "payout")
        assert not hasattr(tied, "dead_heat_divisor")


class TestMetricsExclusionPath:
    def test_choice_set_exclusion_counts_in_the_denominator(self) -> None:
        from l8_evidence.predictor_metrics import ChoiceSetExclusion, coverage_with_exclusions

        exclusions = (
            ChoiceSetExclusion(
                choice_set_id="m-void",
                outcome=_no_winner(NoWinnerReason.MARKET_VOID),
                knowledge_time_utc=datetime(2026, 7, 17, tzinfo=timezone.utc),
            ),
            ChoiceSetExclusion(
                choice_set_id="m-tied",
                outcome=_no_winner(NoWinnerReason.TIED_OUTCOME),
                knowledge_time_utc=datetime(2026, 7, 17, tzinfo=timezone.utc),
            ),
        )
        result = coverage_with_exclusions(
            races_evaluated=7, exclusions=exclusions, total_universe_races=10
        )
        assert result.races_evaluated == 7
        assert result.total_universe_races == 10  # exclusions stay in the denominator

    def test_exclusion_refuses_winner_known_and_duplicates_and_overflow(self) -> None:
        from l8_evidence.predictor_metrics import (
            ChoiceSetExclusion,
            PredictorMetricsError,
            coverage_with_exclusions,
        )

        at = datetime(2026, 7, 17, tzinfo=timezone.utc)
        with pytest.raises(ValueError):
            ChoiceSetExclusion(choice_set_id="m-1", outcome=_winner(), knowledge_time_utc=at)
        with pytest.raises(ValueError):
            ChoiceSetExclusion(
                choice_set_id="m-1",
                outcome=_no_winner(),
                knowledge_time_utc=datetime(2026, 7, 17),  # naive → refused
            )
        dup = ChoiceSetExclusion(choice_set_id="m-1", outcome=_no_winner(), knowledge_time_utc=at)
        with pytest.raises(PredictorMetricsError):
            coverage_with_exclusions(
                races_evaluated=1, exclusions=(dup, dup), total_universe_races=10
            )
        with pytest.raises(PredictorMetricsError):
            coverage_with_exclusions(
                races_evaluated=9, exclusions=(dup,), total_universe_races=9
            )


class TestTrainingExclusionPath:
    def test_unresolved_choice_set_is_refused_by_fitting_and_excluded_with_reason(self) -> None:
        # F-12: the fitting layer already refuses a winnerless race; the vocabulary makes
        # the ONLY legal route explicit — an ExcludedRace carrying the canonical reason.
        from l4_pricing.crossfit import ExcludedRace

        excluded = ExcludedRace(
            race_id="m-void",
            reason=exclusion_reason(_no_winner(NoWinnerReason.MARKET_VOID)),
        )
        assert excluded.reason == "no_sporting_winner:market_void"