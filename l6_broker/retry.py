"""Governed retry after a released reservation (F-13 founder ruling, 2026-07-17).

A released reservation does not license a re-fire. Retry requires ALL of:

1. **confirmed zero exposure** — the caller attests reconciliation confirmed no matched
   stake and no order-state ambiguity on the market (the reservation predicate in
   :mod:`l6_broker.orders` is the structural half of this);
2. **governed cooldown elapsed** — wall-clock UTC seconds since the market's last
   recorded attempt; never a prior process's monotonic clock (monotonic origins do not
   survive restarts). A wall clock observed to go backwards fails closed;
3. **attempt budget remains** — per-market, counted from the immutable attempt log, so
   budgets persist across process restarts;
4. **materially changed market/decision state** — enforced mechanically: the identical
   ``(decision_snapshot_digest, book_state_digest)`` pair may NEVER trigger twice,
   globally, ever, including across restarts. Time passage alone changes neither digest
   and therefore can never constitute material change.

Every refusal is a typed :class:`RetryRefusal` reason, never a bare ``False``.

**Restart discipline:** the governor rebuilds its state (spent budgets, burned digest
pairs, last attempt times) from the append-only attempt log at construction, and starts
UNRECONCILED — every evaluation refuses with ``NOT_RECONCILED_SINCE_RESTART`` until the
caller confirms reconciliation for this process epoch via :meth:`mark_reconciled`.

**Record-before-act:** :meth:`record_attempt` appends to the log BEFORE any order is
transmitted (SPEC-003 discipline). A crash between record and act therefore burns the
digest pair and spends budget — the conservative side: a doubt costs a retry, never a
double-fire.

Governed constants (``cooldown_seconds``, ``attempt_budget``) are mandatory constructor
arguments with no defaults — they come from the pre-registered experiment policy, never
from this module.

No live credentials, production networking, or real order transmission exist anywhere
in this module; it governs the DECISION to retry, offline (ADR 0014 Phase 3A).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum, unique

from l0_raw.store import AppendOnlyLog

__all__ = ["RetryRefusal", "RetryDecision", "RetryGovernor"]

_ATTEMPT_RECORD_TYPE = "retry_attempt"


@unique
class RetryRefusal(Enum):
    """Why a retry was refused. Check order is fixed: exposure dominates everything
    (guard dominance), reconciliation next, then the never-twice digest rule, then the
    budget, then the clock/cooldown."""

    EXPOSURE_NOT_CONFIRMED_ZERO = "EXPOSURE_NOT_CONFIRMED_ZERO"
    NOT_RECONCILED_SINCE_RESTART = "NOT_RECONCILED_SINCE_RESTART"
    DUPLICATE_DECISION_SNAPSHOT = "DUPLICATE_DECISION_SNAPSHOT"
    ATTEMPT_BUDGET_EXHAUSTED = "ATTEMPT_BUDGET_EXHAUSTED"
    CLOCK_WENT_BACKWARDS = "CLOCK_WENT_BACKWARDS"
    COOLDOWN_NOT_ELAPSED = "COOLDOWN_NOT_ELAPSED"


@dataclass(frozen=True)
class RetryDecision:
    """The typed outcome of one evaluation: approved, or refused with a reason."""

    approved: bool
    refusal: RetryRefusal | None

    def __post_init__(self) -> None:
        if self.approved and self.refusal is not None:
            raise ValueError("an approved decision cannot carry a refusal reason")
        if not self.approved and self.refusal is None:
            raise ValueError("a refusal must carry its typed reason, never a bare False")


def _require_aware(now_utc: datetime) -> None:
    if now_utc.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware UTC")


class RetryGovernor:
    """Per-process retry governor over a persistent append-only attempt log."""

    def __init__(self, log: AppendOnlyLog, *, cooldown_seconds: int, attempt_budget: int) -> None:
        if cooldown_seconds <= 0:
            raise ValueError(
                f"cooldown_seconds must be positive, got {cooldown_seconds!r} — the "
                "governed cooldown comes from the pre-registered policy"
            )
        if attempt_budget <= 0:
            raise ValueError(
                f"attempt_budget must be positive, got {attempt_budget!r} — refusing all "
                "retries is done by not constructing a governor, never by a zero budget"
            )
        self._log = log
        self._cooldown = timedelta(seconds=cooldown_seconds)
        self._budget = attempt_budget
        self._reconciled_this_epoch = False
        # Rebuilt from the immutable log: budgets and burned digests survive restarts.
        self._attempts_by_market: dict[str, int] = {}
        self._last_attempt_utc: dict[str, datetime] = {}
        self._seen_digest_pairs: set[tuple[str, str]] = set()
        for meta, payload in log.read():
            if meta.get("record_type") != _ATTEMPT_RECORD_TYPE:
                continue
            record = json.loads(payload.decode("utf-8"))
            market_id = record["market_id"]
            self._attempts_by_market[market_id] = self._attempts_by_market.get(market_id, 0) + 1
            attempt_utc = datetime.fromisoformat(record["attempt_utc"])
            previous = self._last_attempt_utc.get(market_id)
            if previous is None or attempt_utc > previous:
                self._last_attempt_utc[market_id] = attempt_utc
            self._seen_digest_pairs.add(
                (record["decision_snapshot_digest"], record["book_state_digest"])
            )

    def mark_reconciled(self) -> None:
        """The caller confirms post-restart reconciliation completed for this epoch."""
        self._reconciled_this_epoch = True

    def evaluate(
        self,
        market_id: str,
        decision_snapshot_digest: str,
        book_state_digest: str,
        *,
        now_utc: datetime,
        exposure_confirmed_zero: bool,
    ) -> RetryDecision:
        _require_aware(now_utc)
        if not exposure_confirmed_zero:
            return RetryDecision(approved=False, refusal=RetryRefusal.EXPOSURE_NOT_CONFIRMED_ZERO)
        if not self._reconciled_this_epoch:
            return RetryDecision(approved=False, refusal=RetryRefusal.NOT_RECONCILED_SINCE_RESTART)
        if (decision_snapshot_digest, book_state_digest) in self._seen_digest_pairs:
            return RetryDecision(approved=False, refusal=RetryRefusal.DUPLICATE_DECISION_SNAPSHOT)
        if self._attempts_by_market.get(market_id, 0) >= self._budget:
            return RetryDecision(approved=False, refusal=RetryRefusal.ATTEMPT_BUDGET_EXHAUSTED)
        last = self._last_attempt_utc.get(market_id)
        if last is not None:
            if now_utc < last:
                return RetryDecision(approved=False, refusal=RetryRefusal.CLOCK_WENT_BACKWARDS)
            if now_utc - last < self._cooldown:
                return RetryDecision(approved=False, refusal=RetryRefusal.COOLDOWN_NOT_ELAPSED)
        return RetryDecision(approved=True, refusal=None)

    def record_attempt(
        self,
        market_id: str,
        decision_snapshot_digest: str,
        book_state_digest: str,
        *,
        now_utc: datetime,
    ) -> None:
        """Append the attempt to the immutable log BEFORE acting on it (record-before-
        act). Refused while unreconciled — recording an attempt implies acting on one."""
        _require_aware(now_utc)
        if not self._reconciled_this_epoch:
            raise ValueError(
                "cannot record a retry attempt before post-restart reconciliation is "
                "confirmed (F-13)"
            )
        record = {
            "market_id": market_id,
            "decision_snapshot_digest": decision_snapshot_digest,
            "book_state_digest": book_state_digest,
            "attempt_utc": now_utc.isoformat(),
        }
        self._log.append(
            {"record_type": _ATTEMPT_RECORD_TYPE},
            json.dumps(record, sort_keys=True).encode("utf-8"),
        )
        self._attempts_by_market[market_id] = self._attempts_by_market.get(market_id, 0) + 1
        previous = self._last_attempt_utc.get(market_id)
        if previous is None or now_utc > previous:
            self._last_attempt_utc[market_id] = now_utc
        self._seen_digest_pairs.add((decision_snapshot_digest, book_state_digest))
