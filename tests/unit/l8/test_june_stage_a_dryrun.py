"""Stage 2E §6 — synthetic end-to-end dry-run of the whole Stage-A path.

Proves, on June-SHAPED synthetic fixtures (no real outcome): the one atomic extraction produces
an immutable artifact; that artifact regenerates the M1 scorecard BYTE-IDENTICALLY across
reloads; and the raw lockbox is never reopened to re-score (recovery/scoring read only the
artifact). This is the rehearsal that leaves the real seal unspent.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from l8_evidence.june_m1_harness import FrozenPrediction, m1_scorecard, score_bundle
from l8_evidence.june_stage_a_extraction import (
    MinimalOutcome,
    load_artifact,
    recover_stage_a,
    run_stage_a_extraction,
)
from l8_evidence.lockbox import LockboxDefinition, LockboxRegistry, LockboxState
from l8_evidence.prediction_snapshots import DualClockTimestamp

pytestmark = [pytest.mark.spec("SPEC-092"), pytest.mark.spec("SPEC-097")]

_TS = DualClockTimestamp(wall_utc=datetime(2026, 7, 18, tzinfo=timezone.utc), monotonic_ns=1)
_LB = "lockbox-june-2026-tennis-v1"


def _bundle(n: int) -> list[FrozenPrediction]:
    preds = []
    for i in range(n):
        preds.append(FrozenPrediction(
            market_id=f"1.{1000 + i}", tour="ATP" if i % 2 == 0 else "WTA",
            cohort="STRICT", prior_band="20+", cluster_day=f"2026-06-{(i % 28) + 1:02d}",
            competitor_designated=f"td:lo|{i}", competitor_other=f"td:hi|{i}",
            selection_id_designated=2 * i + 1, selection_id_other=2 * i + 2,
            p_raw_designated=0.60, p_cal_designated=0.55 + (i % 10) * 0.01,
        ))
    return preds


def _registry() -> LockboxRegistry:
    reg = LockboxRegistry()
    reg.define(LockboxDefinition(
        lockbox_id=_LB, period_start=datetime(2026, 6, 1).date(),
        period_end=datetime(2026, 6, 30).date(), defined_at=_TS, defined_by="founder"))
    return reg


def test_end_to_end_dryrun_artifact_regenerates_scorecard_byte_identically(tmp_path) -> None:
    preds = _bundle(40)
    ids = frozenset(p.market_id for p in preds)
    # synthetic winners: designated wins on even index
    winners = {p.market_id: (p.selection_id_designated if i % 2 == 0 else p.selection_id_other)
               for i, p in enumerate(preds)}
    reads = {"n": 0}

    def read_outcomes():
        reads["n"] += 1
        return [MinimalOutcome(mid, sid) for mid, sid in winners.items()]

    art = run_stage_a_extraction(
        registry=_registry(), lockbox_id=_LB, accessor="gate-1", at=_TS,
        bundle_market_ids=ids, bundle_digest="sha256:" + "ab" * 32,
        authorisation_digest="sha256:" + "cd" * 32, read_outcomes=read_outcomes,
        burn_record_path=tmp_path / "burn.json", artifact_path=tmp_path / "artifact.json",
    )
    assert reads["n"] == 1  # exactly one raw read

    def scorecard_from_disk() -> str:
        loaded = load_artifact(tmp_path / "artifact.json")
        by_id = {o.market_id: o for o in loaded.outcomes}
        scored, excl = score_bundle(preds, by_id)
        assert excl == ()  # every market scored
        return json.dumps(m1_scorecard(scored), sort_keys=True)

    first = scorecard_from_disk()
    second = scorecard_from_disk()          # a second "process" reload
    assert first == second                  # byte-identical regeneration
    assert reads["n"] == 1                  # raw NEVER reopened to re-score

    # recovery (simulated restart) returns the same artifact without a raw read
    recovered = recover_stage_a(burn_record_path=tmp_path / "burn.json",
                                artifact_path=tmp_path / "artifact.json")
    assert recovered.content_digest() == art.content_digest()
    assert reads["n"] == 1


def test_dryrun_leaves_a_fresh_seal_unspent(tmp_path) -> None:
    # The rehearsal uses its OWN registry; a separate, untouched registry stays SEALED/uncontaminated.
    reg = _registry()
    preds = _bundle(5)
    ids = frozenset(p.market_id for p in preds)
    run_stage_a_extraction(
        registry=reg, lockbox_id=_LB, accessor="gate-1", at=_TS, bundle_market_ids=ids,
        bundle_digest="sha256:" + "ab" * 32, authorisation_digest="sha256:" + "cd" * 32,
        read_outcomes=lambda: [MinimalOutcome(p.market_id, p.selection_id_designated) for p in preds],
        burn_record_path=tmp_path / "b.json", artifact_path=tmp_path / "a.json")
    assert reg.state(_LB) is LockboxState.BURNED
    fresh = _registry()
    assert fresh.is_uncontaminated(_LB) is True   # a different registry instance is untouched
