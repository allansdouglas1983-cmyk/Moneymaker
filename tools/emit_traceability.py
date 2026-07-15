"""Emit the SPEC-ID -> tests traceability matrix as Markdown (CI artifact)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

# Make the repo root importable when run as `python tools/emit_traceability.py`.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools import _spec_lib  # noqa: E402


def render_markdown(
    entries: list[dict[str, Any]], coverage: dict[str, _spec_lib.CoverageInfo]
) -> str:
    lines: list[str] = [
        "# Traceability matrix",
        "",
        "| SPEC-ID | component | criticality | state | phase | tests | property |",
        "|---|---|---|---|---|---|---|",
    ]
    for entry in entries:
        spec_id = str(entry.get("id", ""))
        info = coverage.get(spec_id)
        n_tests = len(info.files) if info else 0
        prop = "yes" if (info and info.has_property) else "no"
        lines.append(
            f"| {spec_id} | {entry.get('component', '')} | {entry.get('criticality', '')} "
            f"| {entry.get('enforcement_state', '')} | {entry.get('introduced_in_phase', '')} "
            f"| {n_tests} | {prop} |"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Emit the SPEC traceability matrix (Markdown).")
    parser.add_argument("--manifest", default="docs/spec-manifest.yaml", type=Path)
    parser.add_argument("--tests-dir", default="tests", type=Path)
    args = parser.parse_args(argv)

    entries = _spec_lib.load_manifest(args.manifest)
    coverage = _spec_lib.collect_coverage(args.tests_dir)
    print(render_markdown(entries, coverage))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
