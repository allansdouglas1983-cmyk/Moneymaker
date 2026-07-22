"""Consolidate the per-module coherence mutation-survivor packets into ONE final packet
(STAGE3-0006 §10).

Reads the per-module packet JSONs (each a list of 21-field survivor entries produced by
``tools/build_mutation_packet.py``) plus their reconciliation JSONs, concatenates the entries,
recomputes the class index, and emits a single reconciliation that must show
missing = extra = duplicate = stale = unclassified = 0 across the whole coherence engine.

approved_by stays null on every entry (an LLM never approves a survivor). Read-only w.r.t. the
repo apart from the three output files. Exit non-zero if any per-module reconciliation was
non-zero, if a survivor_id repeats across modules, or if any entry is UNCLASSIFIED.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def build(packets: list[Path], reconciliations: list[Path],
          ) -> tuple[list[dict[str, object]], dict[str, int], dict[str, object]]:
    merged: list[dict[str, object]] = []
    seen: dict[str, int] = {}
    duplicate = 0
    for p in packets:
        entries = _load(p)
        assert isinstance(entries, list)
        for e in entries:
            assert isinstance(e, dict)
            sid = str(e.get("survivor_id"))
            seen[sid] = seen.get(sid, 0) + 1
            if seen[sid] > 1:
                duplicate += 1
            if e.get("approved_by") is not None:               # invariant: never approved by tool
                raise SystemExit(f"packet {p} entry {sid} has non-null approved_by")
            merged.append(e)

    per_module_bad = []
    stale_total = 0
    unclassified_total = 0
    db_survivor_total = 0
    for r in reconciliations:
        rec = _load(r)
        assert isinstance(rec, dict)
        db_survivor_total += int(rec.get("db_survivor_count", 0))
        stale_total += int(rec.get("stale", 0))
        unclassified_total += int(rec.get("unclassified_count", 0))
        if any(int(rec.get(k, 0)) for k in ("missing", "extra", "duplicate", "stale",
                                            "unclassified_count")):
            per_module_bad.append(str(r))

    class_index: dict[str, int] = {}
    for e in merged:
        c = str(e["proposed_proof_class"])
        class_index[c] = class_index.get(c, 0) + 1

    recon = {
        "modules": len(packets),
        "db_survivor_count_total": db_survivor_total,
        "packet_entry_count": len(merged),
        "missing": db_survivor_total - len(merged),
        "extra": max(0, len(merged) - db_survivor_total),
        "duplicate": duplicate,
        "stale": stale_total,
        "unclassified_count": unclassified_total,
        "per_module_reconciliations_nonzero": per_module_bad,
    }
    return merged, class_index, recon


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Consolidate coherence survivor packets (§10).")
    p.add_argument("--packet", action="append", required=True, type=Path,
                   help="per-module packet JSON (repeatable)")
    p.add_argument("--reconciliation", action="append", required=True, type=Path,
                   help="per-module reconciliation JSON (repeatable)")
    p.add_argument("--out-packet", required=True, type=Path)
    p.add_argument("--out-index", required=True, type=Path)
    p.add_argument("--out-reconciliation", required=True, type=Path)
    args = p.parse_args(argv)

    merged, class_index, recon = build(args.packet, args.reconciliation)
    args.out_packet.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    lines = ["# Coherence mutation survivor class index (CONSOLIDATED — all modules)", "",
             f"total survivors: {len(merged)}", ""]
    for cls, n in sorted(class_index.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"- {cls}: {n}")
    args.out_index.write_text("\n".join(lines) + "\n", encoding="utf-8")
    args.out_reconciliation.write_text(json.dumps(recon, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"survivors": len(merged), "classes": class_index,
                      "reconciliation": recon}, indent=2))
    bad = (recon["missing"] or recon["extra"] or recon["duplicate"] or recon["stale"]
           or recon["unclassified_count"] or recon["per_module_reconciliations_nonzero"])
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
