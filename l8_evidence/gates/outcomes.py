"""Gate outcomes and results (SPEC-093).

Every evidence gate returns one of FOUR outcomes (§10.1) and never a boolean: both the
outcome enum and the result refuse truth-testing by construction, so a verdict can never
silently drive an ``if``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import NoReturn

EVALUATOR_VERSION = "gate-evaluator-v1"


class GateEvaluationError(Exception):
    """Base for every evaluator-side error. An error is never a verdict (CLI exit 4)."""


class GateOutcome(Enum):
    """The four §10.1 verdicts. "Not passed" is not "disproved"."""

    PASS = "PASS"
    CONTINUE = "CONTINUE"
    FAIL_HARM = "FAIL_HARM"
    FAIL_FUTILITY = "FAIL_FUTILITY"

    def __bool__(self) -> NoReturn:
        raise TypeError("a gate outcome is four-valued, never a boolean (SPEC-093)")


@dataclass(frozen=True)
class GateResult:
    """A verdict bound to its full provenance (ADR 0011 decision 9)."""

    gate_id: str
    experiment_id: str
    outcome: GateOutcome
    reasons: tuple[str, ...]
    data_manifest: str
    model_manifest: str
    spec_version: str
    spec_digest: str
    facts_digest: str
    evaluator_version: str
    as_of: date

    def __bool__(self) -> NoReturn:
        raise TypeError("a gate result is four-valued, never a boolean (SPEC-093)")

    def canonical_json(self) -> str:
        """Sorted-key, compact JSON: identical inputs serialise byte-identically."""
        payload = {
            "gate_id": self.gate_id,
            "experiment_id": self.experiment_id,
            "outcome": self.outcome.value,
            "reasons": list(self.reasons),
            "data_manifest": self.data_manifest,
            "model_manifest": self.model_manifest,
            "spec_version": self.spec_version,
            "spec_digest": self.spec_digest,
            "facts_digest": self.facts_digest,
            "evaluator_version": self.evaluator_version,
            "as_of": self.as_of.isoformat(),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))
