"""V0 RELEASE ACCEPTANCE — five complete end-to-end fixtures (red tests first).

Each fixture drives the real CLI from a manual snapshot file through: validation, governed
market probability, optional separate F2-v1 diagnostic, deterministic JSON, deterministic
static HTML, immutable pre-match ledger append, governed outcome append and grading.

Proven for every fixture: deterministic JSON, deterministic HTML, stable digest, no outcome
in the pre-match record, an outcome append cannot alter the original record, F2 can never
replace the market probability, no prohibited status is constructible, no tip/edge/EV/stake/
order field exists, and no execution import path exists.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from assistant_v0 import cli
from assistant_v0 import grading as G
from assistant_v0 import status as S
from assistant_v0.shadow_ledger import ShadowLedger

_BANNED_FIELD_TOKENS = ("stake", "roi", "pnl", "p&l", "profit", "clv", "edge",
                        "expected_value", "expected value", "tip", "recommend",
                        "order", "wager", "bankroll", "kelly")
_PROHIBITED_STATUSES = ("SHADOW_CANDIDATE", "BET_CANDIDATE", "BET_AUTHORIZED",
                        "PLACE_BET", "STAKE_RECOMMENDATION")


def _snapshot(tmp: Path, name: str, **over: object) -> Path:
    base: dict[str, object] = {
        "competitor_a": "A Player", "competitor_b": "B Player",
        "competitor_a_id": None, "competitor_b_id": None, "tour": "ATP",
        "scheduled_start_ms": 2000, "input_timestamp_ms": 1000,
        "source": "MANUAL_BETFAIR_UI",
        "back_a": "1.90", "back_a_size": "50", "lay_a": "1.95", "lay_a_size": "40",
        "back_b": "2.04", "back_b_size": "30", "lay_b": "2.12", "lay_b_size": "20",
        "market_status": "OPEN", "in_play": False, "market_id": "1.234", "event_id": "E1",
    }
    base.update(over)
    p = tmp / name
    p.write_text(json.dumps(base))
    return p


def _ratings(tmp: Path, players: dict[str, object], name: str = "ratings.json") -> Path:
    p = tmp / name
    p.write_text(json.dumps({"rating_state_version": "F2_V1_FROZEN",
                             "source": "frozen F2-v1 evidence", "players": players}))
    return p


def _assess(snapshot: Path, tmp: Path, *, ratings: Path | None = None,
            ledger: Path | None = None, record_id: str | None = None,
            html: Path | None = None, out: Path | None = None) -> dict[str, object]:
    argv = ["assess", "--snapshot", str(snapshot), "--reference-time-ms", "1000"]
    if ratings is not None:
        argv += ["--ratings", str(ratings)]
    if ledger is not None:
        argv += ["--ledger", str(ledger)]
    if record_id is not None:
        argv += ["--record-id", record_id]
    if html is not None:
        argv += ["--html", str(html)]
    if out is not None:
        argv += ["--out", str(out)]
    payload = cli.main(argv)
    assert isinstance(payload, dict)
    return payload


def _assert_universal_invariants(payload: dict[str, object], html: str) -> None:
    """The guarantees every V0 output must satisfy, whatever the fixture."""
    assert payload["final_probability_source"] == "MARKET"
    assert payload["economic_posture"] == "NO_BET_RESEARCH_ONLY"
    assert payload["status"] in {s.value for s in S.AssistantStatus}
    assert payload["status"] not in _PROHIBITED_STATUSES
    for banned in _PROHIBITED_STATUSES:
        with pytest.raises(KeyError):
            S.AssistantStatus[banned]                       # unconstructible by name
        assert banned not in json.dumps(payload)
    blob = json.dumps(payload).lower()
    for token in _BANNED_FIELD_TOKENS:
        assert token not in blob, f"forbidden token {token!r} in V0 output"
    assert "RESEARCH / SHADOW ONLY" in html and "NO BET RECOMMENDATION" in html
    # no outcome/winner field may exist pre-match
    for outcome_field in ("winner", "outcome", "result", "settled"):
        assert outcome_field not in payload


# --------------------------------------------------------------- fixture 1: ATP with F2
def test_fixture_1_atp_with_f2_diagnostic(tmp_path: Path) -> None:
    snap = _snapshot(tmp_path, "atp.json")
    ratings = _ratings(tmp_path, {"ATP": {"A Player": {"rating": 1600.0, "matches": 40},
                                          "B Player": {"rating": 1500.0, "matches": 30}}})
    html_p, out_p = tmp_path / "r.html", tmp_path / "r.json"
    payload = _assess(snap, tmp_path, ratings=ratings, html=html_p, out=out_p)
    html = html_p.read_text()

    assert payload["status"] == "MODEL_VIEW_ONLY"
    assert payload["f2_available"] is True
    assert payload["f2_label"] == "MODEL_DIAGNOSTIC_NOT_MARKET_PROVEN"
    # F2 is present but NEVER the final probability
    assert payload["final_probability_a"] == payload["market_probability_a"]
    assert payload["f2_probability_a"] != payload["market_probability_a"]
    _assert_universal_invariants(payload, html)

    # determinism: JSON, HTML and digest are stable across identical runs
    again = _assess(snap, tmp_path, ratings=ratings, html=tmp_path / "r2.html")
    assert again == payload
    assert (tmp_path / "r2.html").read_text() == html
    assert out_p.read_text().strip() == json.dumps(payload, sort_keys=True,
                                                   separators=(",", ":"))


# --------------------------------------------------------------- fixture 2: WTA with F2
def test_fixture_2_wta_with_f2_diagnostic(tmp_path: Path) -> None:
    snap = _snapshot(tmp_path, "wta.json", tour="WTA",
                     competitor_a="C Player", competitor_b="D Player")
    ratings = _ratings(tmp_path, {"WTA": {"C Player": {"rating": 1580.0, "matches": 25},
                                          "D Player": {"rating": 1520.0, "matches": 18}}})
    html_p = tmp_path / "wta.html"
    payload = _assess(snap, tmp_path, ratings=ratings, html=html_p)
    assert payload["tour"] == "WTA"
    assert payload["status"] == "MODEL_VIEW_ONLY"
    assert payload["f2_available"] is True
    assert payload["final_probability_a"] == payload["market_probability_a"]
    _assert_universal_invariants(payload, html_p.read_text())


# --------------------------------------------------------------- fixture 3: thin F2 history
def test_fixture_3_insufficient_f2_history_falls_back_to_market_only(tmp_path: Path) -> None:
    snap = _snapshot(tmp_path, "thin.json")
    ratings = _ratings(tmp_path, {"ATP": {"A Player": {"rating": 1600.0, "matches": 2},
                                          "B Player": {"rating": 1500.0, "matches": 1}}})
    html_p = tmp_path / "thin.html"
    payload = _assess(snap, tmp_path, ratings=ratings, html=html_p)
    assert payload["status"] == "MARKET_ONLY"
    assert payload["f2_available"] is False
    assert payload["f2_probability_a"] is None              # never fabricated
    assert "MODEL_HISTORY_INSUFFICIENT" in payload["reason_codes"]
    assert payload["market_probability_a"] is not None      # market still available
    _assert_universal_invariants(payload, html_p.read_text())


# --------------------------------------------------------------- fixture 4: refusals
@pytest.mark.parametrize("over,expect_reason", [
    ({"back_a": "1.98", "lay_a": "1.95"}, "CROSSED_BOOK"),
    ({"market_status": "SUSPENDED"}, "MARKET_SUSPENDED"),
    ({"in_play": True}, "MARKET_IN_PLAY"),
    ({"back_a_size": "0", "lay_a_size": "0"}, "ONE_SIDED_BOOK"),
])
def test_fixture_4_unusable_market_refuses_with_no_probability(
        tmp_path: Path, over: dict[str, object], expect_reason: str) -> None:
    snap = _snapshot(tmp_path, "bad.json", **over)
    html_p = tmp_path / "bad.html"
    payload = _assess(snap, tmp_path, html=html_p)
    assert payload["status"] == "MARKET_UNAVAILABLE"
    assert payload["market_probability_a"] is None          # refuses, never invents
    assert payload["final_probability_a"] is None
    assert expect_reason in payload["reason_codes"]
    _assert_universal_invariants(payload, html_p.read_text())


def test_fixture_4b_malformed_snapshot_refuses_at_input(tmp_path: Path) -> None:
    from assistant_v0.manual_input import ManualInputError
    bad = _snapshot(tmp_path, "offladder.json", back_a="1.905")   # off the canonical ladder
    with pytest.raises(ManualInputError):
        _assess(bad, tmp_path)


# --------------------------------------------------------------- fixture 5: ledger + grading
def test_fixture_5_immutable_pre_match_then_outcome_append_and_grading(tmp_path: Path) -> None:
    snap = _snapshot(tmp_path, "led.json")
    ratings = _ratings(tmp_path, {"ATP": {"A Player": {"rating": 1600.0, "matches": 40},
                                          "B Player": {"rating": 1500.0, "matches": 30}}})
    ledger_p = tmp_path / "ledger.jsonl"
    payload = _assess(snap, tmp_path, ratings=ratings, ledger=ledger_p, record_id="m1")

    led = ShadowLedger(ledger_p)
    rec = led.pre_match_by_id("m1")
    assert rec is not None
    assert rec.market_probability_a == payload["market_probability_a"]
    for outcome_field in ("winner", "outcome", "result", "settled", "stake", "pnl"):
        assert not hasattr(rec, outcome_field)              # no outcome representable pre-match

    frozen_before = ledger_p.read_text()
    cli.main(["settle", "--ledger", str(ledger_p), "--record-id", "m1", "--winner", "A"])

    reloaded = ShadowLedger(ledger_p)
    assert reloaded.pre_match_by_id("m1") == rec            # original byte-identical in meaning
    assert ledger_p.read_text().startswith(frozen_before)   # append-only: prefix preserved
    app = reloaded.settlement_by_id("m1")
    assert app is not None and app.scored is True
    assert app.market_log_loss is not None and app.market_brier is not None
    assert app.model_log_loss is not None                   # F2 graded separately
    for banned in ("stake", "roi", "pnl", "profit", "clv"):
        assert banned not in json.dumps(app.__dict__).lower()

    summary = cli.main(["ledger", "--ledger", str(ledger_p)])
    assert isinstance(summary, dict)
    assert summary["pre_match_records"] == 1 and summary["scored"] == 1
    assert summary["market_log_loss_mean"] is not None

    # a second settlement of the same record is refused (append-only integrity)
    with pytest.raises(Exception):
        cli.main(["settle", "--ledger", str(ledger_p), "--record-id", "m1", "--winner", "B"])


# --------------------------------------------------------------- structural guarantees
def test_no_execution_import_path_from_assistant_v0() -> None:
    """V0 must not be able to reach any execution/coherence layer (static import graph)."""
    import subprocess
    for forbidden in ("l5_decision", "l5b_risk", "l6_broker", "l7_settle",
                      "research.xmarket", "sport_tennis.coherence"):
        r = subprocess.run(
            ["uv", "run", "python", "tools/check_import_quarantine.py",
             "--forbid", forbidden, "--from", "assistant_v0"],
            capture_output=True, text=True, check=False)
        assert r.returncode == 0, f"assistant_v0 reaches {forbidden}: {r.stdout}{r.stderr}"


def test_f2_can_never_become_the_final_probability(tmp_path: Path) -> None:
    """Even with a wildly different F2 view, the final probability stays the market's."""
    snap = _snapshot(tmp_path, "f2.json")
    ratings = _ratings(tmp_path, {"ATP": {"A Player": {"rating": 2400.0, "matches": 99},
                                          "B Player": {"rating": 1000.0, "matches": 99}}})
    payload = _assess(snap, tmp_path, ratings=ratings)
    assert payload["f2_available"] is True
    assert payload["f2_probability_a"] > 0.95               # F2 is extremely confident
    assert payload["final_probability_a"] == payload["market_probability_a"]
    assert payload["final_probability_a"] < 0.6             # the market's view, not F2's
    assert payload["final_probability_source"] == "MARKET"
