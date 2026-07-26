"""STAGE3-0006 §5.1 — immutable result-contract guards.

Immutability is a GOVERNED contract, not a probability-value detail. These tests kill the
`@dataclass(frozen=True)` -> `frozen=False` mutants across every advice-critical coherence
result type by proving that field assignment raises FrozenInstanceError, that a held alias
cannot mutate PMF contents, and that the deterministic digest of an instance is stable.
"""
from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest

from sport_tennis.coherence.format_evidence import TIER_A, FormatEvidence
from sport_tennis.coherence.formats import MatchFormat, format_spec
from sport_tennis.coherence.holdout import (
    COMBINED_TOTAL_OVER,
    HOLDOUT_SURFACE_UNAVAILABLE,
    HoldoutMetric,
    HoldoutObservation,
    HoldoutSurface,
)
from sport_tennis.coherence.match import MatchDistribution
from sport_tennis.coherence.pmf import HandicapCover, OverUnder
from sport_tennis.coherence.scoring import SetResult
from sport_tennis.coherence.solver import IdentificationResult, Root, ServerSolve

_ROOT = Root(0.6, 0.6, True, 1e-7, 3.0, False)
_SS = ServerSolve(True, "IDENTIFIED", (_ROOT,))

# One representative valid instance of every frozen coherence result type, with a field to poke.
_INSTANCES = [
    (SetResult(games={(6, 0): 1.0}, first_server_wins=1.0), "first_server_wins"),
    (MatchDistribution(0.5, {12: 1.0}, {0: 1.0}), "match_win_a"),
    (OverUnder(Decimal("22.5"), 0.5, 0.5, 0.0), "over"),
    (HandicapCover(Decimal("-3.5"), 0.5, 0.5, 0.0), "a_covers"),
    (_ROOT, "p_a"),
    (_SS, "status"),
    (IdentificationResult("IDENTIFIED", (), (_SS, _SS), (0.35, 0.9), Decimal("22.5"),
                          MatchFormat.BO3_AD_TB7_ALL_SETS), "status"),
    (HoldoutObservation(COMBINED_TOTAL_OVER, Decimal("24.5"), 0.4, 0.42), "observed_back_prob"),
    (HoldoutMetric(COMBINED_TOTAL_OVER, Decimal("24.5"), 0.3, 0.3, 0.0, 0.4, 0.42, 0.41, 0.0, 2),
     "line"),
    (HoldoutSurface(HOLDOUT_SURFACE_UNAVAILABLE, ()), "status"),
    (format_spec(MatchFormat.BO3_AD_TB7_ALL_SETS), "sets_to_win"),
    (FormatEvidence(TIER_A, "BO3_AD_TB7_ALL_SETS", "GOVERNED_COMPETITION_IDENTITY"), "token"),
]


@pytest.mark.parametrize("instance,field", _INSTANCES, ids=lambda v: type(v).__name__
                         if not isinstance(v, str) else v)
def test_result_type_is_frozen(instance: object, field: str) -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(instance, field, getattr(instance, field))


def test_frozen_covers_every_declared_dataclass() -> None:
    # Guard against a new result type being added without a frozen guard: every dataclass in
    # these modules must be frozen.
    import sport_tennis.coherence.discretisation_stability as m_ds
    import sport_tennis.coherence.formats as m_formats
    import sport_tennis.coherence.format_evidence as m_fe
    import sport_tennis.coherence.holdout as m_holdout
    import sport_tennis.coherence.match as m_match
    import sport_tennis.coherence.pmf as m_pmf
    import sport_tennis.coherence.scan_variants as m_sv
    import sport_tennis.coherence.scoring as m_scoring
    import sport_tennis.coherence.solver as m_solver
    # STAGE3-0006C-D-A3: inventory EXTENDED (never narrowed) to the amendment's two new
    # production modules so ScanVariantDefinition / VariantSolveSnapshot / StabilityDecision
    # are covered by this guard directly.
    for mod in (m_formats, m_fe, m_holdout, m_match, m_pmf, m_scoring, m_solver, m_sv, m_ds):
        for name in dir(mod):
            obj = getattr(mod, name)
            if dataclasses.is_dataclass(obj) and isinstance(obj, type):
                params = getattr(obj, "__dataclass_params__")
                assert params.frozen, f"{mod.__name__}.{name} is not frozen"


def test_alias_cannot_mutate_pmf_contents_via_frozen_field() -> None:
    md = MatchDistribution(0.5, {12: 0.5, 13: 0.5}, {0: 1.0})
    with pytest.raises(dataclasses.FrozenInstanceError):
        md.total_games_pmf = {99: 1.0}  # type: ignore[misc]
    assert md.total_games_pmf == {12: 0.5, 13: 0.5}


def test_frozen_instance_digest_is_stable() -> None:
    r = Root(0.61, 0.59, True, 1e-7, 2.5, False)
    before = dataclasses.astuple(r)
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.p_a = 0.99  # type: ignore[misc]
    assert dataclasses.astuple(r) == before
