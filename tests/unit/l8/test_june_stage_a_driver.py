"""Stage 2E — the real frozen bundle is scoring-ready, and the driver wiring is outcome-blind.

Loads the ACTUAL 1,213-market frozen bundle and proves it flows through the governed join +
scorecard deterministically under SYNTHETIC winners (no June outcome read). Also proves the
driver's authorisation + extractor construction are outcome-blind and correctly scoped.
"""
from __future__ import annotations

import json
from datetime import date

import pytest

from l8_evidence.june_m1_harness import m1_scorecard, score_bundle
from l8_evidence.june_stage_a_driver import (
    BUNDLE_SHA256,
    build_extractor,
    build_june_authorisation,
    bundle_market_ids,
    load_frozen_bundle,
)
from l8_evidence.june_stage_a_extraction import MinimalOutcome
from l8_evidence.tennis_outcomes import OutcomeAccessScope

pytestmark = [pytest.mark.spec("SPEC-092"), pytest.mark.spec("SPEC-097")]

_SHA = "sha256:" + "ab" * 32


def test_real_bundle_loads_1213_and_digest_matches() -> None:
    bundle = load_frozen_bundle()
    assert len(bundle) == 1213
    assert BUNDLE_SHA256.startswith("sha256:")
    tours = {p.tour for p in bundle}
    assert tours == {"ATP", "WTA"}
    assert sum(p.tour == "ATP" for p in bundle) == 592
    assert sum(p.tour == "WTA" for p in bundle) == 621
    # designated is the lower governed competitor id; probabilities are sane
    assert all(p.competitor_designated < p.competitor_other for p in bundle)
    assert all(0.0 < p.p_cal_designated < 1.0 for p in bundle)
    # the 5 mixed-tour homonym markets stay refused (absent from the bundle)
    mixed = {"1.258954329", "1.258960086", "1.259313230", "1.259341082", "1.259381241"}
    assert mixed.isdisjoint(bundle_market_ids(bundle))


def test_real_bundle_is_scoring_ready_under_synthetic_winners() -> None:
    bundle = load_frozen_bundle()
    # SYNTHETIC winners (deterministic, no real outcome): designated wins iff its id is odd.
    outcomes = {p.market_id: MinimalOutcome(
        p.market_id, p.selection_id_designated if p.selection_id_designated % 2 == 1
        else p.selection_id_other) for p in bundle}
    scored, excl = score_bundle(bundle, outcomes)
    assert len(scored) == 1213 and excl == ()
    card = m1_scorecard(scored, min_support=500)
    assert card["n_scored"] == 1213
    assert card["per_tour"]["ATP"]["supported"] is True   # 592 >= 500
    assert card["per_tour"]["WTA"]["supported"] is True   # 621 >= 500
    # deterministic: identical card from a reshuffled scored order
    assert json.dumps(m1_scorecard(list(reversed(scored)), min_support=500), sort_keys=True) == \
        json.dumps(card, sort_keys=True)


def test_driver_authorisation_and_extractor_are_outcome_blind_and_scoped() -> None:
    bundle = load_frozen_bundle()
    auth = build_june_authorisation(model_manifest_sha256=_SHA, feature_manifest_sha256=_SHA,
                                    data_manifest_sha256=_SHA, granted_on=date(2026, 7, 18))
    assert auth.scope is OutcomeAccessScope.JUNE_M1_TRANSFER
    # extractor scoped to EXACTLY the 1,213 bundle markets; sealed set is the full June universe
    sealed = frozenset(bundle_market_ids(bundle)) | {"1.999999"}  # a sealed non-bundle market
    ex = build_extractor(auth, sealed_market_ids=sealed, bundle=bundle)
    # a sealed market NOT in the bundle must still refuse (only the 1,213 are authorised)
    from l8_evidence.tennis_outcomes import JuneLockboxSealedError
    with pytest.raises(JuneLockboxSealedError):
        ex.extract("1.999999", [])
