"""Neutral cross-market observation contracts (STAGE3-0004 §11).

Contracts only — NO fitted mathematics. A CrossMarketObservation records the outcome-blind,
pre-F0 structural facts about one derivative market relative to its Match-Odds sibling; a
CrossMarketObservationSet groups the Match-Odds observation with its Total Games / Game
Handicap observations. There is NO latent parameter, p_A, p_B, coherence score, final
probability, or tip field — none is representable. Raw ``marketType`` is preserved. These are
preparation for EXT-XMARKET-003; they carry no numerical model.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CrossMarketObservation:
    """One derivative's outcome-blind structural observation at F0. No probability/tip."""

    mo_market_id: str
    derivative_market_id: str
    event_id: str | None
    f0_snapshot_id: str
    f0_decision_timestamp_ms: int
    derivative_market_type: str            # RAW marketType, never renamed
    raw_selection_names: tuple[str, ...]
    parsed_line: float | None
    best_three_depth: int
    matched_volume: float
    quote_age_seconds: float
    market_status: str
    in_play: bool
    suspension_status: str
    cross_matching: bool | None
    redundancy_evidence_status: str        # from the cross-matching evidence policy
    settlement_semantics_status: str
    cohort: str
    # OPTIONAL quality fields — NOT computed here (no fitted maths); a future coherence step
    # under EXT-XMARKET-003 may populate them.
    spread_ticks: int | None = None
    normalized_back_lay_probability_interval: tuple[float, float] | None = None

    def _payload(self) -> dict[str, object]:
        d = asdict(self)
        d["raw_selection_names"] = list(self.raw_selection_names)
        d["normalized_back_lay_probability_interval"] = (
            list(self.normalized_back_lay_probability_interval)
            if self.normalized_back_lay_probability_interval is not None else None
        )
        return d

    def provenance_digest(self) -> str:
        blob = json.dumps(self._payload(), sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()


@dataclass(frozen=True)
class CrossMarketObservationSet:
    """One Match-Odds observation + zero-or-more Total Games / Game Handicap observations."""

    mo_observation: CrossMarketObservation
    total_games_observations: tuple[CrossMarketObservation, ...]
    game_handicap_observations: tuple[CrossMarketObservation, ...]
    format_status: str
    synchronization_status: str
    completeness_status: str

    def to_dict(self) -> dict[str, object]:
        return {
            "mo_observation": self.mo_observation._payload(),
            "total_games_observations": [o._payload() for o in self.total_games_observations],
            "game_handicap_observations": [o._payload() for o in self.game_handicap_observations],
            "format_status": self.format_status,
            "synchronization_status": self.synchronization_status,
            "completeness_status": self.completeness_status,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(self.to_json().encode()).hexdigest()
