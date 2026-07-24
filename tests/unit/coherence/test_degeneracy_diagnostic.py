"""STAGE3-0006C-D-A2 — synthetic root-degeneracy diagnostic (RED, tests-first).

Test-only analysis machinery: the four predeclared scan lattices (G0-G3), the parameterised
production harness (production algorithm, injectable lattice, nothing else altered), the §6
root-set stability comparison under the EXISTING strict dedup relation, and the §12 decision
truth table. Production source, root_dedup.py and both goldens must remain byte-identical —
the harness's G0 run must reproduce the production identify() result exactly.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from sport_tennis.coherence import solver as S
from sport_tennis.coherence.formats import MatchFormat

from .degeneracy_harness import (
    compare_lattice_results,
    decide_verdict,
    identify_with_lattice,
    lattice_g0,
    lattice_g1,
    lattice_g2,
    lattice_g3,
)

_FMT = MatchFormat.BO3_AD_TB7_ALL_SETS
_LINE = Decimal("22.5")
_LO, _HI = 0.35, 0.90


# ------------------------------------------------------------------ §5 lattice generators
def test_g0_is_exactly_the_production_axis() -> None:
    g0 = lattice_g0(_LO, _HI)
    assert g0 == [_LO + (_HI - _LO) * i / 12 for i in range(13)]
    assert len(g0) == 13 and g0[0] == _LO and g0[-1] == _HI


def test_g1_nested_double_density() -> None:
    g0, g1 = lattice_g0(_LO, _HI), lattice_g1(lattice_g0(_LO, _HI))
    assert len(g1) == 25
    assert g1[0] == _LO and g1[-1] == _HI
    assert all(x in g1 for x in g0)                        # every G0 coordinate retained
    for a, b in zip(g0, g0[1:]):
        assert (a + b) / 2 in g1                           # exact midpoint inserted
    assert all(x < y for x, y in zip(g1, g1[1:]))          # strictly increasing


def test_g2_half_cell_phase_shift() -> None:
    g0, g2 = lattice_g0(_LO, _HI), lattice_g2(lattice_g0(_LO, _HI))
    assert len(g2) == 13
    assert g2[0] == _LO and g2[-1] == _HI                  # exact boundaries retained
    for i in range(1, 12):                                 # interior shifted by half right-cell
        assert g2[i] == g0[i] + (g0[i + 1] - g0[i]) / 2
    assert all(x < y for x, y in zip(g2, g2[1:]))
    assert len(set(g2)) == len(g2)                         # no duplicates


def test_g3_double_density_phase_shift() -> None:
    g1, g3 = lattice_g1(lattice_g0(_LO, _HI)), lattice_g3(lattice_g1(lattice_g0(_LO, _HI)))
    assert g3[0] == _LO and g3[-1] == _HI
    for i in range(1, len(g1) - 1):
        assert g1[i] + (g1[i + 1] - g1[i]) / 2 in g3
    assert all(x < y for x, y in zip(g3, g3[1:]))
    assert len(set(g3)) == len(g3)


# ------------------------------------------------------------------ §4 harness fidelity
def test_harness_g0_reproduces_production_identify_exactly() -> None:
    tw, to = S.derived_targets(0.5, 0.5, _FMT, _LINE, a_serves_first=True)
    prod = S.identify(tw, to, _LINE, _FMT, domain=(_LO, _HI))
    har = identify_with_lattice(lattice_g0(_LO, _HI), _FMT, _LINE, tw, to, (_LO, _HI))
    assert har["status"] == prod.status
    assert tuple(har["roots"]) == prod.roots                # EXACT float equality
    assert [s["status"] for s in har["per_server"]] == [s.status for s in prod.per_server]
    assert [tuple(s["roots"]) for s in har["per_server"]] == [s.roots for s in prod.per_server]


def test_harness_exposes_candidate_provenance() -> None:
    tw, to = S.derived_targets(0.68, 0.58, _FMT, _LINE, a_serves_first=True)
    har = identify_with_lattice(lattice_g0(_LO, _HI), _FMT, _LINE, tw, to, (_LO, _HI))
    solve = har["per_server"][0]
    assert solve["axis"] == lattice_g0(_LO, _HI)
    assert len(solve["seeds"]) >= 1
    for cand in solve["candidates"]:
        assert set(cand) >= {"seed", "p_a", "p_b", "r2", "converged", "jacobian_det",
                             "condition_scale", "on_boundary"}
    assert any(c["converged"] for c in solve["candidates"])


# ------------------------------------------------------------------ §6 stability comparison
def _fake_result(status: str, roots: list[tuple[float, float]]) -> dict[str, object]:
    made = tuple(S.Root(pa, pb, True, 1e-5, 1.0, False) for pa, pb in roots)
    return {"status": status, "roots": made,
            "per_server": [{"status": status, "roots": made, "axis": [], "seeds": [],
                            "candidates": []}] * 2}


def test_compare_lattices_stable_when_all_agree() -> None:
    r = _fake_result("IDENTIFIED", [(0.6, 0.55)])
    out = compare_lattice_results({"G0": r, "G1": r, "G2": r, "G3": r},
                                  (_LO, _HI), S._DEDUP_TOL)
    assert out["verdict"] == "DISCRETISATION_STABLE"


def test_compare_lattices_sensitive_on_count_or_pairing_change() -> None:
    base = _fake_result("MULTIPLE_ROOTS", [(0.496, 0.496), (0.5043, 0.5043)])
    other = _fake_result("MULTIPLE_ROOTS", [(0.496, 0.496), (0.4997, 0.4997),
                                            (0.5043, 0.5043)])
    out = compare_lattice_results({"G0": base, "G1": other, "G2": base, "G3": base},
                                  (_LO, _HI), S._DEDUP_TOL)
    assert out["verdict"] == "DISCRETISATION_SENSITIVE"
    # pairing failure alone (same count, unpairable coordinates) is also sensitive
    moved = _fake_result("MULTIPLE_ROOTS", [(0.496, 0.496), (0.507, 0.507)])
    out2 = compare_lattice_results({"G0": base, "G1": moved, "G2": base, "G3": base},
                                   (_LO, _HI), S._DEDUP_TOL)
    assert out2["verdict"] == "DISCRETISATION_SENSITIVE"
    # status change is sensitive even between non-actionable statuses
    st = _fake_result("NON_IDENTIFIABLE", [(0.496, 0.496), (0.5043, 0.5043)])
    out3 = compare_lattice_results({"G0": base, "G1": st, "G2": base, "G3": base},
                                   (_LO, _HI), S._DEDUP_TOL)
    assert out3["verdict"] == "DISCRETISATION_SENSITIVE"


# ------------------------------------------------------------------ §12 decision truth table
@pytest.mark.parametrize("facts,verdict", [
    # A: production sensitive; reference stable or extended region; count/status varies by lattice
    (dict(production_stable=False, reference_stable=True, low_residual_extended=True,
          singular_on_path=True, condition_failure_on_path=True,
          counts_or_status_vary_with_lattice=True, diagnostic_bounded=True),
     "AMENDMENT_DISCRETISATION_STABILITY_REQUIRED"),
    (dict(production_stable=False, reference_stable=False, low_residual_extended=True,
          singular_on_path=False, condition_failure_on_path=False,
          counts_or_status_vary_with_lattice=True, diagnostic_bounded=True),
     "AMENDMENT_DISCRETISATION_STABILITY_REQUIRED"),
    # B: both stable; singular/condition evidence on sub-tolerance path
    (dict(production_stable=True, reference_stable=True, low_residual_extended=True,
          singular_on_path=True, condition_failure_on_path=False,
          counts_or_status_vary_with_lattice=False, diagnostic_bounded=True),
     "AMENDMENT_VALLEY_DEGENERACY_REQUIRED"),
    (dict(production_stable=True, reference_stable=True, low_residual_extended=False,
          singular_on_path=False, condition_failure_on_path=True,
          counts_or_status_vary_with_lattice=False, diagnostic_bounded=True),
     "AMENDMENT_VALLEY_DEGENERACY_REQUIRED"),
    # C: production stable + separated; no degeneracy evidence; reference unstable
    (dict(production_stable=True, reference_stable=False, low_residual_extended=False,
          singular_on_path=False, condition_failure_on_path=False,
          counts_or_status_vary_with_lattice=False, diagnostic_bounded=True),
     "REFERENCE_IMPLEMENTATION_DEFECT"),
    # D: both internally stable, still disagreeing, no deciding diagnostics
    (dict(production_stable=True, reference_stable=True, low_residual_extended=False,
          singular_on_path=False, condition_failure_on_path=False,
          counts_or_status_vary_with_lattice=False, diagnostic_bounded=True),
     "MATHEMATICAL_CONTRACT_UNRESOLVED"),
    # E: diagnostic not boundable
    (dict(production_stable=False, reference_stable=False, low_residual_extended=False,
          singular_on_path=False, condition_failure_on_path=False,
          counts_or_status_vary_with_lattice=False, diagnostic_bounded=False),
     "SOLVER_PATH_NOT_ECONOMICAL"),
])
def test_decision_truth_table(facts: dict[str, bool], verdict: str) -> None:
    assert decide_verdict(**facts) == verdict


# ------------------------------------------------------------------ architecture boundary
def test_harness_is_test_only() -> None:
    import subprocess
    out = subprocess.run(
        ["grep", "-rl", "degeneracy_harness",
         "sport_tennis", "assistant_v0", "l4_pricing", "l5_decision", "l6_broker"],
        capture_output=True, text=True, check=False)
    assert out.stdout.strip() == ""      # no production package imports the harness


# ------------------------------------------------------------------ §3 freeze pin
def test_fixture_freeze_artifact_matches_live_production() -> None:
    import json
    from pathlib import Path

    frozen = json.loads(Path(
        "docs/evidence/stage3-cross-market-audit/SOLVER_DEGENERACY_FIXTURE_FREEZE_V1.json"
    ).read_text())
    fx = frozen["fixture"]
    tw, to = S.derived_targets(0.5, 0.5, _FMT, _LINE, a_serves_first=True)
    assert fx["match_odds_target"] == tw and fx["total_games_target"] == to
    prod = S.identify(tw, to, _LINE, _FMT, domain=(_LO, _HI))
    assert prod.status == frozen["production_status"]
    assert [(r.p_a, r.p_b) for r in prod.roots] \
        == [(r["p_a"], r["p_b"]) for r in frozen["production_roots"]]
    assert frozen["production_scan_axis"] == lattice_g0(_LO, _HI)
