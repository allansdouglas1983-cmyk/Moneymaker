"""Tennis domain contracts (ADR 0017 S4; docs/architecture/sport-agnostic-audit.md slice S4).

RED by design for this slice: ``sport_tennis`` is a contracts-only draft
(``docs/decisions/0017-sport-agnostic-transition.md`` Phase 3) — these tests pin the
CONTRACT shape (closed enums, frozen dataclasses, refusals, no-float, adapter
declaration) before any implementation lands. Retirement/walkover/qualification
status fields on :class:`~sport_tennis.domain.Match` are structural facts about a
match, not settlement policy: the settlement RULES that consume them are SPEC-084
(``l7_settle``, ``planned``, ADR 0017 S7) and are out of scope here — nothing in this
module asserts a settlement amount, a void rule, or a payout.
"""
from __future__ import annotations

import dataclasses
import inspect
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from sport_tennis.adapter import TENNIS_ADAPTER, TENNIS_CAPABILITIES
from sport_tennis.domain import (
    SCHEMA_VERSION,
    BestOf,
    Match,
    MarketSelection,
    MarketSnapshot,
    Player,
    QualificationStatus,
    RetirementStatus,
    Round,
    SettlementOutcome,
    ExecutionOutcome,
    Surface,
    Tournament,
    TournamentLevel,
    WalkoverStatus,
)
from l7_settle.outcomes import MarketOutcome, MarketStatus, MatchedPosition

pytestmark = pytest.mark.spec("SPEC-084")


# --- fixtures / builders -----------------------------------------------------------------------


def _player(pid: str = "p1", name: str | None = "Player One") -> Player:
    return Player(player_id=pid, name=name)


def _tournament(
    surface: Surface = Surface.HARD,
    best_of_default: BestOf = BestOf.THREE,
    level: TournamentLevel = TournamentLevel.ATP_250,
) -> Tournament:
    return Tournament(
        tournament_id="t1",
        name="Example Open",
        surface=surface,
        best_of_default=best_of_default,
        level=level,
    )


_UTC_START = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def _match(
    player_a: Player | None = None,
    player_b: Player | None = None,
    tournament: Tournament | None = None,
    round_: Round = Round.QF,
    best_of: BestOf = BestOf.THREE,
    scheduled_start_utc: datetime = _UTC_START,
    qualification_status_a: QualificationStatus = QualificationStatus.MAIN_DRAW,
    qualification_status_b: QualificationStatus = QualificationStatus.MAIN_DRAW,
    retirement_status: RetirementStatus = RetirementStatus.NONE,
    walkover_status: WalkoverStatus = WalkoverStatus.NONE,
    completed: bool = False,
) -> Match:
    return Match(
        match_id="m1",
        tournament=tournament if tournament is not None else _tournament(),
        round=round_,
        best_of=best_of,
        player_a=player_a if player_a is not None else _player("p1", "Player One"),
        player_b=player_b if player_b is not None else _player("p2", "Player Two"),
        scheduled_start_utc=scheduled_start_utc,
        scheduled_start_captured_monotonic_ns=123_456_789,
        qualification_status_a=qualification_status_a,
        qualification_status_b=qualification_status_b,
        retirement_status=retirement_status,
        walkover_status=walkover_status,
        completed=completed,
    )


# --- SCHEMA_VERSION ----------------------------------------------------------------------------


def test_schema_version_present_and_versioned() -> None:
    assert SCHEMA_VERSION == "tennis-domain-v1"


def test_adapter_module_reuses_the_same_schema_version() -> None:
    import sport_tennis.adapter as adapter_mod

    assert adapter_mod.SCHEMA_VERSION == SCHEMA_VERSION


# --- enum closure ------------------------------------------------------------------------------


class TestEnumClosure:
    def test_surface_exact_members(self) -> None:
        assert {m.name for m in Surface} == {"HARD", "CLAY", "GRASS", "CARPET_INDOOR"}

    def test_round_exact_members(self) -> None:
        assert {m.name for m in Round} == {
            "Q1", "Q2", "Q3", "R128", "R64", "R32", "R16", "QF", "SF", "F", "RR",
        }

    def test_best_of_exact_members_and_values(self) -> None:
        assert {m.name for m in BestOf} == {"THREE", "FIVE"}
        assert BestOf.THREE.value == 3
        assert BestOf.FIVE.value == 5

    def test_retirement_status_exact_members(self) -> None:
        assert {m.name for m in RetirementStatus} == {
            "NONE", "RETIRED_BEFORE_SET1_COMPLETE", "RETIRED_AFTER_SET1_COMPLETE",
        }

    def test_walkover_status_exact_members(self) -> None:
        assert {m.name for m in WalkoverStatus} == {"NONE", "WALKOVER"}

    def test_qualification_status_exact_members(self) -> None:
        assert {m.name for m in QualificationStatus} == {
            "MAIN_DRAW", "QUALIFIER", "LUCKY_LOSER", "WILD_CARD",
        }

    def test_tournament_level_exact_members(self) -> None:
        assert {m.name for m in TournamentLevel} == {
            "ATP_250", "ATP_500", "ATP_1000", "GRAND_SLAM",
            "WTA_250", "WTA_500", "WTA_1000", "CHALLENGER", "OTHER",
        }


# --- frozen-ness ---------------------------------------------------------------------------------


class TestFrozen:
    def test_player_is_frozen(self) -> None:
        player = _player()
        with pytest.raises(dataclasses.FrozenInstanceError):
            player.name = "changed"  # type: ignore[misc]

    def test_tournament_is_frozen(self) -> None:
        tournament = _tournament()
        with pytest.raises(dataclasses.FrozenInstanceError):
            tournament.name = "changed"  # type: ignore[misc]

    def test_match_is_frozen(self) -> None:
        match = _match()
        with pytest.raises(dataclasses.FrozenInstanceError):
            match.completed = True  # type: ignore[misc]

    def test_market_selection_is_frozen(self) -> None:
        selection = MarketSelection(selection_id=1, player=_player())
        with pytest.raises(dataclasses.FrozenInstanceError):
            selection.selection_id = 2  # type: ignore[misc]

    def test_market_snapshot_is_frozen(self) -> None:
        match = _match()
        snapshot = MarketSnapshot(
            match=match,
            market_id="1.23",
            selection_a=MarketSelection(selection_id=1, player=match.player_a),
            selection_b=MarketSelection(selection_id=2, player=match.player_b),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            snapshot.market_id = "1.24"  # type: ignore[misc]

    def test_settlement_outcome_is_frozen(self) -> None:
        match = _match()
        outcome = SettlementOutcome(
            match=match, outcome=MarketOutcome(market_status=MarketStatus.SETTLED)
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            outcome.match = match  # type: ignore[misc]

    def test_execution_outcome_is_frozen(self) -> None:
        match = _match()
        execution = ExecutionOutcome(
            match=match,
            position=MatchedPosition(runner_id=1, matched_stake_minor=500, matched_odds=Decimal("2")),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            execution.match = match  # type: ignore[misc]


# --- refusals ------------------------------------------------------------------------------------


class TestPlayerRefusals:
    def test_refuses_empty_player_id(self) -> None:
        with pytest.raises(ValueError):
            Player(player_id="")

    def test_refuses_whitespace_only_player_id(self) -> None:
        with pytest.raises(ValueError):
            Player(player_id="   ")

    def test_name_is_optional(self) -> None:
        player = Player(player_id="p1")
        assert player.name is None


class TestTournamentRefusals:
    def test_refuses_empty_tournament_id(self) -> None:
        with pytest.raises(ValueError):
            Tournament(
                tournament_id="",
                name="Example Open",
                surface=Surface.HARD,
                best_of_default=BestOf.THREE,
                level=TournamentLevel.ATP_250,
            )

    def test_refuses_empty_name(self) -> None:
        with pytest.raises(ValueError):
            Tournament(
                tournament_id="t1",
                name="",
                surface=Surface.HARD,
                best_of_default=BestOf.THREE,
                level=TournamentLevel.ATP_250,
            )


class TestMatchRefusals:
    def test_refuses_same_player_twice(self) -> None:
        same = _player("p1", "Player One")
        with pytest.raises(ValueError):
            _match(player_a=same, player_b=same)

    def test_refuses_same_player_id_with_different_name_objects(self) -> None:
        # Identity is by player_id, not object identity: two distinct Player objects
        # sharing a player_id are still "the same player twice".
        with pytest.raises(ValueError):
            _match(player_a=_player("p1", "Alpha"), player_b=_player("p1", "Beta"))

    def test_refuses_empty_match_id(self) -> None:
        with pytest.raises(ValueError):
            Match(
                match_id="",
                tournament=_tournament(),
                round=Round.QF,
                best_of=BestOf.THREE,
                player_a=_player("p1"),
                player_b=_player("p2"),
                scheduled_start_utc=_UTC_START,
                scheduled_start_captured_monotonic_ns=1,
                qualification_status_a=QualificationStatus.MAIN_DRAW,
                qualification_status_b=QualificationStatus.MAIN_DRAW,
            )

    def test_refuses_naive_scheduled_start(self) -> None:
        with pytest.raises(ValueError):
            _match(scheduled_start_utc=datetime(2026, 7, 20, 12, 0))

    def test_refuses_non_utc_scheduled_start(self) -> None:
        non_utc = timezone(timedelta(hours=1))
        with pytest.raises(ValueError):
            _match(scheduled_start_utc=datetime(2026, 7, 20, 12, 0, tzinfo=non_utc))

    def test_refuses_walkover_and_retirement_together(self) -> None:
        with pytest.raises(ValueError):
            _match(
                walkover_status=WalkoverStatus.WALKOVER,
                retirement_status=RetirementStatus.RETIRED_AFTER_SET1_COMPLETE,
            )

    def test_accepts_walkover_alone(self) -> None:
        match = _match(walkover_status=WalkoverStatus.WALKOVER)
        assert match.walkover_status is WalkoverStatus.WALKOVER
        assert match.retirement_status is RetirementStatus.NONE

    def test_accepts_retirement_alone(self) -> None:
        match = _match(retirement_status=RetirementStatus.RETIRED_BEFORE_SET1_COMPLETE)
        assert match.retirement_status is RetirementStatus.RETIRED_BEFORE_SET1_COMPLETE
        assert match.walkover_status is WalkoverStatus.NONE

    def test_default_statuses_are_none_and_not_completed(self) -> None:
        match = _match()
        assert match.retirement_status is RetirementStatus.NONE
        assert match.walkover_status is WalkoverStatus.NONE
        assert match.completed is False

    def test_refuses_completed_with_retirement(self) -> None:
        # completed means completed in the ordinary sense — the same sense as
        # SPEC-084's COMPLETED outcome, mutually exclusive with retirement/walkover.
        with pytest.raises(ValueError):
            _match(
                completed=True,
                retirement_status=RetirementStatus.RETIRED_AFTER_SET1_COMPLETE,
            )

    def test_refuses_completed_with_walkover(self) -> None:
        with pytest.raises(ValueError):
            _match(completed=True, walkover_status=WalkoverStatus.WALKOVER)

    def test_accepts_completed_with_clean_statuses(self) -> None:
        match = _match(completed=True)
        assert match.completed is True


class TestMarketSelectionRefusals:
    def test_refuses_non_positive_selection_id(self) -> None:
        with pytest.raises(ValueError):
            MarketSelection(selection_id=0, player=_player())

    def test_refuses_negative_selection_id(self) -> None:
        with pytest.raises(ValueError):
            MarketSelection(selection_id=-1, player=_player())


class TestMarketSnapshotRefusals:
    def test_refuses_empty_market_id(self) -> None:
        match = _match()
        with pytest.raises(ValueError):
            MarketSnapshot(
                match=match,
                market_id="",
                selection_a=MarketSelection(selection_id=1, player=match.player_a),
                selection_b=MarketSelection(selection_id=2, player=match.player_b),
            )

    def test_refuses_duplicate_selection_ids(self) -> None:
        match = _match()
        with pytest.raises(ValueError):
            MarketSnapshot(
                match=match,
                market_id="1.23",
                selection_a=MarketSelection(selection_id=1, player=match.player_a),
                selection_b=MarketSelection(selection_id=1, player=match.player_b),
            )

    def test_refuses_selection_player_not_in_match(self) -> None:
        match = _match()
        stranger = _player("p3", "Someone Else")
        with pytest.raises(ValueError):
            MarketSnapshot(
                match=match,
                market_id="1.23",
                selection_a=MarketSelection(selection_id=1, player=match.player_a),
                selection_b=MarketSelection(selection_id=2, player=stranger),
            )

    def test_refuses_both_selections_mapped_to_the_same_match_player(self) -> None:
        match = _match()
        with pytest.raises(ValueError):
            MarketSnapshot(
                match=match,
                market_id="1.23",
                selection_a=MarketSelection(selection_id=1, player=match.player_a),
                selection_b=MarketSelection(selection_id=2, player=match.player_a),
            )

    def test_accepts_a_valid_snapshot(self) -> None:
        match = _match()
        snapshot = MarketSnapshot(
            match=match,
            market_id="1.23",
            selection_a=MarketSelection(selection_id=1, player=match.player_a),
            selection_b=MarketSelection(selection_id=2, player=match.player_b),
        )
        assert snapshot.selection_a.player.player_id == "p1"


# --- thin references reuse l7_settle, never duplicate it ---------------------------------------


class TestThinReferencesReuseL7Settle:
    def test_settlement_outcome_wraps_l7_settle_market_outcome(self) -> None:
        match = _match()
        outcome = SettlementOutcome(
            match=match, outcome=MarketOutcome(market_status=MarketStatus.VOID)
        )
        assert isinstance(outcome.outcome, MarketOutcome)

    def test_execution_outcome_wraps_l7_settle_matched_position(self) -> None:
        match = _match()
        execution = ExecutionOutcome(
            match=match,
            position=MatchedPosition(runner_id=2, matched_stake_minor=1_000, matched_odds=Decimal("3")),
        )
        assert isinstance(execution.position, MatchedPosition)

    def test_domain_module_does_not_redeclare_stake_or_odds_fields(self) -> None:
        # SettlementOutcome/ExecutionOutcome must be thin references: no field on either
        # dataclass may re-declare a stake/odds/commission concept that already exists in
        # l7_settle.outcomes.
        for cls in (SettlementOutcome, ExecutionOutcome):
            field_names = {f.name for f in dataclasses.fields(cls)}
            assert not (field_names & {"matched_stake_minor", "matched_odds", "commission"})


# --- no float anywhere -----------------------------------------------------------------------


class TestNoFloat:
    def test_no_dataclass_field_is_a_float(self) -> None:
        import sport_tennis.domain as domain_mod

        dataclass_types = [
            obj
            for obj in vars(domain_mod).values()
            if isinstance(obj, type) and dataclasses.is_dataclass(obj)
        ]
        assert dataclass_types, "expected at least one dataclass in sport_tennis.domain"
        for cls in dataclass_types:
            for f in dataclasses.fields(cls):
                type_str = f.type if isinstance(f.type, str) else str(f.type)
                assert "float" not in type_str.lower(), (cls.__name__, f.name, type_str)

    def test_module_source_has_no_float_literal_type(self) -> None:
        import sport_tennis.domain as domain_mod

        source = inspect.getsource(domain_mod)
        assert "float(" not in source
        assert ": float" not in source
        assert "-> float" not in source


# --- adapter declaration ---------------------------------------------------------------------


class TestAdapterDeclaration:
    def test_sport_id_is_tennis(self) -> None:
        assert TENNIS_ADAPTER.sport_id == "tennis"

    def test_decision_unit_is_match_and_accepted_by_sport_core(self) -> None:
        # sport_core.adapter.SportAdapter validates decision_unit against the governed
        # closed set (correction 0003, {"race", "match"}); constructing TENNIS_ADAPTER
        # without raising IS the assertion that "match" is accepted.
        assert TENNIS_ADAPTER.decision_unit == "match"

    def test_cluster_key_is_calendar_day_utc(self) -> None:
        assert TENNIS_ADAPTER.cluster_key_name == "calendar_day_utc"

    def test_event_start_name_is_scheduled_start(self) -> None:
        assert TENNIS_ADAPTER.event_start_name == "scheduled_start"

    def test_closing_diagnostic_taints_is_empty_no_benchmark_chosen_yet(self) -> None:
        assert TENNIS_ADAPTER.closing_diagnostic_taints == frozenset()

    def test_capabilities_are_coherent_binary_no_bsp_no_dead_heat_no_rf(self) -> None:
        caps = TENNIS_CAPABILITIES
        assert caps.supports_binary is True
        assert caps.supports_multi_runner is False
        assert caps.supports_bsp is False
        assert caps.supports_dead_heat is False
        assert caps.supports_reduction_factor is False
        assert caps.supports_retirements is True
        assert caps.supports_void_rules is True
        assert caps.supports_in_play is True

    def test_adapter_is_frozen(self) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            TENNIS_ADAPTER.sport_id = "x"  # type: ignore[misc]

    def test_registers_cleanly_in_a_fresh_registry_alongside_racing(self) -> None:
        from sport_core.adapter import SportAdapter, SportAdapterRegistry
        from sport_core.capabilities import SportCapabilities

        racing_caps = SportCapabilities(
            supports_multi_runner=True,
            supports_binary=False,
            supports_bsp=True,
            supports_dead_heat=True,
            supports_reduction_factor=True,
            supports_retirements=False,
            supports_draw=False,
            supports_partial_settlement=True,
            supports_void_rules=True,
            supports_in_play=True,
            supports_pre_match_only=False,
        )
        racing_adapter = SportAdapter(
            sport_id="horse_racing",
            decision_unit="race",
            capabilities=racing_caps,
            cluster_key_name="meeting_day",
            event_start_name="off",
            closing_diagnostic_taints=frozenset({"l8_evidence.reconciled_bsp:RECONCILED_BSP"}),
            events_can_start_early=False,
        )
        registry = SportAdapterRegistry()
        registry.register(racing_adapter)
        registry.register(TENNIS_ADAPTER)
        assert registry.sport_ids() == ("horse_racing", "tennis")
