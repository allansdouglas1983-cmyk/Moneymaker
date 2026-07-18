"""Stage 2E — the exact Stage-A burn DRIVER (wiring only; the burn is founder-gated).

This module assembles the one-time June M1 read from already-verified parts. Importing it, and
everything except :func:`run_stage_a_burn`, is outcome-blind: loading the frozen bundle, building
the governed authorisation, and constructing the extractor touch NO outcome. :func:`run_stage_a_burn`
is the ONLY function that reads June outcomes, and it does so exclusively through the governed
:class:`~l8_evidence.tennis_outcomes.TennisOutcomeExtractor` (JUNE_M1_TRANSFER scope) via the
atomic :func:`~l8_evidence.june_stage_a_extraction.run_stage_a_extraction` — durable burn before
read, one immutable artifact. It is invoked only under an explicit founder ``BURN JUNE STAGE A``.
"""
from __future__ import annotations

import bz2
import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from l8_evidence.june_m1_harness import FrozenPrediction
from l8_evidence.june_stage_a_extraction import MinimalOutcome
from l8_evidence.tennis_outcomes import (
    JUNE_M1_SEAL_AUTHORISATION_DIGEST,
    OutcomeAccessAuthorisation,
    OutcomeAccessScope,
    TennisOutcomeExtractor,
)

__all__ = [
    "BUNDLE_PATH",
    "BUNDLE_SHA256",
    "load_frozen_bundle",
    "bundle_market_ids",
    "build_june_authorisation",
    "build_extractor",
    "read_market_outcome",
]

BUNDLE_PATH = Path("docs/evidence/stage2e-june-m1-bundle/JUNE_M1_PREDICTION_BUNDLE.jsonl")
#: file-bytes sha256 of the frozen, verified bundle (Stage 2E §4 bundle).
BUNDLE_SHA256 = "sha256:37e43f64a65fd89ac3ba03263f224f2c23acb9ee5a93f995367a951bc2906347"

_M1_GATE_VERSION = "probability-m1"
_JUNE_EXPERIMENT_ID = "GATE-M1-JUNE-TRANSFER"


def load_frozen_bundle(path: Path = BUNDLE_PATH) -> tuple[FrozenPrediction, ...]:
    """Load + digest-verify the frozen bundle into FrozenPredictions (outcome-blind)."""
    raw = path.read_bytes()
    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    if digest != BUNDLE_SHA256:
        raise ValueError(f"bundle digest {digest} != expected {BUNDLE_SHA256}")
    preds = []
    for line in raw.decode("utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        preds.append(FrozenPrediction(
            market_id=r["market_id"], tour=r["tour"], cohort=r["cohort"],
            prior_band=r["prior_band"], cluster_day=r["cluster_day"],
            competitor_designated=r["competitor_designated"], competitor_other=r["competitor_other"],
            selection_id_designated=int(r["selection_id_designated"]),
            selection_id_other=int(r["selection_id_other"]),
            p_raw_designated=float(r["p_raw_designated"]),
            p_cal_designated=float(r["p_cal_designated"]),
        ))
    return tuple(preds)


def bundle_market_ids(bundle: Sequence[FrozenPrediction]) -> frozenset[str]:
    return frozenset(p.market_id for p in bundle)


def build_june_authorisation(
    *, model_manifest_sha256: str, feature_manifest_sha256: str, data_manifest_sha256: str,
    granted_on: date,
) -> OutcomeAccessAuthorisation:
    """The one governed June-M1 authorisation, bound to the v2 seal (outcome-blind)."""
    return OutcomeAccessAuthorisation(
        scope=OutcomeAccessScope.JUNE_M1_TRANSFER, experiment_id=_JUNE_EXPERIMENT_ID,
        model_manifest_sha256=model_manifest_sha256,
        feature_manifest_sha256=feature_manifest_sha256,
        data_manifest_sha256=data_manifest_sha256, gate_spec_version=_M1_GATE_VERSION,
        granted_by="founder", granted_on=granted_on,
        seal_authorisation_digest=JUNE_M1_SEAL_AUTHORISATION_DIGEST,
    )


def build_extractor(
    authorisation: OutcomeAccessAuthorisation, *, sealed_market_ids: frozenset[str],
    bundle: Sequence[FrozenPrediction],
) -> TennisOutcomeExtractor:
    """The governed extractor scoped to EXACTLY the 1,213 bundle markets (outcome-blind)."""
    return TennisOutcomeExtractor(
        authorisation, sealed_market_ids=sealed_market_ids,
        june_authorised_market_ids=bundle_market_ids(bundle),
    )


@dataclass(frozen=True)
class _MarketStream:
    market_id: str
    path: Path


def read_market_outcome(extractor: TennisOutcomeExtractor, stream: _MarketStream) -> MinimalOutcome:
    """Extract ONE market's winner via the governed extractor (this reads a June outcome).

    Called only inside the founder-gated burn. Decompresses the market's .bz2 stream and lets
    the governed extractor apply the seal + winner logic."""
    with bz2.open(stream.path, "rt", encoding="utf-8") as fh:
        outcome = extractor.extract(stream.market_id, fh)
    return MinimalOutcome(stream.market_id, outcome.winner_selection_id)
