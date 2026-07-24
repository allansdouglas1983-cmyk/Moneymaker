"""STAGE3-0006C-D-REV2 §17 — reference architecture boundary + a bounded agreement subset (RED).

The full 14-fixture production/reference comparison runs in the §18/§20 report script
(SOLVER_MILESTONE_D_REFERENCE_REPORT.json); this suite enforces the import boundary by AST and
keeps a fast agreement subset runnable inside the mutation gate.
"""
from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

from sport_tennis.coherence import solver as S
from sport_tennis.coherence.formats import MatchFormat
from sport_tennis.coherence.root_dedup import deduplicate_roots
from sport_tennis.coherence.rootset import build_root_set, classify_per_solve
from sport_tennis.coherence.solver_contracts import ParameterDomain

from . import dedup_reference as dref
from . import solver_reference_d as sref

_FMT = MatchFormat.BO3_AD_TB7_ALL_SETS
_LINE = Decimal("22.5")
_ALLOWED_PRODUCTION = {"sport_tennis.coherence.formats", "sport_tennis.coherence.match",
                       "sport_tennis.coherence.pmf"}


# ------------------------------------------------------------------ architecture boundary
def test_reference_solver_import_boundary() -> None:
    src = (Path(__file__).parent / "solver_reference_d.py").read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        for n in names:
            if n.startswith("sport_tennis"):
                assert n in _ALLOWED_PRODUCTION, f"forbidden production import: {n}"
            assert "root_dedup" not in n and "rootset" not in n and "solver_scan" not in n \
                and "solver_iteration" not in n and "solver_contracts" not in n, n
            assert not (n.startswith("sport_tennis") and n.endswith(".solver")), n


def test_dedup_reference_still_import_clean() -> None:
    src = (Path(__file__).parent / "dedup_reference.py").read_text(encoding="utf-8")
    assert "sport_tennis" not in src.split('"""', 2)[2]  # no production import below docstring


# ------------------------------------------------------------------ dedup-level agreement
def test_rootset_facts_agree_with_reference_on_candidate_sets() -> None:
    dom = ParameterDomain.from_symmetric(0.35, 0.90)

    def mk(pa: float, pb: float, res: float = 1e-5, a_first: bool = True) -> S.Root:
        return S.Root(pa, pb, a_first, res, 1.0, False)

    fixtures = [
        [mk(0.5, 0.5, 3e-5), mk(0.5009, 0.5, 1e-5), mk(0.5018, 0.5, 2e-5)],     # chain
        [mk(0.6, 0.42, 3e-5), mk(0.6004, 0.4202, 1e-5, False), mk(0.4, 0.58, 2e-5)],
        [mk(0.7, 0.3, 1e-5), mk(0.55, 0.45, 2e-5), mk(0.4, 0.6, 3e-5)],
        [],
    ]
    for cands in fixtures:
        rs = build_root_set(deduplicate_roots(cands, 1e-3), dom, 1e-3)
        want = dref.ref_dedup(list(cands), 1e-3)
        assert list(rs.representatives) == want["representatives"]
        assert rs.ambiguous == want["ambiguous"]
        assert rs.root_count == len(want["representatives"])


# ------------------------------------------------------------------ end-to-end agreement subset
def test_production_and_reference_agree_unique_interior_root() -> None:
    tw, to = S.derived_targets(0.68, 0.58, _FMT, _LINE, a_serves_first=True)
    prod = S.identify(tw, to, _LINE, _FMT, domain=(0.35, 0.90))
    want = sref.ref_identify(_FMT, _LINE, tw, to, 0.35, 0.90)
    assert prod.status == want["status"]
    assert len(prod.roots) == len(want["roots"])
    for pr, wr in zip(sorted(prod.roots, key=lambda r: (r.p_a, r.p_b)),
                      sorted(want["roots"], key=lambda r: (r.p_a, r.p_b))):
        assert max(abs(pr.p_a - wr.p_a), abs(pr.p_b - wr.p_b)) < 1e-3


def test_production_and_reference_agree_no_root() -> None:
    prod = S.identify(0.98, 0.02, _LINE, _FMT, domain=(0.35, 0.90))
    want = sref.ref_identify(_FMT, _LINE, 0.98, 0.02, 0.35, 0.90)
    assert prod.status == want["status"] == "NO_ROOT"
    assert prod.roots == () and want["roots"] == []


# ------------------------------------------------------------------ status coherence
def test_reference_status_rule_matches_production_classifier() -> None:
    # the reference's literal per-solve status transcription and the production classifier agree
    # on constructed evidence (a cheap cross-check of the decision table itself)
    def mk(pa: float, pb: float, jd: float = 1.0, boundary: bool = False) -> S.Root:
        return S.Root(pa, pb, True, 1e-5, jd, boundary)

    cases = [
        (False, ()), (False, (mk(0.6, 0.55),)), (False, (mk(0.352, 0.6, boundary=True),)),
        (False, (mk(0.6, 0.55, jd=1e-4),)), (False, (mk(0.6, 0.55), mk(0.4, 0.6))),
        (True, ()),
    ]
    for ambiguous, roots in cases:
        got = classify_per_solve(ambiguous, roots, 5e-3)
        if ambiguous:
            want = "NON_IDENTIFIABLE"
        elif not roots:
            want = "NO_ROOT"
        elif len(roots) > 1:
            want = "MULTIPLE_ROOTS"
        elif abs(roots[0].jacobian_det) < 5e-3:
            want = "NON_IDENTIFIABLE"
        elif roots[0].on_boundary:
            want = "BOUNDARY_SOLUTION"
        else:
            want = "IDENTIFIED"
        assert got == want
