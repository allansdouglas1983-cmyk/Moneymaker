"""Stage 2E §4 — the outcome-blind June M1 scoring-join harness, proven with SYNTHETIC data.

No real June outcome is read here. These tests prove the join that will run at the burn is
correct BEFORE the irreversible read: winner selection id -> correct competitor by id (not
order), unknown/mismatched selections refuse, exclusions stay visible, and the scorecard is
deterministic regardless of input order.
"""
from __future__ import annotations

import math

import pytest

from l8_evidence.june_m1_harness import (
    FrozenPrediction,
    HarnessJoinError,
    evaluate_m1_verdict,
    m1_scorecard,
    score_bundle,
    score_market,
)
from l8_evidence.tennis_outcomes import ExtractedMatchOutcome
from sport_core.outcomes import ChoiceSetResolution

pytestmark = [pytest.mark.spec("SPEC-092"), pytest.mark.spec("SPEC-097")]

_LN2 = math.log(2.0)


def _block(*, n=600, ll=0.62, brier=0.21, cil=0.004, slope=1.0, supported=None):
    return {"n": n, "log_loss": ll, "brier": brier, "cal_in_large": cil, "cal_slope": slope,
            "supported": (n >= 500) if supported is None else supported}


def _card(overall=None, atp=None, wta=None):
    return {"overall": overall or _block(), "per_tour": {"ATP": atp or _block(), "WTA": wta or _block()}}


def _pred(market_id: str, *, sel_des: int = 11, sel_oth: int = 22, tour: str = "ATP",
          p_cal: float = 0.62, band: str = "20+", cohort: str = "STRICT",
          day: str = "2026-06-10") -> FrozenPrediction:
    return FrozenPrediction(
        market_id=market_id, tour=tour, cohort=cohort, prior_band=band, cluster_day=day,
        competitor_designated="td-atp:lo|x", competitor_other="td-atp:hi|y",
        selection_id_designated=sel_des, selection_id_other=sel_oth,
        p_raw_designated=0.60, p_cal_designated=p_cal,
    )


def _outcome(market_id: str, winner_selection_id: int) -> ExtractedMatchOutcome:
    return ExtractedMatchOutcome(
        market_id=market_id, resolution=ChoiceSetResolution.WINNER_KNOWN,
        winner_selection_id=winner_selection_id,
        runner_statuses={11: "WINNER", 22: "LOSER"}, settled_time=None,
        authorisation_digest="sha256:" + "cd" * 32,
    )


class TestJoin:
    def test_winner_selection_maps_to_designated_competitor(self) -> None:
        row = score_market(_pred("1.1", sel_des=11, sel_oth=22), _outcome("1.1", 11))
        assert row.y_designated == 1
        row2 = score_market(_pred("1.1", sel_des=11, sel_oth=22), _outcome("1.1", 22))
        assert row2.y_designated == 0

    def test_runner_order_does_not_flip_the_result(self) -> None:
        # Same market, designated selection id 22 instead of 11: result tracks the ID, not order.
        row = score_market(_pred("1.1", sel_des=22, sel_oth=11), _outcome("1.1", 11))
        assert row.y_designated == 0  # designated (22) did NOT win; 11 did
        row2 = score_market(_pred("1.1", sel_des=22, sel_oth=11), _outcome("1.1", 22))
        assert row2.y_designated == 1

    def test_unknown_winner_selection_refuses(self) -> None:
        with pytest.raises(HarnessJoinError):
            score_market(_pred("1.1", sel_des=11, sel_oth=22), _outcome("1.1", 99))

    def test_market_id_mismatch_refuses_wrong_prediction_join(self) -> None:
        with pytest.raises(HarnessJoinError):
            score_market(_pred("1.1"), _outcome("1.2", 11))


class TestBundle:
    def test_every_prediction_accounted_scored_or_excluded(self) -> None:
        preds = [_pred("1.1", sel_des=11, sel_oth=22), _pred("1.2", sel_des=33, sel_oth=44),
                 _pred("1.3", sel_des=55, sel_oth=66)]
        outcomes = {"1.1": _outcome("1.1", 11), "1.2": _outcome("1.2", 44)}  # 1.3 missing
        scored, excl = score_bundle(preds, outcomes)
        assert {r.market_id for r in scored} == {"1.1", "1.2"}
        assert dict(excl) == {"1.3": "NO_OUTCOME_IN_ARTIFACT"}
        assert len(scored) + len(excl) == len(preds)

    def test_unjoinable_outcome_becomes_a_visible_exclusion(self) -> None:
        preds = [_pred("1.1", sel_des=11, sel_oth=22)]
        scored, excl = score_bundle(preds, {"1.1": _outcome("1.1", 999)})
        assert scored == ()
        assert excl[0][0] == "1.1" and excl[0][1].startswith("UNJOINABLE:")

    def test_duplicate_frozen_prediction_refuses(self) -> None:
        with pytest.raises(HarnessJoinError):
            score_bundle([_pred("1.1"), _pred("1.1")], {})

    def test_input_order_does_not_change_scored_output(self) -> None:
        preds = [_pred("1.1", sel_des=11, sel_oth=22), _pred("1.2", sel_des=33, sel_oth=44)]
        out = {"1.1": _outcome("1.1", 11), "1.2": _outcome("1.2", 33)}
        a, _ = score_bundle(preds, out)
        b, _ = score_bundle(list(reversed(preds)), out)
        assert a == b


class TestScorecard:
    def test_scorecard_deterministic_and_support_flagged(self) -> None:
        # 600 ATP + 100 WTA scored rows: ATP supported (>=500), WTA not.
        preds, outs = [], {}
        for i in range(700):
            mid = f"1.{1000 + i}"
            tour = "ATP" if i < 600 else "WTA"
            preds.append(_pred(mid, sel_des=1, sel_oth=2, tour=tour, day=f"2026-06-{(i % 28) + 1:02d}"))
            outs[mid] = _outcome(mid, 1 if i % 2 == 0 else 2)
        scored, _ = score_bundle(preds, outs)
        card = m1_scorecard(scored, min_support=500)
        assert card["n_scored"] == 700
        assert card["per_tour"]["ATP"]["supported"] is True
        assert card["per_tour"]["WTA"]["supported"] is False   # 100 < 500 -> CONTINUE, not fabricated
        assert card["overall"]["supported"] is True
        # deterministic: same rows in any order -> identical card
        assert m1_scorecard(list(reversed(scored)), min_support=500) == card


class TestM1Verdict:
    def test_all_bands_met_passes(self) -> None:
        assert evaluate_m1_verdict(_card())["verdict"] == "PASS"

    def test_cal_in_large_in_grey_band_continues(self) -> None:
        v = evaluate_m1_verdict(_card(overall=_block(cil=0.035)))
        assert v["verdict"] == "CONTINUE"

    def test_cal_in_large_above_harm_boundary_fails_harm(self) -> None:
        v = evaluate_m1_verdict(_card(overall=_block(cil=0.06)))
        assert v["verdict"] == "FAIL_HARM"

    def test_log_loss_worse_than_null_fails_harm(self) -> None:
        v = evaluate_m1_verdict(_card(overall=_block(ll=_LN2 + 0.01)))
        assert v["verdict"] == "FAIL_HARM"

    def test_unsupported_tour_continues_never_passes(self) -> None:
        # WTA below support -> CONTINUE, never PASS, never fabricated
        v = evaluate_m1_verdict(_card(wta=_block(n=100, supported=False)))
        assert v["verdict"] == "CONTINUE"

    def test_slope_out_of_band_continues(self) -> None:
        assert evaluate_m1_verdict(_card(overall=_block(slope=0.80)))["verdict"] == "CONTINUE"

    def test_insufficient_overall_support_never_passes(self) -> None:
        v = evaluate_m1_verdict(_card(overall=_block(n=100, supported=False)))
        assert v["verdict"] != "PASS"
