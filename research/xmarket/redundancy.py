"""Cross-market feasibility audit — empirical redundancy / independent-update evidence
(STAGE3-0002 §12; audit code version xmarket-audit-v1).

The historical feed does NOT expose internal order origin, so this NEVER claims to prove
Betfair cross-matching. It classifies OBSERVABLE co-timing between a derivative market's
book-changing updates and its Match-Odds sibling's, using only pre-F0 publish timestamps
(no prices as economic values, no outcomes). The four founder statuses are the only
outputs; a difference in timestamps alone never yields "non-redundant", and genuine
ambiguity stays UNRESOLVED.

Audit-only. Import-quarantined from l5_decision / l5b_risk / l6_broker. No latent model.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

AUDIT_CODE_VERSION = "xmarket-audit-v1"

OBSERVABLY_NON_REDUNDANT_UPDATES = "OBSERVABLY_NON_REDUNDANT_UPDATES"
OBSERVABLY_REDUNDANT_PATH = "OBSERVABLY_REDUNDANT_PATH"
INDEPENDENCE_UNRESOLVED = "INDEPENDENCE_UNRESOLVED"
INSUFFICIENT_UPDATES = "INSUFFICIENT_UPDATES"

# window label -> milliseconds
_WINDOWS = {"0ms": 0, "100ms": 100, "1s": 1000, "5s": 5000}

# thresholds for the observable classification (audit sensitivities, not policy)
_NON_REDUNDANT_FRACTION = 0.8   # most derivative updates have no MO update within 5 s
_MIN_UPDATES_DEFAULT = 5


@dataclass(frozen=True)
class RedundancyEvidence:
    """Observable co-timing evidence for one derivative vs its MO sibling. Outcome-free."""

    derivative_market_id: str
    derivative_update_count: int
    mo_update_count: int
    frac_deriv_without_mo_within: dict[str, float]
    status: str


def _book_change_times(messages: Iterable[Mapping[str, Any]], market_id: str,
                       cutoff_ms: int) -> list[int]:
    """Publish times of book-changing (rc with batb/batl) messages for market_id, pt<=cutoff."""
    out: list[int] = []
    for msg in messages:
        pt = msg.get("pt")
        if not isinstance(pt, int) or pt > cutoff_ms:
            continue
        for mc in msg.get("mc") or []:
            if mc.get("id") != market_id:
                continue
            for rc in mc.get("rc") or []:
                if "batb" in rc or "batl" in rc:
                    out.append(pt)
                    break
    out.sort()
    return out


def _nearest_gap_ms(t: int, sorted_times: list[int]) -> int | None:
    """Smallest absolute time gap from t to any element of sorted_times (None if empty)."""
    if not sorted_times:
        return None
    import bisect
    i = bisect.bisect_left(sorted_times, t)
    best: int | None = None
    for j in (i - 1, i):
        if 0 <= j < len(sorted_times):
            gap = abs(sorted_times[j] - t)
            if best is None or gap < best:
                best = gap
    return best


def classify(mo_messages: Iterable[Mapping[str, Any]],
             derivative_messages: Iterable[Mapping[str, Any]],
             mo_market_id: str, derivative_market_id: str, cutoff_ms: int,
             min_updates: int = _MIN_UPDATES_DEFAULT) -> RedundancyEvidence:
    """Classify the derivative's independence of its MO sibling from observable pre-F0
    co-timing only. Returns one of the four founder statuses."""
    mo_times = _book_change_times(mo_messages, mo_market_id, cutoff_ms)
    deriv_times = _book_change_times(derivative_messages, derivative_market_id, cutoff_ms)

    frac: dict[str, float] = {}
    n = len(deriv_times)
    for label, w in _WINDOWS.items():
        if n == 0:
            frac[label] = 0.0
            continue
        without = 0
        for t in deriv_times:
            gap = _nearest_gap_ms(t, mo_times)
            if gap is None or gap > w:
                without += 1
        frac[label] = without / n

    if n < min_updates:
        status = INSUFFICIENT_UPDATES
    elif frac["5s"] >= _NON_REDUNDANT_FRACTION:
        # most derivative moves occur with no MO move within 5 s -> derivative moves on its own
        status = OBSERVABLY_NON_REDUNDANT_UPDATES
    elif frac["0ms"] == 0.0:
        # every derivative move coincides exactly with an MO move -> looks like a redundant path
        status = OBSERVABLY_REDUNDANT_PATH
    else:
        status = INDEPENDENCE_UNRESOLVED

    return RedundancyEvidence(
        derivative_market_id=derivative_market_id,
        derivative_update_count=n, mo_update_count=len(mo_times),
        frac_deriv_without_mo_within=frac, status=status,
    )


def status_distribution(evidence: list[RedundancyEvidence]) -> dict[str, int]:
    """Count of each redundancy status across a set of derivatives."""
    return dict(Counter(e.status for e in evidence))
