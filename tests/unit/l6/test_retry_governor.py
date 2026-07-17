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


class TestMutationHardening:
    """Additive pins killing surviving comparison/guard mutants from the F-13 cosmic-ray
    run (report: 33 retry.py survivors). Each test names the mutant class it kills."""

    def test_well_after_cooldown_is_approved(self, tmp_path: Path) -> None:
        # Kills Lt_NotEq on the cooldown comparison: much later than cooldown, fresh
        # digests, budget remaining -> APPROVED (under `!=` this would refuse).
        governor = _ready(_governor(tmp_path))
        governor.record_attempt("1.777", "dec-a", "book-a", now_utc=_T0)
        much_later = _T0 + timedelta(seconds=_COOLDOWN_S * 7)
        decision = governor.evaluate(
            "1.777", "dec-b", "book-b", now_utc=much_later, exposure_confirmed_zero=True
        )
        assert decision.approved

    def test_same_instant_retry_refuses_as_cooldown_not_clock(self, tmp_path: Path) -> None:
        # Kills Lt_LtE on the backwards-clock guard: now == last is NOT a backwards
        # clock; it is an unexpired cooldown, and the reason must say so.
        governor = _ready(_governor(tmp_path))
        governor.record_attempt("1.777", "dec-a", "book-a", now_utc=_T0)
        decision = governor.evaluate(
            "1.777", "dec-b", "book-b", now_utc=_T0, exposure_confirmed_zero=True
        )
        assert decision.refusal is RetryRefusal.COOLDOWN_NOT_ELAPSED

    @pytest.mark.parametrize("bad", [-1, -300])
    def test_negative_governed_constants_refused(self, tmp_path: Path, bad: int) -> None:
        # Kills LtE_Eq / NumberReplacer on the constructor guards: negative values are
        # refused, not only zero.
        with pytest.raises(ValueError):
            RetryGovernor(
                log=AppendOnlyLog(tmp_path / "n1.l0"), cooldown_seconds=bad, attempt_budget=1
            )
        with pytest.raises(ValueError):
            RetryGovernor(
                log=AppendOnlyLog(tmp_path / "n2.l0"), cooldown_seconds=1, attempt_budget=bad
            )

    def test_attempts_beyond_budget_still_refuse(self, tmp_path: Path) -> None:
        # Kills GtE_Eq / NumberReplacer on the budget comparison: record_attempt does
        # not itself enforce the budget, so the count can EXCEED it — evaluation must
        # refuse at count > budget, not only at count == budget.
        governor = _ready(_governor(tmp_path))
        governor.record_attempt("1.777", "dec-a", "book-a", now_utc=_T0)
        governor.record_attempt(
            "1.777", "dec-b", "book-b", now_utc=_T0 + timedelta(seconds=_COOLDOWN_S)
        )
        governor.record_attempt(
            "1.777", "dec-c", "book-c", now_utc=_T0 + timedelta(seconds=_COOLDOWN_S * 2)
        )
        decision = governor.evaluate(
            "1.777",
            "dec-d",
            "book-d",
            now_utc=_T0 + timedelta(seconds=_COOLDOWN_S * 3),
            exposure_confirmed_zero=True,
        )
        assert decision.refusal is RetryRefusal.ATTEMPT_BUDGET_EXHAUSTED

    def test_rebuild_takes_the_latest_attempt_time_from_an_out_of_order_log(
        self, tmp_path: Path
    ) -> None:
        # Kills the Gt_* family on the rebuild max-time logic: an out-of-order log
        # (later attempt recorded first) must still yield the LATEST time as the
        # cooldown anchor.
        # budget 3 so the cooldown branch (not the budget guard) decides.
        first = RetryGovernor(
            log=AppendOnlyLog(tmp_path / "ooo.l0"), cooldown_seconds=_COOLDOWN_S, attempt_budget=3
        )
        first.mark_reconciled()
        late = _T0 + timedelta(seconds=_COOLDOWN_S * 2)
        first.record_attempt("1.777", "dec-a", "book-a", now_utc=late)
        first.record_attempt("1.777", "dec-b", "book-b", now_utc=_T0)  # earlier, second
        rebuilt = RetryGovernor(
            log=AppendOnlyLog(tmp_path / "ooo.l0"), cooldown_seconds=_COOLDOWN_S, attempt_budget=3
        )
        rebuilt.mark_reconciled()
        inside_late_window = late + timedelta(seconds=_COOLDOWN_S - 1)
        decision = rebuilt.evaluate(
            "1.777", "dec-c", "book-c", now_utc=inside_late_window, exposure_confirmed_zero=True
        )
        # Anchored on the LATE attempt this is inside the cooldown window; anchored on
        # the earlier attempt (the mutant) the cooldown would long since have elapsed.
        assert decision.refusal is RetryRefusal.COOLDOWN_NOT_ELAPSED

    def test_in_process_earlier_record_does_not_regress_the_anchor(
        self, tmp_path: Path
    ) -> None:
        # Kills the Gt_* family on the in-process last-attempt update (line 178
        # region): recording an earlier-stamped attempt after a later one must not
        # move the cooldown anchor backwards.
        governor = RetryGovernor(
            log=AppendOnlyLog(tmp_path / "anchor.l0"), cooldown_seconds=_COOLDOWN_S, attempt_budget=3
        )
        governor.mark_reconciled()
        late = _T0 + timedelta(seconds=_COOLDOWN_S * 2)
        governor.record_attempt("1.777", "dec-a", "book-a", now_utc=late)
        governor.record_attempt("1.777", "dec-b", "book-b", now_utc=_T0)
        decision = governor.evaluate(
            "1.777",
            "dec-c",
            "book-c",
            now_utc=late + timedelta(seconds=_COOLDOWN_S - 1),
            exposure_confirmed_zero=True,
        )
        assert decision.refusal is RetryRefusal.COOLDOWN_NOT_ELAPSED

    def test_foreign_record_types_in_the_log_are_skipped_not_fatal(
        self, tmp_path: Path
    ) -> None:
        # Kills NotEq_Is on the record-type filter and ContinueWithBreak on the scan
        # loop: a foreign record BEFORE the attempts must neither crash the rebuild nor
        # truncate it.
        log = AppendOnlyLog(tmp_path / "mixed.l0")
        log.append({"record_type": "unrelated"}, b'{"not": "an attempt"}')
        first = RetryGovernor(log=log, cooldown_seconds=_COOLDOWN_S, attempt_budget=_BUDGET)
        first.mark_reconciled()
        first.record_attempt("1.777", "dec-a", "book-a", now_utc=_T0)
        rebuilt = RetryGovernor(
            log=AppendOnlyLog(tmp_path / "mixed.l0"),
            cooldown_seconds=_COOLDOWN_S,
            attempt_budget=_BUDGET,
        )
        rebuilt.mark_reconciled()
        decision = rebuilt.evaluate(
            "1.777", "dec-a", "book-a", now_utc=_T0 + timedelta(hours=1), exposure_confirmed_zero=True
        )
        assert decision.refusal is RetryRefusal.DUPLICATE_DECISION_SNAPSHOT

    def test_retry_decision_is_frozen(self, tmp_path: Path) -> None:
        # Kills ReplaceTrueWithFalse on the dataclass frozen flag.
        governor = _ready(_governor(tmp_path))
        decision = governor.evaluate(
            "1.777", "dec-a", "book-a", now_utc=_T0, exposure_confirmed_zero=True
        )
        with pytest.raises((AttributeError, TypeError)):
            decision.approved = False  # type: ignore[misc]


class TestMutationHardeningRoundTwo:
    """Round-two kills. The mutation suite runs tests/unit/l6 + tests/properties/l6
    only, so every pin lives here."""

    def test_foreign_record_type_smaller_than_attempt_is_also_skipped(
        self, tmp_path: Path
    ) -> None:
        # Kills NotEq_Gt on the record-type filter: under `>` a type lexicographically
        # SMALLER than "retry_attempt" would be processed as an attempt and crash.
        log = AppendOnlyLog(tmp_path / "mixed2.l0")
        log.append({"record_type": "aaa_marker"}, b'{"not": "an attempt"}')
        governor = RetryGovernor(log=log, cooldown_seconds=_COOLDOWN_S, attempt_budget=_BUDGET)
        governor.mark_reconciled()
        decision = governor.evaluate(
            "1.777", "dec-a", "book-a", now_utc=_T0, exposure_confirmed_zero=True
        )
        assert decision.approved  # the foreign record neither crashed nor counted

    def test_in_order_attempts_advance_the_anchor(self, tmp_path: Path) -> None:
        # Kills Gt_Eq / Gt_Is on the in-process anchor update: after an EARLIER then a
        # LATER attempt, the cooldown must anchor on the later one.
        governor = RetryGovernor(
            log=AppendOnlyLog(tmp_path / "adv.l0"), cooldown_seconds=_COOLDOWN_S, attempt_budget=3
        )
        governor.mark_reconciled()
        late = _T0 + timedelta(seconds=_COOLDOWN_S * 2)
        governor.record_attempt("1.777", "dec-a", "book-a", now_utc=_T0)
        governor.record_attempt("1.777", "dec-b", "book-b", now_utc=late)
        decision = governor.evaluate(
            "1.777",
            "dec-c",
            "book-c",
            now_utc=late + timedelta(seconds=_COOLDOWN_S - 1),
            exposure_confirmed_zero=True,
        )
        assert decision.refusal is RetryRefusal.COOLDOWN_NOT_ELAPSED

    def test_in_order_attempts_advance_the_anchor_across_restart(
        self, tmp_path: Path
    ) -> None:
        # Kills Gt_Eq / Gt_Is on the REBUILD anchor logic for in-order logs.
        first = RetryGovernor(
            log=AppendOnlyLog(tmp_path / "adv2.l0"), cooldown_seconds=_COOLDOWN_S, attempt_budget=3
        )
        first.mark_reconciled()
        late = _T0 + timedelta(seconds=_COOLDOWN_S * 2)
        first.record_attempt("1.777", "dec-a", "book-a", now_utc=_T0)
        first.record_attempt("1.777", "dec-b", "book-b", now_utc=late)
        rebuilt = RetryGovernor(
            log=AppendOnlyLog(tmp_path / "adv2.l0"), cooldown_seconds=_COOLDOWN_S, attempt_budget=3
        )
        rebuilt.mark_reconciled()
        decision = rebuilt.evaluate(
            "1.777",
            "dec-c",
            "book-c",
            now_utc=late + timedelta(seconds=_COOLDOWN_S - 1),
            exposure_confirmed_zero=True,
        )
        assert decision.refusal is RetryRefusal.COOLDOWN_NOT_ELAPSED

    def test_minimal_governed_constants_are_accepted(self, tmp_path: Path) -> None:
        # Kills NumberReplacer (0 -> 1) on the constructor guards: the smallest
        # legitimate governed values construct successfully.
        governor = RetryGovernor(
            log=AppendOnlyLog(tmp_path / "min.l0"), cooldown_seconds=1, attempt_budget=1
        )
        governor.mark_reconciled()

    def test_fresh_market_with_budget_one_is_approved(self, tmp_path: Path) -> None:
        # Kills NumberReplacer (0 -> 1) on the budget lookup default: a market with no
        # recorded attempts has count zero, not one.
        governor = RetryGovernor(
            log=AppendOnlyLog(tmp_path / "fresh.l0"), cooldown_seconds=1, attempt_budget=1
        )
        governor.mark_reconciled()
        decision = governor.evaluate(
            "1.999", "dec-a", "book-a", now_utc=_T0, exposure_confirmed_zero=True
        )
        assert decision.approved
