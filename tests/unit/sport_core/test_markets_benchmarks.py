"""SPEC-095 / ADR 0017 S8: market-kind and closing-benchmark abstractions.

Phase 9 (market abstractions) and Phase 10 (benchmark interfaces) of the ADR 0017
sport-agnostic program: enums/interfaces ONLY, no benchmark selected
(DR-TENNIS-BENCHMARK-001 is unresolved; selection stays evidence-driven post-pilot,
founder-approved). This test module pins:

* ``sport_core.markets``: the closed ``MarketKind`` enum and the frozen
  ``MarketKindPolicy`` that enables exactly {WIN, MATCH_ODDS} for research today,
  refusing every other kind via ``MarketKindDisabledError``;
* ``sport_core.benchmarks``: the runtime-checkable ``ClosingBenchmarkMethod`` protocol,
  the thin optional-series ``PreCloseWindowSummary`` snapshot type, the four reserved
  future method-id constants, and ``selected_benchmark()``'s permanent refusal via
  ``BenchmarkNotSelectedError``.

Both modules are interfaces/enums only — no probability, pricing, or benchmark
computation is implemented anywhere in this slice.
"""
from __future__ import annotations

import dataclasses
import inspect
import tokenize
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pytest

from sport_core.benchmarks import (
    METHOD_ID_FINAL_MIDPOINT,
    METHOD_ID_MICROPRICE,
    METHOD_ID_WAP,
    METHOD_ID_WINDOWED_MIDPOINT,
    BenchmarkNotSelectedError,
    ClosingBenchmarkMethod,
    FUTURE_METHOD_IDS,
    PreCloseWindowSummary,
    PricePoint,
    selected_benchmark,
)
from sport_core.markets import (
    ENABLED_MARKET_KINDS,
    MarketKind,
    MarketKindDisabledError,
    MarketKindPolicy,
    V1_MARKET_KIND_POLICY,
)

pytestmark = pytest.mark.spec("SPEC-095")

_REPO_ROOT = Path(__file__).resolve().parents[3]


# --- MarketKind enum closure -------------------------------------------------------------


def test_market_kind_enum_is_exactly_the_declared_closed_set() -> None:
    assert {member.name for member in MarketKind} == {
        "MATCH_ODDS",
        "WIN",
        "SET_WINNER",
        "CORRECT_SCORE",
        "GAME_MARKETS",
        "OTHER",
    }


def test_market_kind_values_are_stable_strings() -> None:
    # Enum values are the wire-stable identifiers other layers may persist.
    for member in MarketKind:
        assert member.value == member.name


# --- MarketKindPolicy: exactly {WIN, MATCH_ODDS} enabled ---------------------------------


def test_v1_policy_enables_exactly_win_and_match_odds() -> None:
    assert ENABLED_MARKET_KINDS == frozenset({MarketKind.WIN, MarketKind.MATCH_ODDS})
    assert V1_MARKET_KIND_POLICY.enabled_kinds == ENABLED_MARKET_KINDS


@pytest.mark.parametrize("kind", [MarketKind.WIN, MarketKind.MATCH_ODDS])
def test_enabled_kinds_are_accepted_by_require_enabled(kind: MarketKind) -> None:
    V1_MARKET_KIND_POLICY.require_enabled(kind)  # must not raise
    assert V1_MARKET_KIND_POLICY.is_enabled(kind)


@pytest.mark.parametrize(
    "kind",
    [
        MarketKind.SET_WINNER,
        MarketKind.CORRECT_SCORE,
        MarketKind.GAME_MARKETS,
        MarketKind.OTHER,
    ],
)
def test_every_other_kind_is_disabled_and_refused(kind: MarketKind) -> None:
    assert not V1_MARKET_KIND_POLICY.is_enabled(kind)
    with pytest.raises(MarketKindDisabledError):
        V1_MARKET_KIND_POLICY.require_enabled(kind)


def test_market_kind_policy_is_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        V1_MARKET_KIND_POLICY.enabled_kinds = frozenset(MarketKind)  # type: ignore[misc]


def test_market_kind_policy_has_no_runtime_enable_api() -> None:
    # Enabling a kind is a governed constant edit + test change, never a method call.
    public = {
        name
        for name, _ in inspect.getmembers(MarketKindPolicy, predicate=inspect.isfunction)
        if not name.startswith("_")
    }
    assert public == {"is_enabled", "require_enabled"}


def test_game_markets_disabled_note_cites_the_dr_finding() -> None:
    # The docstring must explain GAME_MARKETS stays refused independent of policy
    # choice — Betfair's historical tennis data excludes Game markets entirely.
    text = (_REPO_ROOT / "sport_core" / "markets.py").read_text()
    assert "Game markets" in text
    assert "DR-TENNIS-BENCHMARK-001" in text


def test_founder_design_football_and_binary_markets_expressible_without_new_members() -> None:
    # Football's 3-way match result and a binary financial market must be describable
    # using the existing closed set (MATCH_ODDS / OTHER) — no new MarketKind member.
    football_kind = MarketKind.MATCH_ODDS
    binary_financial_kind = MarketKind.OTHER
    assert football_kind in MarketKind
    assert binary_financial_kind in MarketKind
    assert len(MarketKind) == 6  # closed set unchanged by these design tests


# --- ClosingBenchmarkMethod protocol ------------------------------------------------------


def test_closing_benchmark_method_protocol_is_runtime_checkable() -> None:
    assert getattr(ClosingBenchmarkMethod, "_is_runtime_protocol", False) is True


class _ConformingMethod:
    method_id = "final-midpoint"
    method_version = "v1"

    def compute(self, _window: PreCloseWindowSummary) -> object:
        return None


class _NonConformingMissingCompute:
    method_id = "final-midpoint"
    method_version = "v1"


class _NonConformingMissingId:
    method_version = "v1"

    def compute(self, _window: PreCloseWindowSummary) -> object:
        return None


def test_conforming_dummy_satisfies_the_protocol() -> None:
    assert isinstance(_ConformingMethod(), ClosingBenchmarkMethod)


def test_non_conforming_dummies_fail_the_protocol() -> None:
    assert not isinstance(_NonConformingMissingCompute(), ClosingBenchmarkMethod)
    assert not isinstance(_NonConformingMissingId(), ClosingBenchmarkMethod)


# --- PreCloseWindowSummary: thin, optional, frozen ----------------------------------------


def test_window_summary_is_frozen_and_series_fields_default_to_none() -> None:
    summary = PreCloseWindowSummary(market_ref="m1", selection_ref="s1")
    assert summary.best_back is None
    assert summary.best_lay is None
    assert summary.traded_deltas is None
    assert summary.last_traded_price is None
    assert summary.suspension_markers is None
    with pytest.raises(dataclasses.FrozenInstanceError):
        summary.best_back = ()  # type: ignore[misc]


def test_window_summary_fields_are_limited_to_dr_supported_series() -> None:
    field_names = {f.name for f in dataclasses.fields(PreCloseWindowSummary)}
    assert field_names == {
        "market_ref",
        "selection_ref",
        "best_back",
        "best_lay",
        "traded_deltas",
        "last_traded_price",
        "suspension_markers",
    }


# --- Series points honour the platform type rules (no float price/size, UTC-aware) ---------


def test_price_point_refuses_float_price_and_size() -> None:
    # CLAUDE.md "Types": tick index is an integer, stake/size is integer minor units,
    # never float — enforced at construction, not only by annotation.
    ts = datetime(2026, 7, 17, 12, 0, 0, tzinfo=timezone.utc)
    PricePoint(timestamp_utc=ts, price_tick=50, size_minor=200)  # ints accepted
    with pytest.raises(TypeError):
        PricePoint(timestamp_utc=ts, price_tick=2.5, size_minor=200)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        PricePoint(timestamp_utc=ts, price_tick=50, size_minor=2.0)  # type: ignore[arg-type]


def test_price_point_refuses_naive_timestamp() -> None:
    with pytest.raises(ValueError):
        PricePoint(timestamp_utc=datetime(2026, 7, 17, 12, 0, 0), price_tick=50, size_minor=200)


# --- Reserved future method-id constants ---------------------------------------------------


def test_four_future_method_id_constants_exist_and_are_distinct() -> None:
    ids = {
        METHOD_ID_FINAL_MIDPOINT,
        METHOD_ID_WINDOWED_MIDPOINT,
        METHOD_ID_WAP,
        METHOD_ID_MICROPRICE,
    }
    assert len(ids) == 4
    assert ids == FUTURE_METHOD_IDS
    for method_id in ids:
        assert isinstance(method_id, str) and method_id


# --- selected_benchmark(): permanent refusal ------------------------------------------------


def test_selected_benchmark_always_refuses() -> None:
    with pytest.raises(BenchmarkNotSelectedError):
        selected_benchmark()


def test_selected_benchmark_refusal_cites_the_open_research_question() -> None:
    with pytest.raises(BenchmarkNotSelectedError, match="DR-TENNIS-BENCHMARK-001"):
        selected_benchmark()


def test_racing_closing_benchmark_is_untouched_by_this_module() -> None:
    # ADR 0017 audit risk C1: l8_evidence.clv.ClosingBenchmark.BSP stays
    # racing-adapter-only. This module must not import or re-export it — a mention in
    # a docstring citation is fine, an import is not.
    import sport_core.benchmarks as benchmarks_mod

    assert not hasattr(benchmarks_mod, "ClosingBenchmark")
    import_lines = [
        line.strip()
        for line in inspect.getsource(benchmarks_mod).splitlines()
        if line.strip().startswith(("import ", "from "))
    ]
    assert not any("l8_evidence" in line for line in import_lines)


# --- No numeric pre-registration constants in benchmarks.py ---------------------------------


def test_benchmarks_module_declares_no_numeric_literals() -> None:
    # SPEC-094 discipline: window lengths, staleness thresholds and similar numeric
    # pre-registration values must not appear in an interfaces-only module. Scan actual
    # NUMBER tokens (not digits embedded in string literals like "DR-TENNIS-...-001").
    import sport_core.benchmarks as benchmarks_mod

    source = inspect.getsource(benchmarks_mod)
    number_tokens = [
        tok
        for tok in tokenize.generate_tokens(StringIO(source).readline)
        if tok.type == tokenize.NUMBER
    ]
    assert number_tokens == [], f"unexpected numeric literals: {number_tokens}"
