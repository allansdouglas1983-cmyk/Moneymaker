"""PERSONAL_TENNIS_ASSISTANT_V0 — status registry (STAGE3-0003 §5).

Exactly five allowed statuses. The BET / shadow / stake statuses (SHADOW_CANDIDATE,
BET_CANDIDATE, BET_AUTHORIZED, PLACE_BET, STAKE_RECOMMENDATION) are NOT members of this
enum, so they are unconstructible by design — there is no token to assign. No LLM sets or
overrides a status; the mapping below is deterministic.

The economic posture in V0 is ALWAYS ``NO_BET_RESEARCH_ONLY`` (the default and only
constructible economic posture); the data/model availability is one of the other four.
"""
from __future__ import annotations

from enum import Enum

STATUS_REGISTRY_VERSION = "assistant-v0-status-v1"


class AssistantStatus(Enum):
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    MARKET_UNAVAILABLE = "MARKET_UNAVAILABLE"
    MARKET_ONLY = "MARKET_ONLY"
    MODEL_VIEW_ONLY = "MODEL_VIEW_ONLY"
    NO_BET_RESEARCH_ONLY = "NO_BET_RESEARCH_ONLY"


# The standing economic posture in V0 — never a bet, never a stake, never a tip.
ECONOMIC_POSTURE = AssistantStatus.NO_BET_RESEARCH_ONLY


def data_status(*, input_valid: bool, market_valid: bool, f2_available: bool) -> AssistantStatus:
    """Deterministic data/model availability status (§5). Priority: invalid input ->
    INSUFFICIENT_DATA; no usable market -> MARKET_UNAVAILABLE; a usable market with an
    available F2 diagnostic -> MODEL_VIEW_ONLY; otherwise MARKET_ONLY."""
    if not input_valid:
        return AssistantStatus.INSUFFICIENT_DATA
    if not market_valid:
        return AssistantStatus.MARKET_UNAVAILABLE
    if f2_available:
        return AssistantStatus.MODEL_VIEW_ONLY
    return AssistantStatus.MARKET_ONLY
