"""Governed Betfair tennis OUTCOME extraction (founder decision 4, 2026-07-18).

Outcome extraction is AUTHORISED for the pre-June development scope and IMPLEMENTED here;
June lockbox outcomes remain structurally sealed. Three independent structural facts keep
June closed:

1. **Scope vocabulary** — :class:`OutcomeAccessScope` has exactly one member,
   ``PRE_JUNE_DEVELOPMENT``. A June opening is *unrepresentable*; adding a member is a
   governed change requiring a separate explicit founder authorisation
   (``specs/evidence/lockbox-june-2026-tennis-v1.yaml``).
2. **Sealed membership** — the extractor refuses any market_id in the sealed June
   membership (:func:`load_sealed_market_ids`, digest ``sha256:24df4bd2…``).
3. **Data-level scope check** — any observed ``marketTime`` on/after 2026-06-01 refuses
   even for a market absent from the membership list (the seal binds by data, not only by
   list).

Every extraction is BOUND to its experiment: the mandatory
:class:`OutcomeAccessAuthorisation` carries experiment_id and the model/feature/data
manifests plus the gate-spec version, and its content digest is stamped onto every
extracted outcome. An unregistered post-lockbox model requires a NEW lockbox period —
enforced at the ledger/gate layer; this module contributes the binding.

The unauthenticated module-level :func:`extract_match_outcome` continues to refuse
unconditionally — extraction exists ONLY behind an authorisation record.

This module maps a settlement pattern to an outcome ONLY when it is unambiguous
(exactly one WINNER on a CLOSED definition). Anything else — no CLOSED definition,
zero or multiple winners, removed/void patterns — REFUSES with a typed error rather
than guessing: tennis settlement semantics remain governed by SPEC-084 (which still
refuses) and are not re-invented here for training labels.

Import quarantine: ``l3_features``/``l4_pricing`` are forbidden from importing this
module (Makefile ``verify``), so pre-lockbox consumers cannot reach the winner.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import Enum, unique
from pathlib import Path

from sport_core.outcomes import ChoiceSetResolution

__all__ = [
    "JUNE_LOCKBOX_ID",
    "JUNE_M1_SEAL_AUTHORISATION_DIGEST",
    "OutcomeAccessScope",
    "OutcomeAccessAuthorisation",
    "OutcomeAccessNotAuthorisedError",
    "OutcomeScopeError",
    "JuneLockboxSealedError",
    "SealAuthorisationMismatchError",
    "OutcomeUndeterminedError",
    "ExtractedMatchOutcome",
    "TennisOutcomeExtractor",
    "extract_match_outcome",
    "load_sealed_market_ids",
]

JUNE_LOCKBOX_ID = "lockbox-june-2026-tennis-v1"
_SCOPE_BOUNDARY = "2026-06-01"  # ISO date; any marketTime on/after this is out of scope
_SEALED_MEMBERS_CSV = Path("docs/evidence/lockbox-june-2026-tennis/members.csv")

#: The digest of the ONE governed authorisation that may open June (Stage 2E;
#: specs/evidence/lockbox-june-2026-tennis-v2.yaml). A JUNE_M1_TRANSFER authorisation is valid
#: ONLY carrying exactly this seal digest; the v1 seal cannot authorise June, and no other
#: month/model/programme can reuse this scope (the extractor also binds the exact market set).
JUNE_M1_SEAL_AUTHORISATION_DIGEST = (
    "sha256:f552c7bfafd8432693a26d01519ffac29e1d81d7554901041553952b2ddb88c8"
)


class OutcomeAccessNotAuthorisedError(RuntimeError):
    """Raised by the unauthenticated path. Extraction exists only behind a validated
    :class:`OutcomeAccessAuthorisation`; there is no default and no override."""


class OutcomeScopeError(RuntimeError):
    """The requested extraction falls outside the authorised PRE_JUNE_DEVELOPMENT scope
    (observed marketTime on/after 2026-06-01)."""


class JuneLockboxSealedError(RuntimeError):
    """The market is a member of the sealed June-2026 lockbox (SPEC-092). Refused unless the
    authorisation is the ONE governed JUNE_M1_TRANSFER opening AND the market is in that
    authorisation's explicit authorised set."""


class SealAuthorisationMismatchError(RuntimeError):
    """A JUNE_M1_TRANSFER authorisation did not carry the exact governed v2 seal digest
    (:data:`JUNE_M1_SEAL_AUTHORISATION_DIGEST`). The June opening is bound to that one seal;
    no other seal, month, model or programme may reuse the scope."""


class OutcomeUndeterminedError(RuntimeError):
    """The stream does not carry an unambiguous settlement (no CLOSED definition, or an
    anomalous winner pattern). Unknown blocks; nothing is guessed (SPEC-082/084 spirit)."""


@unique
class OutcomeAccessScope(Enum):
    """The authorised outcome-access scopes. ``PRE_JUNE_DEVELOPMENT`` is the standing
    development scope. ``JUNE_M1_TRANSFER`` is the ONE governed June opening the founder
    authorised in Stage 2E (lockbox-june-2026-tennis-v2) — for the M1 external transfer only,
    bound to the exact v2 seal digest and an explicit market set. No generic
    JUNE/RESEARCH/MODEL/M2/ROI/unrestricted scope exists; adding one is a governed change."""

    PRE_JUNE_DEVELOPMENT = "PRE_JUNE_DEVELOPMENT"
    JUNE_M1_TRANSFER = "JUNE_M1_TRANSFER"


def _require_sha256(name: str, value: str) -> None:
    if not (value.startswith("sha256:") and len(value) == len("sha256:") + 64):
        raise ValueError(f"{name} must be 'sha256:<64 hex>', got {value!r}")


def _require_nonempty(name: str, value: str) -> None:
    if not value:
        raise ValueError(f"{name} must be non-empty")


@dataclass(frozen=True)
class OutcomeAccessAuthorisation:
    """The manifest-bound permission record every extraction carries (founder decision 4:
    'every opening is bound to the experiment, model, feature, data and gate manifests')."""

    scope: OutcomeAccessScope
    experiment_id: str
    model_manifest_sha256: str
    feature_manifest_sha256: str
    data_manifest_sha256: str
    gate_spec_version: str
    granted_by: str
    granted_on: date
    #: Required for JUNE_M1_TRANSFER (binds to the v2 seal), forbidden otherwise. Additive:
    #: defaults to None so every PRE_JUNE_DEVELOPMENT authorisation is unchanged.
    seal_authorisation_digest: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scope, OutcomeAccessScope):
            raise ValueError(f"scope must be an OutcomeAccessScope, got {self.scope!r}")
        _require_nonempty("experiment_id", self.experiment_id)
        _require_sha256("model_manifest_sha256", self.model_manifest_sha256)
        _require_sha256("feature_manifest_sha256", self.feature_manifest_sha256)
        _require_sha256("data_manifest_sha256", self.data_manifest_sha256)
        _require_nonempty("gate_spec_version", self.gate_spec_version)
        _require_nonempty("granted_by", self.granted_by)
        if self.scope is OutcomeAccessScope.JUNE_M1_TRANSFER:
            if self.seal_authorisation_digest is None:
                raise ValueError(
                    "a JUNE_M1_TRANSFER authorisation MUST carry the v2 seal_authorisation_digest"
                )
            _require_sha256("seal_authorisation_digest", self.seal_authorisation_digest)
        elif self.seal_authorisation_digest is not None:
            raise ValueError(
                f"only JUNE_M1_TRANSFER may carry a seal_authorisation_digest; "
                f"scope {self.scope.value} must not"
            )

    def content_digest(self) -> str:
        body = json.dumps(
            {
                "scope": self.scope.value,
                "experiment_id": self.experiment_id,
                "model_manifest_sha256": self.model_manifest_sha256,
                "feature_manifest_sha256": self.feature_manifest_sha256,
                "data_manifest_sha256": self.data_manifest_sha256,
                "gate_spec_version": self.gate_spec_version,
                "granted_by": self.granted_by,
                "granted_on": self.granted_on.isoformat(),
                "seal_authorisation_digest": self.seal_authorisation_digest,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ExtractedMatchOutcome:
    """An extracted, authorisation-stamped training/grading label. Only the unambiguous
    exactly-one-WINNER pattern is representable; everything else refused upstream."""

    market_id: str
    resolution: ChoiceSetResolution
    winner_selection_id: int
    runner_statuses: Mapping[int, str]
    settled_time: str | None
    authorisation_digest: str


def load_sealed_market_ids(path: Path = _SEALED_MEMBERS_CSV) -> frozenset[str]:
    """The sealed June membership (from the founder's seal manifest)."""
    with open(path, newline="", encoding="utf-8") as f:
        return frozenset(row["market_id"] for row in csv.DictReader(f))


class TennisOutcomeExtractor:
    """Authorised outcome extraction over a raw market stream, pre-June scope only."""

    def __init__(
        self,
        authorisation: OutcomeAccessAuthorisation,
        *,
        sealed_market_ids: frozenset[str],
        june_authorised_market_ids: frozenset[str] = frozenset(),
    ) -> None:
        if not isinstance(authorisation, OutcomeAccessAuthorisation):
            raise OutcomeAccessNotAuthorisedError(
                "tennis outcome extraction requires a validated OutcomeAccessAuthorisation"
            )
        if authorisation.scope is OutcomeAccessScope.JUNE_M1_TRANSFER:
            # The ONE governed June opening: bound to the exact v2 seal digest AND an explicit,
            # non-empty authorised market set. A wrong seal, or an empty set, refuses here.
            if authorisation.seal_authorisation_digest != JUNE_M1_SEAL_AUTHORISATION_DIGEST:
                raise SealAuthorisationMismatchError(
                    "JUNE_M1_TRANSFER requires the exact v2 seal digest "
                    f"{JUNE_M1_SEAL_AUTHORISATION_DIGEST!r}; the v1 seal cannot authorise June"
                )
            if not june_authorised_market_ids:
                raise ValueError(
                    "JUNE_M1_TRANSFER requires a non-empty june_authorised_market_ids set"
                )
        elif june_authorised_market_ids:
            # A non-June scope must never carry a June authorised set.
            raise ValueError(
                f"scope {authorisation.scope.value} must not carry june_authorised_market_ids"
            )
        self._auth = authorisation
        self._sealed = sealed_market_ids
        self._june_authorised = june_authorised_market_ids

    def extract(self, market_id: str, stream_lines: Iterable[str]) -> ExtractedMatchOutcome:
        june_open = (
            self._auth.scope is OutcomeAccessScope.JUNE_M1_TRANSFER
            and market_id in self._june_authorised
        )
        if market_id in self._sealed and not june_open:
            raise JuneLockboxSealedError(
                f"market {market_id} is sealed in {JUNE_LOCKBOX_ID}; June outcomes are "
                "inaccessible without the governed JUNE_M1_TRANSFER authorisation for exactly "
                "this market"
            )
        last_closed_runners: dict[int, str] | None = None
        settled_time: str | None = None
        for raw in stream_lines:
            line = raw.strip()
            if not line:
                continue
            msg = json.loads(line)
            for mc in msg.get("mc", []):
                if mc.get("id") != market_id:
                    continue
                md = mc.get("marketDefinition")
                if md is None:
                    continue
                market_time = md.get("marketTime")
                if (
                    isinstance(market_time, str)
                    and market_time[:10] >= _SCOPE_BOUNDARY
                    and not june_open
                ):
                    raise OutcomeScopeError(
                        f"market {market_id} has marketTime {market_time}, on/after "
                        f"{_SCOPE_BOUNDARY}: outside the authorised scope (the seal binds by "
                        "data, not only by membership list; only the governed JUNE_M1_TRANSFER "
                        "authorisation for this exact market may cross the boundary)"
                    )
                if md.get("status") == "CLOSED":
                    runners = md.get("runners") or []
                    last_closed_runners = {
                        int(r["id"]): str(r.get("status", "")) for r in runners if "id" in r
                    }
                    if isinstance(md.get("settledTime"), str):
                        settled_time = md["settledTime"]
        if last_closed_runners is None:
            raise OutcomeUndeterminedError(
                f"market {market_id}: stream carries no CLOSED market definition; "
                "settlement is unknown and unknown blocks"
            )
        winners = [sid for sid, st in last_closed_runners.items() if st == "WINNER"]
        if len(winners) != 1:
            raise OutcomeUndeterminedError(
                f"market {market_id}: anomalous settlement pattern (winners={winners}, "
                f"statuses={last_closed_runners}); tennis void/retirement semantics are "
                "governed by SPEC-084 and are not guessed here"
            )
        return ExtractedMatchOutcome(
            market_id=market_id,
            resolution=ChoiceSetResolution.WINNER_KNOWN,
            winner_selection_id=winners[0],
            runner_statuses=last_closed_runners,
            settled_time=settled_time,
            authorisation_digest=self._auth.content_digest(),
        )


def extract_match_outcome(*_args: object, **_kwargs: object) -> ExtractedMatchOutcome:
    """The unauthenticated path: always refuses. Extraction exists only via
    :class:`TennisOutcomeExtractor` constructed with a validated authorisation."""
    raise OutcomeAccessNotAuthorisedError(
        "tennis outcome extraction requires an OutcomeAccessAuthorisation bound to an "
        "experiment and its manifests; there is no unauthenticated path. June lockbox "
        f"outcomes remain sealed ({JUNE_LOCKBOX_ID})."
    )
