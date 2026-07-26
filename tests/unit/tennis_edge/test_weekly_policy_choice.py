"""Tests for selecting which frozen policy the weekly job runs.

Two vintages now exist. The failure this guards against is not a crash — it is a ledger in
which v1 and v2 rows are mixed under a path that claims to be one record, or a v2 row
labelled with v1's digest. Either would destroy the only thing the ledger is for: being able
to say which rule produced which decision.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from tennis_edge.policy import POLICY_VERSION as V1_VERSION
from tennis_edge.policy_v2 import POLICY_VERSION as V2_VERSION
from tennis_edge.weekly import DEFAULT_LEDGERS, is_in_sample, resolve_ledger_path


class TestLedgerSeparation:
    def test_each_policy_has_its_own_default_ledger(self) -> None:
        assert DEFAULT_LEDGERS[V1_VERSION] != DEFAULT_LEDGERS[V2_VERSION]

    def test_both_policies_are_registered(self) -> None:
        assert set(DEFAULT_LEDGERS) == {V1_VERSION, V2_VERSION}

    def test_the_default_path_names_the_policy(self) -> None:
        """A path that does not say which rule wrote it invites the two being merged."""
        assert "v2" in DEFAULT_LEDGERS[V2_VERSION]

    def test_an_explicit_path_is_honoured(self) -> None:
        chosen = resolve_ledger_path(V2_VERSION, "/tmp/somewhere/else.jsonl")
        assert chosen == Path("/tmp/somewhere/else.jsonl")

    def test_no_explicit_path_uses_the_policy_default(self) -> None:
        assert resolve_ledger_path(V2_VERSION, None) == Path(DEFAULT_LEDGERS[V2_VERSION])

    def test_an_unknown_policy_is_refused(self) -> None:
        with pytest.raises(ValueError, match="unknown policy"):
            resolve_ledger_path("frozen-policy-v99", None)


class TestInSampleRefusal:
    """v2 must not score a match its frozen model was trained on.

    The v1 policy has no model to be trained on, so its ledger can be backfilled over
    history and remain meaningful. v2's model was fitted through a date, and every match at
    or before that date is *in-sample* — scoring it would put a number in the ledger that
    looks prospective and is not. The ledger's whole value is that a row means what it
    appears to mean.
    """

    def test_a_match_on_the_training_boundary_is_in_sample(self) -> None:
        assert is_in_sample(dt.date(2026, 7, 12), trained_through=dt.date(2026, 7, 12))

    def test_a_match_before_the_boundary_is_in_sample(self) -> None:
        assert is_in_sample(dt.date(2020, 1, 1), trained_through=dt.date(2026, 7, 12))

    def test_a_match_after_the_boundary_is_not(self) -> None:
        assert not is_in_sample(dt.date(2026, 7, 13),
                                trained_through=dt.date(2026, 7, 12))

    def test_no_model_means_nothing_is_in_sample(self) -> None:
        """v1 has no training boundary, so its backfill stays legitimate."""
        assert not is_in_sample(dt.date(1999, 1, 1), trained_through=None)
