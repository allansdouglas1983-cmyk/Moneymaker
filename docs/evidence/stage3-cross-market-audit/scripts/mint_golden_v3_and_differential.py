"""STAGE3-0006C-D-A3 §12 — mint SOLVER_GOLDEN_V3_DISCRETISATION_STABLE + classified differential.

Loads the retained V2 golden (SOLVER_GOLDEN_V2_CANONICAL_SET_DEFINED.json), recomputes every
fixture with the AMENDED solver (registered-variant stability check), classifies every
difference into the governed expected class (EXPECTED_STATUS_CHANGE_DISCRETISATION_REFUSAL —
verified against the ACTUAL per-server stability evidence, never inferred from the output diff
alone; UNEXPECTED_CHANGE must be 0), writes the V3 golden (same public fixture structure + a
per-fixture stability-evidence summary + the untouched dedup_unit section, which MUST be
byte-identical to V2's), and emits SOLVER_DISCRETISATION_STABILITY_AMENDMENT_DIFFERENTIAL.json.
Synthetic-only; no market data; no outcomes.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

from sport_tennis.coherence import solver as S
from sport_tennis.coherence.discretisation_stability import StabilityReason
from sport_tennis.coherence.formats import MatchFormat

GOLD = Path("tests/unit/coherence/golden")
D = Path("docs/evidence/stage3-cross-market-audit")
_FMT = MatchFormat.BO3_AD_TB7_ALL_SETS
V2 = json.loads((GOLD / "SOLVER_GOLDEN_V2_CANONICAL_SET_DEFINED.json").read_text())


def _rnd(x: float | None) -> float | None:
    return None if x is None else round(float(x), 9)


def identify_full(tw: float, to: float, line: str, domain: list[float]) -> S.IdentificationResult:
    return S.identify(tw, to, Decimal(line), _FMT, domain=tuple(domain))  # type: ignore[arg-type]


def public_out(r: S.IdentificationResult) -> dict[str, object]:
    """The exact V2 public comparison shape (unchanged serialization of the public fields)."""
    return {
        "status": r.status,
        "roots": sorted([[_rnd(rt.p_a), _rnd(rt.p_b), rt.a_serves_first, _rnd(rt.residual),
                          _rnd(rt.jacobian_det), rt.on_boundary] for rt in r.roots]),
        "per_server": [[s.a_serves_first, s.status,
                        sorted([[_rnd(x.p_a), _rnd(x.p_b)] for x in s.roots])]
                       for s in r.per_server],
        "domain": list(r.domain), "line": str(r.line),
    }


def stability_summary(r: S.IdentificationResult) -> list[dict[str, object]]:
    """V3 serialization addition (serialization_policy: versioned as V3 alongside this golden):
    the immutable per-assignment agreement evidence, summarised deterministically."""
    out = []
    for solve in r.per_server:
        st = solve.stability
        assert st is not None, "amended solver must attach stability evidence"
        out.append({
            "a_serves_first": solve.a_serves_first,
            "stable": st.stable,
            "reason": st.reason.value if st.reason is not None else None,
            "disagreements": list(st.disagreements),
            "variants": [{
                "variant": snap.variant.value,
                "status": snap.status,
                "root_count": len(snap.roots),
                "roots": sorted([[_rnd(x.p_a), _rnd(x.p_b)] for x in snap.roots]),
                "axis_digest": snap.axis_digest,
            } for snap in st.snapshots],
            "decision_digest": st.digest(),
        })
    return out


# ---- derived_targets: stability-independent; must be byte-identical to V2 -------------------
changes: list[dict[str, object]] = []
dt_rows = []
dt_unexpected = 0
for row in V2["derived_targets"]:
    tw, to = S.derived_targets(row["pa"], row["pb"], _FMT, Decimal(row["line"]),
                               a_serves_first=True)
    new = {"pa": row["pa"], "pb": row["pb"], "line": row["line"],
           "tw": _rnd(tw), "to": _rnd(to)}
    dt_rows.append(new)
    if new["tw"] != row["tw"] or new["to"] != row["to"]:
        dt_unexpected += 1
        changes.append({"fixture": f"derived_targets {row}", "class": "UNEXPECTED_CHANGE"})

# ---- identify fixtures: recompute + classify against the ACTUAL stability evidence ----------
id_cases = []
counts = {"EXPECTED_STATUS_CHANGE_DISCRETISATION_REFUSAL": 0,
          "UNEXPECTED_CHANGE": dt_unexpected, "UNCHANGED": 0}
for case in V2["identify"]:
    r = identify_full(case["tw"], case["to"], case["line"], case["domain"])
    new_out = public_out(r)
    stab = stability_summary(r)
    old_out = case["out"]
    id_cases.append({"tw": case["tw"], "to": case["to"], "line": case["line"],
                     "domain": case["domain"], "out": new_out, "stability": stab})
    label = f"identify line={case['line']} domain={case['domain']} tw={case['tw']}"
    any_unstable = any(not s["stable"] for s in stab)
    all_reasons_ok = all(
        s["stable"] or s["reason"] == StabilityReason.DISCRETISATION_UNSTABLE_ROOT_SET.value
        for s in stab)
    if new_out == old_out:
        # the amendment's promise: an all-stable fixture is byte-identical — a fixture that is
        # unchanged while carrying an unstable assignment would itself be unexpected
        cls = "UNCHANGED" if not any_unstable else "UNEXPECTED_CHANGE"
    elif any_unstable and all_reasons_ok:
        # every refused assignment must present as the existing public NON_IDENTIFIABLE with no
        # public roots; the overall change must be attributable to exactly that refusal
        refusal_shape_ok = all(
            (s["stable"]) or (ps[1] == "NON_IDENTIFIABLE" and ps[2] == [])
            for s, ps in zip(stab, new_out["per_server"]))
        cls = ("EXPECTED_STATUS_CHANGE_DISCRETISATION_REFUSAL"
               if refusal_shape_ok else "UNEXPECTED_CHANGE")
    else:
        cls = "UNEXPECTED_CHANGE"
    counts[cls] += 1
    if cls != "UNCHANGED":
        changes.append({"fixture": label, "class": cls,
                        "old_status": old_out["status"], "new_status": new_out["status"],
                        "old_roots": old_out["roots"], "new_roots": new_out["roots"],
                        "per_server_stability": [
                            {"a_serves_first": s["a_serves_first"], "stable": s["stable"],
                             "reason": s["reason"],
                             "variant_counts": [v["root_count"] for v in s["variants"]],
                             "variant_statuses": [v["status"] for v in s["variants"]]}
                            for s in stab]})

# ---- dedup_unit: the A1 canonical dedup is untouched — carried over BYTE-IDENTICALLY --------
dedup_unit = V2["dedup_unit"]

v3 = {"policy": "DISCRETISATION_STABLE (STAGE3-0006C-D-A3; supersedes V2 as the governing "
                "vintage; V1/V2 retained unmodified as historical evidence)",
      "derived_targets": dt_rows, "identify": id_cases, "dedup_unit": dedup_unit}
v3_blob = json.dumps(v3, indent=1, sort_keys=True) + "\n"
(GOLD / "SOLVER_GOLDEN_V3_DISCRETISATION_STABLE.json").write_text(v3_blob)

report = {
    "amendment": "STAGE3-0006C-D-A3 / CROSS_MARKET_COHERENCE_DISCRETISATION_STABILITY_AMENDMENT_V1",
    "old_vintage": "SOLVER_GOLDEN_V2_CANONICAL_SET_DEFINED.json",
    "new_vintage": "SOLVER_GOLDEN_V3_DISCRETISATION_STABLE.json",
    "old_vintage_sha256": hashlib.sha256(
        (GOLD / "SOLVER_GOLDEN_V2_CANONICAL_SET_DEFINED.json").read_bytes()).hexdigest(),
    "new_vintage_sha256": hashlib.sha256(v3_blob.encode()).hexdigest(),
    "dedup_unit_byte_identical_to_v2": v3["dedup_unit"] == V2["dedup_unit"],
    "classified_changes": changes,
    "counts": counts,
    "derived_targets_identical": dt_unexpected == 0,
    "unexpected_change_count": counts["UNEXPECTED_CHANGE"],
    "approved_by": None,
}
blob = json.dumps(report, indent=1, sort_keys=True) + "\n"
(D / "SOLVER_DISCRETISATION_STABILITY_AMENDMENT_DIFFERENTIAL.json").write_text(blob)
print("counts:", counts)
print("differential digest: sha256:" + hashlib.sha256(blob.encode()).hexdigest())
print("v3 sha256:", report["new_vintage_sha256"])
