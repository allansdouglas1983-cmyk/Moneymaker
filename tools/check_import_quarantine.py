"""Static transitive import-graph quarantine (SPEC-100).

Fail if any first-party module reachable from the ``--from`` packages imports the
``--forbid`` package (or a submodule of it). Reports the import chain. Licence *taint*
through hand-copied data (SPECIFICATION.md §6.12) is a separate concern, not covered here.
"""
from __future__ import annotations

import argparse
import ast
import sys
from collections import deque
from pathlib import Path

_IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
}


def _module_name(path: Path, root: Path) -> str:
    parts = list(path.relative_to(root).parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][: -len(".py")]
    return ".".join(parts)


def _iter_py(root: Path) -> list[Path]:
    result: list[Path] = []
    for path in root.rglob("*.py"):
        if any(part in _IGNORE_DIRS for part in path.relative_to(root).parts):
            continue
        result.append(path)
    return result


def _imports_of(path: Path, module: str) -> set[str]:
    """Dotted import targets referenced by ``path`` (best-effort static)."""
    targets: set[str] = set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return targets
    pkg_parts = module.split(".")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                targets.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg_parts[: len(pkg_parts) - node.level]
                prefix = ".".join(base)
                mod = f"{prefix}.{node.module}" if node.module else prefix
            else:
                mod = node.module or ""
            if mod:
                targets.add(mod)
                for alias in node.names:
                    targets.add(f"{mod}.{alias.name}")
    return targets


def _is_forbidden(target: str, forbid: str) -> bool:
    return target == forbid or target.startswith(forbid + ".")


def find_violations(root: Path, forbid: str, from_pkgs: list[str]) -> list[str]:
    """Return forbidden import chains reachable from ``from_pkgs`` (empty if clean)."""
    root = root.resolve()
    modules: dict[str, Path] = {_module_name(p, root): p for p in _iter_py(root)}
    imports: dict[str, set[str]] = {
        name: _imports_of(path, name) for name, path in modules.items()
    }

    def first_party(target: str) -> list[str]:
        return [n for n in modules if n == target or n.startswith(target + ".")]

    violations: list[str] = []
    seen: set[str] = set()
    queue: deque[tuple[str, tuple[str, ...]]] = deque()
    for pkg in from_pkgs:
        for name in first_party(pkg):
            if name not in seen:
                seen.add(name)
                queue.append((name, (name,)))

    while queue:
        name, chain = queue.popleft()
        for target in sorted(imports.get(name, set())):
            if _is_forbidden(target, forbid):
                violations.append(" -> ".join(chain) + f" -> {target}  (forbidden: {forbid})")
                continue
            for nxt in first_party(target):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt, chain + (nxt,)))
    return violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Static import-graph quarantine check.")
    parser.add_argument("--forbid", required=True)
    parser.add_argument("--from", dest="from_pkgs", required=True, nargs="+")
    parser.add_argument("--root", default=".", type=Path)
    args = parser.parse_args(argv)

    violations = find_violations(Path(args.root), args.forbid, list(args.from_pkgs))
    if violations:
        print(
            f"[import-quarantine] FAIL: {len(violations)} forbidden path(s) to {args.forbid}:"
        )
        for violation in violations:
            print(f"  - {violation}")
        return 1
    print(
        f"[import-quarantine] OK: no path from {', '.join(args.from_pkgs)} reaches {args.forbid}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
