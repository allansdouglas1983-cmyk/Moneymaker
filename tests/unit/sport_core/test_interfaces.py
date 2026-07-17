"""ADR 0017 S5 — probability + model interfaces: CONTRACTS ONLY (Phases 4-5).

``sport_core/interfaces.py`` does not exist yet in the repository — these tests are
RED by construction (module import failure) until a lead-reviewed implementation lands
in its own governed slice. They pin the contract this worker's draft
(``/tmp/.../scratchpad/s5/interfaces.py`` at draft time) must satisfy:

* every seam is a ``typing.Protocol`` decorated ``@runtime_checkable``;
* no method body contains anything beyond an optional docstring + ``...``  — this is a
  CONTRACT, never a stub with a numeric placeholder (CLAUDE.md rule 1: a missing feature
  is recoverable, a silently degraded one corrupts every conclusion drawn after it; a
  Protocol with a real body would BE a silent implementation);
  * a conforming dummy structurally satisfies ``isinstance``; a non-conforming one fails;
* every model-style contract (the generic providers keyed on ``model_id`` and every named
  Phase-5 model contract) requires BOTH ``model_id`` and ``model_version`` — SPEC-024/036/
  037's lineage fields all key off exactly this pair;
* the module contains zero float literals and zero numeric probability constants — a
  Protocol file has no business asserting what a probability IS, only what SHAPE a
  probability-producing seam has (CLAUDE.md rule 3: an LLM never estimates a probability;
  a hard-coded numeric constant in this file would be exactly that estimate, laundered
  through a "just typing" seam);
* every generic seam takes the sport-agnostic ``Race`` (the audit's mutually-exclusive
  choice-set contract, native for N==2 and N>2 alike) — the founder's design test that
  every generic protocol must fit football Match Odds and a binary financial market
  unchanged.
"""
from __future__ import annotations

import ast
import inspect
import typing
from typing import get_type_hints

import pytest

pytestmark = pytest.mark.spec("SPEC-034")

# Deliberately a plain import, not importorskip: until a lead-reviewed implementation
# lands in its own governed slice this MUST fail collection (RED), not skip — a skip
# would silently report green on a missing money/evidence-adjacent contract.
import sport_core.interfaces as interfaces  # noqa: E402

# Every protocol this slice defines, mapped to the exact member names (methods + properties)
# a conforming implementation must expose. Hand-enumerated (not derived from typing internals)
# so this test pins the CONTRACT, not whatever the implementation module happens to compute.
_GENERIC_PROVIDER_PROTOCOLS: dict[str, tuple[str, ...]] = {
    "FundamentalProbabilityProvider": ("model_id", "model_version", "predict"),
    "MarketProbabilityProvider": ("price_version", "price"),
    "CombinedProbabilityProvider": ("model_id", "model_version", "combine"),
    "CalibrationProvider": ("model_id", "model_version", "calibrate"),
    "UncertaintyProvider": ("model_id", "model_version", "distribution"),
    "FeatureGenerator": ("generator_id", "generator_version", "generate"),
    "RankingProvider": ("model_id", "model_version", "rank_scores"),
}

_TENNIS_ADAPTER_PROTOCOLS: dict[str, tuple[str, ...]] = {
    "SurfaceRatingProvider": ("model_id", "model_version", "rating"),
    "FitnessSignalProvider": ("model_id", "model_version", "signal"),
    "ServeStrengthProvider": ("model_id", "model_version", "serve_strength"),
    "ReturnStrengthProvider": ("model_id", "model_version", "return_strength"),
}

_MODEL_CONTRACT_PROTOCOLS: dict[str, tuple[str, ...]] = {
    "SurfaceEloModel": ("model_id", "model_version", "rating"),
    "WeightedEloModel": ("model_id", "model_version", "rating"),
    "BradleyTerryModel": ("model_id", "model_version", "win_probability"),
    "RegularisedLogisticModel": ("model_id", "model_version", "feature_schema", "win_probability"),
    "BayesianModel": ("model_id", "model_version", "posterior_samples"),
    "GradientBoostingModel": ("model_id", "model_version", "win_probability"),
    "EnsembleModel": ("model_id", "model_version", "member_model_ids", "posterior_samples"),
    "MarketCombinationModel": ("model_id", "model_version", "combine"),
}

_ALL_PROTOCOLS: dict[str, tuple[str, ...]] = {
    **_GENERIC_PROVIDER_PROTOCOLS,
    **_TENNIS_ADAPTER_PROTOCOLS,
    **_MODEL_CONTRACT_PROTOCOLS,
}

# Protocols whose versioned identity is the model_id/model_version pair — every protocol
# except the market-info seam (deliberately NOT a model, SPEC-036: identity is
# price_version) and the feature generator (identity is generator_id/generator_version,
# since a feature generator is not itself a probability model).
_NON_MODEL_ID_PROTOCOLS = {"MarketProbabilityProvider", "FeatureGenerator"}
_MODEL_ID_IDENTITY_PROTOCOLS = {
    name: members for name, members in _ALL_PROTOCOLS.items() if name not in _NON_MODEL_ID_PROTOCOLS
}


def _protocol(name: str) -> type:
    return typing.cast(type, getattr(interfaces, name))


def _make_conforming(members: tuple[str, ...]) -> object:
    """A minimal object exposing exactly the named attributes, nothing else load-bearing."""
    namespace = {member: (lambda self, *a, **kw: None) for member in members}
    return type("Conforming", (), namespace)()


class _NonConforming:
    """An object satisfying none of these protocols' members."""


# --- every declared protocol is a runtime_checkable Protocol ----------------------------------


@pytest.mark.parametrize("name", sorted(_ALL_PROTOCOLS))
def test_every_protocol_is_a_runtime_checkable_protocol(name: str) -> None:
    cls = _protocol(name)
    assert isinstance(cls, type)
    assert any(base.__name__ == "Protocol" for base in cls.__mro__), f"{name} must subclass typing.Protocol"
    assert getattr(cls, "_is_protocol", False) is True, f"{name} must be a Protocol"
    assert getattr(cls, "_is_runtime_protocol", False) is True, (
        f"{name} must be decorated @runtime_checkable so isinstance() performs a "
        "structural check against a future concrete implementation"
    )


# --- structural conformance: isinstance is the sanctioned check -------------------------------


@pytest.mark.parametrize("name,members", sorted(_ALL_PROTOCOLS.items()))
def test_conforming_dummy_satisfies_isinstance(name: str, members: tuple[str, ...]) -> None:
    cls = _protocol(name)
    dummy = _make_conforming(members)
    assert isinstance(dummy, cls), f"a dummy exposing exactly {members} must satisfy {name}"


@pytest.mark.parametrize("name", sorted(_ALL_PROTOCOLS))
def test_nonconforming_dummy_fails_isinstance(name: str) -> None:
    cls = _protocol(name)
    assert not isinstance(_NonConforming(), cls), (
        f"an object with none of {name}'s members must NOT satisfy isinstance() — a "
        "permissive runtime_checkable check would defeat the whole point of the contract"
    )


@pytest.mark.parametrize("name,members", sorted(_ALL_PROTOCOLS.items()))
def test_dummy_missing_one_member_fails_isinstance(name: str, members: tuple[str, ...]) -> None:
    # Every declared member is load-bearing: dropping any single one must break conformance.
    for missing in members:
        partial = tuple(m for m in members if m != missing)
        dummy = _make_conforming(partial)
        cls = _protocol(name)
        assert not isinstance(dummy, cls), (
            f"{name}: an object missing {missing!r} must not satisfy isinstance() — every "
            "declared member is required, none is optional"
        )


# --- versioned identity is mandatory on every model-style contract ----------------------------


@pytest.mark.parametrize("name,members", sorted(_MODEL_ID_IDENTITY_PROTOCOLS.items()))
def test_model_style_protocol_requires_model_id_and_model_version(
    name: str, members: tuple[str, ...]
) -> None:
    assert "model_id" in members, f"{name} must require model_id"
    assert "model_version" in members, f"{name} must require model_version"


def test_market_probability_provider_never_carries_a_model_id() -> None:
    # SPEC-036: p_market_info is a frozen versioned PRICE, never labelled a model
    # prediction — its identity is price_version, with no model_id/model_version pair.
    cls = _protocol("MarketProbabilityProvider")
    dummy = _make_conforming(("price_version", "price"))
    assert isinstance(dummy, cls)
    without_model_fields = _make_conforming(("price_version", "price", "model_id", "model_version"))
    # Extra attributes are harmless (isinstance only requires presence of protocol members);
    # the real guard is that the protocol itself never lists model_id/model_version, which
    # test_model_style_protocol_requires_model_id_and_model_version's exclusion covers.
    assert isinstance(without_model_fields, cls)
    assert "model_id" not in _GENERIC_PROVIDER_PROTOCOLS["MarketProbabilityProvider"]


# --- structural scan: no method body beyond an optional docstring + Ellipsis ------------------


def _iter_function_defs(tree: ast.AST) -> typing.Iterator[ast.FunctionDef]:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            yield node


def test_no_function_body_contains_anything_but_docstring_and_ellipsis() -> None:
    source_path = inspect.getsourcefile(interfaces)
    assert source_path is not None
    with open(source_path, encoding="utf-8") as fh:
        source = fh.read()
    tree = ast.parse(source, filename=source_path)
    checked = 0
    for func in _iter_function_defs(tree):
        checked += 1
        body = list(func.body)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            body = body[1:]  # drop a leading docstring
        assert len(body) == 1, (
            f"{func.name}: a Protocol method body must be exactly one statement (Ellipsis) "
            f"after an optional docstring, found {len(body)}"
        )
        stmt = body[0]
        assert isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and stmt.value.value is Ellipsis, (
            f"{func.name}: body must be `...` — any other statement is an implementation, "
            "not a contract (ADR 0017 S5 forbids implementations in this slice)"
        )
    assert checked > 0, "expected at least one Protocol method to scan"


def test_zero_float_literals_in_module_source() -> None:
    source_path = inspect.getsourcefile(interfaces)
    assert source_path is not None
    with open(source_path, encoding="utf-8") as fh:
        source = fh.read()
    tree = ast.parse(source, filename=source_path)
    floats = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, float)
    ]
    assert floats == [], f"a Protocol/contract file must contain zero float literals, found {floats}"


def test_zero_bare_numeric_constants_in_module_source() -> None:
    # No numeric literal of any kind belongs in a pure-contract file — a Protocol declares
    # shape, never a threshold, default, or probability value.
    source_path = inspect.getsourcefile(interfaces)
    assert source_path is not None
    with open(source_path, encoding="utf-8") as fh:
        source = fh.read()
    tree = ast.parse(source, filename=source_path)
    numbers = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool)
    ]
    assert numbers == [], f"a Protocol/contract file must contain zero numeric constants, found {numbers}"


# --- reused platform types, not reinvented vocabulary ------------------------------------------


def test_reuses_existing_race_probability_and_distribution_types_not_new_ones() -> None:
    from l3_features.feature_set import FeatureSet
    from l4_pricing.distribution import WinProbabilityDistribution
    from l4_pricing.probability_outputs import (
        CombinedProbability,
        FundamentalProbability,
        MarketProbability,
        RaceProbabilityOutputs,
    )
    from l4_pricing.races import FeatureSchema, Race

    hints = get_type_hints(interfaces.CalibrationProvider.calibrate)
    assert hints["return"] is RaceProbabilityOutputs

    predict_hints = get_type_hints(interfaces.FundamentalProbabilityProvider.predict)
    assert predict_hints["race"] is Race
    assert predict_hints["return"] == typing.Mapping[int, FundamentalProbability]

    price_hints = get_type_hints(interfaces.MarketProbabilityProvider.price)
    assert price_hints["return"] == typing.Mapping[int, MarketProbability]

    combine_hints = get_type_hints(interfaces.CombinedProbabilityProvider.combine)
    assert combine_hints["return"] == typing.Mapping[int, CombinedProbability]

    distribution_hints = get_type_hints(interfaces.UncertaintyProvider.distribution)
    assert distribution_hints["return"] == typing.Mapping[int, WinProbabilityDistribution]

    generate_hints = get_type_hints(interfaces.FeatureGenerator.generate)
    assert generate_hints["return"] is FeatureSet

    feature_schema_getter = vars(interfaces.RegularisedLogisticModel)["feature_schema"].fget
    lr_hints = get_type_hints(feature_schema_getter)
    assert lr_hints["return"] is FeatureSchema


# --- founder design test: every generic seam takes the sport-agnostic Race --------------------


@pytest.mark.parametrize(
    "protocol_name,method_name",
    [
        ("FundamentalProbabilityProvider", "predict"),
        ("MarketProbabilityProvider", "price"),
        ("CombinedProbabilityProvider", "combine"),
        ("UncertaintyProvider", "distribution"),
        ("FeatureGenerator", "generate"),
        ("RankingProvider", "rank_scores"),
    ],
)
def test_generic_seams_take_the_sport_agnostic_race_type(protocol_name: str, method_name: str) -> None:
    # A generic seam must fit football Match Odds (N-way) and a binary financial market
    # (N==2) unchanged — both are instances of the same mutually-exclusive-choice-set Race
    # contract the racing adapter already uses. No racing-only type may appear here.
    from l4_pricing.races import Race

    method = getattr(_protocol(protocol_name), method_name)
    hints = get_type_hints(method)
    assert hints.get("race") is Race, (
        f"{protocol_name}.{method_name} must take the generic Race type so it fits any "
        "sport's mutually exclusive choice set, not a racing-specific one"
    )


def test_tennis_flavoured_protocols_are_documented_as_adapter_level_not_core() -> None:
    # These four are declared per this slice's brief, but the module docstring and each
    # protocol's own docstring must say they are NOT a generic Core seam (report flag: the
    # sport_tennis owner may prefer them relocated there).
    for name in _TENNIS_ADAPTER_PROTOCOLS:
        doc = (_protocol(name).__doc__ or "").lower()
        assert "adapter" in doc or "not a generic core seam" in doc, (
            f"{name} must document that it is sport-adapter-level, not a generic Core seam"
        )


def test_model_contracts_and_providers_carry_deterministic_and_no_llm_docstring_language() -> None:
    for name in _ALL_PROTOCOLS:
        doc = (_protocol(name).__doc__ or "").lower()
        assert "deterministic" in doc, f"{name} docstring must state determinism"
        assert "llm" in doc, f"{name} docstring must state no LLM may implement/back it"
