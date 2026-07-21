"""STAGE3-0002 §12/§17 — empirical redundancy / independent-update evidence (red tests).

The historical feed does NOT expose internal order origin, so this never claims to prove
cross-matching. It classifies OBSERVABLE co-timing between a derivative's book-changing
updates and its Match-Odds sibling's, using ONLY pre-F0 publish timestamps (no prices as
values, no outcomes). Statuses are exactly the founder's four:
OBSERVABLY_NON_REDUNDANT_UPDATES, OBSERVABLY_REDUNDANT_PATH, INDEPENDENCE_UNRESOLVED,
INSUFFICIENT_UPDATES. Timestamp difference ALONE never yields "non-redundant"; ambiguity
stays UNRESOLVED. Hermetic: synthetic message lists.
"""
from __future__ import annotations

from typing import Any

from research.xmarket import redundancy as RD


def _rc(mid: str, pt: int, sel: int = 1, hc: float = 0.0) -> dict[str, Any]:
    return {"pt": pt, "mc": [{"id": mid, "rc": [{"id": sel, "hc": hc,
            "batb": [[0, 1.9, 5.0]], "batl": [[0, 2.0, 5.0]]}]}]}


def test_insufficient_updates_when_too_few() -> None:
    deriv = [_rc("d", 100)]
    mo = [_rc("m", 100)]
    ev = RD.classify(mo, deriv, "m", "d", cutoff_ms=1000, min_updates=5)
    assert ev.status == RD.INSUFFICIENT_UPDATES


def test_non_redundant_when_derivative_moves_without_mo() -> None:
    # derivative updates spaced ~100 s apart; the single MO update is >90 s from all of them
    deriv = [_rc("d", t) for t in (100_000, 200_000, 300_000, 400_000, 500_000, 600_000)]
    mo = [_rc("m", 5_000)]  # one MO update, far (>5 s) from every derivative update
    ev = RD.classify(mo, deriv, "m", "d", cutoff_ms=1_000_000, min_updates=5)
    assert ev.derivative_update_count == 6
    assert ev.frac_deriv_without_mo_within["5s"] > 0.8
    assert ev.status == RD.OBSERVABLY_NON_REDUNDANT_UPDATES


def test_redundant_path_when_every_derivative_update_coincides_with_mo() -> None:
    times = (100, 200, 300, 400, 500, 600)
    deriv = [_rc("d", t) for t in times]
    mo = [_rc("m", t) for t in times]  # exact same publish times
    ev = RD.classify(mo, deriv, "m", "d", cutoff_ms=1000, min_updates=5)
    assert ev.frac_deriv_without_mo_within["0ms"] == 0.0
    assert ev.status == RD.OBSERVABLY_REDUNDANT_PATH


def test_unresolved_when_mixed() -> None:
    times = (100, 200, 300, 400, 500, 600)
    deriv = [_rc("d", t) for t in times]
    # half coincide with MO, half do not
    mo = [_rc("m", t) for t in (100, 300, 500)]
    ev = RD.classify(mo, deriv, "m", "d", cutoff_ms=1000, min_updates=5)
    assert ev.status == RD.INDEPENDENCE_UNRESOLVED


def test_only_pre_cutoff_updates_count() -> None:
    deriv = [_rc("d", t) for t in (100, 200, 300, 400, 500)] + [_rc("d", 9000)]
    mo = [_rc("m", 100)]
    ev = RD.classify(mo, deriv, "m", "d", cutoff_ms=1000, min_updates=5)
    assert ev.derivative_update_count == 5  # the pt=9000 update is excluded


def test_aggregate_status_distribution() -> None:
    evs = [
        RD.RedundancyEvidence("d1", 6, 1, {"0ms": 1.0, "100ms": 1.0, "1s": 1.0, "5s": 1.0},
                              RD.OBSERVABLY_NON_REDUNDANT_UPDATES),
        RD.RedundancyEvidence("d2", 6, 6, {"0ms": 0.0, "100ms": 0.0, "1s": 0.0, "5s": 0.0},
                              RD.OBSERVABLY_REDUNDANT_PATH),
        RD.RedundancyEvidence("d3", 2, 2, {"0ms": 0.5, "100ms": 0.5, "1s": 0.5, "5s": 0.5},
                              RD.INSUFFICIENT_UPDATES),
    ]
    dist = RD.status_distribution(evs)
    assert dist[RD.OBSERVABLY_NON_REDUNDANT_UPDATES] == 1
    assert dist[RD.OBSERVABLY_REDUNDANT_PATH] == 1
    assert dist[RD.INSUFFICIENT_UPDATES] == 1
