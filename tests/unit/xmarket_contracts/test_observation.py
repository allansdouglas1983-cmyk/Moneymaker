"""STAGE3-0004 §11/§14 — neutral cross-market observation contracts (red tests first).

Contracts only, no fitted mathematics. NO latent parameter, p_A, p_B, coherence score, final
probability, or tip field is representable. Raw marketType is preserved. Immutable, with a
deterministic digest and serialization.
"""
from __future__ import annotations

from xmarket_contracts import observation as O


def _obs(**over: object) -> O.CrossMarketObservation:
    base: dict[str, object] = dict(
        mo_market_id="1.mo", derivative_market_id="1.tg", event_id="E1",
        f0_snapshot_id="snap-1", f0_decision_timestamp_ms=1780310700000,
        derivative_market_type="COMBINED_TOTAL", raw_selection_names=("Over", "Under"),
        parsed_line=20.5, best_three_depth=3, matched_volume=500.0, quote_age_seconds=30.0,
        market_status="OPEN", in_play=False, suspension_status="NOT_SUSPENDED",
        cross_matching=False, redundancy_evidence_status="ORIGIN_UNRESOLVED",
        settlement_semantics_status="VERIFIED_CONTRACTUALLY_DIFFERENT_BUT_USABLE_WITH_EXCLUSIONS",
        cohort="STRICT",
    )
    base.update(over)
    return O.CrossMarketObservation(**base)  # type: ignore[arg-type]


def test_observation_has_no_probability_or_tip_field() -> None:
    banned = {"p_a", "p_b", "coherence_score", "score", "final_probability", "tip",
              "tip_status", "latent", "serve_strength", "edge", "ev", "stake",
              "winner", "outcome", "result", "pnl", "probability_adjustment"}
    fields = {f.name.lower() for f in O.CrossMarketObservation.__dataclass_fields__.values()}
    assert not (fields & banned), f"forbidden field present: {fields & banned}"


def test_observation_preserves_raw_market_type() -> None:
    assert _obs().derivative_market_type == "COMBINED_TOTAL"  # raw, never renamed


def test_optional_quality_fields_default_none_not_fitted() -> None:
    o = _obs()
    assert o.spread_ticks is None            # not computed here (no fitted maths)
    assert o.normalized_back_lay_probability_interval is None


def test_observation_is_immutable_with_digest() -> None:
    o = _obs()
    assert o.provenance_digest().startswith("sha256:")
    assert o.provenance_digest() == _obs().provenance_digest()
    assert _obs(parsed_line=21.5).provenance_digest() != o.provenance_digest()


def test_observation_set_shape_and_no_forbidden_fields() -> None:
    mo = _obs(derivative_market_id="1.mo", derivative_market_type="MATCH_ODDS",
              raw_selection_names=("A", "B"), parsed_line=None)
    s = O.CrossMarketObservationSet(
        mo_observation=mo, total_games_observations=(_obs(),),
        game_handicap_observations=(), format_status="FORMAT_UNRESOLVED",
        synchronization_status="USABLE", completeness_status="MO_PLUS_TOTAL_GAMES")
    banned = {"p_a", "p_b", "coherence_score", "score", "final_probability", "tip", "edge",
              "latent", "outcome", "winner"}
    fields = {f.name.lower() for f in O.CrossMarketObservationSet.__dataclass_fields__.values()}
    assert not (fields & banned)
    assert s.digest() == O.CrossMarketObservationSet(
        mo_observation=mo, total_games_observations=(_obs(),), game_handicap_observations=(),
        format_status="FORMAT_UNRESOLVED", synchronization_status="USABLE",
        completeness_status="MO_PLUS_TOTAL_GAMES").digest()


def test_observation_set_deterministic_serialization() -> None:
    mo = _obs(derivative_market_id="1.mo", derivative_market_type="MATCH_ODDS")
    s = O.CrossMarketObservationSet(mo_observation=mo, total_games_observations=(),
                                    game_handicap_observations=(), format_status="X",
                                    synchronization_status="Y", completeness_status="Z")
    assert s.to_json() == s.to_json()
