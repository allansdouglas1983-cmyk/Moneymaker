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


class TestVerificationGuardsAreEquality:
    """Digest guards are EQUALITY, never ordering (founder doctrine): kill != -> < / > / is."""

    def test_require_file_digest_rejects_both_lexical_directions(self, tmp_path: Path) -> None:
        from l8_evidence.june_stage_a_recovery import _require_file_digest
        f = tmp_path / "x.bin"
        f.write_bytes(b"payload")
        actual = _sha256_file(f)
        for wrong in ("sha256:" + "0" * 64, "sha256:" + "f" * 64):   # below AND above
            with pytest.raises(RecoveryIntegrityError):
                _require_file_digest("thing", f, wrong)
        _require_file_digest("thing", f, actual)                      # exact passes
        _require_file_digest("thing", f, actual.encode().decode())    # equal distinct object passes

    def test_corpus_entry_digest_lexically_lower_than_actual_is_refused(self, tmp_path: Path) -> None:
        # kills actual != expected -> actual < expected on the per-file corpus check.
        from l8_evidence.june_stage_a_recovery import _verify_corpus_manifest
        root = tmp_path / "c"
        root.mkdir()
        (root / "f.bz2").write_bytes(b"data")
        manifest = root / "SHA256SUMS.txt"
        manifest.write_text(("0" * 64) + "  f.bz2\n", encoding="utf-8")   # recorded digest BELOW actual
        with pytest.raises(RecoveryIntegrityError):
            _verify_corpus_manifest(root, manifest, _sha256_file(manifest))

    def test_final_artifact_digest_tamper_both_directions_refused(self, tmp_path: Path) -> None:
        s = _incident_shaped(tmp_path)
        run_stage_a_recovery(**s.kwargs())
        payload = json.loads(s.artifact_path.read_text(encoding="utf-8"))
        for wrong in ("sha256:" + "0" * 64, "sha256:" + "f" * 64):
            s.artifact_path.write_text(json.dumps({**payload, "content_digest": wrong}),
                                       encoding="utf-8")
            with pytest.raises(RecoveryIncidentError):
                load_recovery_artifact(s.artifact_path)

    def test_temp_artifact_digest_tamper_both_directions_refused(self, tmp_path: Path) -> None:
        s = _incident_shaped(tmp_path)

        def fault(step: str) -> None:
            if step == "after_temp_artifact":
                raise RuntimeError("crash:after_temp_artifact")
        with pytest.raises(RuntimeError):
            run_stage_a_recovery(**s.kwargs(_fault=fault))
        tmp = s.artifact_path.with_suffix(s.artifact_path.suffix + ".part")
        payload = json.loads(tmp.read_text(encoding="utf-8"))
        for wrong in ("sha256:" + "0" * 64, "sha256:" + "f" * 64):
            tmp.write_text(json.dumps({**payload, "content_digest": wrong}), encoding="utf-8")
            with pytest.raises(RecoveryIncidentError):
                resume_stage_a_recovery(in_progress_path=s.in_progress_path,
                                        artifact_path=s.artifact_path,
                                        completed_path=s.completed_path)
            assert not s.artifact_path.exists()

    def test_large_batch_length_checks_compare_by_value_not_identity(self, tmp_path: Path) -> None:
        # 300 markets: len() values exceed CPython's small-int cache, so a len(a) is-not len(b)
        # mutant on the uniqueness/partition guards would spuriously raise. Must succeed.
        markets = {f"1.{5000 + i}": _settled(f"1.{5000 + i}", 11, 22) for i in range(300)}
        s = _Setup(tmp_path, markets, [_pred(m) for m in markets])
        art = run_stage_a_recovery(**s.kwargs())
        assert len(art.outcomes) == 300 and art.exclusions == ()


class TestManifestParsingHardening:
    def test_malformed_second_line_reports_its_line_number(self, tmp_path: Path) -> None:
        from l8_evidence.june_stage_a_recovery import _verify_corpus_manifest
        root = tmp_path / "c"
        root.mkdir()
        (root / "a.bz2").write_bytes(b"a")
        good = hashlib.sha256(b"a").hexdigest()
        manifest = root / "SHA256SUMS.txt"
        manifest.write_text(f"{good}  a.bz2\nnot-a-manifest-line\n", encoding="utf-8")
        with pytest.raises(RecoveryIntegrityError, match="line 2"):
            _verify_corpus_manifest(root, manifest, _sha256_file(manifest))

    def test_blank_manifest_line_is_skipped_not_terminal(self, tmp_path: Path) -> None:
        # a blank line between entries must not stop verification: corrupt the SECOND file.
        from l8_evidence.june_stage_a_recovery import _verify_corpus_manifest
        root = tmp_path / "c"
        root.mkdir()
        (root / "a.bz2").write_bytes(b"a")
        (root / "b.bz2").write_bytes(b"b")
        ha, hb = hashlib.sha256(b"a").hexdigest(), hashlib.sha256(b"b").hexdigest()
        manifest = root / "SHA256SUMS.txt"
        manifest.write_text(f"{ha}  a.bz2\n\n{hb}  b.bz2\n", encoding="utf-8")
        (root / "b.bz2").write_bytes(b"tampered")
        with pytest.raises(RecoveryIntegrityError, match="b.bz2"):
            _verify_corpus_manifest(root, manifest, _sha256_file(manifest))

    def test_single_token_line_is_malformed_even_if_64_hex(self, tmp_path: Path) -> None:
        # kills `or` -> `and` on the malformed-line guard.
        from l8_evidence.june_stage_a_recovery import _verify_corpus_manifest
        root = tmp_path / "c"
        root.mkdir()
        manifest = root / "SHA256SUMS.txt"
        manifest.write_text(("a" * 64) + "\n", encoding="utf-8")
        with pytest.raises(RecoveryIntegrityError):
            _verify_corpus_manifest(root, manifest, _sha256_file(manifest))

    def test_digest_of_wrong_length_refused_both_directions(self, tmp_path: Path) -> None:
        from l8_evidence.june_stage_a_recovery import _verify_corpus_manifest
        root = tmp_path / "c"
        root.mkdir()
        (root / "a.bz2").write_bytes(b"a")
        for badlen in (63, 65):
            manifest = root / "SHA256SUMS.txt"
            manifest.write_text(("a" * badlen) + "  a.bz2\n", encoding="utf-8")
            with pytest.raises(RecoveryIntegrityError):
                _verify_corpus_manifest(root, manifest, _sha256_file(manifest))

    def test_manifest_path_with_spaces_verifies(self, tmp_path: Path) -> None:
        # maxsplit=1 keeps a spaced path intact; a higher maxsplit would mangle it.
        from l8_evidence.june_stage_a_recovery import _verify_corpus_manifest
        root = tmp_path / "c"
        root.mkdir()
        (root / "a b.bz2").write_bytes(b"ab")
        h = hashlib.sha256(b"ab").hexdigest()
        manifest = root / "SHA256SUMS.txt"
        manifest.write_text(f"{h}  a b.bz2\n", encoding="utf-8")
        _verify_corpus_manifest(root, manifest, _sha256_file(manifest))   # must pass

    def test_missing_streams_message_names_exactly_three_examples(self, tmp_path: Path) -> None:
        markets = {"1.10": _settled("1.10", 11, 22)}
        preds = [_pred(m) for m in ("1.10", "1.20", "1.21", "1.22", "1.23")]
        s = _Setup(tmp_path, markets, preds)
        with pytest.raises(RecoveryIntegrityError) as ei:
            run_stage_a_recovery(**s.kwargs())
        msg = str(ei.value)
        assert "1.22" in msg and "1.23" not in msg    # [:3] shows the 3rd, hides the 4th

    def test_malformed_bundle_lines_raise_typed_integrity_errors(self, tmp_path: Path) -> None:
        from l8_evidence.june_stage_a_recovery import _load_bundle
        for bad in ("{not json", '{"market_id": "1.1"}', '"just a string"'):
            p = tmp_path / "b.jsonl"
            p.write_text(bad + "\n", encoding="utf-8")
            with pytest.raises(RecoveryIntegrityError):
                _load_bundle(p, _sha256_file(p))

    def test_blank_bundle_line_does_not_truncate_the_bundle(self, tmp_path: Path) -> None:
        markets = {"1.10": _settled("1.10", 11, 22), "1.11": _settled("1.11", 11, 22)}
        s = _Setup(tmp_path, markets, [_pred("1.10"), _pred("1.11")])
        s.bundle_path.write_text(
            _bundle_line(_pred("1.10")) + "\n\n" + _bundle_line(_pred("1.11")) + "\n",
            encoding="utf-8")
        art = run_stage_a_recovery(**s.kwargs(bundle_sha256=_sha256_file(s.bundle_path)))
        assert len(art.outcomes) + len(art.exclusions) == 2   # nothing silently dropped


class TestClassifierHardening:
    def _classify(self, lines: list[str], mid: str = "1.50") -> RecoveryExclusion:
        from l8_evidence.june_stage_a_recovery import _classify_exclusion
        return _classify_exclusion(lines, mid, f"{mid}.bz2")

    def test_single_winner_pattern_is_a_conflict_not_an_exclusion(self) -> None:
        # the governed extractor settles exactly-one-winner markets; if the classifier ever sees
        # one, extraction and classification CONFLICT -> typed integrity failure, never a guess.
        from l8_evidence.june_stage_a_recovery import RecoveryIntegrityError as RIE
        lines = [_line("1.50", "CLOSED", [{"id": 1, "status": "WINNER"}, {"id": 2, "status": "LOSER"}])]
        with pytest.raises(RIE, match="conflict"):
            self._classify(lines)

    def test_abandoned_definition_is_not_a_settlement(self) -> None:
        # "ABANDONED" < "CLOSED" lexically: a <= mutant would treat it as CLOSED and misclassify.
        lines = [_line("1.50", "ABANDONED", [{"id": 1, "status": "REMOVED"}, {"id": 2, "status": "REMOVED"}])]
        e = self._classify(lines)
        assert e.reason == "UNDETERMINED_SETTLEMENT:NO_CLOSED_DEFINITION"
        assert "closed=no" in e.settlement_summary

    def test_foreign_smaller_id_closed_def_not_counted_in_summary(self) -> None:
        # foreign mc "1.10" < target "1.50": an id != -> > mutant would absorb the foreign CLOSED.
        lines = [
            "",
            _line("1.10", "CLOSED", [{"id": 9, "status": "REMOVED"}, {"id": 8, "status": "REMOVED"}]),
            json.dumps({"op": "mcm", "pt": 1, "mc": [{"id": "1.50"}]}),          # target mc, no md
            _line("1.50", "OPEN", [{"id": 1, "status": "ACTIVE"}, {"id": 2, "status": "ACTIVE"}]),
        ]
        e = self._classify(lines)
        assert e.reason == "UNDETERMINED_SETTLEMENT:NO_CLOSED_DEFINITION"
        assert "closed=no" in e.settlement_summary and "REMOVED" not in e.settlement_summary

    def test_closed_with_no_runners_is_no_winner_not_void(self) -> None:
        lines = [_line("1.50", "CLOSED", [])]
        e = self._classify(lines)
        assert e.reason == "UNDETERMINED_SETTLEMENT:NO_WINNER"

    def test_single_removed_runner_is_all_removed(self) -> None:
        lines = [_line("1.50", "CLOSED", [{"id": 1, "status": "REMOVED"}])]
        assert self._classify(lines).reason == "UNDETERMINED_SETTLEMENT:BOTH_RUNNERS_REMOVED"

    def test_single_loser_runner_is_no_winner(self) -> None:
        lines = [_line("1.50", "CLOSED", [{"id": 1, "status": "LOSER"}])]
        assert self._classify(lines).reason == "UNDETERMINED_SETTLEMENT:NO_WINNER"

    def test_many_removed_runners_beyond_int_cache_still_all_removed(self) -> None:
        # 300 REMOVED runners: count and total exceed the small-int cache, killing an
        # `== total` -> `is total` mutant that only works on interned ints.
        runners: list[dict[str, object]] = [{"id": i + 1, "status": "REMOVED"} for i in range(300)]
        lines = [_line("1.50", "CLOSED", runners)]
        assert self._classify(lines).reason == "UNDETERMINED_SETTLEMENT:BOTH_RUNNERS_REMOVED"

    def test_incident_summary_pins_exact_status_counts(self, tmp_path: Path) -> None:
        s = _incident_shaped(tmp_path)
        art = run_stage_a_recovery(**s.kwargs())
        assert art.exclusions[0].settlement_summary == "closed=yes statuses={REMOVED:2}"


class TestArtifactDeterminismAndRecords:
    def test_artifact_json_key_order_is_sorted_and_digest_stable(self, tmp_path: Path) -> None:
        s = _incident_shaped(tmp_path)
        art = run_stage_a_recovery(**s.kwargs())
        body = s.artifact_path.read_text(encoding="utf-8")
        assert body.startswith('{"bundle_digest":')            # sorted keys, not insertion order
        keys = list(json.loads(body).keys())
        assert keys == sorted(keys)
        assert art.content_digest() == json.loads(body)["content_digest"]

    def test_in_progress_and_completed_records_have_sorted_keys(self, tmp_path: Path) -> None:
        s = _incident_shaped(tmp_path)
        run_stage_a_recovery(**s.kwargs())
        assert s.in_progress_path.read_text(encoding="utf-8").startswith('{"bundle_digest":')
        assert s.completed_path.read_text(encoding="utf-8").startswith('{"artifact_digest":')

    def test_resume_written_completion_record_has_sorted_keys(self, tmp_path: Path) -> None:
        s = _incident_shaped(tmp_path)
        run_stage_a_recovery(**s.kwargs())
        s.completed_path.unlink()
        resume_stage_a_recovery(in_progress_path=s.in_progress_path,
                                artifact_path=s.artifact_path, completed_path=s.completed_path)
        assert s.completed_path.read_text(encoding="utf-8").startswith('{"artifact_digest":')

    def test_recovery_dataclasses_are_frozen(self, tmp_path: Path) -> None:
        import dataclasses
        s = _incident_shaped(tmp_path)
        art = run_stage_a_recovery(**s.kwargs())
        with pytest.raises(dataclasses.FrozenInstanceError):
            art.lockbox_id = "other"                          # type: ignore[misc]
        e = art.exclusions[0]
        with pytest.raises(dataclasses.FrozenInstanceError):
            e.reason = "other"                                # type: ignore[misc]

    def test_artifact_only_prior_state_refuses_a_fresh_run(self, tmp_path: Path) -> None:
        # kills `or` -> `and` on the single-use guard: an artifact ALONE must refuse.
        s = _incident_shaped(tmp_path)
        s.artifact_path.write_text("{}", encoding="utf-8")
        with pytest.raises(RecoverySingleUseError):
            run_stage_a_recovery(**s.kwargs())

    def test_resume_distinguishes_in_progress_from_never_started(self, tmp_path: Path) -> None:
        s = _incident_shaped(tmp_path)
        with pytest.raises(RecoveryIncidentError, match="never started"):
            resume_stage_a_recovery(in_progress_path=s.in_progress_path,
                                    artifact_path=s.artifact_path, completed_path=s.completed_path)
        s.in_progress_path.write_text("{}", encoding="utf-8")
        with pytest.raises(RecoveryIncidentError, match="in progress"):
            resume_stage_a_recovery(in_progress_path=s.in_progress_path,
                                    artifact_path=s.artifact_path, completed_path=s.completed_path)


class TestTypedExceptionCoverage:
    def test_stream_that_is_a_directory_is_integrity_failure(self, tmp_path: Path) -> None:
        markets = {"1.10": _settled("1.10", 11, 22)}
        s = _Setup(tmp_path, markets, [_pred("1.10"), _pred("1.11")])
        d = s.streams_root / "1.11.bz2"
        d.mkdir()                                             # a DIRECTORY named like a stream
        with pytest.raises(RecoveryIntegrityError):
            run_stage_a_recovery(**s.kwargs())

    def test_truncated_bz2_stream_is_integrity_failure(self, tmp_path: Path) -> None:
        markets = {"1.10": _settled("1.10", 11, 22), "1.11": _settled("1.11", 11, 22)}
        s = _Setup(tmp_path, markets, [_pred(m) for m in markets])
        f = s.streams_root / "1.11.bz2"
        f.write_bytes(f.read_bytes()[:10])                    # torn compressed stream (EOFError)
        with pytest.raises(RecoveryIntegrityError):
            run_stage_a_recovery(**s.kwargs(corpus_manifest_sha256=self._remanifest(s)))

    def test_plain_text_masquerading_as_bz2_is_integrity_failure(self, tmp_path: Path) -> None:
        markets = {"1.10": _settled("1.10", 11, 22), "1.11": _settled("1.11", 11, 22)}
        s = _Setup(tmp_path, markets, [_pred(m) for m in markets])
        (s.streams_root / "1.11.bz2").write_bytes(b"not a bz2 stream")
        with pytest.raises(RecoveryIntegrityError):
            run_stage_a_recovery(**s.kwargs(corpus_manifest_sha256=self._remanifest(s)))

    def _remanifest(self, s: _Setup) -> str:
        entries = []
        for f in sorted(s.streams_root.rglob("*.bz2")):
            entries.append(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.relative_to(s.corpus_root)}")
        s.manifest_path.write_text("\n".join(entries) + "\n", encoding="utf-8")
        return _sha256_file(s.manifest_path)

    def test_artifact_corruptions_raise_typed_incidents(self, tmp_path: Path) -> None:
        s = _incident_shaped(tmp_path)
        run_stage_a_recovery(**s.kwargs())
        good = s.artifact_path.read_text(encoding="utf-8")
        for bad in ("{not json", '{"lockbox_id": "x"}', json.dumps({**json.loads(good), "outcomes": 5})):
            s.artifact_path.write_text(bad, encoding="utf-8")
            with pytest.raises(RecoveryIncidentError):
                load_recovery_artifact(s.artifact_path)
