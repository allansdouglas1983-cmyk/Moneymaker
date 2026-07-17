"""Tennis match settlement CONTRACTS ONLY (SPEC-084, planned, money-critical).

ADR 0017 S7 ("Tennis settlement contracts") authorises the *shape* of tennis match
settlement — a closed outcome enum and an immutable settlement-request record — but
explicitly forbids any empirical settlement RULE. The deterministic mapping from a
tennis match outcome (walkover, retirement before/after set one, disqualification,
cancellation, postponement, surface change, pre-match withdrawal) to how Betfair
actually settles the market, and to how such a match should be treated for model
training, predictor scoring, CLV grading, and P&L grading, is DATA-DEPENDENT: it can
only be written once Betfair's Exchange tennis rules page has been fetched and
reconciled against pilot settlement data. That fetch has not succeeded
(DR-TENNIS-SETTLEMENT-001, research ledger: unresolved).

Guessing the rule would silently corrupt every downstream conclusion (CLAUDE.md rule 1)
— a plausible-looking void/settle guess is *worse* than an explicit gap, because a gap
is visibly blocked and a guess is not. So this module does the opposite of guessing:
every call path that would need the real rule raises a typed, documented refusal
(`SettlementPolicyPendingError`) naming exactly what evidence is missing, instead of
returning a number.

This deliberately covers `COMPLETED` too, not only the ambiguous retirement/walkover
cases. A partial policy — "the obvious COMPLETED case settles normally, the hard cases
are pending" — invites silent divergence: a caller who successfully settles some tennis
matches today will assume the rest "mostly work" the same way, and nothing forces a
review when the founder-approved matrix finally lands. Activating the real policy is
a single, whole-matrix, human-approved change (ADR 0017 S7), not an incremental
softening of this refusal.

Nothing in this module imports, reads, or mutates racing settlement
(`l7_settle.outcomes` / `l7_settle.pnl` / `l7_settle.settlement`). Those modules stay
untouched; this module only speaks of their MarketStatus/void CONCEPTS in prose
(a tennis CANCELLED/POSTPONED market is conceptually a void-like market status in the
same sense `l7_settle.outcomes.MarketStatus.VOID` is for racing) so a future reader can
map vocabulary, not so this module can call that code.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique
from types import MappingProxyType
from typing import Mapping, NoReturn


@unique
class TennisMatchOutcome(Enum):
    """Closed set of tennis match outcomes SPEC-084 must eventually settle.

    Closed deliberately: an open/extensible enum would let a caller invent an outcome
    with no settlement policy at all (not even a documented PENDING refusal). Adding a
    member is a specification change, not a runtime concern.
    """

    COMPLETED = "COMPLETED"
    WALKOVER_BEFORE_PLAY = "WALKOVER_BEFORE_PLAY"
    RETIRED_BEFORE_SET1_COMPLETE = "RETIRED_BEFORE_SET1_COMPLETE"
    RETIRED_AFTER_SET1_COMPLETE = "RETIRED_AFTER_SET1_COMPLETE"
    DISQUALIFICATION = "DISQUALIFICATION"
    CANCELLED = "CANCELLED"
    POSTPONED = "POSTPONED"
    SURFACE_CHANGED = "SURFACE_CHANGED"
    PRE_MATCH_WITHDRAWAL = "PRE_MATCH_WITHDRAWAL"


@dataclass(frozen=True)
class TennisSettlementCase:
    """An immutable request to settle one tennis match under SPEC-084.

    ``winner_selection_id`` is mandatory if and only if ``outcome`` is ``COMPLETED``:
    a completed match has exactly one winning selection; every other outcome in this
    enum is, by construction, a match that did not complete in the ordinary sense, so a
    winner selection would assert a fact the outcome itself does not support. Both
    directions are refused at construction rather than left to a downstream consumer to
    notice.
    """

    match_ref_id: str
    outcome: TennisMatchOutcome
    winner_selection_id: int | None = None

    def __post_init__(self) -> None:
        if self.outcome is TennisMatchOutcome.COMPLETED and self.winner_selection_id is None:
            raise ValueError(
                f"{self.match_ref_id}: outcome COMPLETED requires a winner_selection_id"
            )
        if self.outcome is not TennisMatchOutcome.COMPLETED and self.winner_selection_id is not None:
            raise ValueError(
                f"{self.match_ref_id}: winner_selection_id is only valid when outcome is "
                f"COMPLETED, got outcome={self.outcome.name}"
            )


class SettlementPolicyPendingError(Exception):
    """Raised for every tennis settlement request under SPEC-084 (ADR 0017 S7).

    SPEC-084 requires a deterministic outcome-to-settlement mapping (Betfair
    settlement treatment, model-training inclusion, predictor-score inclusion, CLV
    grading, and P&L grading) for each ``TennisMatchOutcome``. That mapping is
    data-dependent on Betfair's Exchange tennis rules for walkover/retirement/
    disqualification/void handling, verified against pilot settlement data — a fetch
    that has not yet succeeded (DR-TENNIS-SETTLEMENT-001, research ledger:
    unresolved). Until a founder-approved policy activates the whole matrix at once,
    every call raises this error instead of guessing a rule that would silently
    corrupt every conclusion drawn from it (CLAUDE.md rule 1).
    """


# Every founder-specified grading dimension a settled tennis outcome must eventually
# resolve. Order is documentation, not behaviour.
_POLICY_DIMENSIONS = (
    "betfair_settlement",
    "model_training_inclusion",
    "predictor_score_inclusion",
    "clv_grading",
    "pnl_grading",
)

_PENDING = "PENDING_EXCHANGE_RULES_VERIFICATION"

POLICY_MATRIX_TEMPLATE: Mapping[TennisMatchOutcome, Mapping[str, str]] = MappingProxyType(
    {
        outcome: MappingProxyType({dimension: _PENDING for dimension in _POLICY_DIMENSIONS})
        for outcome in TennisMatchOutcome
    }
)
"""Documents the five grading dimensions every outcome will eventually need resolved,
with every cell explicitly pending real-world verification. This is a record of what is
*unknown* and *why* (see ``SettlementPolicyPendingError``), not a default value: nothing
in this module reads this mapping to produce a settlement, and no caller may treat
``PENDING_EXCHANGE_RULES_VERIFICATION`` as a settlement outcome.
"""


def settle_tennis_case(case: TennisSettlementCase) -> NoReturn:
    """Refuse to settle a tennis match: the SPEC-084 policy matrix is not yet approved.

    Every ``TennisMatchOutcome`` — including ``COMPLETED`` — raises
    ``SettlementPolicyPendingError`` naming the outcome. See the module docstring and
    the error's docstring for why the happy path is refused along with the hard cases.
    """
    raise SettlementPolicyPendingError(
        f"{case.match_ref_id}: settlement policy for TennisMatchOutcome.{case.outcome.name} "
        "is PENDING_EXCHANGE_RULES_VERIFICATION (SPEC-084, DR-TENNIS-SETTLEMENT-001 "
        "unresolved) — no deterministic outcome-to-settlement mapping is approved yet."
    )
