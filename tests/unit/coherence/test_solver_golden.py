"""Differential golden: the solver's registered public behaviour is FROZEN — V2 vintage.

GOVERNED VINTAGE CHANGE (STAGE3-0006C-D-A1 / CROSS_MARKET_COHERENCE_ROOT_DEDUP_AMENDMENT_V1):
this oracle now pins SOLVER_GOLDEN_V2_CANONICAL_SET_DEFINED — the amended solver whose root
deduplication is set-defined canonical clustering with ambiguous-chain refusal. The prior vintage
SOLVER_GOLDEN_V1_SEQUENCE_DEFINED.json is RETAINED unmodified as permanent historical evidence of
the corrected sequence-defined defect; the V1->V2 change is fully classified in
SOLVER_ROOT_DEDUP_AMENDMENT_DIFFERENTIAL.json (UNEXPECTED_CHANGE = 0). Any future deviation from
V2 is a registered-contract change requiring a further append-only amendment.
"""
from __future__ import annotations

import itertools
import json
from decimal import Decimal
from pathlib import Path

from sport_tennis.coherence import solver as S
from sport_tennis.coherence.formats import MatchFormat
from sport_tennis.coherence.root_dedup import deduplicate_roots

_FMT = MatchFormat.BO3_AD_TB7_ALL_SETS
_GOLDEN = json.loads(
    (Path(__file__).parent / "golden" / "SOLVER_GOLDEN_V2_CANONICAL_SET_DEFINED.json").read_text())


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


def test_dedup_unit_fixtures_match_golden() -> None:
    """The §8-mandated dedup-level pins: chain refusal (identical for every permutation), valid
    close cluster, distinct multi-root, first-server provenance, boundary metadata."""
    du = _GOLDEN["dedup_unit"]
    tol = du["tolerance"]

    def mk(pa, pb, res=1e-5, a_first=True, jd=1.0, boundary=False):  # noqa: ANN001, ANN202
        return S.Root(p_a=pa, p_b=pb, a_serves_first=a_first, residual=res, jacobian_det=jd,
                      on_boundary=boundary)

    chain = [mk(0.5, 0.5, 3e-5), mk(0.5009, 0.5, 1e-5), mk(0.5018, 0.5, 2e-5)]
    assert deduplicate_roots(chain, tol).serialize() == du["chain_refusal"]
    assert {deduplicate_roots(list(p), tol).digest()
            for p in itertools.permutations(chain)} \
        == {du["chain_all_permutations_digest"]}
    close = [mk(0.5, 0.5, 3e-5), mk(0.5004, 0.5002, 1e-5), mk(0.4998, 0.5004, 2e-5)]
    assert deduplicate_roots(close, tol).serialize() == du["valid_close_cluster"]
    multi = [mk(0.4, 0.6, 1e-5), mk(0.7, 0.3, 5e-5), mk(0.55, 0.45, 9e-5)]
    assert deduplicate_roots(multi, tol).serialize() == du["distinct_multi_root"]
    fserver = [mk(0.5, 0.5, 2e-5, True), mk(0.5002, 0.5001, 1e-5, False)]
    assert deduplicate_roots(fserver, tol).serialize() == du["first_server_provenance"]
    bmix = [mk(0.5, 0.5, 1e-5, boundary=False), mk(0.5004, 0.5, 2e-5, boundary=True)]
    assert deduplicate_roots(bmix, tol).serialize() == du["boundary_metadata"]
