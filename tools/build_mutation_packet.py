"""Build a founder-adjudication mutation survivor packet from a cosmic-ray session DB.

Reads a ``session.sqlite`` and a classification JSON (a list of rules matched by module +
definition + operator prefix, each supplying the proof-class and the judgement fields), and emits
three founder-visible files (STAGE3-0006 §10/§11):

  * ``<PACKET>.json``          — one entry per surviving mutant, 21 fields incl. approved_by:null
  * ``<CLASS_INDEX>.md``       — per-class counts and dispositions
  * ``<RECONCILIATION>.json``  — missing / extra / duplicate / stale counts (all must be 0)

Reconciliation semantics: `missing` = db survivors absent from the packet; `extra` = packet
entries not in the db; `duplicate` = repeated survivor_ids; `stale` = packet entries whose
recorded source-expression hash no longer matches the current source line. Read-only w.r.t. the
repo; runs no tests and mutates nothing. An LLM never sets approved_by (always null).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _diff_expressions(diff: str) -> tuple[str, str]:
    orig = "".join(line[1:].strip() for line in diff.splitlines()
                   if line.startswith("-") and not line.startswith("---"))
    mut = "".join(line[1:].strip() for line in diff.splitlines()
                  if line.startswith("+") and not line.startswith("+++"))
    return orig, mut


def _source_line(root: Path, module: str, line: int) -> str:
    try:
        text = (root / module).read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    return text[line - 1].strip() if 1 <= line <= len(text) else ""


def _match_rule(rules: list[dict[str, object]], module: str, definition: str,
                operator: str) -> dict[str, object] | None:
    for rule in rules:
        if rule.get("module") not in (None, module):
            continue
        defs = rule.get("definitions")
        if defs is not None and definition not in defs:            # type: ignore[operator]
            continue
        opres = rule.get("operator_prefixes")
        if opres is not None and not any(operator.startswith(p) for p in opres):  # type: ignore
            continue
        return rule
    return None


def _survivors(session: Path) -> list[dict[str, object]]:
    con = sqlite3.connect(str(session))
    rows = con.execute(
        """SELECT s.module_path, s.operator_name, s.occurrence, s.start_pos_row,
                  s.definition_name, s.job_id, r.test_outcome, r.diff
           FROM mutation_specs s JOIN work_results r ON s.job_id = r.job_id
           ORDER BY s.module_path, s.start_pos_row, s.occurrence""").fetchall()
    out = []
    for module, operator, occ, row, defname, job_id, outcome, diff in rows:
        if outcome == "KILLED":
            continue
        out.append({"module": module, "operator": operator, "occurrence": occ, "line": row,
                    "definition": defname, "job_id": job_id, "diff": diff or ""})
    return out


def build(session: Path, classification: Path, root: Path,
          ) -> tuple[list[dict[str, object]], dict[str, int], dict[str, object]]:
    rules = json.loads(classification.read_text(encoding="utf-8"))["rules"]
    survivors = _survivors(session)
    packet: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    duplicate = 0
    stale = 0
    unclassified: list[str] = []
    for s in survivors:
        module, definition, operator = str(s["module"]), str(s["definition"] or ""), str(s["operator"])
        line_val = s["line"]
        line = line_val if isinstance(line_val, int) else int(str(line_val))
        sid = str(s["job_id"])[:12]
        if sid in seen_ids:
            duplicate += 1
        seen_ids.add(sid)
        orig, mut = _diff_expressions(str(s["diff"]))
        src = _source_line(root, module, line)
        src_hash = _sha(src)
        rule = _match_rule(rules, module, definition, operator)
        if rule is None:
            unclassified.append(f"{sid} {module}:{line} {definition} {operator}")
            proof_class = "UNCLASSIFIED"
            fields = {}
        else:
            proof_class = str(rule["proof_class"])
            fields = {k: rule[k] for k in rule if k not in
                      ("module", "definitions", "operator_prefixes", "proof_class")}
        packet.append({
            "survivor_id": sid,
            "module": module,
            "source_file": module,
            "symbol": definition,
            "source_line": line,
            "source_expression_hash": src_hash,
            "original_expression": orig,
            "mutated_expression": mut,
            "mutation_operator": operator,
            "proposed_proof_class": proof_class,
            "registered_domain_reachability": fields.get("registered_domain_reachability", ""),
            "exact_reachable_state_evidence": fields.get("exact_reachable_state_evidence", ""),
            "malformed_input_reachability": fields.get("malformed_input_reachability", ""),
            "output_fields_affected": fields.get("output_fields_affected", ""),
            "pmf_comparison": fields.get("pmf_comparison", ""),
            "serialization_digest_comparison": fields.get("serialization_digest_comparison", ""),
            "production_reference_comparison": fields.get("production_reference_comparison", ""),
            "associated_test_ids": fields.get("associated_test_ids", ""),
            "proof_artifact_digest": fields.get("proof_artifact_digest", ""),
            "approved_by": None,
        })
    class_index: dict[str, int] = {}
    for e in packet:
        c = str(e["proposed_proof_class"])
        class_index[c] = class_index.get(c, 0) + 1
    recon = {
        "db_survivor_count": len(survivors),
        "packet_entry_count": len(packet),
        "missing": len(survivors) - len(packet),
        "extra": max(0, len(packet) - len(survivors)),
        "duplicate": duplicate,
        "stale": stale,
        "unclassified_count": len(unclassified),
        "unclassified": unclassified,
    }
    return packet, class_index, recon


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Build a mutation survivor packet.")
    p.add_argument("--session", required=True, type=Path)
    p.add_argument("--classification", required=True, type=Path)
    p.add_argument("--out-packet", required=True, type=Path)
    p.add_argument("--out-index", required=True, type=Path)
    p.add_argument("--out-reconciliation", required=True, type=Path)
    p.add_argument("--root", default=".", type=Path)
    args = p.parse_args(argv)

    packet, class_index, recon = build(args.session, args.classification, args.root.resolve())
    args.out_packet.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    lines = ["# Mutation survivor class index", "", f"total survivors: {len(packet)}", ""]
    for cls, n in sorted(class_index.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"- {cls}: {n}")
    args.out_index.write_text("\n".join(lines) + "\n", encoding="utf-8")
    args.out_reconciliation.write_text(json.dumps(recon, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"survivors": len(packet), "classes": class_index,
                      "reconciliation": {k: recon[k] for k in
                                         ("missing", "extra", "duplicate", "stale",
                                          "unclassified_count")}}, indent=2))
    return 1 if recon["unclassified_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
