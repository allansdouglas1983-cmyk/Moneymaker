"""STAGE3-0006C-D-A1 §8 — mint SOLVER_GOLDEN_V2_CANONICAL_SET_DEFINED + classified differential.

Loads the retained V1 golden (SOLVER_GOLDEN_V1_SEQUENCE_DEFINED.json), recomputes every fixture
with the AMENDED solver, classifies every difference into the governed expected classes
(UNEXPECTED_CHANGE must be 0), writes the V2 golden (same fixture structure + a new dedup_unit
section pinning the amendment's canonical fixtures), and emits
SOLVER_ROOT_DEDUP_AMENDMENT_DIFFERENTIAL.json. Synthetic-only; no market data; no outcomes.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from decimal import Decimal
from pathlib import Path

from sport_tennis.coherence import solver as S
from sport_tennis.coherence.formats import MatchFormat
from sport_tennis.coherence.root_dedup import deduplicate_roots

GOLD = Path("tests/unit/coherence/golden")
D = Path("docs/evidence/stage3-cross-market-audit")
_FMT = MatchFormat.BO3_AD_TB7_ALL_SETS
V1 = json.loads((GOLD / "SOLVER_GOLDEN_V1_SEQUENCE_DEFINED.json").read_text())


def _rnd(x: float | None) -> float | None:
    return None if x is None else round(float(x), 9)


def identify_out(tw: float, to: float, line: str, domain: list[float]) -> dict[str, object]:
    r = S.identify(tw, to, Decimal(line), _FMT, domain=tuple(domain))  # type: ignore[arg-type]
    return {
        "status": r.status,
        "roots": sorted([[_rnd(rt.p_a), _rnd(rt.p_b), rt.a_serves_first, _rnd(rt.residual),
                          _rnd(rt.jacobian_det), rt.on_boundary] for rt in r.roots]),
        "per_server": [[s.a_serves_first, s.status,
                        sorted([[_rnd(x.p_a), _rnd(x.p_b)] for x in s.roots])]
                       for s in r.per_server],
        "domain": list(r.domain), "line": str(r.line),
    }


# ---- derived_targets: dedup-independent; must be byte-identical to V1 ----------------------
changes: list[dict[str, object]] = []
dt_rows = []
dt_unexpected = 0
for row in V1["derived_targets"]:
    tw, to = S.derived_targets(row["pa"], row["pb"], _FMT, Decimal(row["line"]),
                               a_serves_first=True)
    new = {"pa": row["pa"], "pb": row["pb"], "line": row["line"],
           "tw": _rnd(tw), "to": _rnd(to)}
    dt_rows.append(new)
    if new["tw"] != row["tw"] or new["to"] != row["to"]:
        dt_unexpected += 1
        changes.append({"fixture": f"derived_targets {row}", "class": "UNEXPECTED_CHANGE"})

# ---- identify fixtures: recompute + classify -----------------------------------------------
id_cases = []
counts = {"EXPECTED_ROOT_REPRESENTATIVE_CHANGE": 0, "EXPECTED_ROOT_ORDER_CHANGE": 0,
          "EXPECTED_ROOT_COUNT_CHANGE": 0, "EXPECTED_STATUS_CHANGE_AMBIGUOUS_CHAIN": 0,
          "UNEXPECTED_CHANGE": dt_unexpected, "UNCHANGED": 0}
for case in V1["identify"]:
    new_out = identify_out(case["tw"], case["to"], case["line"], case["domain"])
    old_out = case["out"]
    id_cases.append({"tw": case["tw"], "to": case["to"], "line": case["line"],
                     "domain": case["domain"], "out": new_out})
    label = f"identify line={case['line']} domain={case['domain']}"
    if new_out == old_out:
        counts["UNCHANGED"] += 1
        continue
    if new_out["status"] != old_out["status"]:
        # a status change is expected ONLY via the ambiguity refusal
        cls = ("EXPECTED_STATUS_CHANGE_AMBIGUOUS_CHAIN"
               if new_out["status"] == "NON_IDENTIFIABLE" else "UNEXPECTED_CHANGE")
    elif len(new_out["roots"]) != len(old_out["roots"]):
        cls = "UNEXPECTED_CHANGE"     # count may only change via ambiguity (status changes too)
    else:
        # same status, same count: representative/order drift within the retained tolerance?
        def within_tol(a: list, b: list) -> bool:  # noqa: ANN001
            return max(abs(a[0] - b[0]), abs(a[1] - b[1])) < S._DEDUP_TOL
        paired = all(any(within_tol(nr, orr) for orr in old_out["roots"])
                     for nr in new_out["roots"])
        cls = ("EXPECTED_ROOT_REPRESENTATIVE_CHANGE" if paired else "UNEXPECTED_CHANGE")
        if paired and sorted(map(tuple, new_out["roots"])) == sorted(map(tuple, old_out["roots"])):
            cls = "EXPECTED_ROOT_ORDER_CHANGE"
    counts[cls] += 1
    changes.append({"fixture": label, "class": cls,
                    "old_status": old_out["status"], "new_status": new_out["status"],
                    "old_roots": old_out["roots"], "new_roots": new_out["roots"]})

# ---- dedup_unit golden section (§8 mandated fixtures, dedup level) -------------------------
def mk(pa, pb, res=1e-5, a_first=True, jd=1.0, boundary=False):  # noqa: ANN001, ANN201
    return S.Root(p_a=pa, p_b=pb, a_serves_first=a_first, residual=res, jacobian_det=jd,
                  on_boundary=boundary)


TOL = S._DEDUP_TOL
chain = [mk(0.5, 0.5, 3e-5), mk(0.5009, 0.5, 1e-5), mk(0.5018, 0.5, 2e-5)]
close = [mk(0.5, 0.5, 3e-5), mk(0.5004, 0.5002, 1e-5), mk(0.4998, 0.5004, 2e-5)]
multi = [mk(0.4, 0.6, 1e-5), mk(0.7, 0.3, 5e-5), mk(0.55, 0.45, 9e-5)]
fserver = [mk(0.5, 0.5, 2e-5, True), mk(0.5002, 0.5001, 1e-5, False)]
boundary_mix = [mk(0.5, 0.5, 1e-5, boundary=False), mk(0.5004, 0.5, 2e-5, boundary=True)]
chain_digests = {deduplicate_roots(list(p), TOL).digest()
                 for p in itertools.permutations(chain)}
assert len(chain_digests) == 1, "chain must refuse identically for every permutation"
dedup_unit = {
    "tolerance": TOL,
    "chain_refusal": deduplicate_roots(chain, TOL).serialize(),
    "chain_all_permutations_digest": next(iter(chain_digests)),
    "valid_close_cluster": deduplicate_roots(close, TOL).serialize(),
    "distinct_multi_root": deduplicate_roots(multi, TOL).serialize(),
    "first_server_provenance": deduplicate_roots(fserver, TOL).serialize(),
    "boundary_metadata": deduplicate_roots(boundary_mix, TOL).serialize(),
}

v2 = {"policy": "CANONICAL_SET_DEFINED (STAGE3-0006C-D-A1)",
      "derived_targets": dt_rows, "identify": id_cases, "dedup_unit": dedup_unit}
v2_blob = json.dumps(v2, indent=1, sort_keys=True) + "\n"
(GOLD / "SOLVER_GOLDEN_V2_CANONICAL_SET_DEFINED.json").write_text(v2_blob)

report = {
    "amendment": "STAGE3-0006C-D-A1 / CROSS_MARKET_COHERENCE_ROOT_DEDUP_AMENDMENT_V1",
    "old_vintage": "SOLVER_GOLDEN_V1_SEQUENCE_DEFINED.json",
    "new_vintage": "SOLVER_GOLDEN_V2_CANONICAL_SET_DEFINED.json",
    "old_vintage_sha256": hashlib.sha256(
        (GOLD / "SOLVER_GOLDEN_V1_SEQUENCE_DEFINED.json").read_bytes()).hexdigest(),
    "new_vintage_sha256": hashlib.sha256(v2_blob.encode()).hexdigest(),
    "classified_changes": changes,
    "counts": counts,
    "derived_targets_identical": dt_unexpected == 0,
    "unexpected_change_count": counts["UNEXPECTED_CHANGE"],
    "approved_by": None,
}
blob = json.dumps(report, indent=1, sort_keys=True) + "\n"
(D / "SOLVER_ROOT_DEDUP_AMENDMENT_DIFFERENTIAL.json").write_text(blob)
print("counts:", counts)
print("differential digest: sha256:" + hashlib.sha256(blob.encode()).hexdigest())
print("v2 sha256:", report["new_vintage_sha256"])
