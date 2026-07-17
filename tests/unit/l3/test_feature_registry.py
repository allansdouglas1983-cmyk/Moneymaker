"""SPEC-023: the versioned, sport-agnostic feature-declaration registry (ADR 0017 S6).

Covers the declaration contract (provenance mode with a mandatory true-publication-time
rule for backfill, fail-closed licensing status, explicit-exclusion-only missing-data
behaviour, evidence status gated on a gate reference), the registry's append-only
refusals (duplicate name+version, no mutation/delete surface), the sport-agnostic design
test (football Match Odds and binary prediction-market declarations construct cleanly),
and the zero-numeric-literal constraint on the module itself.
"""
from __future__ import annotations

import ast
import inspect

import pytest

import l3_features.feature_registry as feature_registry_module
from l3_features.feature_registry import (
    DuplicateFeatureVersionError,
    EvidenceStatus,
    FeatureDeclaration,
    FeatureDeclarationError,
    FeatureRegistry,
    FeatureRegistryError,
    LicensingStatus,
    MissingDataBehaviour,
    ProvenanceMode,
    UnknownFeatureError,
)
from l3_features import knowledge_time

pytestmark = pytest.mark.spec("SPEC-023")


def _declaration(**overrides: object) -> FeatureDeclaration:
    fields: dict[str, object] = {
        "name": "implied-probability-drift",
        "description": "signed drift of the market implied probability over the window",
        "knowledge_time_semantics": (
            "first usable at the receive_time_utc of the last order-book update in the "
            "window; provably before the off by SPEC-020 build-time enforcement"
        ),
        "source_id": "betfair-stream-capture",
        "licensing_status": LicensingStatus.LICENSED_FOR_RESEARCH,
        "provenance_mode": ProvenanceMode.LIVE_CAPTURED,
        "true_publication_time_rule": None,
        "missing_data_behaviour": MissingDataBehaviour.EXPLICIT_EXCLUSION,
        "deterministic_definition": (
            "difference between window-end and window-start implied probability, both "
            "computed by the versioned reducer"
        ),
        "version": "one",
        "evidence_status": EvidenceStatus.DECLARED,
        "validation_gate_reference": None,
    }
    fields.update(overrides)
    return FeatureDeclaration(**fields)  # type: ignore[arg-type]


class TestFeatureDeclaration:
    def test_live_captured_declared_declaration_constructs(self) -> None:
        declaration = _declaration()
        assert declaration.name == "implied-probability-drift"
        assert declaration.provenance_mode is ProvenanceMode.LIVE_CAPTURED
        assert declaration.evidence_status is EvidenceStatus.DECLARED

    def test_declaration_is_frozen(self) -> None:
        declaration = _declaration()
        with pytest.raises(AttributeError):
            declaration.name = "renamed"  # type: ignore[misc]

    def test_provenance_mode_is_the_knowledge_time_enum(self) -> None:
        # SPEC-023 already defines the closed provenance vocabulary in
        # l3_features.knowledge_time; the registry must reuse it, not fork it.
        assert ProvenanceMode is knowledge_time.ProvenanceMode

    def test_backfilled_without_true_publication_time_rule_is_refused(self) -> None:
        with pytest.raises(FeatureDeclarationError):
            _declaration(
                provenance_mode=ProvenanceMode.BACKFILLED,
                true_publication_time_rule=None,
            )

    def test_backfilled_with_blank_rule_is_refused(self) -> None:
        with pytest.raises(FeatureDeclarationError):
            _declaration(
                provenance_mode=ProvenanceMode.BACKFILLED,
                true_publication_time_rule="   ",
            )

    def test_backfilled_with_declared_rule_constructs(self) -> None:
        declaration = _declaration(
            provenance_mode=ProvenanceMode.BACKFILLED,
            true_publication_time_rule=(
                "true publication time is the provider's published_at field, never the "
                "backfill first_seen_ts"
            ),
        )
        assert declaration.provenance_mode is ProvenanceMode.BACKFILLED

    def test_live_captured_with_publication_rule_is_refused(self) -> None:
        # A live-captured feature has no backfill publication rule; supplying one is a
        # contradictory declaration and must be refused, not ignored.
        with pytest.raises(FeatureDeclarationError):
            _declaration(
                provenance_mode=ProvenanceMode.LIVE_CAPTURED,
                true_publication_time_rule="provider published_at",
            )

    def test_validated_without_gate_reference_is_refused(self) -> None:
        with pytest.raises(FeatureDeclarationError):
            _declaration(
                evidence_status=EvidenceStatus.VALIDATED,
                validation_gate_reference=None,
            )

    def test_validated_with_gate_reference_constructs(self) -> None:
        declaration = _declaration(
            evidence_status=EvidenceStatus.VALIDATED,
            validation_gate_reference="specs/gates/v1.yaml#feature-validation",
        )
        assert declaration.evidence_status is EvidenceStatus.VALIDATED

    def test_declared_with_gate_reference_is_refused(self) -> None:
        # A gate reference on a merely-DECLARED feature would let prose imply a
        # validation that never ran.
        with pytest.raises(FeatureDeclarationError):
            _declaration(
                evidence_status=EvidenceStatus.DECLARED,
                validation_gate_reference="specs/gates/v1.yaml#feature-validation",
            )

    @pytest.mark.parametrize(
        "field",
        [
            "name",
            "description",
            "knowledge_time_semantics",
            "source_id",
            "deterministic_definition",
            "version",
        ],
    )
    def test_blank_required_text_is_refused(self, field: str) -> None:
        with pytest.raises(FeatureDeclarationError):
            _declaration(**{field: "  "})

    def test_wrong_enum_types_are_refused(self) -> None:
        with pytest.raises(FeatureDeclarationError):
            _declaration(licensing_status="LICENSED_FOR_RESEARCH")
        with pytest.raises(FeatureDeclarationError):
            _declaration(provenance_mode="live_captured")
        with pytest.raises(FeatureDeclarationError):
            _declaration(missing_data_behaviour="explicit_exclusion")
        with pytest.raises(FeatureDeclarationError):
            _declaration(evidence_status="DECLARED")


class TestClosedVocabularies:
    def test_licensing_status_members_are_exactly_the_closed_set(self) -> None:
        assert {member.name for member in LicensingStatus} == {
            "LICENSED_FOR_RESEARCH",
            "UNLICENSED",
            "PENDING_REVIEW",
        }

    def test_licensing_is_fail_closed(self) -> None:
        # Anything not explicitly licensed is unusable — including any member that is
        # not LICENSED_FOR_RESEARCH, now or in a future vocabulary extension.
        for member in LicensingStatus:
            expected = member is LicensingStatus.LICENSED_FOR_RESEARCH
            assert member.permits_research_use() is expected

    def test_missing_data_behaviour_has_only_explicit_exclusion(self) -> None:
        # The universe is frozen: a missing feature produces an exclusion with a
        # knowledge-time, never a disappearance and never a silent imputation. No
        # imputation member exists to reach for.
        assert [member.name for member in MissingDataBehaviour] == ["EXPLICIT_EXCLUSION"]

    def test_evidence_status_members_are_exactly_declared_and_validated(self) -> None:
        assert {member.name for member in EvidenceStatus} == {"DECLARED", "VALIDATED"}


class TestFeatureRegistry:
    def test_register_and_retrieve(self) -> None:
        registry = FeatureRegistry()
        declaration = _declaration()
        registry.register(declaration)
        assert registry.declaration_for(declaration.name, declaration.version) is declaration

    def test_duplicate_name_and_version_is_refused(self) -> None:
        registry = FeatureRegistry()
        registry.register(_declaration())
        with pytest.raises(DuplicateFeatureVersionError):
            registry.register(_declaration())

    def test_new_version_of_same_name_is_a_new_entry(self) -> None:
        registry = FeatureRegistry()
        first = _declaration(version="one")
        second = _declaration(version="two")
        registry.register(first)
        registry.register(second)
        assert registry.versions_of(first.name) == ("one", "two")
        assert registry.declarations() == (first, second)

    def test_unknown_feature_is_refused_not_defaulted(self) -> None:
        registry = FeatureRegistry()
        with pytest.raises(UnknownFeatureError):
            registry.declaration_for("never-registered", "one")
        with pytest.raises(UnknownFeatureError):
            registry.versions_of("never-registered")

    def test_unknown_version_of_known_feature_is_refused(self) -> None:
        registry = FeatureRegistry()
        registry.register(_declaration(version="one"))
        with pytest.raises(UnknownFeatureError):
            registry.declaration_for("implied-probability-drift", "two")

    def test_registry_has_no_mutation_or_delete_surface(self) -> None:
        forbidden = (
            "delete",
            "remove",
            "unregister",
            "update",
            "replace",
            "mutate",
            "clear",
            "pop",
        )
        public = [name for name in dir(FeatureRegistry) if not name.startswith("_")]
        for name in public:
            lowered = name.lower()
            assert not any(token in lowered for token in forbidden), name

    def test_error_taxonomy(self) -> None:
        assert issubclass(FeatureDeclarationError, FeatureRegistryError)
        assert issubclass(DuplicateFeatureVersionError, FeatureRegistryError)
        assert issubclass(UnknownFeatureError, FeatureRegistryError)


class TestSportAgnosticDesign:
    """Founder design test: the abstractions must also fit football and binary markets."""

    def test_football_match_odds_feature_declares_cleanly(self) -> None:
        declaration = _declaration(
            name="home-side-rest-days",
            description="days since the home side's previous competitive fixture",
            knowledge_time_semantics=(
                "first usable when the fixture list for the current round is published, "
                "provably before kick-off"
            ),
            source_id="fixture-list-provider",
            deterministic_definition=(
                "calendar-day difference between this fixture's scheduled start date and "
                "the side's previous completed fixture date"
            ),
        )
        registry = FeatureRegistry()
        registry.register(declaration)
        assert registry.declaration_for("home-side-rest-days", "one") is declaration

    def test_binary_prediction_market_feature_declares_cleanly(self) -> None:
        declaration = _declaration(
            name="binary-mid-implied-probability",
            description="implied probability at the midpoint of the binary contract book",
            knowledge_time_semantics=(
                "first usable at receive time of the order-book snapshot, provably "
                "before contract resolution"
            ),
            source_id="prediction-market-feed",
            deterministic_definition=(
                "midpoint of best bid and best ask, expressed as an implied probability "
                "by the versioned reducer"
            ),
        )
        registry = FeatureRegistry()
        registry.register(declaration)
        assert declaration.missing_data_behaviour is MissingDataBehaviour.EXPLICIT_EXCLUSION

    def test_module_mentions_no_sport(self) -> None:
        source = inspect.getsource(feature_registry_module).lower()
        for word in ("racing", "runner", "horse", "tennis", "jockey", "surface elo"):
            assert word not in source, word


class TestNoNumericLiterals:
    def test_module_contains_zero_numeric_literals(self) -> None:
        # Declarations carry no numbers in v-one and the module bakes in none: every
        # numeric quantity in this platform is declared per-experiment or per-feature by
        # a human, never as a module constant.
        source = inspect.getsource(feature_registry_module)
        tree = ast.parse(source)
        numeric = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, (int, float, complex))
            and not isinstance(node.value, bool)
        ]
        assert numeric == []
