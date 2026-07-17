"""F-13 (founder ruling, 2026-07-17): governed retry after a released reservation.

Retry requires ALL of: (1) confirmed zero exposure; (2) governed cooldown elapsed;
(3) attempt budget remains; (4) materially changed market/decision state. The identical
decision snapshot + book-state digest pair must NEVER trigger twice — globally, ever.
Time passage alone is not material change. Budgets persist across process restarts via
the immutable append-only attempt log (never a prior process's monotonic clock), and
after a restart the governor refuses everything until reconciliation is confirmed.
Every refusal is a typed reason, never a bare False.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from l0_raw.store import AppendOnlyLog
from l6_broker.retry import RetryGovernor, RetryRefusal

pytestmark = [pytest.mark.spec("SPEC-054"), pytest.mark.spec("SPEC-071")]

_T0 = datetime(2026, 7, 17, 12, 0, 0, tzinfo=timezone.utc)
_COOLDOWN_S = 300
_BUDGET = 2


def _governor(tmp_path: Path, name: str = "retry.l0") -> RetryGovernor:
    return RetryGovernor(
        log=AppendOnlyLog(tmp_path / name),
        cooldown_seconds=_COOLDOWN_S,
        attempt_budget=_BUDGET,
    )


def _ready(governor: RetryGovernor) -> RetryGovernor:
    governor.mark_reconciled()
    return governor


class TestAllFourConditionsRequired:
    def test_approval_requires_every_condition(self, tmp_path: Path) -> None:
        governor = _ready(_governor(tmp_path))
        decision = governor.evaluate(
            "1.777", "dec-a", "book-a", now_utc=_T0, exposure_confirmed_zero=True
        )
        assert decision.approved and decision.refusal is None

    def test_unconfirmed_exposure_refuses_regardless_of_everything_else(
        self, tmp_path: Path
    ) -> None:
        # Guard dominance: exposure not confirmed zero -> REFUSE, whatever else holds.
        governor = _ready(_governor(tmp_path))
        decision = governor.evaluate(
            "1.777", "dec-a", "book-a", now_utc=_T0, exposure_confirmed_zero=False
        )
        assert not decision.approved
        assert decision.refusal is RetryRefusal.EXPOSURE_NOT_CONFIRMED_ZERO

    def test_identical_digest_pair_never_triggers_twice(self, tmp_path: Path) -> None:
        governor = _ready(_governor(tmp_path))
        governor.record_attempt("1.777", "dec-a", "book-a", now_utc=_T0)
        later = _T0 + timedelta(seconds=_COOLDOWN_S * 10)
        decision = governor.evaluate(
            "1.777", "dec-a", "book-a", now_utc=later, exposure_confirmed_zero=True
        )
        assert not decision.approved
        assert decision.refusal is RetryRefusal.DUPLICATE_DECISION_SNAPSHOT

    def test_time_passage_alone_is_not_material_change(self, tmp_path: Path) -> None:
        # Same digests, arbitrarily later: still the duplicate refusal — the clock is
        # not an input to material change.
        governor = _ready(_governor(tmp_path))
        governor.record_attempt("1.777", "dec-a", "book-a", now_utc=_T0)
        much_later = _T0 + timedelta(days=30)
        decision = governor.evaluate(
            "1.777", "dec-a", "book-a", now_utc=much_later, exposure_confirmed_zero=True
        )
        assert decision.refusal is RetryRefusal.DUPLICATE_DECISION_SNAPSHOT

    def test_cooldown_not_elapsed_refuses_even_with_changed_state(
        self, tmp_path: Path
    ) -> None:
        governor = _ready(_governor(tmp_path))
        governor.record_attempt("1.777", "dec-a", "book-a", now_utc=_T0)
        soon = _T0 + timedelta(seconds=_COOLDOWN_S - 1)
        decision = governor.evaluate(
            "1.777", "dec-b", "book-b", now_utc=soon, exposure_confirmed_zero=True
        )
        assert decision.refusal is RetryRefusal.COOLDOWN_NOT_ELAPSED

    def test_changed_state_after_cooldown_is_approved_then_budget_exhausts(
        self, tmp_path: Path
    ) -> None:
        governor = _ready(_governor(tmp_path))
        governor.record_attempt("1.777", "dec-a", "book-a", now_utc=_T0)
        t1 = _T0 + timedelta(seconds=_COOLDOWN_S)
        second = governor.evaluate(
            "1.777", "dec-b", "book-b", now_utc=t1, exposure_confirmed_zero=True
        )
        assert second.approved
        governor.record_attempt("1.777", "dec-b", "book-b", now_utc=t1)
        t2 = t1 + timedelta(seconds=_COOLDOWN_S)
        third = governor.evaluate(
            "1.777", "dec-c", "book-c", now_utc=t2, exposure_confirmed_zero=True
        )
        assert not third.approved
        assert third.refusal is RetryRefusal.ATTEMPT_BUDGET_EXHAUSTED

    def test_budget_is_per_market(self, tmp_path: Path) -> None:
        governor = _ready(_governor(tmp_path))
        governor.record_attempt("1.777", "dec-a", "book-a", now_utc=_T0)
        governor.record_attempt(
            "1.777", "dec-b", "book-b", now_utc=_T0 + timedelta(seconds=_COOLDOWN_S)
        )
        other_market = governor.evaluate(
            "1.888", "dec-a", "book-x", now_utc=_T0, exposure_confirmed_zero=True
        )
        assert other_market.approved

    def test_wall_clock_going_backwards_fails_closed(self, tmp_path: Path) -> None:
        governor = _ready(_governor(tmp_path))
        governor.record_attempt("1.777", "dec-a", "book-a", now_utc=_T0)
        earlier = _T0 - timedelta(seconds=1)
        decision = governor.evaluate(
            "1.777", "dec-b", "book-b", now_utc=earlier, exposure_confirmed_zero=True
        )
        assert not decision.approved
        assert decision.refusal is RetryRefusal.CLOCK_WENT_BACKWARDS


class TestRestartSemantics:
    def test_budget_and_digests_persist_across_restart(self, tmp_path: Path) -> None:
        first = _ready(_governor(tmp_path))
        first.record_attempt("1.777", "dec-a", "book-a", now_utc=_T0)
        first.record_attempt(
            "1.777", "dec-b", "book-b", now_utc=_T0 + timedelta(seconds=_COOLDOWN_S)
        )
        # New process: same log file, fresh governor.
        second = _ready(_governor(tmp_path))
        much_later = _T0 + timedelta(seconds=_COOLDOWN_S * 10)
        duplicate = second.evaluate(
            "1.777", "dec-a", "book-a", now_utc=much_later, exposure_confirmed_zero=True
        )
        assert duplicate.refusal is RetryRefusal.DUPLICATE_DECISION_SNAPSHOT
        exhausted = second.evaluate(
            "1.777", "dec-c", "book-c", now_utc=much_later, exposure_confirmed_zero=True
        )
        assert exhausted.refusal is RetryRefusal.ATTEMPT_BUDGET_EXHAUSTED

    def test_cooldown_across_restart_uses_wall_clock_from_the_log(
        self, tmp_path: Path
    ) -> None:
        # Never a prior process's monotonic clock: the persisted wall-clock attempt time
        # governs the cooldown in the next process.
        first = _ready(_governor(tmp_path))
        first.record_attempt("1.777", "dec-a", "book-a", now_utc=_T0)
        second = _ready(_governor(tmp_path))
        soon = _T0 + timedelta(seconds=_COOLDOWN_S - 1)
        decision = second.evaluate(
            "1.777", "dec-b", "book-b", now_utc=soon, exposure_confirmed_zero=True
        )
        assert decision.refusal is RetryRefusal.COOLDOWN_NOT_ELAPSED

    def test_restart_requires_reconciliation_before_any_retry(self, tmp_path: Path) -> None:
        governor = _governor(tmp_path)  # NOT reconciled
        decision = governor.evaluate(
            "1.777", "dec-a", "book-a", now_utc=_T0, exposure_confirmed_zero=True
        )
        assert not decision.approved
        assert decision.refusal is RetryRefusal.NOT_RECONCILED_SINCE_RESTART
        governor.mark_reconciled()
        assert governor.evaluate(
            "1.777", "dec-a", "book-a", now_utc=_T0, exposure_confirmed_zero=True
        ).approved


class TestGovernedConstants:
    def test_cooldown_and_budget_are_mandatory_and_positive(self, tmp_path: Path) -> None:
        # Governed constants are supplied per pre-registered policy — no defaults, and
        # non-positive values are refused (a zero budget governor is a contradiction;
        # refusing retries entirely is done by not constructing a governor).
        with pytest.raises(TypeError):
            RetryGovernor(log=AppendOnlyLog(tmp_path / "a.l0"))  # type: ignore[call-arg]
        with pytest.raises(ValueError):
            RetryGovernor(
                log=AppendOnlyLog(tmp_path / "b.l0"), cooldown_seconds=0, attempt_budget=1
            )
        with pytest.raises(ValueError):
            RetryGovernor(
                log=AppendOnlyLog(tmp_path / "c.l0"), cooldown_seconds=1, attempt_budget=0
            )

    def test_record_attempt_refuses_unreconciled_and_naive_time(self, tmp_path: Path) -> None:
        governor = _governor(tmp_path)
        with pytest.raises(ValueError):
            governor.record_attempt("1.777", "dec-a", "book-a", now_utc=_T0)
        governor.mark_reconciled()
        with pytest.raises(ValueError):
            governor.record_attempt(
                "1.777", "dec-a", "book-a", now_utc=datetime(2026, 7, 17, 12, 0, 0)
            )
