"""Order state machine and idempotent order book of record (SPEC-070, SPEC-071).

Phase 3A OFFLINE construction (ADR 0014): no live credentials, no networking, no real
``placeOrders`` call exists anywhere in this module. This is the deterministic
order-domain core that a real broker adapter would sit behind.

SPEC-070 -- order state machine
--------------------------------
``CREATED -> SUBMITTED -> ACKNOWLEDGED -> EXECUTABLE -> PARTIALLY_MATCHED ->
MATCHED|CANCELLED|LAPSED|VOIDED -> SETTLED -> RESETTLED``. ``LEGAL_TRANSITIONS`` below is
the single source of truth; :meth:`Order.transition` raises :class:`IllegalTransitionError`
naming both states for anything not in that table. Every legal transition appends one
immutable :class:`TransitionRecord` to the order's history -- the order itself is a frozen
dataclass, so a transition returns a **new** ``Order``, never mutates the old one.

Betfair semantics for each edge in ``LEGAL_TRANSITIONS`` are documented next to the table.
The state machine additionally models ``PARTIALLY_MATCHED`` because Betfair's general
order model permits it -- but v1 execution is ``taker-v1`` (SPEC-052: FILL_OR_KILL,
minFillSize == full stake). Under that policy a partial fill is never a legitimate
outcome; :meth:`Order.is_taker_v1_incident` flags it as the execution incident it is
(SPECIFICATION.md 6.6), not a state to be tuned away.

SPEC-071 -- idempotent placement
---------------------------------
:class:`OrderBook` is the boundary that enforces "a logical intent may create at most
one economic exposure" (SPECIFICATION.md 12, "Idempotency invariant"). It is keyed on
``customer_order_ref``: replaying the same reference returns the *existing* order
completely unchanged, even when other fields on the replayed command differ -- a
differing-fields replay is recorded as a :class:`PlacementAnomaly` (informational only)
and adds zero exposure. :meth:`OrderBook.exposure_minor` defines the two exposure
measures precisely; both are proven invariant under duplicate commands in
``tests/properties/l6/test_exposure_props.py``.

:class:`OrderBook` also carries two forward-looking guards whose full obligations are
out of this slice's scope (ADR 0014):

* Market reservation (SPEC-054 extension): v1 is one runner per market, so a second
  live intent on an already-reserved market is refused at the broker boundary, not
  merged.
* Unknown-order fail-closed (SPEC-062, lands as its own slice): :meth:`Order.marked_unknown`
  and the corresponding block in :meth:`OrderBook.place` are the structural hook the
  next slice wires reconciliation into. This slice only proves the fail-closed shape;
  its tests stay under the SPEC-071 mark, not SPEC-062, per ADR 0014.

Money types throughout: stakes and matched amounts are integer minor units; price is an
integer tick index into the canonical ladder (``price_contracts.ladder``, SPEC-053) --
never a float, never Decimal odds in the order core. Every transition carries both a UTC
wall-clock reading and a monotonic process-clock reading (SPEC-004); ``TransitionRecord``
stores the pair directly rather than a bound clock-domain object, since the order core
has no need of cross-domain latency comparison -- that lives with the capture layer
(``l0_raw.clock.ClockStamp``), which this money-critical package deliberately does not
depend on.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import Enum
from types import MappingProxyType

from l5_decision.execution import PersistenceType, Side
from price_contracts.ladder import is_valid_index


class OrderState(Enum):
    """The eleven order states of SPEC-070's state machine."""

    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    EXECUTABLE = "EXECUTABLE"
    PARTIALLY_MATCHED = "PARTIALLY_MATCHED"
    MATCHED = "MATCHED"
    CANCELLED = "CANCELLED"
    LAPSED = "LAPSED"
    VOIDED = "VOIDED"
    SETTLED = "SETTLED"
    RESETTLED = "RESETTLED"


# SPEC-070: the single source of truth for legal transitions. Each edge documented with
# its Betfair semantic. MappingProxyType makes the module-level table genuinely
# immutable, not merely conventionally so.
LEGAL_TRANSITIONS: MappingProxyType[OrderState, frozenset[OrderState]] = MappingProxyType(
    {
        # A locally-built intent has not yet been sent to the exchange.
        OrderState.CREATED: frozenset({OrderState.SUBMITTED}),
        # Sent; the exchange has not yet acknowledged. It can still come back LAPSED if
        # the request itself is rejected/times out before an ack (e.g. malformed
        # instruction, marketVersion already stale) -- SPEC-072's guard modelled as a
        # transition, not a live network wiring, in this offline slice.
        OrderState.SUBMITTED: frozenset({OrderState.ACKNOWLEDGED, OrderState.LAPSED}),
        # The exchange has accepted the instruction. EXECUTABLE is reached once it is
        # live on the book; LAPSED if it lapses before becoming executable (e.g.
        # marketVersion guard fires); VOIDED if the market itself is voided in the
        # window between ack and execution.
        OrderState.ACKNOWLEDGED: frozenset({OrderState.EXECUTABLE, OrderState.LAPSED, OrderState.VOIDED}),
        # Live and eligible to match. From here: a full immediate match (MATCHED, the
        # only outcome taker-v1 is designed to produce); an unexpected partial match
        # (PARTIALLY_MATCHED -- a taker-v1 execution incident, never a normal path);
        # voluntary CANCELLED; a marketVersion-driven or FOK-miss LAPSED; or the market
        # is VOIDED underneath the order.
        OrderState.EXECUTABLE: frozenset(
            {
                OrderState.PARTIALLY_MATCHED,
                OrderState.MATCHED,
                OrderState.CANCELLED,
                OrderState.LAPSED,
                OrderState.VOIDED,
            }
        ),
        # An unexpected partial fill under taker-v1 (see is_taker_v1_incident). It can
        # still resolve to a full MATCHED, be CANCELLED (the matched portion stands --
        # only the unmatched remainder is cancelled), LAPSE (e.g. suspension), or VOID.
        OrderState.PARTIALLY_MATCHED: frozenset(
            {OrderState.MATCHED, OrderState.CANCELLED, OrderState.LAPSED, OrderState.VOIDED}
        ),
        # A terminal matching outcome awaiting settlement.
        OrderState.MATCHED: frozenset({OrderState.SETTLED}),
        # Cancelled (any matched portion still stands and awaits settlement).
        OrderState.CANCELLED: frozenset({OrderState.SETTLED}),
        # Lapsed (persistenceType=LAPSE is pinned in v1 -- SPEC-052 -- so any unmatched
        # remainder always lapses rather than resting; any matched portion still stands).
        OrderState.LAPSED: frozenset({OrderState.SETTLED}),
        # The market was voided; this order's positions settle to zero (SPEC-082) but the
        # order record itself still passes through SETTLED to close the lifecycle.
        OrderState.VOIDED: frozenset({OrderState.SETTLED}),
        # Settled once; a resettlement (SPEC-082/SPEC-080) is the only further move.
        OrderState.SETTLED: frozenset({OrderState.RESETTLED}),
        # Resettlements can recur (dead-heat corrections, void corrections, etc.) --
        # RESETTLED is absorbing except for its own self-loop.
        OrderState.RESETTLED: frozenset({OrderState.RESETTLED}),
    }
)


class IllegalTransitionError(Exception):
    """Raised by :meth:`Order.transition` for any edge not in ``LEGAL_TRANSITIONS`` (SPEC-070)."""


class MarketReservedError(Exception):
    """Raised when a new ``customer_order_ref`` targets a market already reserved by a
    live order for a different logical intent (SPEC-054 extension into the broker, ADR 0014).
    """


class PlacementBlockedError(Exception):
    """Raised when any order in the book is flagged unknown -- all further placement is
    blocked until reconciled (SPEC-062 forward dependency; full reconciliation lands in
    its own slice, ADR 0014). No exceptions, no timeout-based assumption of failure.
    """


def _is_plain_int(value: object) -> bool:
    """``True`` only for a genuine ``int`` -- ``bool`` (an ``int`` subclass) and ``float``
    are both refused, matching the ladder's own tick-index discipline (SPEC-053)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _require_utc(at_utc: datetime, *, label: str) -> None:
    if at_utc.tzinfo is None:
        raise ValueError(f"{label} must be timezone-aware UTC, got a naive datetime (SPEC-004)")
    if at_utc.utcoffset() != timedelta(0):
        raise ValueError(f"{label} must be UTC (zero offset), got offset {at_utc.utcoffset()}")


@dataclass(frozen=True)
class TransitionRecord:
    """One entry in an order's append-only history. Dual-clock per SPEC-004: a UTC wall
    reading and a monotonic process-clock reading, both taken at the moment of transition."""

    from_state: OrderState
    to_state: OrderState
    at_utc: datetime
    monotonic_ns: int
    reason: str

    def __post_init__(self) -> None:
        _require_utc(self.at_utc, label="TransitionRecord.at_utc")
        if not _is_plain_int(self.monotonic_ns):
            raise TypeError(f"monotonic_ns must be a plain int, got {type(self.monotonic_ns).__name__}")
        if not self.reason:
            raise ValueError("TransitionRecord.reason must be a non-empty string")


# States from which an order can still originate NEW matched stake (i.e. it has not yet
# reached a terminal matching/cancellation/void/settlement outcome). Used to define
# potential_exposure_minor below.
_LIVE_UNMATCHED_RISK_STATES: frozenset[OrderState] = frozenset(
    {
        OrderState.CREATED,
        OrderState.SUBMITTED,
        OrderState.ACKNOWLEDGED,
        OrderState.EXECUTABLE,
        OrderState.PARTIALLY_MATCHED,
    }
)

# States that release a market reservation (SPEC-054 extension, ADR 0014). Everything
# else -- including CANCELLED/LAPSED, which may still carry a matched portion awaiting
# settlement -- keeps the market reserved to one logical intent.
_RESERVATION_RELEASING_STATES: frozenset[OrderState] = frozenset(
    {OrderState.SETTLED, OrderState.RESETTLED, OrderState.VOIDED}
)


@dataclass(frozen=True)
class Order:
    """The book-of-record entity for one taker-v1 order (SPEC-070/071/052).

    Immutable: every state change is a new ``Order`` produced by :meth:`transition`, with
    the prior instance left untouched and one more :class:`TransitionRecord` appended to
    ``history``. ``matched_stake_minor`` is monotonically non-decreasing across the
    lifetime of an order -- a lapse or cancellation after a partial match leaves the
    matched portion standing; it does not, and structurally cannot, retreat.
    """

    order_id: str
    customer_order_ref: str
    market_id: str
    selection_id: int
    side: Side
    price_tick: int
    stake_minor: int
    market_version: int
    persistence: PersistenceType
    state: OrderState = OrderState.CREATED
    matched_stake_minor: int = 0
    history: tuple[TransitionRecord, ...] = ()
    unknown: bool = False

    def __post_init__(self) -> None:
        if self.side is not Side.BACK:
            raise ValueError(
                f"order {self.customer_order_ref!r}: v1 is back-only; lay/hedge is a hard "
                "prohibition and is refused at construction (SPEC-052)"
            )
        if self.persistence is not PersistenceType.LAPSE:
            raise ValueError(
                f"order {self.customer_order_ref!r}: taker-v1 requires persistenceType=LAPSE "
                f"always, got {self.persistence!r} (SPEC-052)"
            )
        if not _is_plain_int(self.selection_id) or self.selection_id <= 0:
            raise ValueError(f"selection_id must be a positive int, got {self.selection_id!r}")
        if not _is_plain_int(self.market_version) or self.market_version <= 0:
            raise ValueError(f"market_version must be a positive int, got {self.market_version!r}")
        if not is_valid_index(self.price_tick):
            raise ValueError(f"price_tick {self.price_tick!r} is not a valid ladder index (SPEC-053)")
        if not _is_plain_int(self.stake_minor):
            raise TypeError(f"stake_minor must be a plain int (minor units), got {type(self.stake_minor).__name__}")
        if self.stake_minor <= 0:
            raise ValueError(f"stake_minor must be positive, got {self.stake_minor}")
        if not _is_plain_int(self.matched_stake_minor):
            raise TypeError(
                f"matched_stake_minor must be a plain int (minor units), got {type(self.matched_stake_minor).__name__}"
            )
        if self.matched_stake_minor < 0:
            raise ValueError(f"matched_stake_minor must be non-negative, got {self.matched_stake_minor}")
        if self.matched_stake_minor > self.stake_minor:
            raise ValueError(
                f"matched_stake_minor {self.matched_stake_minor} cannot exceed stake_minor {self.stake_minor}"
            )
        if self.state is OrderState.PARTIALLY_MATCHED and not (0 < self.matched_stake_minor < self.stake_minor):
            raise ValueError(
                "PARTIALLY_MATCHED requires 0 < matched_stake_minor < stake_minor, got "
                f"matched={self.matched_stake_minor} stake={self.stake_minor}"
            )
        if self.state is OrderState.MATCHED and self.matched_stake_minor != self.stake_minor:
            raise ValueError(
                "MATCHED requires matched_stake_minor == stake_minor, got "
                f"matched={self.matched_stake_minor} stake={self.stake_minor}"
            )
        if not self.customer_order_ref:
            raise ValueError("customer_order_ref must be a non-empty string (SPEC-071 idempotency key)")

    def transition(
        self,
        to_state: OrderState,
        *,
        at_utc: datetime,
        monotonic_ns: int,
        reason: str,
        matched_stake_minor: int | None = None,
    ) -> Order:
        """Return a NEW ``Order`` advanced to ``to_state``.

        Raises :class:`IllegalTransitionError` naming both states if ``to_state`` is not
        reachable from the current state per ``LEGAL_TRANSITIONS`` -- checked before any
        matched-amount validation, so an illegal edge always raises regardless of the
        ``matched_stake_minor`` supplied. ``matched_stake_minor`` defaults to the current
        value (i.e. unchanged); passing a lower value raises ``ValueError`` -- the
        matched amount is monotonically non-decreasing for the lifetime of an order.
        """
        legal = LEGAL_TRANSITIONS.get(self.state, frozenset())
        if to_state not in legal:
            raise IllegalTransitionError(
                f"illegal transition {self.state.name} -> {to_state.name} for order "
                f"{self.customer_order_ref!r} (SPEC-070)"
            )
        new_matched = self.matched_stake_minor if matched_stake_minor is None else matched_stake_minor
        if not _is_plain_int(new_matched):
            raise TypeError(f"matched_stake_minor must be a plain int, got {type(new_matched).__name__}")
        if new_matched < self.matched_stake_minor:
            raise ValueError(
                f"matched_stake_minor must be monotonically non-decreasing: "
                f"{new_matched} < current {self.matched_stake_minor}"
            )
        record = TransitionRecord(
            from_state=self.state,
            to_state=to_state,
            at_utc=at_utc,
            monotonic_ns=monotonic_ns,
            reason=reason,
        )
        # __post_init__ on the replaced instance re-validates the matched/stake
        # invariants for to_state (e.g. PARTIALLY_MATCHED / MATCHED bounds), so they are
        # declared once, on the entity, rather than duplicated here.
        return replace(
            self,
            state=to_state,
            matched_stake_minor=new_matched,
            history=self.history + (record,),
        )

    def marked_unknown(self) -> Order:
        """Return a copy flagged ``unknown=True``, state otherwise preserved.

        Structural hook for SPEC-062 (fail-closed on unknown order state): the full
        reconciliation obligation lands in its own slice; this slice only guarantees that
        an unknown-flagged order in the book blocks all further placement
        (:meth:`OrderBook.place`).
        """
        return replace(self, unknown=True)

    def is_taker_v1_incident(self) -> bool:
        """``True`` exactly when this order is ``PARTIALLY_MATCHED``.

        ``PARTIALLY_MATCHED`` is reachable in the type system because Betfair's general
        order state machine permits it. But taker-v1 (SPEC-052) pins
        ``timeInForce=FILL_OR_KILL`` with ``minFillSize`` equal to the full stake, so no
        resting remainder can ever exist. Any order that nonetheless lands in
        ``PARTIALLY_MATCHED`` under taker-v1 is an EXECUTION INCIDENT to be reconciled and
        investigated -- never a normal state to be tuned around or silently accepted
        (SPECIFICATION.md 6.6).
        """
        return self.state is OrderState.PARTIALLY_MATCHED


@dataclass(frozen=True)
class PlaceCommand:
    """An intended new order, keyed for idempotency by ``customer_order_ref`` (SPEC-071).

    Deliberately unvalidated beyond field types being the right shape for comparison: a
    genuinely new command's field values are validated when :class:`Order` is
    constructed from it (invalid values raise there); a *duplicate* command's fields are
    never used to construct anything -- they are only compared against the existing
    order to detect a differing-fields replay, which must never change economic exposure
    regardless of what it contains.
    """

    customer_order_ref: str
    market_id: str
    selection_id: int
    side: Side
    price_tick: int
    stake_minor: int
    market_version: int
    persistence: PersistenceType


# The PlaceCommand fields that are compared against an existing order to detect a
# differing-fields duplicate (SPEC-071). customer_order_ref itself is the lookup key, not
# a comparison field.
_COMMAND_COMPARISON_FIELDS: tuple[str, ...] = (
    "market_id",
    "selection_id",
    "side",
    "price_tick",
    "stake_minor",
    "market_version",
    "persistence",
)


@dataclass(frozen=True)
class PlacementAnomaly:
    """Recorded when a replayed ``customer_order_ref`` carries different field values
    than the order already on file. Informational only -- it never changes exposure
    (SPEC-071: "changing informational metadata must not alter the decision")."""

    customer_order_ref: str
    differing_fields: tuple[str, ...]
    at_utc: datetime
    monotonic_ns: int


@dataclass(frozen=True)
class Exposure:
    """The two exposure measures :meth:`OrderBook.exposure_minor` returns together.

    ``potential_exposure_minor`` -- sum of ``stake_minor`` over orders in this market
    still in a state that could originate NEW matched stake (``CREATED``, ``SUBMITTED``,
    ``ACKNOWLEDGED``, ``EXECUTABLE``, ``PARTIALLY_MATCHED``). This is the conservative
    upper bound of what could still be matched: under taker-v1's FILL_OR_KILL the whole
    stake is atomically at risk during the ``EXECUTABLE`` window, so the full
    ``stake_minor`` (not merely the unmatched remainder) is counted for as long as the
    order could still act.

    ``matched_exposure_minor`` -- sum of ``matched_stake_minor`` over ALL orders in this
    market whose state is not ``VOIDED`` (a voided market's matched stake is refunded, so
    it is excluded). This is a cumulative ledger-style total of stake that was ever
    actually matched and economically realised on this market; it is not filtered to
    "still live" orders, since a settled order's matched stake was real money at risk and
    remains part of the record.
    """

    potential_exposure_minor: int
    matched_exposure_minor: int


class OrderBook:
    """The idempotent book of record for one broker session (SPEC-071).

    Keyed on ``customer_order_ref``. Enforces, in this order, every time :meth:`place`
    is called:

    1. Fail-closed on any order flagged unknown (SPEC-062 forward dependency) -- this
       guard dominates even a pure idempotent replay, because "all further placement" in
       the spec text draws no exception for replays.
    2. Idempotent short-circuit: an existing ``customer_order_ref`` returns the existing
       order unchanged, recording a :class:`PlacementAnomaly` if the replayed fields
       differ, but never constructing a new order and never touching exposure.
    3. Market reservation (SPEC-054 extension, ADR 0014): a genuinely new reference is
       refused with :class:`MarketReservedError` if any order already reserves the same
       market. First command wins; only its own duplicates are exempt (handled by step 2
       before this check is ever reached).
    """

    def __init__(self) -> None:
        self._by_ref: dict[str, Order] = {}
        self._anomalies: list[PlacementAnomaly] = []

    def place(self, command: PlaceCommand, *, at_utc: datetime, monotonic_ns: int) -> Order:
        if any(order.unknown for order in self._by_ref.values()):
            raise PlacementBlockedError(
                "an order in this book is in an UNKNOWN state; all further placement is "
                "blocked until it is reconciled -- no exceptions, no timeout-based "
                "assumption of failure (SPEC-062 forward dependency, ADR 0014)"
            )

        existing = self._by_ref.get(command.customer_order_ref)
        if existing is not None:
            differing = _differing_fields(command, existing)
            if differing:
                self._anomalies.append(
                    PlacementAnomaly(
                        customer_order_ref=command.customer_order_ref,
                        differing_fields=differing,
                        at_utc=at_utc,
                        monotonic_ns=monotonic_ns,
                    )
                )
            return existing

        reserving_order = self._reserving_order(command.market_id)
        if reserving_order is not None:
            raise MarketReservedError(
                f"market {command.market_id!r} is already reserved by order "
                f"{reserving_order.customer_order_ref!r} (state={reserving_order.state.name}); "
                "v1 permits one position per market (SPEC-054 extension, ADR 0014)"
            )

        order = Order(
            # Deterministic book-of-record id: same command inputs always produce the same
            # book (money code is deterministic; a random id would break replayability).
            # Uniqueness follows from customer_order_ref uniqueness within this book; the
            # exchange's own betId is a separate concern for the real adapter (Phase 3B).
            order_id="ord-" + hashlib.sha256(command.customer_order_ref.encode("utf-8")).hexdigest()[:24],
            customer_order_ref=command.customer_order_ref,
            market_id=command.market_id,
            selection_id=command.selection_id,
            side=command.side,
            price_tick=command.price_tick,
            stake_minor=command.stake_minor,
            market_version=command.market_version,
            persistence=command.persistence,
        )
        self._by_ref[command.customer_order_ref] = order
        return order

    def update(self, order: Order) -> None:
        """Persist a transitioned ``Order`` back into the book, keyed by its existing
        ``customer_order_ref``. Raises ``KeyError`` if the reference is not on file --
        ``update`` records lifecycle progress for an order that already went through
        :meth:`place`, it does not create new orders."""
        if order.customer_order_ref not in self._by_ref:
            raise KeyError(f"no order on file for customer_order_ref {order.customer_order_ref!r}")
        self._by_ref[order.customer_order_ref] = order

    def get(self, customer_order_ref: str) -> Order | None:
        return self._by_ref.get(customer_order_ref)

    def orders(self) -> tuple[Order, ...]:
        return tuple(self._by_ref.values())

    @property
    def anomalies(self) -> tuple[PlacementAnomaly, ...]:
        return tuple(self._anomalies)

    def exposure_minor(self, market_id: str) -> Exposure:
        """The two exposure measures for ``market_id`` -- see :class:`Exposure`."""
        potential = 0
        matched = 0
        for order in self._by_ref.values():
            if order.market_id != market_id:
                continue
            if order.state in _LIVE_UNMATCHED_RISK_STATES:
                potential += order.stake_minor
            if order.state is not OrderState.VOIDED:
                matched += order.matched_stake_minor
        return Exposure(potential_exposure_minor=potential, matched_exposure_minor=matched)

    def _reserving_order(self, market_id: str) -> Order | None:
        for order in self._by_ref.values():
            if order.market_id == market_id and order.state not in _RESERVATION_RELEASING_STATES:
                return order
        return None


def _differing_fields(command: PlaceCommand, existing: Order) -> tuple[str, ...]:
    differing = [name for name in _COMMAND_COMPARISON_FIELDS if getattr(command, name) != getattr(existing, name)]
    return tuple(differing)
