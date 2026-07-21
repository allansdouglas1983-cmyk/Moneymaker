"""PERSONAL_TENNIS_ASSISTANT_V0 — append-only shadow ledger (STAGE3-0003 §10).

Append-only, immutable personal probability/operational-evidence ledger. A pre-match record
stores the manual-snapshot digest, the market and (optional) F2 diagnostic probabilities,
the status, reason codes and digests — and carries NO outcome / winner / P&L / bet field by
construction. After settlement a SEPARATE append records the governed sporting outcome and
the market/model proper scores (log loss, Brier), referencing the pre-match record; the
original pre-match record is never rewritten. There is NO shadow ROI or P&L, and no
hypothetical bet — the ledger's purpose in V0 is probability and operational evidence only.

The class exposes only append/read methods — no update/delete/rewrite API exists.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


class ShadowLedgerError(Exception):
    """An append violates the append-only ledger's integrity."""


@dataclass(frozen=True)
class PreMatchRecord:
    """Immutable pre-match record. NO outcome/winner/P&L/bet field is representable."""

    record_id: str
    snapshot_digest: str
    tour: str
    competitor_a: str
    competitor_b: str
    market_probability_a: float | None
    market_probability_b: float | None
    f2_probability_a: float | None
    f2_probability_b: float | None
    status: str
    reason_codes: tuple[str, ...]
    data_digest: str
    policy_digest: str
    model_view_digest: str
    created_at_ms: int


@dataclass(frozen=True)
class SettlementAppend:
    """Post-settlement append. Proper scores only — no ROI, no P&L, no stake, no bet."""

    record_id: str
    winner: str                 # governed sporting outcome (which competitor won)
    scored: bool
    market_log_loss: float | None
    market_brier: float | None
    model_log_loss: float | None
    model_brier: float | None
    exclusion_reason: str | None


def log_loss(p: float, label: int) -> float:
    """Binary log loss of probability ``p`` against a 0/1 ``label`` for that competitor."""
    if not 0.0 < p < 1.0:
        raise ShadowLedgerError(f"probability {p} must be in the open interval (0,1)")
    return -(label * math.log(p) + (1 - label) * math.log(1.0 - p))


def brier(p: float, label: int) -> float:
    """Brier score (squared error) of ``p`` against a 0/1 ``label``."""
    return (p - label) ** 2


class ShadowLedger:
    """Append-only JSONL ledger. Only append/read methods; no update/delete/rewrite."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._pre: dict[str, PreMatchRecord] = {}
        self._settle: dict[str, SettlementAppend] = {}
        if self._path.exists():
            self._load()

    def _load(self) -> None:
        for line in self._path.read_text().splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            kind = obj.pop("_kind")
            if kind == "pre_match":
                obj["reason_codes"] = tuple(obj["reason_codes"])
                rec = PreMatchRecord(**obj)
                self._pre[rec.record_id] = rec
            elif kind == "settlement":
                app = SettlementAppend(**obj)
                self._settle[app.record_id] = app

    def _append_line(self, kind: str, payload: dict[str, object]) -> None:
        payload = {"_kind": kind, **payload}
        with self._path.open("a") as fh:
            fh.write(json.dumps(payload, sort_keys=True) + "\n")

    def append_pre_match(self, rec: PreMatchRecord) -> None:
        if rec.record_id in self._pre:
            raise ShadowLedgerError(f"pre-match record {rec.record_id!r} already exists (append-only)")
        d = asdict(rec)
        d["reason_codes"] = list(rec.reason_codes)
        self._append_line("pre_match", d)
        self._pre[rec.record_id] = rec

    def append_settlement(self, app: SettlementAppend) -> None:
        if app.record_id not in self._pre:
            raise ShadowLedgerError(f"no pre-match record {app.record_id!r} to settle")
        if app.record_id in self._settle:
            raise ShadowLedgerError(f"settlement for {app.record_id!r} already exists (append-only)")
        self._append_line("settlement", asdict(app))
        self._settle[app.record_id] = app

    def pre_match_by_id(self, record_id: str) -> PreMatchRecord | None:
        return self._pre.get(record_id)

    def settlement_by_id(self, record_id: str) -> SettlementAppend | None:
        return self._settle.get(record_id)

    def all_pre_match(self) -> tuple[PreMatchRecord, ...]:
        return tuple(self._pre.values())
