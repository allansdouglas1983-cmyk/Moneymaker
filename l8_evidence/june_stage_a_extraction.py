"""Stage 2E §5 — the one-time ATOMIC June Stage-A outcome extraction (SPEC-092).

Two governed guarantees are structural here, not conventional:

**A. Durable-burn-before-read.** The lockbox access is written durably (fsync) BEFORE the first
real outcome is read, so there is no crash window in which a June outcome has been read while the
registry still treats the lockbox as unopened. Recovery may finalize an already-complete
temporary artifact but NEVER re-reads the raw lockbox; where a crash leaves no finalizable
artifact, this stops with a typed incident rather than improvising a second raw access.

**B. Conditional Stage-B reachability.** The immutable outcome artifact is read once. Stage-B
(SPEC-032 development) access to it requires the EXACT use-policy digest and an immutable
M1-PASS attestation; M1 CONTINUE/FAIL/technical-failure/digest-mismatch makes Stage B
structurally unreachable, and Stage B has no reference to the raw lockbox at all.

The raw June read is injected as a callable, so this module never opens raw files itself and is
fully provable with synthetic data. Determinism + durability only; no LLM decides anything.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from l8_evidence.lockbox import GATE_1_ID, LockboxRegistry
from l8_evidence.prediction_snapshots import DualClockTimestamp

__all__ = [
    "JUNE_ARTIFACT_USE_POLICY_DIGEST",
    "StageAIncidentError",
    "StageBUnreachableError",
    "MinimalOutcome",
    "ImmutableOutcomeArtifact",
    "M1PassAttestation",
    "run_stage_a_extraction",
    "recover_stage_a",
    "load_artifact",
    "attest_m1_pass",
    "open_stage_b_reader",
]

#: The exact governed use-policy digest (specs/evidence/june-outcome-artifact-use-policy-v1.yaml)
#: — Stage B must present exactly this to reach the artifact (Stage 2E §2 / requirement B).
JUNE_ARTIFACT_USE_POLICY_DIGEST = (
    "sha256:84efd4a22cc4c778ff31867afc9a52a67718a22226aaefec97f942e279661338"
)

_FaultHook = Callable[[str], None]


class StageAIncidentError(RuntimeError):
    """A crash left the lockbox durably burned with no finalizable artifact. The result is
    unrecoverable without a NEW lockbox period; a second raw access is forbidden (SPEC-092).
    Stop, preserve the incident, do not improvise a rerun."""


class StageBUnreachableError(RuntimeError):
    """Stage-B artifact access was refused: M1 was not PASS, the use-policy digest did not
    match, or the attestation did not bind to this artifact. Stage B is structurally
    unreachable (Stage 2E §2 / requirement B)."""


@dataclass(frozen=True)
class MinimalOutcome:
    """The minimum governed outcome fields retained per market (no prices, no P&L)."""

    market_id: str
    winner_selection_id: int


@dataclass(frozen=True)
class ImmutableOutcomeArtifact:
    """The single hash-bound artifact the one burn creates. Every downstream computation (M1,
    conditional Stage-B) runs from THIS, never from the raw lockbox."""

    lockbox_id: str
    bundle_digest: str
    authorisation_digest: str
    grant_at_utc: str
    outcomes: tuple[MinimalOutcome, ...]

    def content_digest(self) -> str:
        body = json.dumps(
            {
                "lockbox_id": self.lockbox_id,
                "bundle_digest": self.bundle_digest,
                "authorisation_digest": self.authorisation_digest,
                "grant_at_utc": self.grant_at_utc,
                "outcomes": [[o.market_id, o.winner_selection_id]
                             for o in sorted(self.outcomes, key=lambda o: o.market_id)],
            },
            sort_keys=True, separators=(",", ":"),
        )
        return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()

    def to_json(self) -> str:
        payload = {
            "lockbox_id": self.lockbox_id,
            "bundle_digest": self.bundle_digest,
            "authorisation_digest": self.authorisation_digest,
            "grant_at_utc": self.grant_at_utc,
            "outcomes": [{"market_id": o.market_id, "winner_selection_id": o.winner_selection_id}
                         for o in sorted(self.outcomes, key=lambda o: o.market_id)],
            "content_digest": self.content_digest(),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _fsync_path(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _durable_write(path: Path, data: str) -> None:
    """Write + fsync the file, then fsync its parent directory (durable single file)."""
    tmp = path.with_suffix(path.suffix + ".part")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)          # atomic within a directory
    _fsync_path(path.parent)


def _noop(_step: str) -> None:
    return None


def run_stage_a_extraction(
    *,
    registry: LockboxRegistry,
    lockbox_id: str,
    accessor: str,
    at: DualClockTimestamp,
    bundle_market_ids: frozenset[str],
    bundle_digest: str,
    authorisation_digest: str,
    read_outcomes: Callable[[], Sequence[MinimalOutcome]],
    burn_record_path: Path,
    artifact_path: Path,
    _fault: _FaultHook = _noop,
) -> ImmutableOutcomeArtifact:
    """Execute the one-time atomic extraction (requirement A ordering).

    ``read_outcomes`` is the ONLY raw-lockbox access and is invoked exactly once, strictly
    AFTER the burn is durable. Steps: validate → GATE-1 grant → **durable burn record** →
    read → validate → durable artifact. ``_fault(step)`` lets tests crash at a named step."""
    if burn_record_path.exists() or artifact_path.exists():
        raise StageAIncidentError(
            "a prior extraction state exists; use recover_stage_a, never a fresh run"
        )
    # (1) GATE-1 grant — logs+burns in the registry (in-memory). Raises if already burned.
    grant = registry.access(lockbox_id, accessor=accessor, purpose="GATE-M1-JUNE-TRANSFER",
                            gate_id=GATE_1_ID, at=at)
    # (2) DURABLE BURN RECORD — written and fsync'd BEFORE any outcome is read.
    burn_record = json.dumps({
        "lockbox_id": lockbox_id, "accessor": accessor, "gate_id": GATE_1_ID,
        "grant_at_utc": grant.at.wall_utc.isoformat(), "bundle_digest": bundle_digest,
        "authorisation_digest": authorisation_digest, "state": "OPENED_EXTRACTION_IN_PROGRESS",
    }, sort_keys=True, separators=(",", ":"))
    _durable_write(burn_record_path, burn_record)
    _fault("after_burn_record")
    # (3) THE ONE RAW READ — only now, with the burn already durable.
    outcomes = tuple(read_outcomes())
    _fault("after_raw_read")
    # (4) validate against the frozen bundle (count/uniqueness/join/schema)
    _validate_outcomes(outcomes, bundle_market_ids)
    artifact = ImmutableOutcomeArtifact(
        lockbox_id=lockbox_id, bundle_digest=bundle_digest,
        authorisation_digest=authorisation_digest, grant_at_utc=grant.at.wall_utc.isoformat(),
        outcomes=outcomes,
    )
    # (5) durable immutable artifact (temp → fsync → atomic rename)
    _durable_write(artifact_path, artifact.to_json())
    _fault("after_artifact")
    return artifact


def _validate_outcomes(outcomes: Sequence[MinimalOutcome], bundle_market_ids: frozenset[str]) -> None:
    ids = [o.market_id for o in outcomes]
    if len(ids) != len(set(ids)):
        raise StageAIncidentError("duplicate market ids in extracted outcomes")
    got = set(ids)
    if not got <= bundle_market_ids:
        raise StageAIncidentError(
            f"extracted outcomes outside the frozen bundle: {sorted(got - bundle_market_ids)[:5]}"
        )


def load_artifact(artifact_path: Path) -> ImmutableOutcomeArtifact:
    """Load + verify an immutable artifact from disk (digest self-check)."""
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    artifact = ImmutableOutcomeArtifact(
        lockbox_id=payload["lockbox_id"], bundle_digest=payload["bundle_digest"],
        authorisation_digest=payload["authorisation_digest"], grant_at_utc=payload["grant_at_utc"],
        outcomes=tuple(MinimalOutcome(o["market_id"], int(o["winner_selection_id"]))
                       for o in payload["outcomes"]),
    )
    if artifact.content_digest() != payload["content_digest"]:
        raise StageAIncidentError(f"artifact {artifact_path} failed its digest self-check")
    return artifact


def recover_stage_a(*, burn_record_path: Path, artifact_path: Path) -> ImmutableOutcomeArtifact:
    """Crash recovery. NEVER re-reads the raw lockbox.

    * final artifact present + digest-valid -> return it;
    * burn record present but no valid artifact -> STOP with StageAIncidentError (the lockbox is
      durably burned; a second raw access is forbidden — preserve the incident);
    * no burn record -> the lockbox was never durably opened; nothing to recover.
    """
    if artifact_path.exists():
        return load_artifact(artifact_path)          # complete: finalize by simply using it
    if burn_record_path.exists():
        raise StageAIncidentError(
            "durable burn record exists but no finalizable artifact: the June lockbox is spent "
            "and the outcome artifact is missing/incomplete. A second raw access is forbidden "
            "(SPEC-092). Preserve the incident; a new lockbox period is required."
        )
    raise StageAIncidentError(
        "no burn record and no artifact: the lockbox was never durably opened; run_stage_a_extraction"
    )


# ---------------------------------------------------------------------------------------------
# Requirement B — conditional Stage-B gating
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class M1PassAttestation:
    """Immutable proof that the frozen M1 evaluator returned PASS on this exact artifact. Only
    :func:`attest_m1_pass` can mint one, and only from a PASS verdict."""

    artifact_digest: str
    use_policy_digest: str
    m1_gate_version: str
    _token: object

    def content_digest(self) -> str:
        body = json.dumps({"artifact_digest": self.artifact_digest,
                           "use_policy_digest": self.use_policy_digest,
                           "m1_gate_version": self.m1_gate_version},
                          sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


_ATTEST_TOKEN = object()   # module-private; an attestation cannot be forged from outside


def attest_m1_pass(
    *, verdict: str, artifact: ImmutableOutcomeArtifact, use_policy_digest: str,
    m1_gate_version: str,
) -> M1PassAttestation:
    """Mint a PASS attestation — ONLY when verdict == 'PASS' and the use-policy digest is exact.
    Any other verdict (CONTINUE/FAIL_HARM/FAIL_FUTILITY/technical failure) refuses."""
    if verdict != "PASS":
        raise StageBUnreachableError(
            f"M1 verdict is {verdict!r}, not PASS: Stage B is structurally unreachable"
        )
    if use_policy_digest != JUNE_ARTIFACT_USE_POLICY_DIGEST:
        raise StageBUnreachableError("use-policy digest mismatch: Stage B unreachable")
    return M1PassAttestation(
        artifact_digest=artifact.content_digest(), use_policy_digest=use_policy_digest,
        m1_gate_version=m1_gate_version, _token=_ATTEST_TOKEN,
    )


def open_stage_b_reader(
    artifact: ImmutableOutcomeArtifact, *, use_policy_digest: str,
    m1_attestation: M1PassAttestation,
) -> tuple[MinimalOutcome, ...]:
    """Return the artifact's outcomes for Stage-B SPEC-032 development — ONLY with the exact
    use-policy digest AND a genuine PASS attestation bound to this artifact. Reads the artifact
    only; there is no raw-lockbox reference here. Any mismatch -> StageBUnreachableError."""
    if use_policy_digest != JUNE_ARTIFACT_USE_POLICY_DIGEST:
        raise StageBUnreachableError("Stage B requires the exact June use-policy digest")
    if not isinstance(m1_attestation, M1PassAttestation) or m1_attestation._token is not _ATTEST_TOKEN:
        raise StageBUnreachableError("Stage B requires a genuine M1 PASS attestation")
    if m1_attestation.use_policy_digest != JUNE_ARTIFACT_USE_POLICY_DIGEST:
        raise StageBUnreachableError("attestation carries a mismatched use-policy digest")
    if m1_attestation.artifact_digest != artifact.content_digest():
        raise StageBUnreachableError("attestation does not bind to this artifact")
    return tuple(sorted(artifact.outcomes, key=lambda o: o.market_id))
