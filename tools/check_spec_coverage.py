"""Check that active/verified SPEC-IDs are declared, covered, and consistent.

Support/evidence tooling. Division of labour (ADR 0001): this verifies declaration +
coverage + consistency; the separate pytest CI steps enforce that referenced tests pass.
Together they satisfy SPECIFICATION.md §12.3 ("any ID lacks a passing test").
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

# Make the repo root importable when run as `python tools/check_spec_coverage.py`.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools import _spec_lib  # noqa: E402

_PROTECTED = {"active", "verified"}


def _base_manifest(base_ref: str, manifest_path: Path) -> list[dict[str, Any]] | None:
    """Load the manifest from a git base ref, or None if it is unavailable."""
    try:
        rel = str(manifest_path.resolve().relative_to(_ROOT))
    except ValueError:
        rel = str(manifest_path)
    try:
        completed = subprocess.run(
            ["git", "show", f"{base_ref}:{rel}"],
            cwd=str(_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    try:
        return _spec_lib.parse_manifest_text(completed.stdout)
    except (ValueError, yaml.YAMLError):
        return None


def _verification_loss(
    base: list[dict[str, Any]], index: dict[str, dict[str, Any]]
) -> list[str]:
    errors: list[str] = []
    for bentry in base:
        bid = bentry.get("id")
        if not isinstance(bid, str):
            continue
        b_state = bentry.get("enforcement_state")
        b_money = bentry.get("criticality") == "money"
        b_protected = b_state in _PROTECTED
        head = index.get(bid)
        if head is None:
            # A protected ID may not silently disappear; a money ID (any state) may not be
            # deleted without rationale (manifest rule).
            if b_protected:
                errors.append(f"verification loss: {bid} ({b_state}) present on base but now absent")
            elif b_money:
                errors.append(
                    f"criticality: money ID {bid} present on base but now absent "
                    "(deletion needs rationale)"
                )
            continue
        if b_protected and head.get("enforcement_state") not in _PROTECTED:
            errors.append(
                f"verification loss: {bid} downgraded from {b_state} to "
                f"{head.get('enforcement_state')}"
            )
        # "An ID must not be downgraded from money in an ordinary PR" applies to ALL money
        # IDs, including `planned` ones (a foreseeable way to pre-downgrade before activation).
        if b_money and head.get("criticality") != "money":
            errors.append(f"criticality downgrade: {bid} money -> {head.get('criticality')}")
    return errors


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Check SPEC-ID coverage against the manifest.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--enforce-states", default="active,verified")
    parser.add_argument("--tests-dir", default="tests", type=Path)
    parser.add_argument("--require-causal-declarations", action="store_true")
    parser.add_argument("--require-properties-for", default=None)
    parser.add_argument("--detect-verification-loss", action="store_true")
    parser.add_argument("--base-ref", default="origin/main")
    args = parser.parse_args(argv)

    entries = _spec_lib.load_manifest(args.manifest)
    index = _spec_lib.index_manifest(entries)
    enforced_states = {s.strip() for s in args.enforce_states.split(",") if s.strip()}
    coverage = _spec_lib.collect_coverage(args.tests_dir)

    errors: list[str] = []

    for ref_id in sorted(coverage):
        if ref_id not in index:
            errors.append(f"test references unknown SPEC-ID {ref_id}")

    for entry in entries:
        state = entry.get("enforcement_state")
        if state not in enforced_states:
            continue
        spec_id = str(entry.get("id", "<no-id>"))
        criticality = entry.get("criticality", "")
        info = coverage.get(spec_id)
        if info is None or not info.files:
            errors.append(f"{spec_id} ({state}) has no test referencing it")
        elif args.require_properties_for and criticality == args.require_properties_for:
            if not info.has_property:
                errors.append(
                    f"{spec_id} ({criticality}) has no property-based test under a properties/ dir"
                )
        if args.require_causal_declarations and criticality == "money":
            has_ri = bool(entry.get("relevant_inputs"))
            has_mp = bool(entry.get("metamorphic_properties"))
            if has_ri != has_mp:
                errors.append(
                    f"{spec_id} declares only one of relevant_inputs/metamorphic_properties; "
                    "declare both (numerical ID) or neither (structural/guard ID)"
                )

    if args.detect_verification_loss:
        base = _base_manifest(args.base_ref, args.manifest)
        if base is None:
            print(f"[spec-coverage] no base manifest at {args.base_ref}; skipping loss detection")
        else:
            errors.extend(_verification_loss(base, index))

    if errors:
        print(f"[spec-coverage] FAIL ({len(errors)} problem(s)):")
        for err in errors:
            print(f"  - {err}")
        return 1
    enforced = sum(1 for e in entries if e.get("enforcement_state") in enforced_states)
    print(f"[spec-coverage] OK: {enforced} enforced ID(s) covered and consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
