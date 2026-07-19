"""Founder-authorised governed June Stage-A RECOVERY (Incident Option B, 2026-07-19; SPEC-092).

This module is a SEPARATELY GOVERNED, SINGLE-USE access to the founder-retained June corpus. It
never claims the first burn did not occur: the original burn record stays immutable, its spent
token is never reused, and every artifact this module produces is digest-bound to the recovery
authorisation AND the original burn record (the linkage is part of the content digest).

The driver correction the incident demanded lives here: a legitimate per-market undetermined
settlement (void/cancelled, no winner, multiple winners, never-closed) becomes an EXPLICIT
:class:`RecoveryExclusion` in the denominator — never a batch abort and never a fabricated
winner — while a malformed, conflicting, or integrity-invalid market still stops the batch with
a typed :class:`RecoveryIntegrityError`. Winners come ONLY from the governed
:class:`~l8_evidence.tennis_outcomes.TennisOutcomeExtractor`; this module never derives one.

State machine (crash-safe; proven by fault-injection tests):
  verify everything -> durable RECOVERY_ACCESS_IN_PROGRESS (fsync) -> the ONE raw read ->
  validate -> temp artifact (fsync) -> atomic rename -> durable RECOVERY_COMPLETED.
:func:`resume_stage_a_recovery` finalizes an already-complete artifact WITHOUT any corpus access
(it takes no corpus argument at all — structurally incapable of a raw read) and declares a typed
incident for every state whose repair would need one. A second recovery attempt is refused.
"""
from __future__ import annotations

import bz2
import hashlib
import json
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from l8_evidence.june_m1_harness import FrozenPrediction
from l8_evidence.june_stage_a_driver import (
    build_extractor,
    build_june_authorisation,
    bundle_market_ids,
)
from l8_evidence.june_stage_a_extraction import MinimalOutcome, _durable_write, _fsync_path
from l8_evidence.prediction_snapshots import DualClockTimestamp
from l8_evidence.tennis_outcomes import OutcomeUndeterminedError, TennisOutcomeExtractor

__all__ = [
    "RecoveryIntegrityError",
    "RecoveryIncidentError",
    "RecoverySingleUseError",
    "RecoveryExclusion",
    "RecoveryOutcomeArtifact",
    "run_stage_a_recovery",
    "resume_stage_a_recovery",
    "load_recovery_artifact",
]

_LOCKBOX_ID = "lockbox-june-2026-tennis-v1"


class RecoveryIntegrityError(RuntimeError):
    """A manifest/digest mismatch, malformed market, wrong-market stream, missing stream, or
    duplicate bundle entry. The batch STOPS; nothing is guessed and no partial artifact exists."""


class RecoveryIncidentError(RuntimeError):
    """The recovery state machine reached a state whose repair would require another raw access
    (or was never started). A third access is forbidden; return to the founder."""


class RecoverySingleUseError(RuntimeError):
    """The single-use recovery authority is already consumed (completed record exists) or a
    prior partial state exists. A fresh recovery run is refused; use resume_stage_a_recovery."""


@dataclass(frozen=True)
class RecoveryExclusion:
    """An EXPLICIT exclusion: a bundle market whose June settlement is legitimately undetermined.
    Stays in the denominator; carries a canonical reason, its source stream identity and a
    compact settlement-pattern summary. It structurally cannot carry a winner."""

    market_id: str
    reason: str
    source: str
    settlement_summary: str


@dataclass(frozen=True)
class RecoveryOutcomeArtifact:
    """The single immutable artifact of the ONE recovery access: governed winner outcomes plus
    explicit exclusions, digest-bound to the recovery authorisation and the ORIGINAL burn record
    (the linkage participates in the content digest, so it cannot be silently dropped)."""

    lockbox_id: str
    bundle_digest: str
    recovery_authorisation_digest: str
    original_burn_record_digest: str
    grant_at_utc: str
    outcomes: tuple[MinimalOutcome, ...]
    exclusions: tuple[RecoveryExclusion, ...]

    def content_digest(self) -> str:
        body = json.dumps(
            {
                "lockbox_id": self.lockbox_id,
                "bundle_digest": self.bundle_digest,
                "recovery_authorisation_digest": self.recovery_authorisation_digest,
                "original_burn_record_digest": self.original_burn_record_digest,
                "grant_at_utc": self.grant_at_utc,
                "outcomes": [[o.market_id, o.winner_selection_id]
                             for o in sorted(self.outcomes, key=lambda o: o.market_id)],
                "exclusions": [[e.market_id, e.reason, e.source, e.settlement_summary]
                               for e in sorted(self.exclusions, key=lambda e: e.market_id)],
            },
            sort_keys=True, separators=(",", ":"),
        )
        return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()

    def to_json(self) -> str:
        payload = {
            "lockbox_id": self.lockbox_id,
            "bundle_digest": self.bundle_digest,
            "recovery_authorisation_digest": self.recovery_authorisation_digest,
            "original_burn_record_digest": self.original_burn_record_digest,
            "grant_at_utc": self.grant_at_utc,
            "outcomes": [{"market_id": o.market_id, "winner_selection_id": o.winner_selection_id}
                         for o in sorted(self.outcomes, key=lambda o: o.market_id)],
            "exclusions": [{"market_id": e.market_id, "reason": e.reason, "source": e.source,
                            "settlement_summary": e.settlement_summary}
                           for e in sorted(self.exclusions, key=lambda e: e.market_id)],
            "content_digest": self.content_digest(),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _noop(_step: str) -> None:
    return None


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def _require_file_digest(name: str, path: Path, expected: str) -> None:
    if not path.is_file():
        raise RecoveryIntegrityError(f"{name} missing: {path}")
    actual = _sha256_file(path)
    if actual != expected:
        raise RecoveryIntegrityError(f"{name} digest {actual} != expected {expected}")


def _verify_corpus_manifest(corpus_root: Path, manifest_path: Path, manifest_sha256: str) -> None:
    """Verify the COMPLETE retained-corpus checksum manifest: the manifest's own digest, then
    every listed file's existence and content hash. Any deviation is an integrity failure."""
    _require_file_digest("corpus checksum manifest", manifest_path, manifest_sha256)
    for lineno, raw in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or len(parts[0]) != 64:
            raise RecoveryIntegrityError(f"corpus manifest line {lineno} is malformed: {raw!r}")
        digest, rel = parts
        target = corpus_root / rel
        if not target.is_file():
            raise RecoveryIntegrityError(f"corpus file listed in manifest is missing: {rel}")
        if _sha256_file(target) != "sha256:" + digest:
            raise RecoveryIntegrityError(f"corpus file does not match its manifest digest: {rel}")


def _load_bundle(bundle_path: Path, bundle_sha256: str) -> tuple[FrozenPrediction, ...]:
    """Load + digest-verify a frozen prediction bundle; duplicate market ids are refused."""
    _require_file_digest("prediction bundle", bundle_path, bundle_sha256)
    preds: list[FrozenPrediction] = []
    for line in bundle_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            preds.append(FrozenPrediction(
                market_id=r["market_id"], tour=r["tour"], cohort=r["cohort"],
                prior_band=r["prior_band"], cluster_day=r["cluster_day"],
                competitor_designated=r["competitor_designated"],
                competitor_other=r["competitor_other"],
                selection_id_designated=int(r["selection_id_designated"]),
                selection_id_other=int(r["selection_id_other"]),
                p_raw_designated=float(r["p_raw_designated"]),
                p_cal_designated=float(r["p_cal_designated"]),
            ))
        except (ValueError, KeyError, TypeError) as exc:
            raise RecoveryIntegrityError(f"bundle line is malformed: {exc}") from exc
    ids = [p.market_id for p in preds]
    if len(ids) != len(set(ids)):
        raise RecoveryIntegrityError("duplicate market ids in the prediction bundle")
    return tuple(preds)


def _locate_streams(bundle: Sequence[FrozenPrediction],
                    streams_root: Path) -> tuple[tuple[str, Path], ...]:
    """Resolve each bundle market's .bz2 stream (sorted by market id). Missing -> integrity."""
    index: dict[str, Path] = {}
    for p in streams_root.rglob("*.bz2"):
        index.setdefault(p.stem, p)
    located: list[tuple[str, Path]] = []
    missing: list[str] = []
    for pred in sorted(bundle, key=lambda pr: pr.market_id):
        path = index.get(pred.market_id)
        (located.append((pred.market_id, path)) if path is not None
         else missing.append(pred.market_id))
    if missing:
        raise RecoveryIntegrityError(
            f"{len(missing)} bundle market(s) have no stream, e.g. {missing[:3]}")
    return tuple(located)


def _settlement_summary(lines: Sequence[str], market_id: str) -> tuple[bool, bool, dict[str, int]]:
    """Compact deterministic summary of the buffered stream for the EXCLUSION record only
    (winners are never derived here): (saw_target_mc, saw_closed, last-CLOSED status counts)."""
    saw_target = False
    saw_closed = False
    counts: dict[str, int] = {}
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        msg = json.loads(line)
        for mc in msg.get("mc", []):
            if mc.get("id") != market_id:
                continue
            saw_target = True
            md = mc.get("marketDefinition")
            if md is None:
                continue
            if md.get("status") == "CLOSED":
                saw_closed = True
                counts = {}
                for r in md.get("runners") or []:
                    if "id" in r:
                        st = str(r.get("status", ""))
                        counts[st] = counts.get(st, 0) + 1
    return saw_target, saw_closed, counts


def _classify_exclusion(lines: Sequence[str], market_id: str, source: str) -> RecoveryExclusion:
    """Map a governed OutcomeUndeterminedError refusal to its canonical explicit exclusion."""
    saw_target, saw_closed, counts = _settlement_summary(lines, market_id)
    if not saw_target:
        raise RecoveryIntegrityError(
            f"stream {source} never references market {market_id}: wrong or corrupt stream file")
    n_winners = counts.get("WINNER", 0)
    total = sum(counts.values())
    if not saw_closed:
        reason = "UNDETERMINED_SETTLEMENT:NO_CLOSED_DEFINITION"
    elif n_winners == 1:
        # exactly-one-winner is the governed extractor's SETTLED pattern: extraction refused yet
        # the same buffered data classifies as settled — a conflict, never an exclusion.
        raise RecoveryIntegrityError(
            f"stream {source}: extraction and classification conflict for market {market_id} "
            "(single-winner pattern reached the exclusion classifier)")
    elif n_winners > 1:
        reason = "UNDETERMINED_SETTLEMENT:MULTIPLE_WINNERS"
    elif total > 0 and counts.get("REMOVED", 0) == total:
        # n_winners == 0 is guaranteed here (the two branches above cover >= 1).
        reason = "UNDETERMINED_SETTLEMENT:BOTH_RUNNERS_REMOVED"
    else:
        reason = "UNDETERMINED_SETTLEMENT:NO_WINNER"
    summary = "closed=" + ("yes" if saw_closed else "no") + " statuses={" + ",".join(
        f"{k}:{v}" for k, v in sorted(counts.items())) + "}"
    return RecoveryExclusion(market_id=market_id, reason=reason, source=source,
                             settlement_summary=summary)


def read_market_outcome_or_exclusion(
    extractor: TennisOutcomeExtractor, market_id: str, path: Path,
) -> MinimalOutcome | RecoveryExclusion:
    """Read ONE market's stream exactly once. A governed winner comes ONLY from the extractor;
    a legitimate undetermined settlement becomes an explicit exclusion; anything malformed or
    integrity-invalid raises RecoveryIntegrityError and stops the batch."""
    try:
        with bz2.open(path, "rt", encoding="utf-8") as fh:
            lines = fh.readlines()
    except (OSError, EOFError, ValueError) as exc:
        raise RecoveryIntegrityError(f"cannot read stream {path.name}: {exc}") from exc
    try:
        outcome = extractor.extract(market_id, lines)
        return MinimalOutcome(market_id, outcome.winner_selection_id)
    except OutcomeUndeterminedError:
        return _classify_exclusion(lines, market_id, path.name)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise RecoveryIntegrityError(f"malformed stream {path.name}: {exc}") from exc


def run_stage_a_recovery(
    *,
    bundle_path: Path,
    bundle_sha256: str,
    corpus_root: Path,
    corpus_manifest_path: Path,
    corpus_manifest_sha256: str,
    streams_root: Path,
    m1_manifest_path: Path,
    m1_manifest_sha256: str,
    original_burn_record_path: Path,
    original_burn_record_sha256: str,
    incident_record_path: Path,
    incident_record_sha256: str,
    recovery_authorisation_path: Path,
    sealed_market_ids: frozenset[str],
    model_manifest_sha256: str,
    feature_manifest_sha256: str,
    data_manifest_sha256: str,
    granted_on: date,
    at: DualClockTimestamp,
    in_progress_path: Path,
    artifact_path: Path,
    completed_path: Path,
    _fault: Callable[[str], None] = _noop,
) -> RecoveryOutcomeArtifact:
    """Execute the ONE governed recovery access (founder authorisation june-stage-a-recovery-v1).

    Every verification runs BEFORE any durable state, so a refusal here does not consume the
    single-use authority. The raw read happens exactly once, strictly after the durable
    RECOVERY_ACCESS_IN_PROGRESS record. ``_fault(step)`` lets tests crash at a named step."""
    # (0) single-use guard: any prior durable recovery state refuses a FRESH run.
    if completed_path.exists() or artifact_path.exists() or in_progress_path.exists():
        raise RecoverySingleUseError(
            "prior recovery state exists; the recovery authority is single-use — "
            "use resume_stage_a_recovery, never a second recovery run")
    # (1) complete raw-corpus checksum manifest.
    _verify_corpus_manifest(corpus_root, corpus_manifest_path, corpus_manifest_sha256)
    # (2) frozen prediction bundle (digest + schema + uniqueness).
    bundle = _load_bundle(bundle_path, bundle_sha256)
    # (3) M1 prospective manifest.
    _require_file_digest("M1 manifest", m1_manifest_path, m1_manifest_sha256)
    # (4) the governed authorisation binds the v2 seal digest at construction (below); the
    #     use-policy digest is enforced by the Stage-B gate, which is unchanged by recovery.
    # (5) the original incident record — present and digest-exact (linkage integrity).
    _require_file_digest("original burn record", original_burn_record_path,
                         original_burn_record_sha256)
    _require_file_digest("incident record", incident_record_path, incident_record_sha256)
    if not recovery_authorisation_path.is_file():
        raise RecoveryIntegrityError(
            f"recovery authorisation missing: {recovery_authorisation_path}")
    authorisation_digest = _sha256_file(recovery_authorisation_path)
    # (6) governed extractor + stream resolution (outcome-blind), still before durable state.
    auth = build_june_authorisation(
        model_manifest_sha256=model_manifest_sha256,
        feature_manifest_sha256=feature_manifest_sha256,
        data_manifest_sha256=data_manifest_sha256, granted_on=granted_on)
    extractor = build_extractor(auth, sealed_market_ids=sealed_market_ids, bundle=bundle)
    streams = _locate_streams(bundle, streams_root)
    _fault("before_in_progress")
    # (7) durable RECOVERY_ACCESS_IN_PROGRESS — fsync'd BEFORE any raw read.
    _durable_write(in_progress_path, json.dumps({
        "state": "RECOVERY_ACCESS_IN_PROGRESS", "lockbox_id": _LOCKBOX_ID,
        "recovery_authorisation_digest": authorisation_digest,
        "original_burn_record_digest": original_burn_record_sha256,
        "bundle_digest": bundle_sha256, "grant_at_utc": at.wall_utc.isoformat(),
    }, sort_keys=True, separators=(",", ":")))
    _fault("after_in_progress")
    # (8) THE ONE RAW READ — each authorised market exactly once, in sorted market-id order.
    outcomes: list[MinimalOutcome] = []
    exclusions: list[RecoveryExclusion] = []
    for market_id, path in streams:
        result = read_market_outcome_or_exclusion(extractor, market_id, path)
        (outcomes.append(result) if isinstance(result, MinimalOutcome)
         else exclusions.append(result))
    _fault("after_raw_read")
    # (9)/(10) validate the exact denominator partition: outcomes + exclusions == bundle.
    got = [o.market_id for o in outcomes] + [e.market_id for e in exclusions]
    if len(got) != len(set(got)):
        raise RecoveryIntegrityError("duplicate market ids across outcomes/exclusions")
    if set(got) != bundle_market_ids(bundle):
        raise RecoveryIntegrityError(
            "outcomes + exclusions do not partition the frozen bundle exactly")
    artifact = RecoveryOutcomeArtifact(
        lockbox_id=_LOCKBOX_ID, bundle_digest=bundle_sha256,
        recovery_authorisation_digest=authorisation_digest,
        original_burn_record_digest=original_burn_record_sha256,
        grant_at_utc=at.wall_utc.isoformat(),
        outcomes=tuple(outcomes), exclusions=tuple(exclusions),
    )
    # (11) temp artifact (fsync) -> atomic rename -> durable completion marker.
    tmp = artifact_path.with_suffix(artifact_path.suffix + ".part")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(artifact.to_json())
        fh.flush()
        os.fsync(fh.fileno())
    _fault("after_temp_artifact")
    os.replace(tmp, artifact_path)
    _fsync_path(artifact_path.parent)
    _fault("after_final_artifact")
    # (12) mark the single-use recovery access completed.
    _durable_write(completed_path, json.dumps({
        "state": "RECOVERY_COMPLETED", "artifact_digest": artifact.content_digest(),
        "grant_at_utc": at.wall_utc.isoformat(),
    }, sort_keys=True, separators=(",", ":")))
    # (13) the raw corpus is never reopened after finalization (enforced by the single-use
    #      guard above and by resume_stage_a_recovery's corpus-free signature).
    return artifact


def load_recovery_artifact(path: Path) -> RecoveryOutcomeArtifact:
    """Load + digest-self-check a recovery artifact. Corrupt or mismatched -> incident."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        artifact = RecoveryOutcomeArtifact(
            lockbox_id=payload["lockbox_id"], bundle_digest=payload["bundle_digest"],
            recovery_authorisation_digest=payload["recovery_authorisation_digest"],
            original_burn_record_digest=payload["original_burn_record_digest"],
            grant_at_utc=payload["grant_at_utc"],
            outcomes=tuple(MinimalOutcome(o["market_id"], int(o["winner_selection_id"]))
                           for o in payload["outcomes"]),
            exclusions=tuple(RecoveryExclusion(e["market_id"], e["reason"], e["source"],
                                               e["settlement_summary"])
                             for e in payload["exclusions"]),
        )
        stored = payload["content_digest"]
    except (ValueError, KeyError, TypeError) as exc:
        raise RecoveryIncidentError(f"recovery artifact {path} is unreadable: {exc}") from exc
    if artifact.content_digest() != stored:
        raise RecoveryIncidentError(f"recovery artifact {path} failed its digest self-check")
    return artifact


def resume_stage_a_recovery(
    *, in_progress_path: Path, artifact_path: Path, completed_path: Path,
) -> RecoveryOutcomeArtifact:
    """Crash recovery for the recovery access. Takes NO corpus argument — it is structurally
    incapable of a raw read. Finalizes only a complete, digest-valid artifact; every other state
    is a typed incident (a third access is forbidden — return to the founder)."""
    tmp = artifact_path.with_suffix(artifact_path.suffix + ".part")
    if artifact_path.exists():
        artifact = load_recovery_artifact(artifact_path)      # digest-valid or incident
        if not completed_path.exists():
            _durable_write(completed_path, json.dumps({
                "state": "RECOVERY_COMPLETED", "artifact_digest": artifact.content_digest(),
                "grant_at_utc": artifact.grant_at_utc,
            }, sort_keys=True, separators=(",", ":")))
        return artifact
    if tmp.exists():
        # A COMPLETE temporary artifact may be finalized without any raw access; a torn or
        # invalid one may not be treated as final.
        try:
            payload = json.loads(tmp.read_text(encoding="utf-8"))
            candidate = RecoveryOutcomeArtifact(
                lockbox_id=payload["lockbox_id"], bundle_digest=payload["bundle_digest"],
                recovery_authorisation_digest=payload["recovery_authorisation_digest"],
                original_burn_record_digest=payload["original_burn_record_digest"],
                grant_at_utc=payload["grant_at_utc"],
                outcomes=tuple(MinimalOutcome(o["market_id"], int(o["winner_selection_id"]))
                               for o in payload["outcomes"]),
                exclusions=tuple(RecoveryExclusion(e["market_id"], e["reason"], e["source"],
                                                   e["settlement_summary"])
                                 for e in payload["exclusions"]),
            )
            if candidate.content_digest() != payload["content_digest"]:
                raise RecoveryIncidentError("temporary artifact digest mismatch")
        except RecoveryIncidentError:
            raise RecoveryIncidentError(
                "temporary recovery artifact is incomplete or corrupt; it must not be finalized "
                "and a third raw access is forbidden — return to the founder") from None
        except (ValueError, KeyError, TypeError) as exc:
            raise RecoveryIncidentError(
                "temporary recovery artifact is incomplete or corrupt; it must not be finalized "
                f"and a third raw access is forbidden — return to the founder ({exc})") from exc
        os.replace(tmp, artifact_path)
        _fsync_path(artifact_path.parent)
        _durable_write(completed_path, json.dumps({
            "state": "RECOVERY_COMPLETED", "artifact_digest": candidate.content_digest(),
            "grant_at_utc": candidate.grant_at_utc,
        }, sort_keys=True, separators=(",", ":")))
        return candidate
    if in_progress_path.exists():
        raise RecoveryIncidentError(
            "recovery access is durably in progress with no finalizable artifact: the single-use "
            "authority is consumed and a third raw access is forbidden — return to the founder")
    raise RecoveryIncidentError(
        "no durable recovery state exists: the recovery was never started; a fresh "
        "run_stage_a_recovery is required")
