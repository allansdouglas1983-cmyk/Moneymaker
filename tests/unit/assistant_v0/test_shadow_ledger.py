"""STAGE3-0003 §10/§12 — V0 append-only shadow ledger (red tests first).

Append-only. A pre-match record stores the snapshot digest, market/model probabilities,
status, reason codes and digests — and NO outcome/winner/P&L field (structurally). After
settlement a SEPARATE append may add a governed sporting outcome + log loss + Brier +
exclusion, referencing the pre-match record; the original pre-match record is never
rewritten. No shadow ROI or P&L; no hypothetical bet. Scoring math is tested with synthetic
0/1 labels — the governed outcome path is NOT invoked here.
"""
from __future__ import annotations

import math

import pytest

from assistant_v0 import shadow_ledger as SL


def _pre(record_id: str = "r1") -> SL.PreMatchRecord:
    return SL.PreMatchRecord(
        record_id=record_id, snapshot_digest="sha256:aa", tour="ATP",
        competitor_a="A", competitor_b="B",
        market_probability_a=0.6, market_probability_b=0.4,
        f2_probability_a=None, f2_probability_b=None,
        status="MARKET_ONLY", reason_codes=("MARKET_PRICE_AVAILABLE", "RESEARCH_ONLY_NO_BET"),
        data_digest="sha256:d", policy_digest="sha256:p", model_view_digest="sha256:m",
        created_at_ms=1000,
    )


def test_pre_match_record_has_no_outcome_field() -> None:
    banned = {"winner", "outcome", "result", "won", "pnl", "profit", "loss", "roi", "clv",
              "ev", "stake", "bet", "settled"}
    fields = {f.name.lower() for f in SL.PreMatchRecord.__dataclass_fields__.values()}
    assert not (fields & banned), f"outcome/bet field present pre-match: {fields & banned}"


def test_settlement_append_has_no_roi_or_pnl_field() -> None:
    banned = {"roi", "pnl", "profit", "stake", "bet", "return_", "payout"}
    fields = {f.name.lower() for f in SL.SettlementAppend.__dataclass_fields__.values()}
    assert not (fields & banned), f"ROI/P&L/bet field present: {fields & banned}"


def test_ledger_is_append_only_no_update_or_delete() -> None:
    for forbidden in ("update", "delete", "remove", "rewrite", "set", "pop"):
        assert not hasattr(SL.ShadowLedger, forbidden)


def test_append_and_read_pre_match(tmp_path) -> None:
    led = SL.ShadowLedger(tmp_path / "ledger.jsonl")
    led.append_pre_match(_pre("r1"))
    got = led.pre_match_by_id("r1")
    assert got is not None and got.market_probability_a == 0.6


def test_duplicate_pre_match_id_refuses(tmp_path) -> None:
    led = SL.ShadowLedger(tmp_path / "ledger.jsonl")
    led.append_pre_match(_pre("r1"))
    with pytest.raises(SL.ShadowLedgerError):
        led.append_pre_match(_pre("r1"))


def test_settlement_for_unknown_record_refuses(tmp_path) -> None:
    led = SL.ShadowLedger(tmp_path / "ledger.jsonl")
    app = SL.SettlementAppend(record_id="nope", winner="A", scored=True,
                              market_log_loss=0.5, market_brier=0.16,
                              model_log_loss=None, model_brier=None, exclusion_reason=None)
    with pytest.raises(SL.ShadowLedgerError):
        led.append_settlement(app)


def test_settlement_append_does_not_modify_original(tmp_path) -> None:
    led = SL.ShadowLedger(tmp_path / "ledger.jsonl")
    led.append_pre_match(_pre("r1"))
    before = led.pre_match_by_id("r1")
    led.append_settlement(SL.SettlementAppend(
        record_id="r1", winner="A", scored=True, market_log_loss=0.5108, market_brier=0.16,
        model_log_loss=None, model_brier=None, exclusion_reason=None))
    after = led.pre_match_by_id("r1")
    assert before == after                        # original never rewritten
    assert led.settlement_by_id("r1") is not None


def test_log_loss_and_brier_math() -> None:
    # market said p_a = 0.6; competitor A won (label 1 for A)
    assert SL.log_loss(0.6, 1) == pytest.approx(-math.log(0.6))
    assert SL.brier(0.6, 1) == pytest.approx((0.6 - 1.0) ** 2)
    assert SL.log_loss(0.6, 0) == pytest.approx(-math.log(0.4))


def test_persistence_roundtrip_is_deterministic(tmp_path) -> None:
    p = tmp_path / "ledger.jsonl"
    led = SL.ShadowLedger(p)
    led.append_pre_match(_pre("r1"))
    led.append_pre_match(_pre("r2"))
    reread = SL.ShadowLedger(p)
    assert {r.record_id for r in reread.all_pre_match()} == {"r1", "r2"}
