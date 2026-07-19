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


class TestMetricsGoldenValues:
    """Pin exact SPEC-097 metric arithmetic (kills log-loss/brier/cil/slope mutations)."""

    def test_metrics_exact(self) -> None:
        from l8_evidence.june_m1_harness import _metrics
        m = _metrics([(0.6, 1), (0.4, 0), (0.7, 0), (0.3, 1), (0.8, 1), (0.55, 0), (0.2, 0), (0.9, 1)])
        assert m == {"n": 8, "log_loss": 0.597469, "brier": 0.211563,
                     "cal_in_large": -0.225956, "cal_slope": 0.931158}

    def test_metrics_empty(self) -> None:
        from l8_evidence.june_m1_harness import _metrics
        assert _metrics([]) == {"n": 0}

    def test_scorecard_exact_values_and_structure(self) -> None:
        rows = [_pred(f"1.{i}", tour="ATP" if i < 3 else "WTA", band="20+" if i % 2 == 0 else "1-4",
                      day=f"2026-06-0{i+1}") for i in range(5)]
        outs = {r.market_id: _outcome(r.market_id, 11 if i % 2 == 0 else 22) for i, r in enumerate(rows)}
        scored, _ = score_bundle(rows, outs)
        card = m1_scorecard(scored, min_support=3)
        assert card["n_scored"] == 5
        assert card["n_utc_day_clusters"] == 5
        assert card["per_tour"]["ATP"]["n"] == 3 and card["per_tour"]["ATP"]["supported"] is True
        assert card["per_tour"]["WTA"]["n"] == 2 and card["per_tour"]["WTA"]["supported"] is False
        assert set(card["prior_history_cohorts"]) == {"20+", "1-4"}


class TestJoinHardening:
    """Kill Eq->Is (small-int interning) and !=->> (lexical) survivors with real-scale values."""

    def test_large_selection_ids_map_by_value_not_identity(self) -> None:
        # 9632014 / 24966308 are NOT interned; == must hold, `is` would not.
        p = _pred("1.1", sel_des=9632014, sel_oth=24966308)
        assert score_market(p, _outcome("1.1", 9632014)).y_designated == 1
        assert score_market(p, _outcome("1.1", 24966308)).y_designated == 0
        with pytest.raises(HarnessJoinError):
            score_market(p, _outcome("1.1", 9999999))   # unknown large id refuses

    def test_market_mismatch_refuses_both_lexical_directions(self) -> None:
        with pytest.raises(HarnessJoinError):   # outcome id lexically GREATER
            score_market(_pred("1.1"), _outcome("1.2", 11))
        with pytest.raises(HarnessJoinError):   # outcome id lexically SMALLER
            score_market(_pred("1.5"), _outcome("1.2", 11))


class TestVerdictBoundaries:
    """Boundary-exact tests kill band-constant NumberReplacer + comparison-operator survivors."""

    def test_cal_pass_band_edges(self) -> None:
        assert evaluate_m1_verdict(_card(overall=_block(cil=0.02)))["verdict"] == "PASS"
        assert evaluate_m1_verdict(_card(overall=_block(cil=0.0201)))["verdict"] == "CONTINUE"

    def test_cal_harm_band_edges(self) -> None:
        assert evaluate_m1_verdict(_card(overall=_block(cil=0.05)))["verdict"] == "CONTINUE"
        assert evaluate_m1_verdict(_card(overall=_block(cil=0.0501)))["verdict"] == "FAIL_HARM"
        # negative side symmetric
        assert evaluate_m1_verdict(_card(overall=_block(cil=-0.0501)))["verdict"] == "FAIL_HARM"

    def test_slope_band_edges(self) -> None:
        assert evaluate_m1_verdict(_card(overall=_block(slope=0.90)))["verdict"] == "PASS"
        assert evaluate_m1_verdict(_card(overall=_block(slope=0.8999)))["verdict"] == "CONTINUE"
        assert evaluate_m1_verdict(_card(overall=_block(slope=1.10)))["verdict"] == "PASS"
        assert evaluate_m1_verdict(_card(overall=_block(slope=1.1001)))["verdict"] == "CONTINUE"

    def test_brier_edge(self) -> None:
        assert evaluate_m1_verdict(_card(overall=_block(brier=0.2499)))["verdict"] == "PASS"
        assert evaluate_m1_verdict(_card(overall=_block(brier=0.25)))["verdict"] == "FAIL_HARM"

    def test_log_loss_edge(self) -> None:
        assert evaluate_m1_verdict(_card(overall=_block(ll=_LN2 - 1e-9)))["verdict"] == "PASS"
        assert evaluate_m1_verdict(_card(overall=_block(ll=_LN2)))["verdict"] == "FAIL_HARM"

    def test_scorecard_support_boundary(self) -> None:
        def rows(n):
            return [_pred(f"1.{1000+i}", sel_des=1, sel_oth=2) for i in range(n)]

        def outs(rs):
            return {r.market_id: _outcome(r.market_id, 1) for r in rs}
        r500 = rows(500)
        assert m1_scorecard(score_bundle(r500, outs(r500))[0], min_support=500)["overall"]["supported"] is True
        r499 = rows(499)
        assert m1_scorecard(score_bundle(r499, outs(r499))[0], min_support=500)["overall"]["supported"] is False


class TestValidationAndCohortHardening:
    def test_frozen_prediction_rejects_probabilities_at_the_open_interval_edges(self) -> None:
        for bad in (0.0, 1.0, -0.1, 1.1):
            with pytest.raises(ValueError):
                _pred("1.1", p_cal=bad)
        with pytest.raises(ValueError):
            FrozenPrediction(market_id="1.1", tour="ATP", cohort="STRICT", prior_band="20+",
                             cluster_day="2026-06-10", competitor_designated="a", competitor_other="b",
                             selection_id_designated=1, selection_id_other=2,
                             p_raw_designated=0.0, p_cal_designated=0.5)  # p_raw at edge

    def test_frozen_prediction_rejects_bad_market_tour_and_equal_ids(self) -> None:
        with pytest.raises(ValueError):
            _pred("")                                   # empty market_id
        with pytest.raises(ValueError):
            _pred("1.1", tour="MIXED")                  # tour not ATP/WTA
        with pytest.raises(ValueError):
            _pred("1.1", sel_des=7, sel_oth=7)          # equal selection ids
        with pytest.raises(ValueError):
            FrozenPrediction(market_id="1.1", tour="ATP", cohort="STRICT", prior_band="20+",
                             cluster_day="2026-06-10", competitor_designated="same",
                             competitor_other="same", selection_id_designated=1, selection_id_other=2,
                             p_raw_designated=0.5, p_cal_designated=0.5)  # equal competitor ids

    def test_scorecard_cohort_membership_is_exact(self) -> None:
        rows = [_pred("1.1", band="20+"), _pred("1.2", band="20+"), _pred("1.3", band="1-4"),
                _pred("1.4", band="5-9")]
        outs = {r.market_id: _outcome(r.market_id, 11) for r in rows}
        card = m1_scorecard(score_bundle(rows, outs)[0], min_support=1)
        cohorts = card["prior_history_cohorts"]
        assert cohorts["20+"]["n"] == 2
        assert cohorts["1-4"]["n"] == 1
        assert cohorts["5-9"]["n"] == 1

    def test_scorecard_min_support_default_is_500(self) -> None:
        # 300 rows: default min_support=500 -> unsupported; explicit 250 -> supported.
        rows = [_pred(f"1.{2000+i}", sel_des=1, sel_oth=2) for i in range(300)]
        outs = {r.market_id: _outcome(r.market_id, 1) for r in rows}
        scored = score_bundle(rows, outs)[0]
        assert m1_scorecard(scored)["overall"]["supported"] is False          # default 500
        assert m1_scorecard(scored, min_support=250)["overall"]["supported"] is True

    def test_verdict_min_support_default_is_500(self) -> None:
        # overall n=300 with supported=True but default min_support=500 -> CONTINUE via the n check
        assert evaluate_m1_verdict(_card(overall=_block(n=300, supported=True)))["verdict"] == "CONTINUE"


class TestJoinIdentityVsEquality:
    """Kill == -> is on the selection-id join: winner and stored id are value-equal but DIFFERENT
    objects (as in production, where both come from separate int() parses). `is` would refuse."""

    def test_join_matches_by_value_not_object_identity(self) -> None:
        des = int("9632014")            # distinct object
        oth = int("24966308")
        p = _pred("1.1", sel_des=des, sel_oth=oth)
        win_des = int("9632" + "014")   # same VALUE as des, different object
        assert win_des is not des and win_des == des
        assert score_market(p, _outcome("1.1", win_des)).y_designated == 1
        win_oth = 24000000 + 966308     # runtime-computed, distinct object, == oth
        assert win_oth is not oth and win_oth == oth
        assert score_market(p, _outcome("1.1", win_oth)).y_designated == 0


class TestFrozenPredictionIdentityChecks:
    def test_equal_ids_as_distinct_objects_are_rejected(self) -> None:
        same_sel = int("70000000")
        with pytest.raises(ValueError):   # value-equal DIFFERENT-object selection ids -> reject
            _pred("1.1", sel_des=same_sel, sel_oth=int("7000" + "0000"))
        comp = "td:x|" + "z"
        with pytest.raises(ValueError):   # value-equal DIFFERENT-object competitor ids -> reject
            FrozenPrediction(market_id="1.1", tour="ATP", cohort="STRICT", prior_band="20+",
                             cluster_day="2026-06-10", competitor_designated=comp,
                             competitor_other="td:x|" + "z", selection_id_designated=1,
                             selection_id_other=2, p_raw_designated=0.5, p_cal_designated=0.5)


class TestOptimiserDifferentialFixtures:
    """§4/§5: difficult-convergence golden values across the constructible domain. Any optimiser/
    Hessian/iteration-limit mutant that changes an OBSERVABLE metric on ANY fixture is killed;
    the module exposes only these five metrics (no iteration count), so this is the full surface."""

    def _m(self, pairs):
        from l8_evidence.june_m1_harness import _metrics
        return _metrics(pairs)

    def test_weak_identification_flat_likelihood(self) -> None:
        assert self._m([(0.5, 1), (0.5, 0)] * 3) == {
            "n": 6, "log_loss": 0.693147, "brier": 0.25, "cal_in_large": 0.0, "cal_slope": 1.0}

    def test_separable_all_positive(self) -> None:
        assert self._m([(0.6, 1), (0.7, 1), (0.8, 1), (0.55, 1), (0.9, 1)]) == {
            "n": 5, "log_loss": 0.358768, "brier": 0.1005, "cal_in_large": 26.735659, "cal_slope": 0.54242}

    def test_separable_all_negative(self) -> None:
        assert self._m([(0.4, 0), (0.3, 0), (0.2, 0), (0.45, 0), (0.1, 0)]) == {
            "n": 5, "log_loss": 0.358768, "brier": 0.1005, "cal_in_large": -26.735637, "cal_slope": 0.54242}

    def test_boundary_probabilities(self) -> None:
        assert self._m([(0.001, 1), (0.999, 0), (0.002, 0), (0.998, 1), (0.5, 1)]) == {
            "n": 5, "log_loss": 2.902532, "brier": 0.449202, "cal_in_large": 0.405465, "cal_slope": -54.234543}

    def test_min_n_one(self) -> None:
        assert self._m([(0.6, 1)]) == {
            "n": 1, "log_loss": 0.510826, "brier": 0.16, "cal_in_large": 27.225578, "cal_slope": 1.0}

    def test_imbalanced_rare_positive(self) -> None:
        assert self._m([(0.1, 0)] * 20 + [(0.9, 1)]) == {
            "n": 21, "log_loss": 0.105361, "brier": 0.01, "cal_in_large": -1.164531, "cal_slope": 7.903299}


class TestClampReachabilityAndFrozen:
    """§6: the clamp branch IS reachable via valid FrozenPrediction probabilities (0<p<1 allows
    p<=1e-12) and via my in {0,1}; boundary goldens pin the epsilon on both sides. §7: dataclass
    frozen-immutability + equality kill @dataclass decorator removal."""

    def _m(self, pairs):
        from l8_evidence.june_m1_harness import _metrics
        return _metrics(pairs)

    def test_clamp_probability_below_epsilon(self) -> None:
        # p<=1e-12 is a valid FrozenPrediction input: the clamp pins log_loss/brier/cil (stable,
        # epsilon-dependent) and the overflow guard keeps cal_slope FINITE (no crash).
        import math
        m = self._m([(1e-15, 1), (0.5, 0)])
        assert (m["n"], m["log_loss"], m["brier"], m["cal_in_large"]) == (2, 14.162084, 0.625, 1.098612)
        assert math.isfinite(m["cal_slope"])

    def test_clamp_probability_above_one_minus_epsilon_does_not_overflow(self) -> None:
        import math
        m = self._m([(1 - 1e-15, 0), (0.5, 1)])   # would OverflowError without the guard
        assert (m["n"], m["log_loss"], m["brier"], m["cal_in_large"]) == (2, 14.162084, 0.625, -1.098612)
        assert math.isfinite(m["cal_slope"])

    def test_frozen_prediction_is_frozen_and_has_value_equality(self) -> None:
        import dataclasses
        p = _pred("1.1")
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.p_cal_designated = 0.9   # type: ignore[misc]
        assert _pred("1.1") == _pred("1.1")           # value equality (generated __eq__)
        assert _pred("1.1") != _pred("1.2")

    def test_scored_row_is_frozen_and_equal_by_value(self) -> None:
        import dataclasses
        r = score_market(_pred("1.1", sel_des=11, sel_oth=22), _outcome("1.1", 11))
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.y_designated = 0   # type: ignore[misc]
        r2 = score_market(_pred("1.1", sel_des=11, sel_oth=22), _outcome("1.1", 11))
        assert r == r2


class TestVerdictOrderingAndControlFlow:
    """Kill worse() severity-ordering (no downgrade), the n<min_support boundary, brier>= vs ==,
    default flags, band-membership identity, and the score_bundle exclusion continue->break."""

    def test_worse_never_downgrades_severity(self) -> None:
        # overall FAIL_HARM (cil>0.05) AND a tour merely CONTINUE (slope) -> final stays FAIL_HARM.
        v = evaluate_m1_verdict(_card(overall=_block(cil=0.06), wta=_block(slope=0.80)))
        assert v["verdict"] == "FAIL_HARM"
        # CONTINUE reached first (overall slope) then FAIL_HARM (tour brier) -> FAIL_HARM.
        v2 = evaluate_m1_verdict(_card(overall=_block(slope=0.80), atp=_block(brier=0.30)))
        assert v2["verdict"] == "FAIL_HARM"

    def test_all_four_severity_levels_are_distinct_and_ordered(self) -> None:
        assert evaluate_m1_verdict(_card())["verdict"] == "PASS"
        assert evaluate_m1_verdict(_card(overall=_block(cil=0.03)))["verdict"] == "CONTINUE"
        assert evaluate_m1_verdict(_card(overall=_block(brier=0.30)))["verdict"] == "FAIL_HARM"
        # FAIL_HARM must dominate a co-occurring CONTINUE (ordering 3 > 1)
        assert evaluate_m1_verdict(_card(overall=_block(cil=0.06, slope=0.5)))["verdict"] == "FAIL_HARM"

    def test_n_overall_at_min_support_boundary(self) -> None:
        # n exactly == min_support must NOT trip the n<min_support CONTINUE guard.
        assert evaluate_m1_verdict(_card(overall=_block(n=500, supported=True)))["verdict"] == "PASS"
        assert evaluate_m1_verdict(_card(overall=_block(n=499, supported=True)))["verdict"] == "CONTINUE"

    def test_brier_strictly_above_band_fails_harm(self) -> None:
        # kills >= -> == : brier 0.30 (> 0.25, not equal) must FAIL_HARM.
        assert evaluate_m1_verdict(_card(overall=_block(brier=0.30)))["verdict"] == "FAIL_HARM"

    def test_missing_supported_flag_defaults_unsupported(self) -> None:
        blk = {"n": 600, "log_loss": 0.62, "brier": 0.21, "cal_in_large": 0.004, "cal_slope": 1.0}
        # no 'supported' key -> defaults False -> CONTINUE (kills False->True default)
        assert evaluate_m1_verdict({"overall": blk, "per_tour": {"ATP": blk, "WTA": blk}})["verdict"] == "CONTINUE"

    def test_missing_n_defaults_zero_and_continues(self) -> None:
        blk = {"log_loss": 0.62, "brier": 0.21, "cal_in_large": 0.004, "cal_slope": 1.0, "supported": True}
        # no 'n' key -> default 0 < min_support -> CONTINUE (kills the 0 default replacer)
        assert evaluate_m1_verdict({"overall": blk, "per_tour": {"ATP": blk, "WTA": blk}})["verdict"] == "CONTINUE"

    def test_scorecard_band_membership_distinct_objects(self) -> None:
        band = "2" + "0+"          # value "20+" as a distinct object from other rows' literal
        rows = [_pred("1.1", band=band), _pred("1.2", band="1-4")]
        outs = {r.market_id: _outcome(r.market_id, 11) for r in rows}
        card = m1_scorecard(score_bundle(rows, outs)[0], min_support=1)
        assert card["prior_history_cohorts"]["20+"]["n"] == 1   # matched by value, not identity

    def test_score_bundle_early_missing_does_not_drop_later(self) -> None:
        # first (sorted) market missing outcome; later present -> must still score the later
        # (kills the exclusion `continue` -> `break`).
        preds = [_pred("1.1", sel_des=11, sel_oth=22), _pred("1.2", sel_des=33, sel_oth=44)]
        scored, excl = score_bundle(preds, {"1.2": _outcome("1.2", 33)})
        assert {r.market_id for r in scored} == {"1.2"}
        assert dict(excl) == {"1.1": "NO_OUTCOME_IN_ARTIFACT"}
