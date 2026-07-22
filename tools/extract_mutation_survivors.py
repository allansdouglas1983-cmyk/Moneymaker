"""Extract per-survivor detail from a cosmic-ray session database.

Reads a cosmic-ray ``session.sqlite`` (produced by ``cosmic-ray init``/``exec``) and emits one
structured record per SURVIVING mutant (``test_outcome != 'KILLED'``), joining the mutation spec
(module, position, operator, enclosing definition) with the work result (outcome, diff). Used to
build the founder-adjudication mutation survivor packet (STAGE3-0005 §6/§8). Read-only; it never
runs tests or mutates anything.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def _annotation_line(module_path: str, line: int, root: Path) -> bool:
    """True if the mutated source line is (part of) a type annotation — heuristic used to flag
    the PEP-563 equivalence class. Conservative: only flags obvious annotation contexts."""
    try:
        text = (root / module_path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    if not (1 <= line <= len(text)):
        return False
    src = text[line - 1].strip()
    # a def/param annotation, a return annotation, or a bare `name: Type` annotation line
    if src.startswith(("def ", "async def ")) or "->" in src:
        return True
    # `name: T | U` variable/param annotation without assignment execution semantics
    return (":" in src and "|" in src and "==" not in src and "=" not in src.split(":", 1)[0])


def extract(session: Path, root: Path) -> list[dict[str, object]]:
    con = sqlite3.connect(str(session))
    rows = con.execute(
        """
        SELECT s.module_path, s.operator_name, s.occurrence, s.start_pos_row, s.start_pos_col,
               s.end_pos_row, s.end_pos_col, s.definition_name, s.job_id,
               r.worker_outcome, r.test_outcome, r.diff
        FROM mutation_specs s JOIN work_results r ON s.job_id = r.job_id
        ORDER BY s.module_path, s.start_pos_row, s.occurrence
        """
    ).fetchall()
    survivors: list[dict[str, object]] = []
    for (module_path, operator_name, occurrence, sr, sc, er, ec, defname, job_id,
         worker_outcome, test_outcome, diff) in rows:
        if test_outcome == "KILLED":
            continue
        survivors.append({
            "survivor_id": str(job_id)[:12],
            "job_id": job_id,
            "module": module_path,
            "line": sr,
            "col": sc,
            "end_line": er,
            "end_col": ec,
            "definition": defname,
            "operator": operator_name,
            "occurrence": occurrence,
            "worker_outcome": worker_outcome,
            "test_outcome": test_outcome,
            "is_annotation_line": _annotation_line(module_path, sr, root),
            "diff": diff,
        })
    return survivors


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Extract surviving mutants from a cosmic-ray session.")
    p.add_argument("--session", required=True, type=Path)
    p.add_argument("--root", default=".", type=Path)
    p.add_argument("--json", action="store_true", help="emit JSON array (else a summary)")
    args = p.parse_args(argv)

    survivors = extract(args.session, args.root.resolve())
    if args.json:
        print(json.dumps(survivors, indent=2))
        return 0
    by_mod: dict[str, int] = {}
    by_ann = {"annotation": 0, "non_annotation": 0}
    for s in survivors:
        by_mod[str(s["module"])] = by_mod.get(str(s["module"]), 0) + 1
        by_ann["annotation" if s["is_annotation_line"] else "non_annotation"] += 1
    print(f"survivors: {len(survivors)}")
    for mod, n in sorted(by_mod.items()):
        print(f"  {mod}: {n}")
    print(f"  annotation-line: {by_ann['annotation']}  non-annotation: {by_ann['non_annotation']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
