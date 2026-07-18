"""F1 — the structural null: uniform 1/N(active) through the SAME StageOneFamily seam
as every real family (Stage 2B §3). It exists to prove the harness cannot manufacture
signal: it carries no player-strength information, no odds, no identity — its fitted
artefact is metadata-free and its prediction depends only on the count of active
selections. If F1 ever appears superior through a path unavailable to real families,
that is a pipeline defect, never a model result. No special evaluator path exists."""
from __future__ import annotations

from typing import TYPE_CHECKING, Mapping, Sequence

if TYPE_CHECKING:
    from l4_pricing.horizon import HorizonLabel
    from l4_pricing.races import FeatureSchema, Race

__all__ = ["StructuralNullFamily"]


class _NullModel:
    """Deliberately empty: the null has nothing to learn and nothing to leak."""


class StructuralNullFamily:
    family_id = "structural-null-v1"

    def fit(
        self,
        _races: "Sequence[Race]",
        _schema: "FeatureSchema",
        *,
        horizon: "HorizonLabel",  # noqa: ARG002  # pylint: disable=unused-argument
        max_iter: int,  # noqa: ARG002  # pylint: disable=unused-argument
    ) -> _NullModel:
        return _NullModel()

    def predict(
        self, _model: object, race: "Race", *, horizon: "HorizonLabel"  # noqa: ARG002  # pylint: disable=unused-argument
    ) -> Mapping[int, float]:
        active = [r.runner_id for r in race.runners if not r.non_runner]
        return {rid: 1.0 / len(active) for rid in active}
