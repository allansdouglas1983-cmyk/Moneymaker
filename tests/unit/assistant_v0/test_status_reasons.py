"""STAGE3-0003 §5/§8/§12 — V0 status + reason-code registry (red tests first).

Allowed statuses are exactly the five in the directive; the BET/shadow/stake statuses are
NOT enum members, so they are unconstructible by design. No LLM sets a status. Reason codes
are neutral tokens (no causal/promotional language).
"""
from __future__ import annotations

import pytest

from assistant_v0 import reason_codes as RC
from assistant_v0 import status as S


def test_exactly_the_five_allowed_statuses() -> None:
    assert {s.name for s in S.AssistantStatus} == {
        "INSUFFICIENT_DATA", "MARKET_UNAVAILABLE", "MARKET_ONLY",
        "MODEL_VIEW_ONLY", "NO_BET_RESEARCH_ONLY",
    }


@pytest.mark.parametrize("banned", [
    "SHADOW_CANDIDATE", "BET_CANDIDATE", "BET_AUTHORIZED", "PLACE_BET", "STAKE_RECOMMENDATION",
])
def test_bet_family_statuses_are_unconstructible(banned: str) -> None:
    assert banned not in {s.name for s in S.AssistantStatus}
    with pytest.raises(KeyError):
        S.AssistantStatus[banned]


def test_economic_posture_is_always_no_bet_research_only() -> None:
    assert S.ECONOMIC_POSTURE is S.AssistantStatus.NO_BET_RESEARCH_ONLY


def test_status_mapping_priority() -> None:
    assert S.data_status(input_valid=False, market_valid=True, f2_available=True) \
        is S.AssistantStatus.INSUFFICIENT_DATA
    assert S.data_status(input_valid=True, market_valid=False, f2_available=True) \
        is S.AssistantStatus.MARKET_UNAVAILABLE
    assert S.data_status(input_valid=True, market_valid=True, f2_available=True) \
        is S.AssistantStatus.MODEL_VIEW_ONLY
    assert S.data_status(input_valid=True, market_valid=True, f2_available=False) \
        is S.AssistantStatus.MARKET_ONLY


def test_reason_codes_present_and_neutral() -> None:
    names = {c.name for c in RC.ReasonCode}
    for required in ("MARKET_PRICE_AVAILABLE", "MARKET_PRICE_UNAVAILABLE",
                     "MODEL_HISTORY_AVAILABLE", "MODEL_HISTORY_INSUFFICIENT",
                     "MODEL_MARKET_AGREEMENT", "MODEL_MARKET_DISAGREEMENT",
                     "MODEL_NOT_MARKET_PROVEN", "CROSS_MARKET_LAYER_BLOCKED",
                     "LOWER_TIER_DERIVATIVE_COVERAGE_ABSENT", "QUOTE_TIMESTAMP_MISSING",
                     "MARKET_SUSPENDED", "MARKET_IN_PLAY", "CROSSED_BOOK",
                     "IDENTITY_UNRESOLVED", "RESEARCH_ONLY_NO_BET"):
        assert required in names
    # neutral tokens only — no promotional/causal language anywhere in the registry
    promo = ("SAFE", "VALUE", "GUARANTEED", "WILL_WIN", "STRONG", "MUST_BACK", "SURE")
    joined = " ".join(names)
    assert not any(p in joined for p in promo)


def test_reason_registry_version_pinned() -> None:
    assert RC.REASON_CODE_REGISTRY_VERSION == "assistant-v0-reasons-v1"
    assert S.STATUS_REGISTRY_VERSION == "assistant-v0-status-v1"
