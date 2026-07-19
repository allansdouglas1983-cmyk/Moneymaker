"""Stage 2E §5 — the one-time atomic June extraction + conditional Stage-B gating.

Proves requirement A (durable-burn-before-read; recovery never re-reads raw) and requirement B
(Stage B needs the exact use-policy digest + a genuine M1 PASS attestation bound to the artifact;
any non-PASS / mismatch is structurally unreachable). All synthetic — no real June outcome.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from l8_evidence.june_stage_a_extraction import (
    JUNE_ARTIFACT_USE_POLICY_DIGEST,
    ImmutableOutcomeArtifact,
    M1PassAttestation,
    MinimalOutcome,
    StageAIncidentError,
    StageBUnreachableError,
    attest_m1_pass,
    load_artifact,
    open_stage_b_reader,
    recover_stage_a,
    run_stage_a_extraction,
)
from l8_evidence.lockbox import (
    GATE_1_ID,
    LockboxBurnedError,
    LockboxDefinition,
    LockboxRegistry,
    LockboxState,
)
from l8_evidence.prediction_snapshots import DualClockTimestamp

pytestmark = [pytest.mark.spec("SPEC-092")]


def _probe_token() -> object:
    import l8_evidence.june_stage_a_extraction as m
    return m._ATTEST_TOKEN

_TS = DualClockTimestamp(wall_utc=datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc), monotonic_ns=1)
_LB = "lockbox-june-2026-tennis-v1"
_BUNDLE_IDS = frozenset({"1.1", "1.2", "1.3"})
_BUNDLE_DIGEST = "sha256:" + "ab" * 32
_AUTH_DIGEST = "sha256:" + "cd" * 32


def _registry() -> LockboxRegistry:
    reg = LockboxRegistry()
    reg.define(LockboxDefinition(
        lockbox_id=_LB, period_start=datetime(2026, 6, 1).date(),
        period_end=datetime(2026, 6, 30).date(), defined_at=_TS, defined_by="founder",
    ))
    return reg


def _outcomes() -> list[MinimalOutcome]:
    return [MinimalOutcome("1.1", 11), MinimalOutcome("1.2", 44), MinimalOutcome("1.3", 55)]


def _run(
    reg: LockboxRegistry,
    tmp_path: Path,
    *,
    reader: Callable[[], Sequence[MinimalOutcome]] | None = None,
    fault: Callable[[str], None] | None = None,
) -> tuple[ImmutableOutcomeArtifact, dict[str, int]]:
    calls = {"n": 0}
    def default_reader() -> list[MinimalOutcome]:
        calls["n"] += 1
        return _outcomes()
    kwargs: dict[str, Any] = dict(
        registry=reg, lockbox_id=_LB, accessor="gate-1", at=_TS,
        bundle_market_ids=_BUNDLE_IDS, bundle_digest=_BUNDLE_DIGEST,
        authorisation_digest=_AUTH_DIGEST, read_outcomes=reader or default_reader,
        burn_record_path=tmp_path / "burn.json", artifact_path=tmp_path / "artifact.json",
    )
    if fault is not None:
        kwargs["_fault"] = fault
    art = run_stage_a_extraction(**kwargs)
    return art, calls


class TestHappyPath:
    def test_extraction_produces_verified_artifact_and_burns_registry(self, tmp_path: Path) -> None:
        reg = _registry()
        art, calls = _run(reg, tmp_path)
        assert calls["n"] == 1
        assert reg.state(_LB) is LockboxState.BURNED
        assert {o.market_id for o in art.outcomes} == {"1.1", "1.2", "1.3"}
        # artifact on disk verifies against its own digest
        loaded = load_artifact(tmp_path / "artifact.json")
        assert loaded.content_digest() == art.content_digest()


class TestRequirementA_DurableBurnBeforeRead:
    def test_burn_is_durable_before_any_outcome_read(self, tmp_path: Path) -> None:
        # Fault immediately after the durable burn record, before the read: the raw reader must
        # NOT have run, yet the burn record is already durable.
        reg = _registry()
        def fault(step: str) -> None:
            if step == "after_burn_record":
                raise RuntimeError("crash before read")
        with pytest.raises(RuntimeError, match="crash before read"):
            _run(reg, tmp_path, fault=fault)
        assert (tmp_path / "burn.json").exists()          # durably opened
        assert not (tmp_path / "artifact.json").exists()

    def test_crash_after_read_before_artifact_is_incident_no_reread(self, tmp_path: Path) -> None:
        reg = _registry()
        def fault(step: str) -> None:
            if step == "after_raw_read":
                raise RuntimeError("crash after read")
        with pytest.raises(RuntimeError, match="crash after read"):
            _run(reg, tmp_path, fault=fault)
        # Recovery must NOT re-read raw; it declares an incident (burn record but no artifact).
        with pytest.raises(StageAIncidentError):
            recover_stage_a(burn_record_path=tmp_path / "burn.json",
                            artifact_path=tmp_path / "artifact.json")

    def test_crash_after_artifact_recovers_by_finalizing_no_reread(self, tmp_path: Path) -> None:
        reg = _registry()
        def fault(step: str) -> None:
            if step == "after_artifact":
                raise RuntimeError("crash after artifact")
        with pytest.raises(RuntimeError, match="crash after artifact"):
            _run(reg, tmp_path, fault=fault)
        # The complete artifact exists -> recovery finalizes it, never touching raw.
        art = recover_stage_a(burn_record_path=tmp_path / "burn.json",
                              artifact_path=tmp_path / "artifact.json")
        assert {o.market_id for o in art.outcomes} == {"1.1", "1.2", "1.3"}

    def test_a_second_fresh_run_is_refused(self, tmp_path: Path) -> None:
        reg = _registry()
        _run(reg, tmp_path)
        # burn record + artifact exist -> a fresh run refuses (must recover instead).
        with pytest.raises(StageAIncidentError):
            _run(_registry(), tmp_path)

    def test_registry_refuses_a_second_gate1_access(self, tmp_path: Path) -> None:
        reg = _registry()
        _run(reg, tmp_path)
        with pytest.raises(LockboxBurnedError):
            reg.access(_LB, accessor="again", purpose="x", gate_id=GATE_1_ID, at=_TS)

    def test_outcomes_outside_bundle_refuse(self, tmp_path: Path) -> None:
        with pytest.raises(StageAIncidentError):
            _run(_registry(), tmp_path, reader=lambda: [MinimalOutcome("1.999", 1)])

    def test_duplicate_market_ids_refuse(self, tmp_path: Path) -> None:
        with pytest.raises(StageAIncidentError):
            _run(_registry(), tmp_path,
                 reader=lambda: [MinimalOutcome("1.1", 1), MinimalOutcome("1.1", 2)])


class TestRequirementB_ConditionalStageB:
    def _artifact(self, tmp_path: Path) -> ImmutableOutcomeArtifact:
        art, _ = _run(_registry(), tmp_path)
        return art

    def test_pass_attestation_unlocks_stage_b(self, tmp_path: Path) -> None:
        art = self._artifact(tmp_path)
        att = attest_m1_pass(verdict="PASS", artifact=art,
                             use_policy_digest=JUNE_ARTIFACT_USE_POLICY_DIGEST,
                             m1_gate_version="probability-m1")
        rows = open_stage_b_reader(art, use_policy_digest=JUNE_ARTIFACT_USE_POLICY_DIGEST,
                                   m1_attestation=att)
        assert {o.market_id for o in rows} == {"1.1", "1.2", "1.3"}

    @pytest.mark.parametrize("verdict", ["CONTINUE", "FAIL_HARM", "FAIL_FUTILITY", "TECHNICAL_FAILURE"])
    def test_non_pass_makes_stage_b_unreachable(self, tmp_path: Path, verdict: str) -> None:
        art = self._artifact(tmp_path)
        with pytest.raises(StageBUnreachableError):
            attest_m1_pass(verdict=verdict, artifact=art,
                           use_policy_digest=JUNE_ARTIFACT_USE_POLICY_DIGEST,
                           m1_gate_version="probability-m1")

    def test_wrong_use_policy_digest_blocks_attestation_and_reader(self, tmp_path: Path) -> None:
        art = self._artifact(tmp_path)
        with pytest.raises(StageBUnreachableError):
            attest_m1_pass(verdict="PASS", artifact=art,
                           use_policy_digest="sha256:" + "00" * 32, m1_gate_version="x")
        good = attest_m1_pass(verdict="PASS", artifact=art,
                              use_policy_digest=JUNE_ARTIFACT_USE_POLICY_DIGEST, m1_gate_version="x")
        with pytest.raises(StageBUnreachableError):
            open_stage_b_reader(art, use_policy_digest="sha256:" + "00" * 32, m1_attestation=good)

    def test_forged_attestation_refused(self, tmp_path: Path) -> None:
        art = self._artifact(tmp_path)
        forged = M1PassAttestation(artifact_digest=art.content_digest(),
                                   use_policy_digest=JUNE_ARTIFACT_USE_POLICY_DIGEST,
                                   m1_gate_version="x", _token=object())
        with pytest.raises(StageBUnreachableError):
            open_stage_b_reader(art, use_policy_digest=JUNE_ARTIFACT_USE_POLICY_DIGEST,
                                m1_attestation=forged)

    def test_attestation_bound_to_a_different_artifact_refused(self, tmp_path: Path) -> None:
        art = self._artifact(tmp_path)
        other = art.__class__(lockbox_id=art.lockbox_id, bundle_digest=art.bundle_digest,
                              authorisation_digest=art.authorisation_digest,
                              grant_at_utc=art.grant_at_utc,
                              outcomes=(MinimalOutcome("1.1", 11),))  # different outcome set
        att_other = attest_m1_pass(verdict="PASS", artifact=other,
                                   use_policy_digest=JUNE_ARTIFACT_USE_POLICY_DIGEST,
                                   m1_gate_version="x")
        with pytest.raises(StageBUnreachableError):
            open_stage_b_reader(art, use_policy_digest=JUNE_ARTIFACT_USE_POLICY_DIGEST,
                                m1_attestation=att_other)


class TestExtractionMutationHardening:
    def test_strict_subset_extraction_succeeds(self, tmp_path: Path) -> None:
        # Outcomes a STRICT subset of the bundle must be accepted (kills <= -> == / < on the
        # subset check): a market can refuse at burn, leaving fewer outcomes than the bundle.
        reg = _registry()
        art, _ = _run(reg, tmp_path, reader=lambda: [MinimalOutcome("1.1", 11), MinimalOutcome("1.2", 44)])
        assert {o.market_id for o in art.outcomes} == {"1.1", "1.2"}  # 1.3 legitimately absent

    def test_corrupt_artifact_on_disk_fails_digest_selfcheck(self, tmp_path: Path) -> None:
        reg = _registry()
        _run(reg, tmp_path)
        p = tmp_path / "artifact.json"
        blob = p.read_text().replace('"winner_selection_id":11', '"winner_selection_id":22')
        p.write_text(blob)  # tamper -> content no longer matches stored digest
        with pytest.raises(StageAIncidentError):
            load_artifact(p)

    def test_recover_returns_bytewise_same_artifact(self, tmp_path: Path) -> None:
        reg = _registry()
        art, _ = _run(reg, tmp_path)
        rec = recover_stage_a(burn_record_path=tmp_path / "burn.json",
                              artifact_path=tmp_path / "artifact.json")
        assert rec.content_digest() == art.content_digest()
        assert tuple((o.market_id, o.winner_selection_id) for o in rec.outcomes) == \
            tuple((o.market_id, o.winner_selection_id) for o in art.outcomes)


class TestDigestDirectionHardening:
    """Kill != -> < / > / is-not on digest EQUALITY checks: a wrong digest on EITHER lexical
    side of the real one must reject (real use-policy digest starts '84...')."""

    _SMALLER = "sha256:" + "00" * 32   # < 84...
    _LARGER = "sha256:" + "ff" * 32    # > 84...

    def _artifact(self, tmp_path: Path) -> ImmutableOutcomeArtifact:
        art, _ = _run(_registry(), tmp_path)
        return art

    @pytest.mark.parametrize("wrong", [_SMALLER, _LARGER])
    def test_attest_rejects_wrong_use_policy_both_directions(self, tmp_path: Path, wrong: str) -> None:
        with pytest.raises(StageBUnreachableError):
            attest_m1_pass(verdict="PASS", artifact=self._artifact(tmp_path),
                           use_policy_digest=wrong, m1_gate_version="x")

    @pytest.mark.parametrize("wrong", [_SMALLER, _LARGER])
    def test_reader_rejects_wrong_use_policy_both_directions(self, tmp_path: Path, wrong: str) -> None:
        art = self._artifact(tmp_path)
        good = attest_m1_pass(verdict="PASS", artifact=art,
                              use_policy_digest=JUNE_ARTIFACT_USE_POLICY_DIGEST, m1_gate_version="x")
        with pytest.raises(StageBUnreachableError):
            open_stage_b_reader(art, use_policy_digest=wrong, m1_attestation=good)

    @pytest.mark.parametrize("wrong", [_SMALLER, _LARGER])
    def test_attestation_carrying_wrong_use_policy_both_directions_refused(self, tmp_path: Path, wrong: str) -> None:
        art = self._artifact(tmp_path)
        # a genuine tokened attestation but with a tampered use_policy_digest field
        forged = M1PassAttestation(artifact_digest=art.content_digest(), use_policy_digest=wrong,
                                   m1_gate_version="x", _token=_probe_token())
        with pytest.raises(StageBUnreachableError):
            open_stage_b_reader(art, use_policy_digest=JUNE_ARTIFACT_USE_POLICY_DIGEST,
                                m1_attestation=forged)


class TestLargeInputHardening:
    def test_large_no_duplicate_extraction_succeeds(self, tmp_path: Path) -> None:
        # >256 markets, no dups: kills `len(ids) != len(set(ids))` -> `is not` (list lengths
        # above the small-int cache are distinct objects; `is not` would falsely flag a dup and
        # break the real 1,213-market burn).
        n = 400
        ids = frozenset(f"1.{1000+i}" for i in range(n))
        reg = LockboxRegistry()
        reg.define(LockboxDefinition(lockbox_id=_LB, period_start=datetime(2026, 6, 1).date(),
                   period_end=datetime(2026, 6, 30).date(), defined_at=_TS, defined_by="founder"))
        art = run_stage_a_extraction(
            registry=reg, lockbox_id=_LB, accessor="g", at=_TS, bundle_market_ids=ids,
            bundle_digest=_BUNDLE_DIGEST, authorisation_digest=_AUTH_DIGEST,
            read_outcomes=lambda: [MinimalOutcome(f"1.{1000+i}", i + 1) for i in range(n)],
            burn_record_path=tmp_path / "b.json", artifact_path=tmp_path / "a.json")
        assert len(art.outcomes) == n


def _dup(s: str) -> str:
    """A value-equal but guaranteed DIFFERENT string object (as a digest loaded at runtime)."""
    d = s.encode("utf-8").decode("utf-8")
    assert d == s and d is not s
    return d


def _artifact_obj(winner: int) -> ImmutableOutcomeArtifact:
    return ImmutableOutcomeArtifact(lockbox_id=_LB, bundle_digest=_BUNDLE_DIGEST,
        authorisation_digest=_AUTH_DIGEST, grant_at_utc="2026-07-18T12:00:00+00:00",
        outcomes=(MinimalOutcome("1.1", winner),))


# deterministic digest ordering: winner 22 -> lowest content_digest, winner 11 -> highest
_ART_LO = _artifact_obj(22)
_ART_HI = _artifact_obj(11)
assert _ART_LO.content_digest() < _ART_HI.content_digest()


class TestDigestEqualityIsNotOrdering:
    """§3: `actual != expected` is EQUALITY. Kill mutants to `<`, `>`, and `is not` — with wrong
    digests on BOTH lexical sides AND a value-equal different-object correct digest (match path)."""

    def test_attest_verdict_equality_not_identity(self) -> None:
        # verdict != "PASS" -> is not : a value-equal different-object 'PASS' must still PASS.
        att = attest_m1_pass(verdict=_dup("PASS"), artifact=_ART_LO,
                             use_policy_digest=JUNE_ARTIFACT_USE_POLICY_DIGEST, m1_gate_version="x")
        assert isinstance(att, M1PassAttestation)

    def test_attest_use_policy_equality_not_identity(self) -> None:
        att = attest_m1_pass(verdict="PASS", artifact=_ART_LO,
                             use_policy_digest=_dup(JUNE_ARTIFACT_USE_POLICY_DIGEST), m1_gate_version="x")
        assert isinstance(att, M1PassAttestation)

    def test_reader_use_policy_equality_not_identity(self) -> None:
        att = attest_m1_pass(verdict="PASS", artifact=_ART_LO,
                             use_policy_digest=JUNE_ARTIFACT_USE_POLICY_DIGEST, m1_gate_version="x")
        rows = open_stage_b_reader(_ART_LO, use_policy_digest=_dup(JUNE_ARTIFACT_USE_POLICY_DIGEST),
                                   m1_attestation=att)
        assert len(rows) == 1

    def test_reader_attestation_use_policy_equality_not_identity(self) -> None:
        att = M1PassAttestation(artifact_digest=_ART_LO.content_digest(),
                                use_policy_digest=_dup(JUNE_ARTIFACT_USE_POLICY_DIGEST),
                                m1_gate_version="x", _token=_probe_token())
        rows = open_stage_b_reader(_ART_LO, use_policy_digest=JUNE_ARTIFACT_USE_POLICY_DIGEST,
                                   m1_attestation=att)
        assert len(rows) == 1

    def test_reader_artifact_binding_rejects_both_orderings(self) -> None:
        # attestation bound to the LOW-digest artifact, applied to the HIGH-digest one, and vice
        # versa: != rejects both; < and > each accept exactly one ordering -> both killed.
        att_lo = attest_m1_pass(verdict="PASS", artifact=_ART_LO,
                                use_policy_digest=JUNE_ARTIFACT_USE_POLICY_DIGEST, m1_gate_version="x")
        att_hi = attest_m1_pass(verdict="PASS", artifact=_ART_HI,
                                use_policy_digest=JUNE_ARTIFACT_USE_POLICY_DIGEST, m1_gate_version="x")
        with pytest.raises(StageBUnreachableError):
            open_stage_b_reader(_ART_HI, use_policy_digest=JUNE_ARTIFACT_USE_POLICY_DIGEST, m1_attestation=att_lo)
        with pytest.raises(StageBUnreachableError):
            open_stage_b_reader(_ART_LO, use_policy_digest=JUNE_ARTIFACT_USE_POLICY_DIGEST, m1_attestation=att_hi)

    def test_reader_artifact_binding_accepts_equal_value_recomputed_digest(self) -> None:
        # content_digest() is recomputed fresh (different object) at open time: is-not would wrongly reject.
        att = attest_m1_pass(verdict="PASS", artifact=_ART_LO,
                             use_policy_digest=JUNE_ARTIFACT_USE_POLICY_DIGEST, m1_gate_version="x")
        assert len(open_stage_b_reader(_ART_LO, use_policy_digest=JUNE_ARTIFACT_USE_POLICY_DIGEST,
                                       m1_attestation=att)) == 1

    def test_load_artifact_digest_equality_both_sides_and_identity(self, tmp_path: Path) -> None:
        reg = _registry()
        _run(reg, tmp_path)
        p = tmp_path / "artifact.json"
        import json
        payload = json.loads(p.read_text())
        real = payload["content_digest"]
        # tamper the stored digest to a value LOWER and HIGHER than the real -> both must fail.
        for wrong in ("sha256:" + "00" * 32, "sha256:" + "ff" * 32):
            p.write_text(json.dumps({**payload, "content_digest": wrong}))
            with pytest.raises(StageAIncidentError):
                load_artifact(p)
        # a value-equal different-object stored digest must LOAD (kills != -> is not).
        p.write_text(json.dumps({**payload, "content_digest": _dup(real)}))
        assert load_artifact(p).content_digest() == real


class TestDigestAndControlFlowHardening:
    def test_content_digest_exact_value(self) -> None:
        # kills arithmetic/sort_keys mutants in content_digest/to_json (pinned exact string).
        assert _ART_LO.content_digest() == "sha256:1bfc8ca6819c15bfd2bfcb82f8c98dd09a1775b943984aef4713f1a38ebe8c27"

    def test_to_json_roundtrips_to_same_digest(self) -> None:
        import json
        payload = json.loads(_ART_LO.to_json())
        assert payload["content_digest"] == _ART_LO.content_digest()

    def test_fresh_run_refuses_if_only_burn_record_present(self, tmp_path: Path) -> None:
        # kills `or` -> `and` at the prior-state guard: a leftover burn record alone must refuse.
        (tmp_path / "burn.json").write_text("{}")
        with pytest.raises(StageAIncidentError):
            _run(_registry(), tmp_path)

    def test_fresh_run_refuses_if_only_artifact_present(self, tmp_path: Path) -> None:
        (tmp_path / "artifact.json").write_text("{}")
        with pytest.raises(StageAIncidentError):
            _run(_registry(), tmp_path)

    def test_recover_distinguishes_incident_from_never_opened(self, tmp_path: Path) -> None:
        # kills the AddNot on `if burn_record_path.exists()`: the two cases raise DIFFERENT messages.
        (tmp_path / "burn.json").write_text("{}")
        with pytest.raises(StageAIncidentError, match="durable burn record exists"):
            recover_stage_a(burn_record_path=tmp_path / "burn.json", artifact_path=tmp_path / "none.json")
        with pytest.raises(StageAIncidentError, match="never durably opened"):
            recover_stage_a(burn_record_path=tmp_path / "absent.json", artifact_path=tmp_path / "none.json")


class TestFrozenDataclassImmutability:
    """§7: MinimalOutcome / ImmutableOutcomeArtifact / M1PassAttestation are frozen. Kills
    ReplaceTrueWithFalse on @dataclass(frozen=True): frozen=False makes them mutable AND
    (eq=True default) unhashable."""

    def test_minimal_outcome_is_frozen_and_hashable(self) -> None:
        import dataclasses
        o = MinimalOutcome("1.1", 7)
        with pytest.raises(dataclasses.FrozenInstanceError):
            o.market_id = "1.2"   # type: ignore[misc]
        assert hash(o) == hash(MinimalOutcome("1.1", 7))

    def test_artifact_is_frozen_and_hashable(self) -> None:
        import dataclasses
        a = _artifact_obj(11)
        with pytest.raises(dataclasses.FrozenInstanceError):
            a.lockbox_id = "other"   # type: ignore[misc]
        assert isinstance(hash(a), int)

    def test_attestation_is_frozen_and_hashable(self) -> None:
        import dataclasses
        att = M1PassAttestation("sha256:" + "0" * 64, JUNE_ARTIFACT_USE_POLICY_DIGEST, "v1", _probe_token())
        with pytest.raises(dataclasses.FrozenInstanceError):
            att.m1_gate_version = "v2"   # type: ignore[misc]
        assert isinstance(hash(att), int)


class TestDeterministicSerialization:
    """Kill ReplaceTrueWithFalse on sort_keys=True in to_json and the durable burn record: stable
    key order is an evidence-integrity requirement for the durable artifact bytes."""

    def test_to_json_key_order_is_sorted(self) -> None:
        import json
        s = _artifact_obj(11).to_json()
        keys = list(json.loads(s).keys())
        assert keys == sorted(keys)
        assert s.startswith('{"authorisation_digest":')   # only sorted order yields this prefix

    def test_burn_record_key_order_is_sorted(self, tmp_path: Path) -> None:
        _run(_registry(), tmp_path)
        body = (tmp_path / "burn.json").read_text(encoding="utf-8")
        assert body.startswith('{"accessor":')   # sorted; insertion order would start with "lockbox_id"


class TestAttestationContentDigest:
    """Kill the 11 arithmetic/bitwise mutants of `"sha256:" + hexdigest` AND sort_keys=True in
    M1PassAttestation.content_digest (an uncalled-but-public evidence method): any str OP str
    raises TypeError; sort_keys=False changes the digest. Pin the exact value."""

    def test_attestation_content_digest_exact_value(self) -> None:
        att = M1PassAttestation(artifact_digest=_ART_LO.content_digest(),
                                use_policy_digest=JUNE_ARTIFACT_USE_POLICY_DIGEST,
                                m1_gate_version="x", _token=_probe_token())
        assert att.content_digest() == "sha256:bd3c631d1fc43d43aa61767fc27b29922698ec279417f70105eebe7051baab21"


class TestValidationMessageIsSetDifference:
    """Kill ReplaceBinaryOperator_Sub_* on (got - bundle_market_ids) in the error message and the
    `[:5]` truncation: the message names exactly the out-of-bundle ids (difference), nothing in-bundle."""

    def test_message_shows_only_out_of_bundle_ids(self) -> None:
        from l8_evidence.june_stage_a_extraction import _validate_outcomes
        with pytest.raises(StageAIncidentError) as ei:
            _validate_outcomes(
                (MinimalOutcome("good1", 1), MinimalOutcome("bad1", 2)),
                frozenset({"good1", "good2"}),
            )
        msg = str(ei.value)
        assert "bad1" in msg          # difference contains the offender
        assert "good1" not in msg     # & (intersection) would show good1
        assert "good2" not in msg     # | / ^ would show good2

    def test_message_truncates_at_five_offenders(self) -> None:
        from l8_evidence.june_stage_a_extraction import _validate_outcomes
        # six out-of-bundle ids b0..b5 (sorted): [:5] shows b0..b4, hides b5. Kills [:6] (would show
        # b5) and [:4] (would hide b4).
        offenders = tuple(MinimalOutcome(f"b{i}", i) for i in range(6))
        with pytest.raises(StageAIncidentError) as ei:
            _validate_outcomes(offenders, frozenset())
        msg = str(ei.value)
        assert "b4" in msg and "b5" not in msg


class TestKeywordOnlyAndTokenIdentity:
    def test_reader_use_policy_is_keyword_only(self) -> None:
        # `*` -> `/` makes use_policy_digest/m1_attestation positional; original keeps them
        # keyword-only, so a positional call MUST NOT be accepted as those params.
        art = _artifact_obj(11)
        with pytest.raises(TypeError):
            open_stage_b_reader(art, "x", "y")   # type: ignore[call-arg, arg-type]

    def test_forged_attestation_token_with_evil_eq_is_refused(self) -> None:
        # SECURITY: the attestation token is checked by IDENTITY (`is not`). A forged attestation
        # whose _token only __eq__-equals the sentinel defeats `!=` but not `is not`.
        class _EvilEq:
            def __eq__(self, other: object) -> bool:  # equals anything
                return True
            __hash__ = None  # type: ignore[assignment]
        art = _artifact_obj(11)
        forged = M1PassAttestation(artifact_digest=art.content_digest(),
                                   use_policy_digest=JUNE_ARTIFACT_USE_POLICY_DIGEST,
                                   m1_gate_version="v1", _token=_EvilEq())
        with pytest.raises(StageBUnreachableError):
            open_stage_b_reader(art, use_policy_digest=JUNE_ARTIFACT_USE_POLICY_DIGEST,
                                m1_attestation=forged)
