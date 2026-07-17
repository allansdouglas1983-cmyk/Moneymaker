"""SPEC-095 / ADR 0017 S8: closing-benchmark METHOD abstraction for future non-racing
sports (tennis first).

This is the interface half of Phase 10 ("benchmark interfaces... NO benchmark chosen").
It defines:

* a thin, honestly-scoped snapshot type describing what a pre-close book/trade window
  can even contain, built ONLY from fields the founder's data-sourcing research
  (DR-TENNIS-BENCHMARK-001, ``docs/research/``) found the advanced/historical Betfair
  files provably carry: best back/lay price+size series, traded-volume deltas, last
  traded price, timestamps, and suspension markers. Nothing here invents a data field
  the files do not have;
* a runtime-checkable ``Protocol`` any future closing-benchmark method must satisfy;
* four NAMED future method-id constants (no implementations — a class per method would
  imply a chosen, working computation, which does not exist yet);
* a ``selected_benchmark()`` accessor that REFUSES: DR-TENNIS-BENCHMARK-001 is
  unresolved, benchmark selection is evidence-driven and stays blocked on pilot data
  plus founder approval (ADR 0017 program, Phase 10; ``docs/architecture/
  sport-agnostic-audit.md`` risk C1).

Deliberately absent, on the same discipline as SPEC-094/SPEC-060: NO window-length
values, NO staleness thresholds, NO minimum-liquidity cutoffs, and no other numeric
pre-registration constant. Those are exactly the kind of value SPEC-094 requires be
declared *before observation* as part of a pre-registered experiment, not baked into an
interfaces-only module before any pilot exists. When a benchmark method is eventually
selected, its numeric parameters belong in that experiment's pre-registration record
(and, for the frozen closing-benchmark spec shape, a governed ``close-v2`` — see
``specs/prices/close-v1.yaml``, which stays racing/BSP-scoped and untouched by this
module).

Relationship to the existing racing benchmark
------------------------------------------------
Racing's settlement-time closing benchmark is ``l8_evidence.clv.ClosingBenchmark`` (two
members: ``BSP`` and ``PRE_SUSPENSION_WAP``). This module does not import, extend, or
alter it — ``ClosingBenchmark.BSP`` has no tennis equivalent (tennis has no Starting
Price mechanism) and stays racing-adapter-only, exactly as
``docs/architecture/sport-agnostic-audit.md`` risk C1 requires. A future non-racing
closing-benchmark selection is a NEW, separately evidence-gated type; it does not retrofit
onto ``ClosingBenchmark``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Sequence, runtime_checkable

__all__ = [
    "BenchmarkNotSelectedError",
    "PricePoint",
    "TradedDeltaPoint",
    "LastTradedPricePoint",
    "SuspensionMarker",
    "PreCloseWindowSummary",
    "ClosingBenchmarkMethod",
    "METHOD_ID_FINAL_MIDPOINT",
    "METHOD_ID_WINDOWED_MIDPOINT",
    "METHOD_ID_WAP",
    "METHOD_ID_MICROPRICE",
    "FUTURE_METHOD_IDS",
    "selected_benchmark",
]


def _require_utc_aware(name: str, value: datetime) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware UTC, got a naive datetime")


def _require_int(name: str, value: int) -> None:
    # The annotation alone does not stop a float at runtime; the platform's type rules
    # (CLAUDE.md "Types") forbid float prices and float sizes everywhere, including in
    # interface-layer series types that no benchmark reads yet.
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(
            f"{name} must be an int (tick index / integer minor units), "
            f"got {type(value).__name__}"
        )


class BenchmarkNotSelectedError(LookupError):
    """Raised by :func:`selected_benchmark`. Benchmark selection for non-racing sports
    is evidence-driven and stays blocked on pilot data plus founder approval
    (DR-TENNIS-BENCHMARK-001 is unresolved) — there is no default, no "best guess", and
    no fallback method. Refusal is the only correct behaviour until a human resolves it.
    """


@dataclass(frozen=True)
class PricePoint:
    """One observation of a best back or best lay price+size at a point in time.

    ``price_tick`` is an INTEGER index into the canonical Betfair ladder and
    ``size_minor`` an INTEGER count of currency minor units, per CLAUDE.md's "Types"
    section — floats are refused at construction, not merely discouraged by the
    annotation. This type does not redefine the ladder; it only names a series element
    (``sport_core`` may not import ``l5_decision``'s ladder machinery — the analytics
    import boundary forbids it — so the tick index travels as a plain ``int`` here).
    """

    timestamp_utc: datetime
    price_tick: int
    size_minor: int

    def __post_init__(self) -> None:
        _require_utc_aware("timestamp_utc", self.timestamp_utc)
        _require_int("price_tick", self.price_tick)
        _require_int("size_minor", self.size_minor)


@dataclass(frozen=True)
class TradedDeltaPoint:
    """One traded-volume delta observation ahead of the close (matched size at a tick
    between two observations, not a cumulative total)."""

    timestamp_utc: datetime
    price_tick: int
    size_delta_minor: int

    def __post_init__(self) -> None:
        _require_utc_aware("timestamp_utc", self.timestamp_utc)
        _require_int("price_tick", self.price_tick)
        _require_int("size_delta_minor", self.size_delta_minor)


@dataclass(frozen=True)
class LastTradedPricePoint:
    """One last-traded-price observation."""

    timestamp_utc: datetime
    price_tick: int

    def __post_init__(self) -> None:
        _require_utc_aware("timestamp_utc", self.timestamp_utc)
        _require_int("price_tick", self.price_tick)


@dataclass(frozen=True)
class SuspensionMarker:
    """One suspension-state transition. ``suspended`` is True at a suspension-start
    marker and False at the corresponding resumption; this type carries no judgement
    about why the market suspended."""

    timestamp_utc: datetime
    suspended: bool

    def __post_init__(self) -> None:
        _require_utc_aware("timestamp_utc", self.timestamp_utc)


@dataclass(frozen=True)
class PreCloseWindowSummary:
    """A frozen, thin summary of what a pre-close book/trade window can contain.

    Every series field is OPTIONAL (``None`` by default) and is a reference to a series
    that may or may not be available for a given market/selection/provenance — this
    type does not assert any series is always present, and it does not compute anything
    (no window length, no aggregation) itself. ``market_ref``/``selection_ref`` are
    opaque identifiers; this module does not define what a market or selection is (that
    is ``sport_core.markets`` and the sport adapters' job).

    Fields are limited to what the founder's DR-TENNIS-BENCHMARK-001 sourcing research
    found the advanced/historical Betfair files provably carry: best back/lay price+size
    series, traded deltas, last traded price, timestamps, and suspension markers. No
    other field is invented.
    """

    market_ref: object
    selection_ref: object
    best_back: Sequence[PricePoint] | None = None
    best_lay: Sequence[PricePoint] | None = None
    traded_deltas: Sequence[TradedDeltaPoint] | None = None
    last_traded_price: Sequence[LastTradedPricePoint] | None = None
    suspension_markers: Sequence[SuspensionMarker] | None = None


@runtime_checkable
class ClosingBenchmarkMethod(Protocol):
    """Deterministic contract any future closing-benchmark computation must satisfy.

    ``method_id``/``method_version`` identify the method (see the ``METHOD_ID_*``
    constants below for the names reserved for future implementations).
    ``compute`` takes a :class:`PreCloseWindowSummary` and returns the computed closing
    reference. No implementation of this protocol exists in this module — it is
    checked structurally (``isinstance`` against ``runtime_checkable``), never
    instantiated here.
    """

    method_id: str
    method_version: str

    def compute(self, window: PreCloseWindowSummary) -> object: ...


# Reserved method-id constants for future, NOT-YET-IMPLEMENTED closing-benchmark
# methods (ADR 0017 Phase 10). Each is a plain string identifier, not a class or
# function — implementing one is a future, separately evidence-gated slice, and doing
# so does not, by itself, select it as `the` benchmark (see selected_benchmark()).
METHOD_ID_FINAL_MIDPOINT = "final-midpoint"
METHOD_ID_WINDOWED_MIDPOINT = "windowed-midpoint"
METHOD_ID_WAP = "wap"
METHOD_ID_MICROPRICE = "microprice"

FUTURE_METHOD_IDS: frozenset[str] = frozenset(
    {
        METHOD_ID_FINAL_MIDPOINT,
        METHOD_ID_WINDOWED_MIDPOINT,
        METHOD_ID_WAP,
        METHOD_ID_MICROPRICE,
    }
)


def selected_benchmark() -> ClosingBenchmarkMethod:
    """Always refuses. Benchmark selection stays evidence-driven, post-pilot, and
    requires founder approval — DR-TENNIS-BENCHMARK-001 is unresolved (ADR 0017 program
    Phase 10; ``docs/architecture/sport-agnostic-audit.md`` risk C1). There is
    deliberately no default, no heuristic pick among ``FUTURE_METHOD_IDS``, and no
    environment/config override: selecting a benchmark is a human, evidence-gated
    decision, not a runtime code path.
    """
    raise BenchmarkNotSelectedError(
        "no closing-benchmark method is selected: selection is evidence-driven and "
        "blocked on pilot data plus founder approval (DR-TENNIS-BENCHMARK-001 is "
        "unresolved; ADR 0017 Phase 10). Racing's benchmark, l8_evidence.clv."
        "ClosingBenchmark.BSP, is unaffected and is not a fallback for this accessor."
    )
