"""A6 (audit F-10/F-11/F-12, founder order): generic choice-set outcome vocabulary.

REPRESENTATIONAL ONLY. This vocabulary names how a mutually exclusive choice set
resolved — a known winner, no sporting winner (void / abandoned / tied), or not yet
resolved — so that training, metrics and snapshots can account for such sets explicitly
instead of silently omitting them. It encodes NO settlement consequence: racing
settlement stays SPEC-082 behind the racing policy; tennis settlement stays SPEC-084 and
REFUSED. A tied outcome here is a structure ("more than one selection shares the
result"), never a payout rule.

FOUNDER SEMANTIC CORRECTION (A6 reopened narrowly, 2026-07-17): a genuine tie/dead heat
is a RESOLVED outcome with a non-empty winner set — it must never be collapsed into
NO_SPORTING_WINNER. Four distinct resolutions: one winner; multiple winners; no sporting
winner; pending. Sporting resolution, model-training eligibility and exchange financial
settlement remain separate concerns; payout logic stays outside sport_core.

Pins:
* coherence refusals both directions (winner iff WINNER_KNOWN; winner SET of >= 2 iff
  MULTIPLE_WINNERS — a singleton is WINNER_KNOWN, never a one-element set; reason iff
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


def _multi(*sels: int) -> ChoiceSetOutcome:
    return ChoiceSetOutcome(
        resolution=ChoiceSetResolution.MULTIPLE_WINNERS,
        winner_selection_ids=frozenset(sels),
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
            "MULTIPLE_WINNERS",
            "NO_SPORTING_WINNER",
            "PENDING",
        }

    def test_no_winner_reasons_exact(self) -> None:
        # TIED_OUTCOME deliberately does NOT exist here: a tie has winners.
        assert {m.name for m in NoWinnerReason} == {
            "MARKET_VOID",
            "EVENT_ABANDONED",
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

    def test_multiple_winners_requires_a_set_of_at_least_two(self) -> None:
        outcome = _multi(4, 9)
        assert outcome.winner_selection_ids == frozenset({4, 9})
        with pytest.raises(ValueError):
            _multi()  # empty set is not a resolution with winners
        with pytest.raises(ValueError):
            _multi(4)  # a singleton is WINNER_KNOWN, never MULTIPLE_WINNERS
        with pytest.raises(ValueError):
            ChoiceSetOutcome(
                resolution=ChoiceSetResolution.MULTIPLE_WINNERS,
                winner_selection_ids=frozenset({4, 9}),
                no_winner_reason=NoWinnerReason.MARKET_VOID,
            )
        with pytest.raises(ValueError):
            ChoiceSetOutcome(
                resolution=ChoiceSetResolution.WINNER_KNOWN,
                winner_selection_id=4,
                winner_selection_ids=frozenset({4, 9}),
            )

    def test_no_sporting_winner_requires_reason_and_no_winner(self) -> None:
        outcome = _no_winner(NoWinnerReason.EVENT_ABANDONED)
        assert outcome.no_winner_reason is NoWinnerReason.EVENT_ABANDONED
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
        assert exclusion_reason(_multi(4, 9)) == "multiple_winners"
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

    def test_racing_dead_heat_is_resolved_with_multiple_winners_not_collapsed(self) -> None:
        # Founder correction: a dead heat HAS sporting winners — a resolved, non-empty
        # winner set — and must never be collapsed into NO_SPORTING_WINNER. The PAYOUT
        # stays in racing settlement (SPEC-082); nothing here computes one.
        tied = _multi(4, 9)
        assert tied.resolution is ChoiceSetResolution.MULTIPLE_WINNERS
        assert tied.no_winner_reason is None
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
                # Model-training eligibility is separate from sporting resolution: a
                # dead-heated set is RESOLVED (winners exist) yet unevaluable by
                # exactly-one-winner metrics, so it is excludable with its own reason.
                choice_set_id="m-tied",
                outcome=_multi(4, 9),
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