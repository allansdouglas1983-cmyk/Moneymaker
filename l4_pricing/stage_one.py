"""The stage-one model-family seam (A5; audit F-06).

Fold assignment, leakage discipline, exclusions, provenance and OOF production are owned
by the crossfit ORCHESTRATOR (:func:`l4_pricing.crossfit.cross_fit`); a family only fits
and predicts through this seam. Conditional logit is ONE registered implementation
(:data:`l4_pricing.conditional_logit.CONDITIONAL_LOGIT_FAMILY`), not the owner of the
honest OOF path.

A family that cannot fit a training window raises :class:`StageOneFitRefusal` (the
typed refusal base conditional logit's ``SeparationError``/``FitDidNotConverge`` also
inherit) — the orchestrator turns it into explicit per-race exclusions, never a crash
and never a silent skip. A family NEVER supplies provenance: the orchestrator minted
``trained_through``/``training_race_ids`` from its own fold bookkeeping before the
family ever saw the data, so no implementation can misreport what trained it.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Mapping, Protocol, Sequence, runtime_checkable

if TYPE_CHECKING:
    from l4_pricing.horizon import HorizonLabel
    from l4_pricing.races import FeatureSchema, Race

__all__ = ["StageOneFitRefusal", "StageOneFamily"]


class StageOneFitRefusal(Exception):
    """A stage-one family's typed refusal to fit a training window.

    Honest behaviour, not an error to silence: the orchestrator excludes the affected
    fold's races with the refusal text as the explicit reason.
    """


@runtime_checkable
class StageOneFamily(Protocol):
    """One stage-one model family: fit a training window, predict one choice set.

    Deterministic tested code only — no LLM may implement or back a family (CLAUDE.md
    rule 3). ``family_id`` is the family's versioned identity. The fitted artefact is
    opaque to the orchestrator; only ``predict`` may consume it, and the orchestrator
    validates every predicted probability set before minting an OOF row.
    """

    @property
    def family_id(self) -> str: ...

    def fit(
        self,
        races: Sequence["Race"],
        schema: "FeatureSchema",
        *,
        horizon: "HorizonLabel",
        max_iter: int,
    ) -> object: ...

    def predict(
        self, model: object, race: "Race", *, horizon: "HorizonLabel"
    ) -> Mapping[int, float]: ...
