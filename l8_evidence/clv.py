"""SPEC-095: CLV diagnostic family — signal, intended-order, realised-fill CLV and
execution-policy value.

CLV ("closing line value") is a DIAGNOSTIC FAMILY, never a training target
(``.claude/rules/evidence.md``: "CLV is a diagnostic family, not a training target";
SPECIFICATION.md §8: "Do not train the platform to maximise CLV. That risks building a
system that predicts future market opinion rather than outcomes or net utility."). This
module computes four distinct, separately-typed quantities and nothing else:

* :class:`SignalCLV` — the candidate's decision-threshold price at signal time vs the
  close, regardless of whether an order was ever submitted. Measures the model's
  information content in isolation from execution.
* :class:`IntendedOrderCLV` — the price the decision layer INTENDED to cross at (the
  requested limit price) vs the close. Measures decision timing.
* :class:`RealisedFillCLV` — the ACTUAL matched price vs the close. Measures capture. This
  type cannot be constructed for an order that never filled: the constructor REQUIRES
  ``matched_stake_minor > 0`` as evidence of a fill, and there is no optional
  "hypothetical price" parameter anywhere in this module — see :class:`UnfilledOrder` for
  the honest artifact an unfilled order gets instead
  ("for unfilled orders, realised CLV does not exist... this is the difference between
  measurement and fiction", SPECIFICATION.md §8).
* :class:`ExecutionPolicyValue` — realised-fill CLV minus intended-order CLV on the SAME
  order. Measures what execution added or cost relative to what was intended.

These are four DISTINCT types, not one type with a discriminating tag — a function that
needs a :class:`RealisedFillCLV` will not type-check against a :class:`SignalCLV`, the same
conflation guard SPEC-051 uses for ``p_market_info`` / ``odds_exec`` / ``p_close``.

Closing benchmarks
------------------
Exactly TWO closing benchmarks are retained (SPECIFICATION.md §8: "Retain two closing
diagnostics: BSP, and a defined final pre-suspension WAP/microprice window"):
:class:`ClosingBenchmark` has exactly two members, ``BSP`` and ``PRE_SUSPENSION_WAP``. They
are never averaged or merged into a third "blended" figure — every CLV value names which
one it was computed against (:class:`ClosingPrice.benchmark`), and
:class:`ExecutionPolicyValue` REFUSES to combine two components computed against different
benchmarks (or against the same benchmark kind but a different underlying observation).

"A defined pre-suspension WAP/microprice window" is made STRUCTURAL, not prose:
:class:`ClosingPrice` requires ``window_start_seconds_before_suspension`` (the more distant
edge, > 0) and ``window_end_seconds_before_suspension`` (the edge closer to suspension,
>= 0, and strictly less than the start) whenever ``benchmark`` is
``PRE_SUSPENSION_WAP``; ``BSP`` carries no window at all (both fields MUST be ``None``).

Sign convention — read this before touching any bps figure
------------------------------------------------------------
For a BACK bet, implied-probability basis points captured versus the close is defined as::

    clv_bps = (1/odds_close - 1/odds_taken) * 10000

quantized to 2 decimal places (``ROUND_HALF_EVEN``, Python's ``Decimal`` default rounding
mode — the same convention used for currency-minor-unit rounding elsewhere in this
codebase). POSITIVE means the taken price was LONGER (a bigger decimal number) than the
close — you backed at odds the market later shortened away from, i.e. you beat the close.
NEGATIVE means you backed at a shorter price than the close ultimately settled to.

Worked fixture (also asserted byte-for-byte in ``tests/unit/l8/test_clv.py``): taken
``3.00`` vs close ``2.50``::

    1/2.50 - 1/3.00 = 0.4 - 0.333333... = 0.066666...  ->  * 10000 = 666.666...  ->  666.67 bps

taken (3.00) is longer than close (2.50), so the result is positive, matching "you beat the
close" — as required.

Every one of the four CLV types additionally exposes ``odds_ratio`` (``odds_taken /
odds_close``) as a SECONDARY raw-odds-ratio representation, computed at the ambient
``Decimal`` context precision (28 significant digits) and left unquantized since it is a
secondary diagnostic, not the primary bps figure.

Both ``clv_bps`` and ``odds_ratio`` are properties, recomputed on every access from the
type's stored raw ``Decimal`` fields — never cached, so there is nowhere for a stale
derived value to hide (the same convention ``l8_evidence.paired_inference.PairedRace.d_r``
uses).

CLV is not a training target — the structural half of the enforcement
-----------------------------------------------------------------------
This module imports NOTHING beyond the Python standard library: no ``l4_pricing``, no
``l5_decision``/``l5b_risk``/``l6_broker``/``l7_settle``, no other first-party package at
all. A pricing or fill model literally cannot reach into this module to consume a CLV value
as a feature or label, and this module cannot reach back into pricing to compute one — the
import-graph direction (this module is an ``l8_evidence`` LEAF; nothing upstream of it ever
imports it, and it imports nothing downstream of it) is the enforcement, checked
mechanically in ``tests/unit/l8/test_clv.py`` via
``tools.check_import_quarantine.find_violations`` (the same checker SPEC-100/SPEC-045 use)
and via a public-name scan that refuses any public name containing ``target`` or ``label``
(the ML-target/ML-label vocabulary) anywhere in this module's public surface.

No LLM creates, alters, smooths or repairs any of the values in this module — every number
here is deterministic arithmetic over caller-supplied ``Decimal``/``int`` inputs.

Ambiguity resolutions taken while drafting this slice (see the task's final report for the
full list):

* The task brief's own worked example computes ``1/odds_close - 1/odds_taken`` (positive
  for taken=3.00, close=2.50), while a separate sentence in the same brief states the
  formula the other way around (``1/odds_taken - 1/odds_close``). Those two statements
  contradict each other for any non-equal pair of odds. The worked, numerically-checkable
  fixture is treated as authoritative over the prose formula, since it is the only one that
  is falsifiable against arithmetic: ``clv_bps = (1/odds_close - 1/odds_taken) * 10000``.
* "Signal CLV... regardless of whether an order was submitted" is read as: :class:`SignalCLV`
  is keyed by a ``candidate_ref`` (an opaque identifier for the decision instant/runner
  being evaluated), NOT an ``order_ref`` — unlike the other three types, which all concern
  an order that WAS submitted (intended or realised) and are keyed by ``order_ref``.
* :class:`ExecutionPolicyValue` is defined per this slice's brief as
  ``realised.clv_bps - intended.clv_bps`` on the matching order — a narrower reading than
  SPECIFICATION.md §8's fuller "realised P&L + opportunity cost of non-fills and fallbacks"
  (that fuller net-counterfactual-policy-value figure belongs with the fill-probability
  model, SPEC-040/042, once it exists; it is out of scope here and not claimed by this
  module).
* :class:`ExecutionPolicyValue` requires the two components' :class:`ClosingPrice` objects
  to be fully equal (same benchmark, same odds, same window where applicable), not merely
  the same benchmark KIND — two WAP observations with different windows are not "the same
  benchmark" for this purpose.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from enum import Enum
from typing import Sequence

__all__ = [
    "ClvError",
    "ClosingPriceError",
    "ExecutionPolicyValueError",
    "CLVBatchError",
    "UnfilledOrderError",
    "ClosingBenchmark",
    "UnfilledOutcome",
    "ClosingPrice",
    "SignalCLV",
    "IntendedOrderCLV",
    "RealisedFillCLV",
    "ExecutionPolicyValue",
    "UnfilledOrder",
    "CLVBatch",
    "realised_fill_clvs",
]

_HASH_PREFIX = "sha256:"
_BPS_QUANTUM = Decimal("0.01")


class ClvError(ValueError):
    """Base error for this module (SPEC-095)."""


class ClosingPriceError(ClvError):
    """A :class:`ClosingPrice`'s own fields are internally inconsistent."""


class ExecutionPolicyValueError(ClvError):
    """The two components handed to :class:`ExecutionPolicyValue` do not reference the
    same order, or were evaluated against different closing-price observations."""


class CLVBatchError(ClvError):
    """A :func:`realised_fill_clvs` call was given an inconsistent fill/unfilled set (a
    duplicated ``order_ref``, or one present in both the filled and unfilled sequences)."""


class UnfilledOrderError(ClvError):
    """An :class:`UnfilledOrder`'s own fields are internally inconsistent."""


class ClosingBenchmark(Enum):
    """The two — and only two — closing diagnostics retained (SPECIFICATION.md §8). Never
    averaged or merged: every CLV value names exactly one of these."""

    BSP = "BSP"
    PRE_SUSPENSION_WAP = "PRE_SUSPENSION_WAP"


class UnfilledOutcome(Enum):
    """The honest terminal state of an order that never matched. There is deliberately no
    catch-all ``UNKNOWN``/``OTHER`` member that could quietly absorb an unclassified state."""

    LAPSED = "LAPSED"
    CANCELLED = "CANCELLED"
    EXPIRED_UNMATCHED = "EXPIRED_UNMATCHED"


def _require_decimal_odds(
    value: object, field_name: str, error_cls: type[ClvError] = ClvError
) -> None:
    if not isinstance(value, Decimal):
        raise TypeError(f"{field_name} must be a Decimal, got {type(value).__name__}")
    if not value > Decimal(1):
        raise error_cls(f"{field_name} {value!r} must be > 1")


def _require_nonempty(
    value: str, field_name: str, error_cls: type[ClvError] = ClvError
) -> None:
    if not value or not value.strip():
        raise error_cls(f"{field_name} must be non-empty")


def _clv_bps(odds_taken: Decimal, odds_close: Decimal) -> Decimal:
    """``(1/odds_close - 1/odds_taken) * 10000``, quantized to 2dp (``ROUND_HALF_EVEN``).

    See the module docstring's "Sign convention" section for the worked fixture and the
    ambiguity resolution over the brief's two conflicting formula statements.
    """
    p_close = Decimal(1) / odds_close
    p_taken = Decimal(1) / odds_taken
    raw_bps = (p_close - p_taken) * Decimal(10000)
    return raw_bps.quantize(_BPS_QUANTUM, rounding=ROUND_HALF_EVEN)


def _odds_ratio(odds_taken: Decimal, odds_close: Decimal) -> Decimal:
    """``odds_taken / odds_close`` at ambient ``Decimal`` context precision — a secondary,
    unquantized representation; see the module docstring."""
    return odds_taken / odds_close


def _jsonable(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _content_digest(instance: object) -> str:
    payload = _jsonable(dataclasses.asdict(instance))  # type: ignore[call-overload]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return _HASH_PREFIX + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ClosingPrice:
    """One closing benchmark observation (SPEC-095).

    ``odds`` is a plain ``Decimal`` price greater than 1 — NOT necessarily an on-ladder tick
    index like :class:`price_contracts.prices.ClosePrice`, because a pre-suspension WAP is a
    volume-weighted average that will generally fall between ticks.

    ``BSP`` carries no window: both window fields MUST be ``None``. ``PRE_SUSPENSION_WAP``
    carries a MANDATORY window: ``window_start_seconds_before_suspension`` (the more distant
    edge, > 0) and ``window_end_seconds_before_suspension`` (the edge closer to suspension,
    >= 0), with ``start > end`` strictly enforced — "a defined... window" made structural.
    """

    benchmark: ClosingBenchmark
    odds: Decimal
    window_start_seconds_before_suspension: int | None = None
    window_end_seconds_before_suspension: int | None = None

    def __post_init__(self) -> None:
        _require_decimal_odds(self.odds, "odds", ClosingPriceError)
        if self.benchmark is ClosingBenchmark.BSP:
            if (
                self.window_start_seconds_before_suspension is not None
                or self.window_end_seconds_before_suspension is not None
            ):
                raise ClosingPriceError(
                    "BSP carries no window; both window fields must be None"
                )
            return
        start = self.window_start_seconds_before_suspension
        end = self.window_end_seconds_before_suspension
        if start is None or end is None:
            raise ClosingPriceError(
                "PRE_SUSPENSION_WAP requires both window fields to be set"
            )
        if not isinstance(start, int) or isinstance(start, bool):
            raise TypeError("window_start_seconds_before_suspension must be a plain int")
        if not isinstance(end, int) or isinstance(end, bool):
            raise TypeError("window_end_seconds_before_suspension must be a plain int")
        if start <= 0:
            raise ClosingPriceError("window_start_seconds_before_suspension must be > 0")
        if end < 0:
            raise ClosingPriceError("window_end_seconds_before_suspension must be >= 0")
        if start <= end:
            raise ClosingPriceError(
                "window_start_seconds_before_suspension must be strictly greater than "
                "window_end_seconds_before_suspension"
            )

    def content_digest(self) -> str:
        """Deterministic ``sha256:<hex>`` over every field."""
        return _content_digest(self)


@dataclass(frozen=True)
class SignalCLV:
    """Signal CLV (SPECIFICATION.md §8): the candidate's decision-threshold price at signal
    time vs the close, regardless of whether an order was ever submitted. Keyed by
    ``candidate_ref`` (a decision instant / candidate identifier), not an order — unlike the
    other three CLV types, no order need ever have existed for this one.
    """

    candidate_ref: str
    closing: ClosingPrice
    odds_at_signal: Decimal

    def __post_init__(self) -> None:
        _require_nonempty(self.candidate_ref, "candidate_ref")
        _require_decimal_odds(self.odds_at_signal, "odds_at_signal")

    @property
    def clv_bps(self) -> Decimal:
        return _clv_bps(self.odds_at_signal, self.closing.odds)

    @property
    def odds_ratio(self) -> Decimal:
        return _odds_ratio(self.odds_at_signal, self.closing.odds)

    def content_digest(self) -> str:
        return _content_digest(self)


@dataclass(frozen=True)
class IntendedOrderCLV:
    """Intended-order CLV (SPECIFICATION.md §8): the price the decision layer INTENDED to
    cross at (the requested limit price) vs the close. Measures decision timing, independent
    of whether the order actually filled.
    """

    order_ref: str
    closing: ClosingPrice
    odds_intended: Decimal

    def __post_init__(self) -> None:
        _require_nonempty(self.order_ref, "order_ref")
        _require_decimal_odds(self.odds_intended, "odds_intended")

    @property
    def clv_bps(self) -> Decimal:
        return _clv_bps(self.odds_intended, self.closing.odds)

    @property
    def odds_ratio(self) -> Decimal:
        return _odds_ratio(self.odds_intended, self.closing.odds)

    def content_digest(self) -> str:
        return _content_digest(self)


@dataclass(frozen=True)
class RealisedFillCLV:
    """Realised-fill CLV (SPECIFICATION.md §8): the ACTUAL matched price vs the close.

    Constructing this type IS the evidence of a fill: ``matched_stake_minor`` must be a
    positive plain int (integer minor currency units — CLAUDE.md "Types"). There is
    deliberately no optional "hypothetical price" parameter anywhere on this type, or
    anywhere in this module: an order that never matched cannot produce one of these — see
    :class:`UnfilledOrder` for the honest artifact instead.
    """

    order_ref: str
    closing: ClosingPrice
    odds_matched: Decimal
    matched_stake_minor: int

    def __post_init__(self) -> None:
        _require_nonempty(self.order_ref, "order_ref")
        _require_decimal_odds(self.odds_matched, "odds_matched")
        if not isinstance(self.matched_stake_minor, int) or isinstance(
            self.matched_stake_minor, bool
        ):
            raise TypeError("matched_stake_minor must be a plain int")
        if self.matched_stake_minor <= 0:
            raise ClvError(
                "matched_stake_minor must be > 0 — a fill without a positive matched stake "
                "is not a fill; there is no way to construct a RealisedFillCLV for an "
                "unfilled order"
            )

    @property
    def clv_bps(self) -> Decimal:
        return _clv_bps(self.odds_matched, self.closing.odds)

    @property
    def odds_ratio(self) -> Decimal:
        return _odds_ratio(self.odds_matched, self.closing.odds)

    def content_digest(self) -> str:
        return _content_digest(self)


@dataclass(frozen=True)
class ExecutionPolicyValue:
    """Execution-policy value for one order (SPECIFICATION.md §8): ``realised.clv_bps -
    intended.clv_bps`` — what execution added or cost relative to what the decision layer
    intended to cross at. Constructed ONLY from the two typed components; there is no way to
    build one from bare numbers, so it can never mix a realised fill from one order with an
    intention from another, and it refuses to combine components evaluated against
    different closing-price observations (different benchmark KIND, or the same benchmark
    kind with a different odds/window — e.g. two different WAP windows are not "the same
    benchmark" for this purpose).
    """

    intended: IntendedOrderCLV
    realised: RealisedFillCLV

    def __post_init__(self) -> None:
        if self.intended.order_ref != self.realised.order_ref:
            raise ExecutionPolicyValueError(
                f"order_ref mismatch: intended={self.intended.order_ref!r} "
                f"realised={self.realised.order_ref!r} — execution-policy value requires "
                "both components to reference the SAME order"
            )
        if self.intended.closing.benchmark is not self.realised.closing.benchmark:
            raise ExecutionPolicyValueError(
                f"benchmark mismatch: intended={self.intended.closing.benchmark.value} "
                f"realised={self.realised.closing.benchmark.value} — the two closing "
                "benchmarks (BSP, PRE_SUSPENSION_WAP) are never compared against each other"
            )
        if self.intended.closing != self.realised.closing:
            raise ExecutionPolicyValueError(
                "intended and realised must share the identical closing-price observation "
                "(same odds and, for PRE_SUSPENSION_WAP, the same window) — not merely the "
                "same benchmark kind"
            )

    @property
    def order_ref(self) -> str:
        return self.realised.order_ref

    @property
    def value_bps(self) -> Decimal:
        """``realised.clv_bps - intended.clv_bps``. Positive means the fill captured MORE
        implied-probability basis points versus the close than the intended order alone
        would have; negative means execution gave some of the intended CLV back."""
        return self.realised.clv_bps - self.intended.clv_bps

    def content_digest(self) -> str:
        return _content_digest(self)


@dataclass(frozen=True)
class UnfilledOrder:
    """The honest artifact for an order that never matched (SPECIFICATION.md §8: "for
    unfilled orders, realised CLV does not exist... this is the difference between
    measurement and fiction"). Carries only the order reference and an explicit terminal
    outcome — never a price, hypothetical or otherwise.
    """

    order_ref: str
    outcome: UnfilledOutcome

    def __post_init__(self) -> None:
        _require_nonempty(self.order_ref, "order_ref", UnfilledOrderError)

    def content_digest(self) -> str:
        return _content_digest(self)


@dataclass(frozen=True)
class CLVBatch:
    """The honest result of evaluating realised-fill CLV over a MIXED set of orders
    (SPEC-095): filled orders' :class:`RealisedFillCLV` values, and unfilled orders'
    :class:`UnfilledOrder` records, kept SEPARATELY and BOTH always present. An unfilled
    order is never dropped from this artifact and never assigned a price.
    ``filled_count + unfilled_count == total_count`` always, so a denominator computed from
    this batch can never silently exclude the unfilled tail.
    """

    realised: tuple[RealisedFillCLV, ...]
    unfilled: tuple[UnfilledOrder, ...]
    filled_count: int
    unfilled_count: int
    total_count: int

    def __post_init__(self) -> None:
        if self.filled_count != len(self.realised):
            raise CLVBatchError("filled_count must equal len(realised)")
        if self.unfilled_count != len(self.unfilled):
            raise CLVBatchError("unfilled_count must equal len(unfilled)")
        if self.total_count != self.filled_count + self.unfilled_count:
            raise CLVBatchError("total_count must equal filled_count + unfilled_count")

    def content_digest(self) -> str:
        return _content_digest(self)


def realised_fill_clvs(
    fills: Sequence[RealisedFillCLV],
    unfilled: Sequence[UnfilledOrder],
) -> CLVBatch:
    """Evaluate realised-fill CLV over a mixed order set (SPEC-095).

    Returns realised CLVs ONLY for ``fills`` (each already backed, by construction of
    :class:`RealisedFillCLV`, by a positive matched stake) PLUS the ``unfilled`` records
    separately — an unfilled order is never silently dropped and never priced. Refuses a
    duplicated ``order_ref`` within either sequence, and refuses an ``order_ref`` present in
    BOTH sequences (an order cannot be simultaneously filled and unfilled).
    """
    fill_refs = [f.order_ref for f in fills]
    unfilled_refs = [u.order_ref for u in unfilled]
    if len(set(fill_refs)) != len(fill_refs):
        dup = sorted({r for r in fill_refs if fill_refs.count(r) > 1})
        raise CLVBatchError(f"duplicate order_ref(s) among fills: {dup}")
    if len(set(unfilled_refs)) != len(unfilled_refs):
        dup = sorted({r for r in unfilled_refs if unfilled_refs.count(r) > 1})
        raise CLVBatchError(f"duplicate order_ref(s) among unfilled: {dup}")
    overlap = sorted(set(fill_refs) & set(unfilled_refs))
    if overlap:
        raise CLVBatchError(
            f"order_ref(s) present in both fills and unfilled (an order cannot be both): "
            f"{overlap}"
        )
    return CLVBatch(
        realised=tuple(fills),
        unfilled=tuple(unfilled),
        filled_count=len(fills),
        unfilled_count=len(unfilled),
        total_count=len(fills) + len(unfilled),
    )
