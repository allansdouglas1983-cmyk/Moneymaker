"""STAGE3-0006B §5 — differential golden: the solver's registered public behaviour is FROZEN.

This pins the exact `derived_targets` targets and `identify` results (status, canonical roots,
per-server statuses) of the solver as it stood before the §5-§13 mutation-surface refactor. The
refactor MUST reproduce every value byte-for-byte; any deviation is a registered-contract change
requiring an append-only amendment + explicit disclosure (§5). It is the regression oracle for the
refactor and a permanent guard on the solver's public contract.
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from sport_tennis.coherence import solver as S
from sport_tennis.coherence.formats import MatchFormat

_FMT = MatchFormat.BO3_AD_TB7_ALL_SETS
_GOLDEN = json.loads(
    (Path(__file__).parent / "golden" / "solver_behaviour_golden.json").read_text())


def _rnd(x: float | None) -> float | None:
    return None if x is None else round(float(x), 9)


def test_derived_targets_match_golden() -> None:
    for row in _GOLDEN["derived_targets"]:
        tw, to = S.derived_targets(row["pa"], row["pb"], _FMT, Decimal(row["line"]),
                                   a_serves_first=True)
        assert _rnd(tw) == row["tw"], row
        assert _rnd(to) == row["to"], row


def test_identify_matches_golden() -> None:
    for case in _GOLDEN["identify"]:
        r = S.identify(case["tw"], case["to"], Decimal(case["line"]), _FMT,
                       domain=tuple(case["domain"]))  # type: ignore[arg-type]
        got = {
            "status": r.status,
            "roots": sorted([[_rnd(rt.p_a), _rnd(rt.p_b), rt.a_serves_first, _rnd(rt.residual),
                              _rnd(rt.jacobian_det), rt.on_boundary] for rt in r.roots]),
            "per_server": [[s.a_serves_first, s.status,
                            sorted([[_rnd(x.p_a), _rnd(x.p_b)] for x in s.roots])]
                           for s in r.per_server],
            "domain": list(r.domain), "line": str(r.line),
        }
        assert got == case["out"], f"golden mismatch for {case['line']} {case['domain']}"
