"""STAGE3-0003 §7/§12 — V0 output contract (red tests first).

The output shows the market probability (the final V0 decision probability), best back/lay,
implied interval, timestamps, quote age, data-quality status, an OPTIONAL separate F2
diagnostic (labelled, never final), model-vs-market disagreement, reason codes, status, and
digests. It MUST NOT contain edge / EV / stake / tip / recommended-side / profit fields.
"""
from __future__ import annotations

from decimal import Decimal

from assistant_v0 import f2_diagnostic as F2
from assistant_v0 import manual_input as MI
from assistant_v0 import market_probability as MP
from assistant_v0 import output as O
from assistant_v0 import status as S


def _snap(**over: object) -> MI.ManualMarketSnapshot:
    base: dict[str, object] = dict(
        competitor_a="A", competitor_b="B", competitor_a_id=None, competitor_b_id=None,
        tour="ATP", scheduled_start_ms=2000, input_timestamp_ms=1000,
        source="MANUAL_BETFAIR_UI",
        back_a=Decimal("1.90"), back_a_size=Decimal("50"),
        lay_a=Decimal("1.95"), lay_a_size=Decimal("40"),
        back_b=Decimal("2.02"), back_b_size=Decimal("30"),
        lay_b=Decimal("2.10"), lay_b_size=Decimal("20"),
        market_status="OPEN", in_play=False, market_id="1.234", event_id="E1",
    )
    base.update(over)
    return MI.ManualMarketSnapshot(**base)  # type: ignore[arg-type]


def _build(f2: F2.F2Diagnostic | None = None) -> O.AssistantOutput:
    snap = _snap()
    market = MP.assess_market(snap, reference_time_ms=1000)
    if f2 is None:
        f2 = F2.unavailable(F2.MODEL_HISTORY_INSUFFICIENT)
    return O.build_output(snap, market, f2, reference_time_ms=1000)


def test_output_has_no_bet_or_value_fields() -> None:
    out = _build()
    banned = {"edge", "expected_value", "ev", "stake", "tip", "recommended_side",
              "side", "prospective_profit", "profit", "roi", "clv", "value"}
    fields = {f.name.lower() for f in type(out).__dataclass_fields__.values()}
    assert not (fields & banned), f"forbidden field present: {fields & banned}"
    # also absent from the serialized JSON keys
    blob = out.to_json()
    assert not any(b in blob for b in ("expected_value", "\"stake\"", "\"tip\"", "\"edge\""))


def test_market_probability_is_the_final_probability() -> None:
    out = _build()
    assert out.final_probability_source == "MARKET"
    assert out.market_probability_a == out.final_probability_a


def test_f2_never_becomes_final_even_when_available() -> None:
    f2 = F2.F2Diagnostic(available=True, p_a=0.70, p_b=0.30,
                         history_count_a=50, history_count_b=40,
                         label="MODEL_DIAGNOSTIC_NOT_MARKET_PROVEN", reason=None)
    out = _build(f2)
    assert out.final_probability_source == "MARKET"            # never MODEL
    assert out.final_probability_a == out.market_probability_a  # not the F2 value
    assert out.f2_probability_a == 0.70
    assert out.f2_label == "MODEL_DIAGNOSTIC_NOT_MARKET_PROVEN"
    assert out.status is S.AssistantStatus.MODEL_VIEW_ONLY


def test_status_market_only_when_no_f2() -> None:
    out = _build(F2.unavailable(F2.MODEL_HISTORY_INSUFFICIENT))
    assert out.status is S.AssistantStatus.MARKET_ONLY
    assert out.economic_posture is S.AssistantStatus.NO_BET_RESEARCH_ONLY


def test_fair_odds_are_labelled_and_derived_from_market() -> None:
    out = _build()
    assert out.market_fair_odds_a is not None
    # fair odds = 1 / market probability
    assert abs(out.market_fair_odds_a - (1.0 / out.market_probability_a)) < 1e-9


def test_model_market_disagreement_reported() -> None:
    f2 = F2.F2Diagnostic(available=True, p_a=0.70, p_b=0.30, history_count_a=50,
                         history_count_b=40, label="MODEL_DIAGNOSTIC_NOT_MARKET_PROVEN",
                         reason=None)
    out = _build(f2)
    assert out.model_market_disagreement_a is not None
    assert abs(out.model_market_disagreement_a - (0.70 - out.market_probability_a)) < 1e-9


def test_output_json_is_deterministic() -> None:
    assert _build().to_json() == _build().to_json()


def test_digests_present() -> None:
    out = _build()
    assert out.data_digest and out.policy_digest and out.model_view_digest
