"""PERSONAL_TENNIS_ASSISTANT_V0 — deterministic reason-code registry (STAGE3-0003 §8).

Frozen, neutral tokens derived from the numerical core. They carry NO causal or promotional
language: no "safe bet", "value", "guaranteed", "will win", "strong", "must back". An LLM
may render an approved code into plain language but never invents a reason or a number.
"""
from __future__ import annotations

from enum import Enum

# v2 (PROGRAMME RESET AND OPERATIONAL V0 RELEASE §6): APPEND-ONLY extension adding
# ONE_SIDED_BOOK for the mandated two-sided-book validation. No token was removed or
# renamed; every v1 token retains its exact meaning.
REASON_CODE_REGISTRY_VERSION = "assistant-v0-reasons-v2"


class ReasonCode(Enum):
    """The frozen V0 reason-code registry (§8). Neutral, sign/availability tokens only."""

    MARKET_PRICE_AVAILABLE = "MARKET_PRICE_AVAILABLE"
    MARKET_PRICE_UNAVAILABLE = "MARKET_PRICE_UNAVAILABLE"
    MODEL_HISTORY_AVAILABLE = "MODEL_HISTORY_AVAILABLE"
    MODEL_HISTORY_INSUFFICIENT = "MODEL_HISTORY_INSUFFICIENT"
    MODEL_MARKET_AGREEMENT = "MODEL_MARKET_AGREEMENT"
    MODEL_MARKET_DISAGREEMENT = "MODEL_MARKET_DISAGREEMENT"
    MODEL_NOT_MARKET_PROVEN = "MODEL_NOT_MARKET_PROVEN"
    CROSS_MARKET_LAYER_BLOCKED = "CROSS_MARKET_LAYER_BLOCKED"
    LOWER_TIER_DERIVATIVE_COVERAGE_ABSENT = "LOWER_TIER_DERIVATIVE_COVERAGE_ABSENT"
    QUOTE_TIMESTAMP_MISSING = "QUOTE_TIMESTAMP_MISSING"
    MARKET_SUSPENDED = "MARKET_SUSPENDED"
    MARKET_IN_PLAY = "MARKET_IN_PLAY"
    CROSSED_BOOK = "CROSSED_BOOK"
    ONE_SIDED_BOOK = "ONE_SIDED_BOOK"
    IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"
    RESEARCH_ONLY_NO_BET = "RESEARCH_ONLY_NO_BET"
