"""Generic choice-set outcome vocabulary (A6; audit F-10/F-11/F-12).

REPRESENTATIONAL ONLY. This module names how one mutually exclusive choice set resolved:
a known winner, no sporting winner (void / abandoned / tied), or not yet resolved — so
that training, metrics and snapshot layers can account for such sets EXPLICITLY (an
exclusion with a reason and a knowledge-time) instead of silently omitting them, which
is the "disappearance" the evidence rules forbid.

It deliberately encodes NO settlement consequence:

* racing settlement (dead-heat payouts, reduction factors, void handling) stays in
  ``l7_settle`` behind the racing policy (SPEC-082);
* tennis settlement stays SPEC-084 and REFUSED — ``TIED_OUTCOME`` and ``MARKET_VOID``
  here are STRUCTURES ("more than one selection shares the result"; "the market
  resolved with no sporting winner"), never rules about money. Nothing in this module
  computes, implies, or defaults a payout, and no consumer may treat a resolution
  member as one.

The canonical exclusion-reason strings are machine-stable: they feed
``l4_pricing.crossfit.ExcludedRace.reason`` and the predictor-metrics exclusion path,
so the same unresolved choice set is described identically everywhere it is excluded.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique

__all__ = [
    "ChoiceSetResolution",
    "NoWinnerReason",
    "ChoiceSetOutcome",
    "exclusion_reason",
]


@unique
class ChoiceSetResolution(Enum):
    """How the choice set resolved. Closed deliberately — adding a member is a governed
    specification change, not a runtime concern."""

    WINNER_KNOWN = "WINNER_KNOWN"
    NO_SPORTING_WINNER = "NO_SPORTING_WINNER"
    PENDING = "PENDING"


@unique
class NoWinnerReason(Enum):
    """Why no sporting winner exists. Structures, never payout rules:

    * ``MARKET_VOID`` — the market resolved void (racing void; a tennis walkover's
      market treatment is SPEC-084's to decide LATER — recording a void here records
      the exchange's observed resolution, not a rule of ours);
    * ``EVENT_ABANDONED`` — the event was abandoned (racing abandonment, football
      abandonment);
    * ``TIED_OUTCOME`` — more than one selection shares the result (racing dead heat
      as a structure; the PAYOUT stays in SPEC-082's racing settlement).
    """

    MARKET_VOID = "MARKET_VOID"
    EVENT_ABANDONED = "EVENT_ABANDONED"
    TIED_OUTCOME = "TIED_OUTCOME"


@dataclass(frozen=True)
class ChoiceSetOutcome:
    """One choice set's resolution. Coherence refused both directions:

    * ``WINNER_KNOWN`` requires ``winner_selection_id`` and forbids a reason;
    * ``NO_SPORTING_WINNER`` requires ``no_winner_reason`` and forbids a winner;
    * ``PENDING`` carries nothing.
    """

    resolution: ChoiceSetResolution
    winner_selection_id: int | None = None
    no_winner_reason: NoWinnerReason | None = None

    def __post_init__(self) -> None:
        if self.resolution is ChoiceSetResolution.WINNER_KNOWN:
            if self.winner_selection_id is None:
                raise ValueError("WINNER_KNOWN requires winner_selection_id")
            if self.no_winner_reason is not None:
                raise ValueError("WINNER_KNOWN must not carry a no_winner_reason")
        elif self.resolution is ChoiceSetResolution.NO_SPORTING_WINNER:
            if self.no_winner_reason is None:
                raise ValueError("NO_SPORTING_WINNER requires a no_winner_reason")
            if self.winner_selection_id is not None:
                raise ValueError("NO_SPORTING_WINNER must not carry a winner_selection_id")
        else:  # PENDING
            if self.winner_selection_id is not None:
                raise ValueError("PENDING must not carry a winner_selection_id")
            if self.no_winner_reason is not None:
                raise ValueError("PENDING must not carry a no_winner_reason")


def exclusion_reason(outcome: ChoiceSetOutcome) -> str:
    """The canonical, machine-stable exclusion reason for an unresolved/no-winner set.

    A ``WINNER_KNOWN`` outcome is evaluable, not excludable — asking for its exclusion
    reason is refused so a resolved set can never be quietly dropped under an
    exclusion label.
    """
    if outcome.resolution is ChoiceSetResolution.WINNER_KNOWN:
        raise ValueError(
            "a WINNER_KNOWN choice set is evaluable, not excludable; it has no "
            "exclusion reason"
        )
    if outcome.resolution is ChoiceSetResolution.PENDING:
        return "outcome_pending"
    assert outcome.no_winner_reason is not None  # construction-guaranteed
    return f"no_sporting_winner:{outcome.no_winner_reason.value.lower()}"
