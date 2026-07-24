"""STAGE3-0006C-D-A3-FINALIZE §7 — pending founder-survivor inventory builder.

Enumerates every still-unapproved (approved_by:null) mutation packet on the Stage-3 cross-market
path, with exact counts and artifact digests, to prevent pending gates being forgotten. Reads
existing evidence artifacts only; approves/merges nothing. Emits
PENDING_FOUNDER_SURVIVOR_INVENTORY_STAGE3_V1.md.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

D = Path("docs/evidence/stage3-cross-market-audit")


def dg(name: str) -> str:
    p = D / name
    return ("sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()) if p.exists() else "MISSING"


def count(name: str) -> int | str:
    p = D / name
    if not p.exists():
        return "MISSING"
    d = json.loads(p.read_text())
    if isinstance(d, list):
        return len(d)
    for k in ("survivors", "survivor_packet", "entries"):
        if isinstance(d, dict) and isinstance(d.get(k), list):
            return len(d[k])
    return "?"


# component -> (packet, class_index, reconciliation, survivor_count_file, scope)
FAM = [
    ("xmarket_contracts", "MUTATION_SURVIVOR_PACKET_XMARKET_CONTRACTS_FINAL_V1.json",
     "MUTATION_SURVIVOR_CLASS_INDEX_XMARKET_CONTRACTS_FINAL_V1.md",
     "MUTATION_RECONCILIATION_XMARKET_CONTRACTS_FINAL_V1.json", "synthetic-only (execution-quarantined)"),
    ("xmarket_linkage", "MUTATION_SURVIVOR_PACKET_XMARKET_LINKAGE_V1.json",
     "MUTATION_SURVIVOR_CLASS_INDEX_XMARKET_LINKAGE_V1.md",
     "MUTATION_RECONCILIATION_XMARKET_LINKAGE_V1.json", "synthetic-only (execution-quarantined)"),
    ("xmarket_parsers", "MUTATION_SURVIVOR_PACKET_XMARKET_PARSERS_V1.json",
     "MUTATION_SURVIVOR_CLASS_INDEX_XMARKET_PARSERS_V1.md",
     "MUTATION_RECONCILIATION_XMARKET_PARSERS_V1.json", "synthetic-only (execution-quarantined)"),
    ("xmarket_synchronizer", "MUTATION_SURVIVOR_PACKET_XMARKET_SYNCHRONIZER_V1.json",
     "MUTATION_SURVIVOR_CLASS_INDEX_XMARKET_SYNCHRONIZER_V1.md",
     "MUTATION_RECONCILIATION_XMARKET_SYNCHRONIZER_V1.json", "synthetic-only (execution-quarantined)"),
    ("xmarket_observation", "MUTATION_SURVIVOR_PACKET_XMARKET_OBSERVATION_V1.json",
     "MUTATION_SURVIVOR_CLASS_INDEX_XMARKET_OBSERVATION_V1.md",
     "MUTATION_RECONCILIATION_XMARKET_OBSERVATION_V1.json", "synthetic-only (0 survivors)"),
    ("solver_milestone_b_stable_sort", "SOLVER_MILESTONE_B_SCAN_SURVIVORS.json",
     "SOLVER_MILESTONE_B_SCAN_CLASS_INDEX.md", "SOLVER_MILESTONE_B_SCAN_RECONCILIATION.json",
     "synthetic-only (solver seed ranking)"),
    ("root_dedup_a1", "ROOT_DEDUP_AMENDMENT_SURVIVORS.json",
     "ROOT_DEDUP_AMENDMENT_CLASS_INDEX.md", "ROOT_DEDUP_AMENDMENT_RECONCILIATION.json",
     "synthetic-only (solver canonical dedup)"),
    ("discretisation_stability_a3", "MUTATION_SURVIVOR_PACKET_DISCRETISATION_STABILITY_A3_FINAL_V1.json",
     "MUTATION_SURVIVOR_CLASS_INDEX_DISCRETISATION_STABILITY_A3_FINAL_V1.md",
     "MUTATION_RECONCILIATION_DISCRETISATION_STABILITY_A3_FINAL_V1.json",
     "synthetic-only (solver stability check)"),
    ("coherence_scoring", "MUTATION_SURVIVOR_PACKET_COHERENCE_SCORING_V1.json",
     "MUTATION_SURVIVOR_CLASS_INDEX_COHERENCE_SCORING_V1.md",
     "MUTATION_RECONCILIATION_COHERENCE_SCORING_V1.json", "synthetic-only (coherence math)"),
    ("coherence_match", "MUTATION_SURVIVOR_PACKET_COHERENCE_MATCH_V1.json",
     "MUTATION_SURVIVOR_CLASS_INDEX_COHERENCE_MATCH_V1.md",
     "MUTATION_RECONCILIATION_COHERENCE_MATCH_V1.json", "synthetic-only (coherence math)"),
    ("coherence_holdout", "MUTATION_SURVIVOR_PACKET_COHERENCE_HOLDOUT_V1.json",
     "MUTATION_SURVIVOR_CLASS_INDEX_COHERENCE_HOLDOUT_V1.md",
     "MUTATION_RECONCILIATION_COHERENCE_HOLDOUT_V1.json", "synthetic-only (coherence math)"),
    ("coherence_formats", "MUTATION_SURVIVOR_PACKET_COHERENCE_FORMATS_V1.json",
     "MUTATION_SURVIVOR_CLASS_INDEX_COHERENCE_FORMATS_V1.md",
     "MUTATION_RECONCILIATION_COHERENCE_FORMATS_V1.json", "synthetic-only (coherence math)"),
    ("coherence_format_evidence", "MUTATION_SURVIVOR_PACKET_COHERENCE_FORMAT_EVIDENCE_V1.json",
     "MUTATION_SURVIVOR_CLASS_INDEX_COHERENCE_FORMAT_EVIDENCE_V1.md",
     "MUTATION_RECONCILIATION_COHERENCE_FORMAT_EVIDENCE_V1.json", "synthetic-only (coherence math)"),
    ("coherence_pmf", "MUTATION_SURVIVOR_PACKET_COHERENCE_PMF_V1.json",
     "MUTATION_SURVIVOR_CLASS_INDEX_COHERENCE_PMF_V1.md",
     "MUTATION_RECONCILIATION_COHERENCE_PMF_V1.json", "synthetic-only (0 survivors)"),
]

lines = ["# Pending founder-survivor inventory — Stage-3 cross-market path",
         "",
         "Directive: STAGE3-0006C-D-A3-FINALIZE §7. Purpose: prevent pending mutation gates from "
         "being forgotten. This inventory APPROVES and MERGES nothing; every listed packet keeps "
         "`approved_by: null` and remains PENDING founder adjudication. Commit `37bac01`.",
         "",
         "All listed components are **synthetic-only** research surfaces (the coherence/xmarket "
         "engines are offline, import-quarantined from `l6_broker`/execution, V0 and "
         "`p_market_info`); **none is exposed** to live trading. Source-change and "
         "deterministic-remapping columns reflect whether the source has moved since the packet "
         "was produced (the A3 packet is verified byte-identical to HEAD this turn; the others are "
         "the source of truth for their own components and were not re-run this turn).",
         "",
         "| Component | Survivors | Packet (digest) | Class index (digest) | Reconciliation (digest) | Founder status | Scope |",
         "|---|---|---|---|---|---|---|"]

total = 0
for comp, pk, ci, rc, scope in FAM:
    n = count(pk)
    if isinstance(n, int):
        total += n
    lines.append(f"| {comp} | {n} | `{pk}` ({dg(pk)[:23]}…) | `{ci}` ({dg(ci)[:23]}…) | "
                 f"`{rc}` ({dg(rc)[:23]}…) | PENDING (approved_by:null) | {scope} |")

lines += [
    "",
    "## Full digests",
    "",
]
for comp, pk, ci, rc, scope in FAM:
    lines.append(f"- **{comp}** — packet {dg(pk)} · class-index {dg(ci)} · reconciliation {dg(rc)}")

lines += [
    "",
    "## Notes",
    "",
    f"- **Total pending survivors across the Stage-3 cross-market path: {total}** "
    "(approved_by:null).",
    "- The directive named four families explicitly: xmarket contracts/plumbing (**85** in the "
    "contracts packet; the plumbing packets linkage=15, parsers=16, synchronizer=54, "
    "observation=0 are listed separately above), Milestone-B stable-sort (**1**), root-dedup A1 "
    "(**46**), discretisation-stability A3 (**16**).",
    "- `MUTATION_SURVIVOR_PACKET_XMARKET_CONTRACTS_V1_FINAL.json` is a byte-identical duplicate of "
    "the contracts packet (same sha256) — one name, not two gates.",
    "- Every non-solver completed coherence-module packet still carrying approved_by:null is "
    "listed (scoring=33, match=11, holdout=10, formats=3, format_evidence=3, pmf=0).",
    "- No packet is merged or approved here. Milestone D remains PAUSED. No source, test, golden, "
    "threshold, database or classification was changed to build this inventory.",
]

(D / "PENDING_FOUNDER_SURVIVOR_INVENTORY_STAGE3_V1.md").write_text("\n".join(lines) + "\n")
blob = (D / "PENDING_FOUNDER_SURVIVOR_INVENTORY_STAGE3_V1.md").read_bytes()
print("inventory sha256:", hashlib.sha256(blob).hexdigest())
print("total pending survivors:", total)
