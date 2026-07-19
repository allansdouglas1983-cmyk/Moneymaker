"""Founder-authorised governed June Stage-A RECOVERY (Option B, 2026-07-19) — tests-first.

The recovery is a separately governed, SINGLE-USE access: it never rewrites the original burn
record, never reuses the spent token, and corrects the driver defect — a legitimate per-market
undetermined settlement becomes an EXPLICIT exclusion in the denominator, never a batch abort,
while malformed/integrity-invalid input still stops the batch with a typed error. ALL fixtures
are SYNTHETIC; no real June outcome is read here.
"""
from __future__ import annotations

import bz2
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from l8_evidence.june_m1_harness import FrozenPrediction, score_bundle
from l8_evidence.june_stage_a_recovery import (
    RecoveryExclusion,
    RecoveryIncidentError,
    RecoveryIntegrityError,
    RecoveryOutcomeArtifact,
    RecoverySingleUseError,
    load_recovery_artifact,
    resume_stage_a_recovery,
    run_stage_a_recovery,
)
from l8_evidence.prediction_snapshots import DualClockTimestamp

pytestmark = [pytest.mark.spec("SPEC-092")]

_AT = DualClockTimestamp(wall_utc=datetime(2026, 7, 19, 18, 0, tzinfo=timezone.utc), monotonic_ns=1)
_SHA = "sha256:" + "ab" * 32
_JUNE_TIME = "2026-06-15T10:00:00.000Z"


def _sha256_file(p: Path) -> str:
    return "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()


def _line(market_id: str, status: str, runners: list[dict[str, object]], *,
          settled: str | None = None, market_time: str = _JUNE_TIME) -> str:
    md: dict[str, object] = {"status": status, "marketTime": market_time,
                             "runners": runners, "marketType": "MATCH_ODDS"}
    if settled is not None:
        md["settledTime"] = settled
    return json.dumps({"op": "mcm", "pt": 1, "mc": [{"id": market_id, "marketDefinition": md}]})


def _settled(mid: str, winner: int, loser: int) -> list[str]:
    return [
        _line(mid, "OPEN", [{"id": winner, "status": "ACTIVE"}, {"id": loser, "status": "ACTIVE"}]),
        _line(mid, "CLOSED", [{"id": winner, "status": "WINNER"}, {"id": loser, "status": "LOSER"}],
              settled="2026-06-15T12:00:00.000Z"),
    ]


def _void_removed(mid: str, a: int, b: int) -> list[str]:
    return [
        _line(mid, "OPEN", [{"id": a, "status": "ACTIVE"}, {"id": b, "status": "ACTIVE"}]),
        _line(mid, "CLOSED", [{"id": a, "status": "REMOVED"}, {"id": b, "status": "REMOVED"}]),
    ]


def _pred(mid: str, *, sel_des: int = 11, sel_oth: int = 22, tour: str = "ATP") -> FrozenPrediction:
    return FrozenPrediction(
        market_id=mid, tour=tour, cohort="STRICT", prior_band="20+", cluster_day="2026-06-15",
        competitor_designated="td:lo|x", competitor_other="td:hi|y",
        selection_id_designated=sel_des, selection_id_other=sel_oth,
        p_raw_designated=0.60, p_cal_designated=0.62,
    )


def _bundle_line(p: FrozenPrediction) -> str:
    return json.dumps({
        "market_id": p.market_id, "tour": p.tour, "cohort": p.cohort, "prior_band": p.prior_band,
        "cluster_day": p.cluster_day, "competitor_designated": p.competitor_designated,
        "competitor_other": p.competitor_other, "selection_id_designated": p.selection_id_designated,
        "selection_id_other": p.selection_id_other, "p_raw_designated": p.p_raw_designated,
        "p_cal_designated": p.p_cal_designated,
    })


class _Setup:
    """One synthetic recovery world: corpus + manifest + bundle + incident records + paths."""

    def __init__(self, tmp_path: Path, markets: dict[str, list[str]],
                 preds: list[FrozenPrediction]) -> None:
        self.root = tmp_path
        self.corpus_root = tmp_path / "corpus"
        self.streams_root = self.corpus_root / "extracted"
        self.streams_root.mkdir(parents=True)
        for mid, lines in markets.items():
            with bz2.open(self.streams_root / f"{mid}.bz2", "wt", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
        entries = []
        for f in sorted(self.streams_root.rglob("*.bz2")):
            entries.append(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.relative_to(self.corpus_root)}")
        self.manifest_path = self.corpus_root / "SHA256SUMS.txt"
        self.manifest_path.write_text("\n".join(entries) + "\n", encoding="utf-8")
        self.manifest_sha256 = _sha256_file(self.manifest_path)
        self.bundle_path = tmp_path / "bundle.jsonl"
        self.bundle_path.write_text("\n".join(_bundle_line(p) for p in preds) + "\n", encoding="utf-8")
        self.bundle_sha256 = _sha256_file(self.bundle_path)
        self.m1_manifest_path = tmp_path / "m1_manifest.jsonl"
        self.m1_manifest_path.write_text('{"m1": "manifest"}\n', encoding="utf-8")
        self.m1_manifest_sha256 = _sha256_file(self.m1_manifest_path)
        self.burn_record_path = tmp_path / "BURN_RECORD.json"
        self.burn_record_path.write_text('{"state":"OPENED_EXTRACTION_IN_PROGRESS"}', encoding="utf-8")
        self.burn_record_sha256 = _sha256_file(self.burn_record_path)
        self.incident_path = tmp_path / "INCIDENT.md"
        self.incident_path.write_text("# incident\n", encoding="utf-8")
        self.incident_sha256 = _sha256_file(self.incident_path)
        self.authorisation_path = tmp_path / "recovery-authorisation.yaml"
        self.authorisation_path.write_text("recovery_authorisation:\n  id: june-stage-a-recovery-v1\n",
                                           encoding="utf-8")
        self.authorisation_sha256 = _sha256_file(self.authorisation_path)
        self.in_progress_path = tmp_path / "RECOVERY_ACCESS_RECORD.json"
        self.artifact_path = tmp_path / "RECOVERY_OUTCOME_ARTIFACT.json"
        self.completed_path = tmp_path / "RECOVERY_COMPLETED.json"
        self.sealed = frozenset(markets.keys()) | {p.market_id for p in preds}

    def kwargs(self, **overrides: Any) -> dict[str, Any]:
        kw: dict[str, Any] = dict(
            bundle_path=self.bundle_path, bundle_sha256=self.bundle_sha256,
            corpus_root=self.corpus_root, corpus_manifest_path=self.manifest_path,
            corpus_manifest_sha256=self.manifest_sha256, streams_root=self.streams_root,
            m1_manifest_path=self.m1_manifest_path, m1_manifest_sha256=self.m1_manifest_sha256,
            original_burn_record_path=self.burn_record_path,
            original_burn_record_sha256=self.burn_record_sha256,
            incident_record_path=self.incident_path, incident_record_sha256=self.incident_sha256,
            recovery_authorisation_path=self.authorisation_path,
            sealed_market_ids=self.sealed,
            model_manifest_sha256=_SHA, feature_manifest_sha256=_SHA, data_manifest_sha256=_SHA,
            granted_on=date(2026, 7, 19), at=_AT,
            in_progress_path=self.in_progress_path, artifact_path=self.artifact_path,
            completed_path=self.completed_path,
        )
        kw.update(overrides)
        return kw


def _incident_shaped(tmp_path: Path) -> _Setup:
    """settled -> settled -> BOTH RUNNERS REMOVED -> settled (the exact incident shape)."""
    markets = {
        "1.10": _settled("1.10", 11, 22),
        "1.11": _settled("1.11", 22, 11),
        "1.12": _void_removed("1.12", 11, 22),
        "1.13": _settled("1.13", 11, 22),
    }
    preds = [_pred(m) for m in markets]
    return _Setup(tmp_path, markets, preds)


class TestRecoveryHappyPathAndExclusions:
    def test_incident_shaped_batch_completes_with_one_explicit_exclusion(self, tmp_path: Path) -> None:
        s = _incident_shaped(tmp_path)
        art = run_stage_a_recovery(**s.kwargs())
        assert {o.market_id for o in art.outcomes} == {"1.10", "1.11", "1.13"}
        assert [e.market_id for e in art.exclusions] == ["1.12"]
        assert art.exclusions[0].reason == "UNDETERMINED_SETTLEMENT:BOTH_RUNNERS_REMOVED"
        assert art.exclusions[0].source == "1.12.bz2"
        assert "winner" not in art.exclusions[0].settlement_summary.lower()  # no fabricated winner
        assert load_recovery_artifact(s.artifact_path).content_digest() == art.content_digest()
        assert s.completed_path.exists() and s.in_progress_path.exists()

    def test_winners_are_the_governed_extractor_values(self, tmp_path: Path) -> None:
        s = _incident_shaped(tmp_path)
        art = run_stage_a_recovery(**s.kwargs())
        by_id = {o.market_id: o.winner_selection_id for o in art.outcomes}
        assert by_id == {"1.10": 11, "1.11": 22, "1.13": 11}

    def test_void_first_in_batch(self, tmp_path: Path) -> None:
        markets = {"1.10": _void_removed("1.10", 1, 2), "1.11": _settled("1.11", 11, 22)}
        s = _Setup(tmp_path, markets, [_pred(m) for m in markets])
        art = run_stage_a_recovery(**s.kwargs())
        assert [e.market_id for e in art.exclusions] == ["1.10"]
        assert {o.market_id for o in art.outcomes} == {"1.11"}

    def test_void_last_in_batch(self, tmp_path: Path) -> None:
        markets = {"1.10": _settled("1.10", 11, 22), "1.99": _void_removed("1.99", 1, 2)}
        s = _Setup(tmp_path, markets, [_pred(m) for m in markets])
        art = run_stage_a_recovery(**s.kwargs())
        assert [e.market_id for e in art.exclusions] == ["1.99"]

    def test_several_void_markets(self, tmp_path: Path) -> None:
        markets = {
            "1.10": _void_removed("1.10", 1, 2), "1.11": _settled("1.11", 11, 22),
            "1.12": _void_removed("1.12", 3, 4), "1.13": _settled("1.13", 22, 11),
            "1.14": _void_removed("1.14", 5, 6),
        }
        s = _Setup(tmp_path, markets, [_pred(m) for m in markets])
        art = run_stage_a_recovery(**s.kwargs())
        assert [e.market_id for e in art.exclusions] == ["1.10", "1.12", "1.14"]
        assert all(e.reason == "UNDETERMINED_SETTLEMENT:BOTH_RUNNERS_REMOVED" for e in art.exclusions)
        assert {o.market_id for o in art.outcomes} == {"1.11", "1.13"}

    def test_all_markets_void(self, tmp_path: Path) -> None:
        markets = {"1.10": _void_removed("1.10", 1, 2), "1.11": _void_removed("1.11", 3, 4)}
        s = _Setup(tmp_path, markets, [_pred(m) for m in markets])
        art = run_stage_a_recovery(**s.kwargs())
        assert art.outcomes == ()
        assert len(art.exclusions) == 2

    def test_closed_no_winner_is_explicit_exclusion(self, tmp_path: Path) -> None:
        markets = {"1.10": [
            _line("1.10", "CLOSED", [{"id": 1, "status": "LOSER"}, {"id": 2, "status": "LOSER"}]),
        ], "1.11": _settled("1.11", 11, 22)}
        s = _Setup(tmp_path, markets, [_pred(m) for m in markets])
        art = run_stage_a_recovery(**s.kwargs())
        assert art.exclusions[0].reason == "UNDETERMINED_SETTLEMENT:NO_WINNER"

    def test_multiple_winners_is_explicit_exclusion(self, tmp_path: Path) -> None:
        markets = {"1.10": [
            _line("1.10", "CLOSED", [{"id": 1, "status": "WINNER"}, {"id": 2, "status": "WINNER"}]),
        ], "1.11": _settled("1.11", 11, 22)}
        s = _Setup(tmp_path, markets, [_pred(m) for m in markets])
        art = run_stage_a_recovery(**s.kwargs())
        assert art.exclusions[0].reason == "UNDETERMINED_SETTLEMENT:MULTIPLE_WINNERS"

    def test_no_closed_definition_is_explicit_exclusion(self, tmp_path: Path) -> None:
        markets = {"1.10": [
            _line("1.10", "OPEN", [{"id": 1, "status": "ACTIVE"}, {"id": 2, "status": "ACTIVE"}]),
        ], "1.11": _settled("1.11", 11, 22)}
        s = _Setup(tmp_path, markets, [_pred(m) for m in markets])
        art = run_stage_a_recovery(**s.kwargs())
        assert art.exclusions[0].reason == "UNDETERMINED_SETTLEMENT:NO_CLOSED_DEFINITION"


class TestDenominatorAndDeterminism:
    def test_outcomes_plus_exclusions_partition_the_bundle_exactly(self, tmp_path: Path) -> None:
        s = _incident_shaped(tmp_path)
        art = run_stage_a_recovery(**s.kwargs())
        out_ids = {o.market_id for o in art.outcomes}
        exc_ids = {e.market_id for e in art.exclusions}
        assert out_ids | exc_ids == {"1.10", "1.11", "1.12", "1.13"}
        assert out_ids & exc_ids == set()
        assert len(art.outcomes) + len(art.exclusions) == 4   # nothing silently dropped

    def test_exclusion_visible_in_downstream_scoring_denominator(self, tmp_path: Path) -> None:
        # the void market is NEVER a normal loss: it has no scored row, and it appears as an
        # explicit exclusion when the bundle is joined against the artifact outcomes.
        s = _incident_shaped(tmp_path)
        art = run_stage_a_recovery(**s.kwargs())
        preds = [_pred(m) for m in ("1.10", "1.11", "1.12", "1.13")]
        scored, excl = score_bundle(preds, {o.market_id: o for o in art.outcomes})
        assert {r.market_id for r in scored} == {"1.10", "1.11", "1.13"}
        assert dict(excl) == {"1.12": "NO_OUTCOME_IN_ARTIFACT"}
        assert all(r.market_id != "1.12" for r in scored)

    def test_unknown_winner_selection_id_becomes_unjoinable_exclusion(self, tmp_path: Path) -> None:
        markets = {"1.10": _settled("1.10", 999, 22)}   # winner 999 is neither prediction selection
        s = _Setup(tmp_path, markets, [_pred("1.10")])
        art = run_stage_a_recovery(**s.kwargs())
        scored, excl = score_bundle([_pred("1.10")], {o.market_id: o for o in art.outcomes})
        assert scored == ()
        assert excl[0][0] == "1.10" and excl[0][1].startswith("UNJOINABLE:")

    def test_artifact_bytes_deterministic_and_rerun_identical(self, tmp_path: Path) -> None:
        s1 = _incident_shaped(tmp_path / "a")
        s2 = _incident_shaped(tmp_path / "b")
        run_stage_a_recovery(**s1.kwargs())
        run_stage_a_recovery(**s2.kwargs())
        assert s1.artifact_path.read_bytes() == s2.artifact_path.read_bytes()


class TestIntegrityFailuresStopTheBatch:
    def test_malformed_settlement_mid_batch_stops_with_no_artifact(self, tmp_path: Path) -> None:
        markets = {"1.10": _settled("1.10", 11, 22), "1.11": ["{not valid json"],
                   "1.12": _settled("1.12", 11, 22)}
        s = _Setup(tmp_path, markets, [_pred(m) for m in markets])
        with pytest.raises(RecoveryIntegrityError):
            run_stage_a_recovery(**s.kwargs())
        assert not s.artifact_path.exists()          # no partial artifact
        assert not s.completed_path.exists()         # no partial completion -> no scorecard possible
        assert s.in_progress_path.exists()           # the access is durably marked in progress

    def test_stream_for_a_different_market_is_integrity_failure(self, tmp_path: Path) -> None:
        # the file exists but references ONLY another market: wrong file, not a settlement fact.
        markets = {"1.10": _settled("1.99", 11, 22), "1.11": _settled("1.11", 11, 22)}
        s = _Setup(tmp_path, markets, [_pred(m) for m in markets])
        with pytest.raises(RecoveryIntegrityError):
            run_stage_a_recovery(**s.kwargs())
        assert not s.artifact_path.exists()

    def test_missing_stream_refuses_before_any_durable_state(self, tmp_path: Path) -> None:
        markets = {"1.10": _settled("1.10", 11, 22)}
        preds = [_pred("1.10"), _pred("1.11")]        # 1.11 has no stream file
        s = _Setup(tmp_path, markets, preds)
        with pytest.raises(RecoveryIntegrityError):
            run_stage_a_recovery(**s.kwargs())
        assert not s.in_progress_path.exists()        # the single-use access was NOT consumed

    def test_corpus_manifest_mismatch_refuses_before_any_durable_state(self, tmp_path: Path) -> None:
        s = _incident_shaped(tmp_path)
        victim = next(iter(sorted(s.streams_root.rglob("*.bz2"))))
        victim.write_bytes(b"corrupted")              # content no longer matches the manifest
        with pytest.raises(RecoveryIntegrityError):
            run_stage_a_recovery(**s.kwargs())
        assert not s.in_progress_path.exists()

    def test_duplicate_bundle_market_refuses(self, tmp_path: Path) -> None:
        markets = {"1.10": _settled("1.10", 11, 22)}
        s = _Setup(tmp_path, markets, [_pred("1.10")])
        line = _bundle_line(_pred("1.10"))
        s.bundle_path.write_text(line + "\n" + line + "\n", encoding="utf-8")
        with pytest.raises(RecoveryIntegrityError):
            run_stage_a_recovery(**s.kwargs(bundle_sha256=_sha256_file(s.bundle_path)))
        assert not s.in_progress_path.exists()


class TestSingleUseAndLinkage:
    def test_original_burn_record_is_never_modified(self, tmp_path: Path) -> None:
        s = _incident_shaped(tmp_path)
        before = s.burn_record_path.read_bytes()
        run_stage_a_recovery(**s.kwargs())
        assert s.burn_record_path.read_bytes() == before

    def test_artifact_carries_the_recovery_linkage_digests(self, tmp_path: Path) -> None:
        s = _incident_shaped(tmp_path)
        art = run_stage_a_recovery(**s.kwargs())
        assert art.recovery_authorisation_digest == s.authorisation_sha256
        assert art.original_burn_record_digest == s.burn_record_sha256
        # linkage is digest-bound: a different linkage value yields a different content digest.
        other = RecoveryOutcomeArtifact(
            lockbox_id=art.lockbox_id, bundle_digest=art.bundle_digest,
            recovery_authorisation_digest="sha256:" + "00" * 32,
            original_burn_record_digest=art.original_burn_record_digest,
            grant_at_utc=art.grant_at_utc, outcomes=art.outcomes, exclusions=art.exclusions)
        assert other.content_digest() != art.content_digest()

    def test_tampered_original_burn_record_refuses_before_access(self, tmp_path: Path) -> None:
        s = _incident_shaped(tmp_path)
        s.burn_record_path.write_text("{}", encoding="utf-8")   # digest no longer matches
        with pytest.raises(RecoveryIntegrityError):
            run_stage_a_recovery(**s.kwargs())
        assert not s.in_progress_path.exists()

    def test_tampered_incident_record_refuses_before_access(self, tmp_path: Path) -> None:
        s = _incident_shaped(tmp_path)
        s.incident_path.write_text("# altered\n", encoding="utf-8")
        with pytest.raises(RecoveryIntegrityError):
            run_stage_a_recovery(**s.kwargs())
        assert not s.in_progress_path.exists()

    def test_completed_recovery_refuses_a_second_recovery_access(self, tmp_path: Path) -> None:
        s = _incident_shaped(tmp_path)
        art = run_stage_a_recovery(**s.kwargs())
        with pytest.raises(RecoverySingleUseError):
            run_stage_a_recovery(**s.kwargs())
        # resume stays idempotent and needs NO corpus at all
        again = resume_stage_a_recovery(in_progress_path=s.in_progress_path,
                                        artifact_path=s.artifact_path,
                                        completed_path=s.completed_path)
        assert again.content_digest() == art.content_digest()

    def test_prior_partial_state_refuses_a_fresh_run(self, tmp_path: Path) -> None:
        s = _incident_shaped(tmp_path)
        s.in_progress_path.write_text("{}", encoding="utf-8")
        with pytest.raises(RecoverySingleUseError):
            run_stage_a_recovery(**s.kwargs())


class TestCrashAndRecoveryPolicy:
    def _fault_at(self, step: str) -> Any:
        def fault(s: str) -> None:
            if s == step:
                raise RuntimeError(f"crash:{s}")
        return fault

    def test_crash_before_grant_leaves_nothing_and_fresh_run_is_allowed(self, tmp_path: Path) -> None:
        s = _incident_shaped(tmp_path)
        with pytest.raises(RuntimeError, match="crash:before_in_progress"):
            run_stage_a_recovery(**s.kwargs(_fault=self._fault_at("before_in_progress")))
        assert not s.in_progress_path.exists() and not s.artifact_path.exists()
        with pytest.raises(RecoveryIncidentError):    # resume: nothing durable -> never started
            resume_stage_a_recovery(in_progress_path=s.in_progress_path,
                                    artifact_path=s.artifact_path, completed_path=s.completed_path)
        art = run_stage_a_recovery(**s.kwargs())      # no raw read happened -> fresh run permitted
        assert len(art.outcomes) == 3

    def test_crash_after_grant_before_read_is_an_incident_no_reread(self, tmp_path: Path) -> None:
        s = _incident_shaped(tmp_path)
        with pytest.raises(RuntimeError, match="crash:after_in_progress"):
            run_stage_a_recovery(**s.kwargs(_fault=self._fault_at("after_in_progress")))
        assert s.in_progress_path.exists() and not s.artifact_path.exists()
        with pytest.raises(RecoveryIncidentError):
            resume_stage_a_recovery(in_progress_path=s.in_progress_path,
                                    artifact_path=s.artifact_path, completed_path=s.completed_path)

    def test_crash_during_read_is_an_incident_no_reread(self, tmp_path: Path) -> None:
        s = _incident_shaped(tmp_path)
        with pytest.raises(RuntimeError, match="crash:after_raw_read"):
            run_stage_a_recovery(**s.kwargs(_fault=self._fault_at("after_raw_read")))
        assert s.in_progress_path.exists() and not s.artifact_path.exists()
        with pytest.raises(RecoveryIncidentError):
            resume_stage_a_recovery(in_progress_path=s.in_progress_path,
                                    artifact_path=s.artifact_path, completed_path=s.completed_path)

    def test_crash_after_temp_artifact_finalizes_without_raw_access(self, tmp_path: Path) -> None:
        s = _incident_shaped(tmp_path)
        with pytest.raises(RuntimeError, match="crash:after_temp_artifact"):
            run_stage_a_recovery(**s.kwargs(_fault=self._fault_at("after_temp_artifact")))
        assert not s.artifact_path.exists()
        import shutil
        shutil.rmtree(s.corpus_root)                  # corpus GONE -> resume provably reads no raw
        art = resume_stage_a_recovery(in_progress_path=s.in_progress_path,
                                      artifact_path=s.artifact_path, completed_path=s.completed_path)
        assert len(art.outcomes) == 3 and len(art.exclusions) == 1
        assert s.artifact_path.exists() and s.completed_path.exists()

    def test_corrupt_temp_artifact_is_an_incident_not_finalized(self, tmp_path: Path) -> None:
        s = _incident_shaped(tmp_path)
        with pytest.raises(RuntimeError, match="crash:after_temp_artifact"):
            run_stage_a_recovery(**s.kwargs(_fault=self._fault_at("after_temp_artifact")))
        tmp = s.artifact_path.with_suffix(s.artifact_path.suffix + ".part")
        tmp.write_bytes(tmp.read_bytes()[:-20])       # torn write (crash during fsync)
        with pytest.raises(RecoveryIncidentError):
            resume_stage_a_recovery(in_progress_path=s.in_progress_path,
                                    artifact_path=s.artifact_path, completed_path=s.completed_path)
        assert not s.artifact_path.exists()           # a corrupt temp is never finalized

    def test_crash_after_final_rename_before_completion_marker(self, tmp_path: Path) -> None:
        s = _incident_shaped(tmp_path)
        with pytest.raises(RuntimeError, match="crash:after_final_artifact"):
            run_stage_a_recovery(**s.kwargs(_fault=self._fault_at("after_final_artifact")))
        assert s.artifact_path.exists() and not s.completed_path.exists()
        import shutil
        shutil.rmtree(s.corpus_root)                  # no raw access possible on resume
        art = resume_stage_a_recovery(in_progress_path=s.in_progress_path,
                                      artifact_path=s.artifact_path, completed_path=s.completed_path)
        assert s.completed_path.exists()
        assert art.content_digest() == load_recovery_artifact(s.artifact_path).content_digest()

    def test_repeated_resume_after_completion_is_idempotent(self, tmp_path: Path) -> None:
        s = _incident_shaped(tmp_path)
        art = run_stage_a_recovery(**s.kwargs())
        a1 = resume_stage_a_recovery(in_progress_path=s.in_progress_path,
                                     artifact_path=s.artifact_path, completed_path=s.completed_path)
        a2 = resume_stage_a_recovery(in_progress_path=s.in_progress_path,
                                     artifact_path=s.artifact_path, completed_path=s.completed_path)
        assert a1.content_digest() == a2.content_digest() == art.content_digest()


class TestExclusionRecordShape:
    def test_exclusion_fields_are_complete_and_minimal(self, tmp_path: Path) -> None:
        s = _incident_shaped(tmp_path)
        art = run_stage_a_recovery(**s.kwargs())
        e = art.exclusions[0]
        assert isinstance(e, RecoveryExclusion)
        assert e.market_id == "1.12"
        assert e.reason == "UNDETERMINED_SETTLEMENT:BOTH_RUNNERS_REMOVED"
        assert e.source == "1.12.bz2"                     # source artifact identity
        assert "REMOVED" in e.settlement_summary          # pattern summary...
        assert "selection" not in e.settlement_summary    # ...without unnecessary raw fields
        assert not hasattr(e, "winner_selection_id")      # structurally cannot carry a winner
