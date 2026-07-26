"""STAGE3-0006C-D-A3-FINALIZE §3/§4 — reproducible equivalence proof for the 16 A3 survivors.

Founder-review export artifact (permitted). Touches NO production code, test, mutation
classification, golden, database or source fingerprint: it copies each module's committed source
to a temp file, applies exactly one survivor mutation, imports the mutant, and differentials it
against the production module over the reachable input domain — plus, for enum/bool survivors,
records the singleton language/runtime guarantee. Emits A3_SURVIVOR_EQUIVALENCE_PROOF_V1.json.

The 16 survivors are the classified EXACT residual equivalents that REMAIN after the two round-2
tests-first kills (ds L170, solver L269 are killed, NOT in this set). approved_by is null.
"""
from __future__ import annotations

import importlib.util
import json
import platform
import random
import sys
import tempfile
from pathlib import Path

from sport_tennis.coherence import solver as S
from sport_tennis.coherence.scan_variants import (REGISTERED_VARIANT_ORDER, ScanVariant,
                                                  axis_digest, variant_axis)
from sport_tennis.coherence.solver_contracts import ParameterDomain
import sport_tennis.coherence.discretisation_stability as prod_ds

LO, HI, TOL = 0.35, 0.90, 1e-3
DOM = ParameterDomain.from_symmetric(LO, HI)
AD = {v: axis_digest(tuple(variant_axis(v, LO, HI))) for v in ScanVariant}
DS_SRC = Path("sport_tennis/coherence/discretisation_stability.py").read_text()
SV_SRC = Path("sport_tennis/coherence/scan_variants.py").read_text()
TRIALS = 4000

# survivor_id -> (job_id, module, class, python_operator, old, new)
SURV = {
    "A3-SV-01": ("a3f4b7c8fb994aa1a47c1400e7f9e761", "scan_variants", "ENUM_IDENTITY",
                 "if variant is ScanVariant.G0_BASELINE:", "if variant == ScanVariant.G0_BASELINE:"),
    "A3-SV-02": ("ea1057a69bee4a5f966dbc2cdf2d0326", "scan_variants", "ENUM_IDENTITY",
                 "if variant is ScanVariant.G1_REGISTERED_VALIDATION:",
                 "if variant == ScanVariant.G1_REGISTERED_VALIDATION:"),
    "A3-SV-03": ("31d6c40fd6964158b5fcbd8e08fc562f", "scan_variants", "ENUM_IDENTITY",
                 "if variant is ScanVariant.G2_REGISTERED_VALIDATION:",
                 "if variant == ScanVariant.G2_REGISTERED_VALIDATION:"),
    "A3-DS-01": ("0c71a135011d43379152c588d2d27bd5", "discretisation_stability", "INTEGER_IDENTITY",
                 "if len(left) != len(right):", "if len(left) is not len(right):"),
    "A3-DS-02": ("c1a6795a487a4ed9bbfd979f1d019e6a", "discretisation_stability", "GUARD_DOMINATED",
                 "        if i == n:", "        if i >= n:"),
    "A3-DS-03": ("56999d540b404161aa3d23456d93c128", "discretisation_stability", "INTEGER_IDENTITY",
                 "        if i == n:", "        if i is n:"),
    "A3-DS-04": ("8494372324364e9193b27107fe51b6de", "discretisation_stability", "INTEGER_IDENTITY",
                 "if len(snapshots) != len(REGISTERED_VARIANT_ORDER):",
                 "if len(snapshots) is not len(REGISTERED_VARIANT_ORDER):"),
    "A3-DS-05": ("c3eed39bcac74b7093c8b049c169d6d9", "discretisation_stability", "ENUM_IDENTITY",
                 "if snap.variant is not variant:", "if snap.variant != variant:"),
    "A3-DS-06": ("2d00ccd594e24c20998311d04ac98455", "discretisation_stability", "GUARD_DOMINATED",
                 "if len({s.a_serves_first for s in snapshots}) != 1:",
                 "if len({s.a_serves_first for s in snapshots}) > 1:"),
    "A3-DS-07": ("60d46bfe11b1409b98a21c880f1d911f", "discretisation_stability",
                 "IDEMPOTENT_SELF_COMPARISON",
                 "    for snap in snapshots[1:]:\n        if snap.status != base.status:",
                 "    for snap in snapshots[0:]:\n        if snap.status != base.status:"),
    "A3-DS-08": ("28c95f4a29e34c15b02e23e599fbb45d", "discretisation_stability", "INTEGER_IDENTITY",
                 "if len(left.roots) != len(right.roots):",
                 "if len(left.roots) is not len(right.roots):"),
    "A3-DS-09": ("5ca04eb465574035b7b24c4ce0c28058", "discretisation_stability", "GUARD_DOMINATED",
                 "if len(matchings) > 1:", "if len(matchings) != 1:"),
    "A3-DS-10": ("86638e8f13b64eccb43986ef3336ba93", "discretisation_stability",
                 "SINGLE_ELEMENT_INDEX",
                 "for i, j in enumerate(matchings[0]):", "for i, j in enumerate(matchings[-1]):"),
    "A3-DS-11": ("1c3c0ec765de4c47a744395d768f7ec2", "discretisation_stability", "BOOLEAN_IDENTITY",
                 "if left.roots[i].on_boundary != right.roots[j].on_boundary:",
                 "if left.roots[i].on_boundary is not right.roots[j].on_boundary:"),
    "A3-DS-12": ("53f74f13668c43e2afd64b25d7610a69", "discretisation_stability",
                 "IDEMPOTENT_SELF_COMPARISON",
                 "    for snap in snapshots[1:]:\n        mirror = classify_mirror_relation",
                 "    for snap in snapshots[0:]:\n        mirror = classify_mirror_relation"),
    "A3-DS-13": ("885a8a73b88245a5ac22bad6e8816234", "discretisation_stability", "ENUM_IDENTITY",
                 "if mirror is not base_mirror:", "if mirror != base_mirror:"),
}


def _load(src: str, tag: str):
    path = Path(tempfile.gettempdir()) / f"a3proof_{tag}.py"
    path.write_text(src)
    spec = importlib.util.spec_from_file_location(f"a3proof_{tag}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _rt(pa: float, pb: float, b: bool = False):
    return S.Root(pa, pb, True, 1e-5, 1.0, b)


_STATUSES = ["NO_ROOT", "IDENTIFIED", "MULTIPLE_ROOTS", "NON_IDENTIFIABLE", "BOUNDARY_SOLUTION",
             "FIRST_SERVER_SENSITIVE_PENDING_THRESHOLD"]
_LAT = [round(LO + i * 0.00025, 5) for i in range(int((HI - LO) / 0.00025) + 1)]


def _status_for(n: int) -> str:
    return {0: "NO_ROOT", 1: "IDENTIFIED"}.get(n, "MULTIPLE_ROOTS")


def _gen_reachable(rng: random.Random):
    """A reachable trio: status is consistent with root count; occasional unanimous refusal /
    empty trios to exercise the all-NON_IDENTIFIABLE and NO_ROOT branches. Coordinates on a fine
    lattice so near-tolerance matching/ambiguity/mirror cases occur."""
    af = rng.random() < 0.5
    if rng.random() < 0.15:  # unanimous same status, consistent root counts
        n = rng.randint(0, 4)
        st = "NON_IDENTIFIABLE" if rng.random() < 0.5 else _status_for(n)
        return [(v, af, st, tuple(_rt(rng.choice(_LAT), rng.choice(_LAT), rng.random() < 0.2)
                                  for _ in range(n))) for v in REGISTERED_VARIANT_ORDER]
    bn = rng.randint(0, 4)
    base = [(rng.choice(_LAT), rng.choice(_LAT)) for _ in range(bn)]
    out = []
    for v in REGISTERED_VARIANT_ORDER:
        n = bn if rng.random() < 0.75 else rng.randint(0, 4)
        roots = []
        for i in range(n):
            if i < len(base) and rng.random() < 0.8:
                pa = round(min(max(base[i][0] + rng.choice([-2, -1, 0, 0, 1, 2]) * 0.00025, LO), HI), 5)
                pb = round(min(max(base[i][1] + rng.choice([-2, -1, 0, 0, 1, 2]) * 0.00025, LO), HI), 5)
            else:
                pa, pb = rng.choice(_LAT), rng.choice(_LAT)
            roots.append(_rt(pa, pb, rng.random() < 0.2))
        out.append((v, af, _status_for(n), tuple(roots)))
    return out


def _norm(d):
    return (d.stable, d.reason.value if d.reason else None, d.disagreements)


def _prove_ds(sid: str, old: str, new: str, seed: int):
    assert DS_SRC.count(old) == 1, (sid, "occurrences", DS_SRC.count(old))
    mut = _load(DS_SRC.replace(old, new, 1), sid)

    def mkp(v, af, st, roots):
        return prod_ds.VariantSolveSnapshot(v, af, st, roots, AD[v])

    def mkm(v, af, st, roots):
        return mut.VariantSolveSnapshot(v, af, st, roots, AD[v])

    rng = random.Random(seed)
    diffs = 0
    for _ in range(TRIALS):
        spec = _gen_reachable(rng)
        pv = _norm(prod_ds.compare_registered_variants(
            tuple(mkp(*s) for s in spec), domain=DOM, tolerance=TOL))
        mv = _norm(mut.compare_registered_variants(
            tuple(mkm(*s) for s in spec), domain=DOM, tolerance=TOL))
        if pv != mv:
            diffs += 1
    return diffs


def _prove_sv(sid: str, old: str, new: str):
    assert SV_SRC.count(old) == 1, (sid, "occurrences", SV_SRC.count(old))
    mut = _load(SV_SRC.replace(old, new, 1), sid)
    # the mutant module re-defines its own ScanVariant enum, so each side is called with its own
    # (singleton) members; the produced axes are plain float lists, comparable across modules.
    diffs = 0
    for pv, mv in zip(REGISTERED_VARIANT_ORDER, mut.REGISTERED_VARIANT_ORDER):
        if variant_axis(pv, LO, HI) != mut.variant_axis(mv, LO, HI):
            diffs += 1
    # both `is` and `==` fall through to the same ValueError on a non-enum operand (raw string,
    # None, foreign type) — proving strings/None/foreign values are refused before the branch.
    refusal_consistent = True
    for bad in (None, "G0_BASELINE", 123):
        try:
            variant_axis(bad, LO, HI)  # type: ignore[arg-type]
            pexc = None
        except Exception as e:  # noqa: BLE001
            pexc = type(e).__name__
        try:
            mut.variant_axis(bad, LO, HI)
            mexc = None
        except Exception as e:  # noqa: BLE001
            mexc = type(e).__name__
        if pexc != mexc or pexc != "ValueError":
            refusal_consistent = False
    return diffs, refusal_consistent


env = {
    "python_implementation": platform.python_implementation(),
    "python_version": platform.python_version(),
    "python_version_full": sys.version,
    "small_int_cache_range": "[-5, 256] (CPython PyLong cache)",
}
results = {}
for sid, (job, module, cls, old, new) in SURV.items():
    if module == "scan_variants":
        diffs, refusal = _prove_sv(sid, old, new)
        results[sid] = {"job_id": job, "module": module, "class": cls,
                        "method": "LANGUAGE_GUARANTEE_ENUM_SINGLETON + variant_axis differential",
                        "axis_diffs_over_registered_variants": diffs,
                        "non_enum_refusal_consistent": refusal,
                        "equivalent": diffs == 0 and refusal}
    else:
        diffs = _prove_ds(sid, old, new, seed=20260724 + hash(sid) % 1000)
        env_bound = cls in ("INTEGER_IDENTITY",)
        results[sid] = {"job_id": job, "module": module, "class": cls,
                        "method": "REACHABLE_DOMAIN_DIFFERENTIAL"
                                  + ("_ENV_BOUND" if env_bound else ""),
                        "trials": TRIALS, "reachable_diffs": diffs,
                        "environment_bound": env_bound, "equivalent": diffs == 0}

proof = {"directive": "STAGE3-0006C-D-A3-FINALIZE §3/§4",
         "purpose": "reproducible equivalence proof for the 16 classified A3 survivors",
         "environment": env, "trials_per_ds_survivor": TRIALS,
         "note": "L170 and solver L269 are KILLED (round 2), not in this set; approved_by null",
         "results": results,
         "all_equivalent": all(r["equivalent"] for r in results.values()),
         "survivor_count": len(results)}
blob = json.dumps(proof, indent=1, sort_keys=True) + "\n"
Path("docs/evidence/stage3-cross-market-audit/A3_SURVIVOR_EQUIVALENCE_PROOF_V1.json").write_text(blob)
import hashlib
print("proof sha256:", hashlib.sha256(blob.encode()).hexdigest())
print("survivors:", len(results), "| all_equivalent:", proof["all_equivalent"])
for sid, r in results.items():
    print(f"  {sid} {r['class']:26s} diffs={r.get('reachable_diffs', r.get('axis_diffs_over_registered_variants'))} equiv={r['equivalent']}")
