"""STAGE3-0006C-D-A2 — staged degeneracy diagnostic driver (test-only; production untouched).

Stages (each bounded, run in its own foreground call):
  freeze                 -> fixture freeze part
  grids G0 G2 / G1 G3    -> production lattice-sensitivity parts
  reference R0|R1|R2     -> reference resolution parts
  surface                -> bounding box + 129x129 matrix + pair paths + det bisection
  decide                 -> provenance audit + §6/§7/§9 classification + §12 verdict + artifacts

All stages write machine-readable parts under --out (default docs/evidence/.../degen_run1).
`generated_at_utc` is the ONLY nondeterministic field and is isolated for the §14 byte-identity
comparison. No production file is imported for writing; nothing is mutated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, ".")
from sport_tennis.coherence import solver as S  # noqa: E402
from sport_tennis.coherence.formats import MatchFormat  # noqa: E402
from tests.unit.coherence import degeneracy_harness as H  # noqa: E402
from tests.unit.coherence import solver_reference_d as sref  # noqa: E402

D = Path("docs/evidence/stage3-cross-market-audit")
_FMT = MatchFormat.BO3_AD_TB7_ALL_SETS
_LINE = Decimal("22.5")
_LO, _HI = 0.35, 0.90
SCHEMA = "degeneracy-diagnostic-v1"


def meta() -> dict[str, object]:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()

    def sha(p: str) -> str:
        return hashlib.sha256(Path(p).read_bytes()).hexdigest()

    return {
        "schema_version": SCHEMA,
        "commit": commit,
        "source_digests": {
            "solver.py": sha("sport_tennis/coherence/solver.py"),
            "root_dedup.py": sha("sport_tennis/coherence/root_dedup.py"),
            "rootset.py": sha("sport_tennis/coherence/rootset.py"),
            "harness": sha("tests/unit/coherence/degeneracy_harness.py"),
            "reference": sha("tests/unit/coherence/solver_reference_d.py"),
            "golden_v2": sha(
                "tests/unit/coherence/golden/SOLVER_GOLDEN_V2_CANONICAL_SET_DEFINED.json"),
            "amendment": sha(
                "specs/programme/cross-market-coherence-root-dedup-amendment-v1.yaml"),
        },
        "constants": {"_COARSE_N": S._COARSE_N, "_N_SEED": S._N_SEED, "_CLUSTER_R": S._CLUSTER_R,
                      "_ROOT_TOL": S._ROOT_TOL, "_DEDUP_TOL": S._DEDUP_TOL,
                      "_JAC_TOL": S._JAC_TOL, "_BOUNDARY_TOL": S._BOUNDARY_TOL,
                      "_NEWTON_SINGULAR": S._NEWTON_SINGULAR},
        "deterministic_seed": None,
    }


def fixture() -> dict[str, object]:
    tw, to = S.derived_targets(0.5, 0.5, _FMT, _LINE, a_serves_first=True)
    fx = {"format": _FMT.name, "line": str(_LINE), "domain": [_LO, _HI],
          "generating_pair": [0.5, 0.5], "generating_first_server": True,
          "match_odds_target": tw, "total_games_target": to,
          "note": "synthetic targets derived from (0.5, 0.5); the match-odds target plays the "
                  "role the market target would play — NO market data was read"}
    fx["fixture_digest"] = "sha256:" + hashlib.sha256(
        json.dumps(fx, sort_keys=True).encode()).hexdigest()
    return fx


def root_row(r: S.Root, a_first: bool, tw: float, to: float) -> dict[str, object]:
    f1, f2 = S._residual(r.p_a, r.p_b, a_first, _FMT, _LINE, tw, to)
    jac = S._jacobian_matrix(r.p_a, r.p_b, a_first, _FMT, _LINE, tw, to)
    return {"p_a": r.p_a, "p_b": r.p_b, "a_serves_first": r.a_serves_first,
            "residual_vector": [f1, f2], "residual_norm": r.residual,
            "jacobian": jac.serialize(), "determinant": jac.determinant(),
            "condition_scale": jac.condition_scale(),
            "singular": abs(jac.determinant()) < S._JAC_TOL, "on_boundary": r.on_boundary}


def _sidecar(out: Path, key: str, runtime: float) -> None:
    """Runtimes live OUTSIDE the deterministic artifacts (excluded from the §14 byte-identity
    comparison along with the isolated timestamp field)."""
    f = out / "runtimes_sidecar.json"
    data = json.loads(f.read_text()) if f.exists() else {}
    data[key] = round(runtime, 3)
    f.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")


def write(out: Path, name: str, payload: dict[str, object]) -> None:
    payload = {**meta(), **payload, "generated_at_utc": datetime.now(timezone.utc).isoformat()}
    out.mkdir(parents=True, exist_ok=True)
    (out / name).write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n")
    print("wrote", out / name)


def stage_freeze(out: Path) -> None:
    fx = fixture()
    tw, to = fx["match_odds_target"], fx["total_games_target"]
    prod = S.identify(tw, to, _LINE, _FMT, domain=(_LO, _HI))
    ref = sref.ref_identify(_FMT, _LINE, tw, to, _LO, _HI)
    deep = ref["roots"][0] if ref["roots"] else None
    payload = {
        "fixture": fx,
        "production_scan_axis": H.lattice_g0(_LO, _HI),
        "seed_rule": "rank_seed_nodes(grid, _N_SEED, _CLUSTER_R) — lowest residual-norm nodes, "
                     "Chebyshev-clustered",
        "production_status": prod.status,
        "production_roots": [root_row(r, r.a_serves_first, tw, to) for r in prod.roots],
        "per_server": [{"a_serves_first": s.a_serves_first, "status": s.status,
                        "roots": [root_row(r, s.a_serves_first, tw, to) for r in s.roots]}
                       for s in prod.per_server],
        "cluster_provenance": [c.serialize() for c in
                               __import__("sport_tennis.coherence.root_dedup",
                                          fromlist=["deduplicate_roots"]).deduplicate_roots(
                                   list(prod.roots), S._DEDUP_TOL).clusters],
        "reference_status": ref["status"],
        "reference_roots": [{"p_a": r.p_a, "p_b": r.p_b, "residual_norm": r.residual,
                             "jacobian_det": r.jacobian_det, "on_boundary": r.on_boundary}
                            for r in ref["roots"]],
        "reference_deepest": None if deep is None else
            {"p_a": deep.p_a, "p_b": deep.p_b, "residual_norm": deep.residual,
             "jacobian_det": deep.jacobian_det},
    }
    write(out, "SOLVER_DEGENERACY_FIXTURE_FREEZE_V1.json", payload)


def stage_grids(out: Path, names: list[str]) -> None:
    fx = fixture()
    tw, to = fx["match_odds_target"], fx["total_games_target"]
    g0 = H.lattice_g0(_LO, _HI)
    lattices = {"G0": g0, "G1": H.lattice_g1(g0), "G2": H.lattice_g2(g0),
                "G3": H.lattice_g3(H.lattice_g1(g0))}
    for name in names:
        t0 = time.monotonic()
        res = H.identify_with_lattice(lattices[name], _FMT, _LINE, tw, to, (_LO, _HI))
        runtime = time.monotonic() - t0
        payload = {
            "lattice": name, "axis": lattices[name], "axis_size": len(lattices[name]),
            "status": res["status"],
            "roots": [root_row(r, r.a_serves_first, tw, to) for r in res["roots"]],
            "union_ambiguous": res["union_ambiguous"],
            "per_server": [{"a_serves_first": s["a_serves_first"], "status": s["status"],
                            "seed_count": len(s["seeds"]), "seeds": s["seeds"],
                            "accepted_before_dedup": s["accepted_before_dedup"],
                            "candidates": s["candidates"],
                            "roots": [[r.p_a, r.p_b] for r in s["roots"]]}
                           for s in res["per_server"]],
        }
        write(out, f"grid_{name}.json", payload)
        _sidecar(out, f"grid_{name}", runtime)


def stage_reference(out: Path, rname: str) -> None:
    fx = fixture()
    tw, to = fx["match_odds_target"], fx["total_games_target"]
    if rname == "R0":
        axis = [_LO + (_HI - _LO) * k / 26 for k in range(27)]
    elif rname == "R1":
        axis = [_LO + (_HI - _LO) * k / 52 for k in range(53)]
    else:  # R2: R1 with half-cell phase shift, boundaries retained
        r1 = [_LO + (_HI - _LO) * k / 52 for k in range(53)]
        axis = H.lattice_g2(r1)
    t0 = time.monotonic()
    ref = sref.ref_identify(_FMT, _LINE, tw, to, _LO, _HI, axis=axis)
    runtime = time.monotonic() - t0
    payload = {
        "resolution": rname, "axis_size": len(axis), "axis_first_last": [axis[0], axis[-1]],
        "status": ref["status"],
        "roots": [{"p_a": r.p_a, "p_b": r.p_b, "residual_norm": r.residual,
                   "jacobian_det": r.jacobian_det,
                   "singular": abs(r.jacobian_det) < S._JAC_TOL,
                   "on_boundary": r.on_boundary} for r in ref["roots"]],
        "per_assignment_status": {"a_first": ref["per"][True], "b_first": ref["per"][False]},
    }
    write(out, f"reference_{rname}.json", payload)
    _sidecar(out, f"reference_{rname}", runtime)


def stage_surface(out: Path) -> None:
    fx = fixture()
    tw, to = fx["match_odds_target"], fx["total_games_target"]
    pts: list[tuple[float, float]] = []
    for name in ("G0", "G1", "G2", "G3"):
        data = json.loads((out / f"grid_{name}.json").read_text())
        pts += [(r["p_a"], r["p_b"]) for r in data["roots"]]
    for rname in ("R0", "R1", "R2"):
        data = json.loads((out / f"reference_{rname}.json").read_text())
        pts += [(r["p_a"], r["p_b"]) for r in data["roots"]]
    pad = S._DEDUP_TOL
    box = [max(_LO, min(p[0] for p in pts) - pad), min(_HI, max(p[0] for p in pts) + pad),
           max(_LO, min(p[1] for p in pts) - pad), min(_HI, max(p[1] for p in pts) + pad)]
    n = 129
    ax = [box[0] + (box[1] - box[0]) * i / (n - 1) for i in range(n)]
    ay = [box[2] + (box[3] - box[2]) * i / (n - 1) for i in range(n)]
    conv_tol2 = S._ROOT_TOL * S._ROOT_TOL
    matrix = []
    conv_cells = []
    for i, pa in enumerate(ax):
        row = []
        for j, pb in enumerate(ay):
            f1, f2 = S._residual(pa, pb, True, _FMT, _LINE, tw, to)
            r2 = f1 * f1 + f2 * f2
            row.append([f1, f2, r2])
            if r2 <= conv_tol2:
                conv_cells.append([i, j])
        matrix.append(row)
    # jacobian fields on a decimated 33x33 sublattice (full 129x129 jacobians = 4x residual cost;
    # residual matrix is complete, jacobian sampled deterministically every 4th node)
    jac_rows = []
    for i in range(0, n, 4):
        for j in range(0, n, 4):
            jac = S._jacobian_matrix(ax[i], ay[j], True, _FMT, _LINE, tw, to)
            jac_rows.append([i, j, jac.determinant(), jac.condition_scale(),
                             abs(jac.determinant()) < S._JAC_TOL])
    # non-adjacent converged-cell test (§9 D)
    def adjacent(a: list[int], b: list[int]) -> bool:
        return max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= 1
    extended = any(not adjacent(a, b) for i, a in enumerate(conv_cells)
                   for b in conv_cells[i + 1:])
    write(out, "SOLVER_DEGENERACY_SURFACE_MATRIX_V1.json", {
        "bounding_box": {"p_a": [box[0], box[1]], "p_b": [box[2], box[3]],
                         "padding": pad, "clipped_to_domain": [_LO, _HI]},
        "lattice_n": n, "axis_p_a": ax, "axis_p_b": ay,
        "residual_matrix_f1_f2_r2": matrix,
        "jacobian_sublattice_every_4": jac_rows,
        "converged_cells": conv_cells,
        "low_residual_region_extended": extended,
        "label": "SYNTHETIC_FINITE_DIAGNOSTIC_EVIDENCE",
    })
    # §8.3/§8.4 pair paths over canonical production roots from all lattices
    canon: list[tuple[float, float]] = []
    for name in ("G0", "G1", "G2", "G3"):
        data = json.loads((out / f"grid_{name}.json").read_text())
        for r in data["roots"]:
            if not any(max(abs(r["p_a"] - c[0]), abs(r["p_b"] - c[1])) < S._DEDUP_TOL
                       for c in canon):
                canon.append((r["p_a"], r["p_b"]))
    paths = []
    for i, a in enumerate(canon):
        for b in canon[i + 1:]:
            samples = []
            for k in range(257):
                t = k / 256
                pa, pb = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                f1, f2 = S._residual(pa, pb, True, _FMT, _LINE, tw, to)
                jac = S._jacobian_matrix(pa, pb, True, _FMT, _LINE, tw, to)
                samples.append([pa, pb, f1, f2, f1 * f1 + f2 * f2, jac.determinant(),
                                jac.condition_scale(),
                                abs(jac.determinant()) < S._JAC_TOL,
                                f1 * f1 + f2 * f2 <= conv_tol2])
            # §8.4 determinant sign-change bisection
            zeros = []
            for k in range(256):
                d0, d1 = samples[k][5], samples[k + 1][5]
                if d0 * d1 < 0:
                    t0, t1 = k / 256, (k + 1) / 256
                    for _ in range(80):
                        tm = (t0 + t1) / 2
                        pa = a[0] + (b[0] - a[0]) * tm
                        pb = a[1] + (b[1] - a[1]) * tm
                        dm = S._jacobian_matrix(pa, pb, True, _FMT, _LINE, tw, to).determinant()
                        if dm == 0.0:
                            break
                        if (dm < 0) == (d0 < 0):
                            t0 = tm
                        else:
                            t1 = tm
                    pa = a[0] + (b[0] - a[0]) * (t0 + t1) / 2
                    pb = a[1] + (b[1] - a[1]) * (t0 + t1) / 2
                    f1, f2 = S._residual(pa, pb, True, _FMT, _LINE, tw, to)
                    zeros.append({"t": (t0 + t1) / 2, "p_a": pa, "p_b": pb,
                                  "residual_vector": [f1, f2], "r2": f1 * f1 + f2 * f2,
                                  "residual_converged": f1 * f1 + f2 * f2 <= conv_tol2})
            all_conv = all(s[8] for s in samples)
            cond_fail = any(s[8] and s[7] for s in samples)
            sing_on_path = any(z["residual_converged"] for z in zeros)
            paths.append({"endpoints": [list(a), list(b)], "samples": samples,
                          "determinant_zeros": zeros,
                          "CONNECTED_SUBTOLERANCE_PATH_OBSERVED": all_conv,
                          "SINGULAR_POINT_ON_SUBTOLERANCE_PATH_OBSERVED": sing_on_path,
                          "CONDITION_FAILURE_ON_SUBTOLERANCE_PATH_OBSERVED": cond_fail})
    write(out, "SOLVER_DEGENERACY_PATH_DIAGNOSTICS_V1.json", {
        "canonical_production_roots": [list(c) for c in canon],
        "paths": paths, "label": "SYNTHETIC_FINITE_DIAGNOSTIC_EVIDENCE",
    })


def stage_decide(out: Path) -> None:
    grids = {n: json.loads((out / f"grid_{n}.json").read_text())
             for n in ("G0", "G1", "G2", "G3")}
    refs = {n: json.loads((out / f"reference_{n}.json").read_text())
            for n in ("R0", "R1", "R2")}
    paths = json.loads((out / "SOLVER_DEGENERACY_PATH_DIAGNOSTICS_V1.json").read_text())
    surface = json.loads((out / "SOLVER_DEGENERACY_SURFACE_MATRIX_V1.json").read_text())

    lattice_results = {}
    for name, g in grids.items():
        lattice_results[name] = {
            "status": g["status"],
            "roots": tuple(S.Root(r["p_a"], r["p_b"], r["a_serves_first"], r["residual_norm"],
                                  r["determinant"], r["on_boundary"]) for r in g["roots"]),
            "per_server": g["per_server"]}
    comparison = H.compare_lattice_results(lattice_results, (_LO, _HI), S._DEDUP_TOL)
    production_stable = comparison["verdict"] == "DISCRETISATION_STABLE"
    counts = {n: len(g["roots"]) for n, g in grids.items()}
    statuses = {n: g["status"] for n, g in grids.items()}
    counts_or_status_vary = len(set(counts.values())) > 1 or len(set(statuses.values())) > 1 \
        or not production_stable

    ref_statuses = {n: r["status"] for n, r in refs.items()}
    ref_counts = {n: len(r["roots"]) for n, r in refs.items()}
    deep_pts = {n: (r["roots"][0]["p_a"], r["roots"][0]["p_b"]) if r["roots"] else None
                for n, r in refs.items()}
    ref_stable = len(set(ref_statuses.values())) == 1 and len(set(ref_counts.values())) == 1 \
        and all(p is not None for p in deep_pts.values()) \
        and all(max(abs(deep_pts["R0"][0] - p[0]), abs(deep_pts["R0"][1] - p[1])) < S._DEDUP_TOL
                for p in deep_pts.values())

    singular_on_path = any(p["SINGULAR_POINT_ON_SUBTOLERANCE_PATH_OBSERVED"]
                           for p in paths["paths"])
    condition_failure = any(p["CONDITION_FAILURE_ON_SUBTOLERANCE_PATH_OBSERVED"]
                            for p in paths["paths"])
    connected = any(p["CONNECTED_SUBTOLERANCE_PATH_OBSERVED"] for p in paths["paths"])
    extended = surface["low_residual_region_extended"]

    verdict = H.decide_verdict(
        production_stable=production_stable, reference_stable=ref_stable,
        low_residual_extended=extended, singular_on_path=singular_on_path,
        condition_failure_on_path=condition_failure,
        counts_or_status_vary_with_lattice=counts_or_status_vary, diagnostic_bounded=True)

    write(out, "SOLVER_DEGENERACY_PRODUCTION_GRID_SENSITIVITY_V1.json", {
        "comparison": comparison, "per_lattice_counts": counts,
        "per_lattice_status": statuses,
        "production_verdict": comparison["verdict"]})
    write(out, "SOLVER_DEGENERACY_REFERENCE_SENSITIVITY_V1.json", {
        "per_resolution_status": ref_statuses, "per_resolution_counts": ref_counts,
        "deepest_points": {k: list(v) if v else None for k, v in deep_pts.items()},
        "reference_verdict": "REFERENCE_STABLE" if ref_stable
                             else "REFERENCE_DISCRETISATION_SENSITIVE"})
    prov = {}
    for name, g in grids.items():
        prov[name] = [{"a_serves_first": s["a_serves_first"], "status": s["status"],
                       "seed_count": s["seed_count"],
                       "candidates": s["candidates"]} for s in g["per_server"]]
    write(out, "SOLVER_DEGENERACY_CANDIDATE_PROVENANCE_V1.json", {"per_lattice": prov})
    write(out, "SOLVER_DEGENERACY_DECISION_V1.json", {
        "facts": {"production_stable": production_stable, "reference_stable": ref_stable,
                  "low_residual_region_extended": extended,
                  "connected_subtolerance_path_observed": connected,
                  "singular_point_on_subtolerance_path_observed": singular_on_path,
                  "condition_failure_on_subtolerance_path_observed": condition_failure,
                  "counts_or_status_vary_with_lattice": counts_or_status_vary,
                  "per_lattice_counts": counts, "per_lattice_status": statuses,
                  "per_resolution_status": ref_statuses},
        "verdict": verdict, "label": "SYNTHETIC_FINITE_DIAGNOSTIC_EVIDENCE",
        "approved_by": None})
    print("VERDICT:", verdict)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--out", default=str(D / "degen_run1"))
    a = ap.parse_args()
    out = Path(a.out)
    if a.stage == "freeze":
        stage_freeze(out)
    elif a.stage == "grids":
        stage_grids(out, a.args)
    elif a.stage == "reference":
        stage_reference(out, a.args[0])
    elif a.stage == "surface":
        stage_surface(out)
    elif a.stage == "decide":
        stage_decide(out)
    else:
        raise SystemExit(f"unknown stage {a.stage}")


main()
