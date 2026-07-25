"""V0 release — governed outcome append + probability grading (red tests first).

Grading joins a governed sporting outcome to an existing immutable pre-match record and
scores the probabilities that were recorded BEFORE the match: log loss and Brier for the
market probability (the final V0 probability) and, separately, for the F2-v1 diagnostic.
The pre-match record is never rewritten. There is NO stake, EV, ROI, P&L or CLV anywhere —
this is probability quality only.
"""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from assistant_v0 import grading as G
from assistant_v0.shadow_ledger import PreMatchRecord, ShadowLedger, ShadowLedgerError


def _rec(record_id: str = "r1", *, p_market_a: float | None = 0.6,
         p_f2_a: float | None = 0.7, status: str = "MARKET_ONLY") -> PreMatchRecord:
    return PreMatchRecord(
        record_id=record_id, snapshot_digest="sha256:snap", tour="ATP",
        competitor_a="A Player", competitor_b="B Player",
        market_probability_a=p_market_a,
        market_probability_b=None if p_market_a is None else 1.0 - p_market_a,
        f2_probability_a=p_f2_a,
        f2_probability_b=None if p_f2_a is None else 1.0 - p_f2_a,
        status=status, reason_codes=("MARKET_PRICE_AVAILABLE",),
        data_digest="sha256:d", policy_digest="sha256:p", model_view_digest="sha256:m",
        created_at_ms=1000)


def test_grade_scores_market_and_model_against_winner_a() -> None:
    app = G.grade_settlement(_rec(), winner="A")
    assert app.scored is True
    assert app.exclusion_reason is None
    assert app.market_log_loss == pytest.approx(-math.log(0.6))
    assert app.market_brier == pytest.approx((0.6 - 1.0) ** 2)
    assert app.model_log_loss == pytest.approx(-math.log(0.7))
    assert app.model_brier == pytest.approx((0.7 - 1.0) ** 2)


def test_grade_scores_against_winner_b_using_the_b_probability() -> None:
    app = G.grade_settlement(_rec(), winner="B")
    assert app.market_log_loss == pytest.approx(-math.log(0.4))
    assert app.market_brier == pytest.approx((0.6 - 0.0) ** 2)
    assert app.model_log_loss == pytest.approx(-math.log(0.3))


def test_missing_market_probability_is_excluded_not_invented() -> None:
    app = G.grade_settlement(_rec(p_market_a=None, status="MARKET_UNAVAILABLE"), winner="A")
    assert app.scored is False
    assert app.market_log_loss is None and app.market_brier is None
    assert app.exclusion_reason == G.NO_MARKET_PROBABILITY


def test_missing_f2_diagnostic_scores_market_only() -> None:
    app = G.grade_settlement(_rec(p_f2_a=None), winner="A")
    assert app.scored is True
    assert app.market_log_loss is not None
    assert app.model_log_loss is None and app.model_brier is None


def test_unknown_winner_token_refuses() -> None:
    with pytest.raises(G.GradingError):
        G.grade_settlement(_rec(), winner="C")
    with pytest.raises(G.GradingError):
        G.grade_settlement(_rec(), winner="a")          # exact token only


def test_settlement_append_never_alters_the_pre_match_record(tmp_path: Path) -> None:
    led = ShadowLedger(tmp_path / "l.jsonl")
    rec = _rec()
    led.append_pre_match(rec)
    before = led.pre_match_by_id("r1")
    G.settle_in_ledger(led, record_id="r1", winner="A")
    after = led.pre_match_by_id("r1")
    assert before == after == rec
    assert not hasattr(after, "winner")


def test_settling_an_unknown_record_refuses(tmp_path: Path) -> None:
    led = ShadowLedger(tmp_path / "l.jsonl")
    with pytest.raises(ShadowLedgerError):
        G.settle_in_ledger(led, record_id="nope", winner="A")


def test_double_settlement_refuses(tmp_path: Path) -> None:
    led = ShadowLedger(tmp_path / "l.jsonl")
    led.append_pre_match(_rec())
    G.settle_in_ledger(led, record_id="r1", winner="A")
    with pytest.raises(ShadowLedgerError):
        G.settle_in_ledger(led, record_id="r1", winner="B")


def test_ledger_summary_aggregates_only_scored_records(tmp_path: Path) -> None:
    led = ShadowLedger(tmp_path / "l.jsonl")
    led.append_pre_match(_rec("r1", p_market_a=0.6, p_f2_a=0.7))
    led.append_pre_match(_rec("r2", p_market_a=0.5, p_f2_a=None))
    led.append_pre_match(_rec("r3", p_market_a=None, p_f2_a=None,
                              status="MARKET_UNAVAILABLE"))
    G.settle_in_ledger(led, record_id="r1", winner="A")
    G.settle_in_ledger(led, record_id="r2", winner="B")
    G.settle_in_ledger(led, record_id="r3", winner="A")
    s = G.summarise_ledger(led)
    assert s["pre_match_records"] == 3
    assert s["settled"] == 3
    assert s["scored"] == 2                                     # r3 excluded (no probability)
    assert s["excluded"] == 1
    assert s["exclusions"] == {G.NO_MARKET_PROBABILITY: 1}
    assert s["market_log_loss_mean"] == pytest.approx(
        (-math.log(0.6) + -math.log(0.5)) / 2)
    assert s["market_brier_mean"] == pytest.approx(((0.6 - 1) ** 2 + (0.5 - 0) ** 2) / 2)
    assert s["model_scored"] == 1                               # only r1 carried an F2 view
    assert s["model_log_loss_mean"] == pytest.approx(-math.log(0.7))


def test_market_excluded_but_f2_still_graded_separately() -> None:
    """The two views are scored independently: a missing market probability excludes the
    MARKET score without suppressing the F2 diagnostic score (and never substitutes it)."""
    app = G.grade_settlement(_rec(p_market_a=None, p_f2_a=0.7,
                                  status="MARKET_UNAVAILABLE"), winner="A")
    assert app.scored is False                       # 'scored' tracks the FINAL (market) view
    assert app.market_log_loss is None and app.market_brier is None
    assert app.exclusion_reason == G.NO_MARKET_PROBABILITY
    assert app.model_log_loss is not None            # F2 graded on its own terms
    assert app.model_brier is not None


def test_ledger_summary_of_empty_ledger_is_explicit_not_zero(tmp_path: Path) -> None:
    s = G.summarise_ledger(ShadowLedger(tmp_path / "l.jsonl"))
    assert s["pre_match_records"] == 0 and s["scored"] == 0
    assert s["market_log_loss_mean"] is None                    # no fabricated 0.0
    assert s["model_log_loss_mean"] is None


def test_summary_is_deterministic_and_carries_no_money_field(tmp_path: Path) -> None:
    led = ShadowLedger(tmp_path / "l.jsonl")
    led.append_pre_match(_rec())
    G.settle_in_ledger(led, record_id="r1", winner="A")
    assert G.summarise_ledger(led) == G.summarise_ledger(led)
    blob = repr(G.summarise_ledger(led)).lower()
    for banned in ("stake", "roi", "p&l", "pnl", "profit", "clv", "edge",
                   "expected_value", " ev", "bet"):
        assert banned not in blob


def test_grading_matches_an_independent_reference() -> None:
    """Independent literal reference for the two proper scores (Tier B numerical rule)."""
    for p, winner, label in ((0.62, "A", 1), (0.62, "B", 0), (0.31, "A", 1), (0.9, "B", 0)):
        app = G.grade_settlement(_rec(p_market_a=p, p_f2_a=None), winner=winner)
        ref_ll = -(label * math.log(p) + (1 - label) * math.log(1 - p))
        ref_br = (p - label) ** 2
        assert app.market_log_loss == pytest.approx(ref_ll)
        assert app.market_brier == pytest.approx(ref_br)
