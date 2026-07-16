"""§6.12 model lineage manifest (ADR 0012 decision 9).

Carries exactly the §6.12 field set. ``container_digest`` reuses the platform's single
environment-fingerprint definition (l1_reduce), fits are deterministic so ``random_seeds`` is
the empty tuple recorded explicitly, and the digest is canonical JSON → ``sha256:<hex>`` —
the exact format the gate evaluator's ``--model-manifest`` binding validates. The §6.12
live-build lineage rejection is a Phase-3 hook; the structure and digest exist now.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from l1_reduce.reducer import environment_digest


@dataclass(frozen=True)
class ModelManifest:
    """Immutable lineage record for one fitted model version (§6.11/§6.12)."""

    model_id: str
    training_data_manifest: str
    source_ids: tuple[str, ...]
    license_check_status: str
    feature_schema_hash: str
    code_commit: str
    gate_results: tuple[str, ...]
    approved_scope: str
    container_digest: str = field(default_factory=environment_digest)
    random_seeds: tuple[int, ...] = ()

    @property
    def digest(self) -> str:
        canonical = json.dumps(
            {
                "approved_scope": self.approved_scope,
                "code_commit": self.code_commit,
                "container_digest": self.container_digest,
                "feature_schema_hash": self.feature_schema_hash,
                "gate_results": list(self.gate_results),
                "license_check_status": self.license_check_status,
                "model_id": self.model_id,
                "random_seeds": list(self.random_seeds),
                "source_ids": list(self.source_ids),
                "training_data_manifest": self.training_data_manifest,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
