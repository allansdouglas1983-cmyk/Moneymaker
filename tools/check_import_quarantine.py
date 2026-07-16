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


def _imports_of(path: Path, module: str) -> tuple[set[str], list[str]]:
    """Dotted import targets referenced by ``path``, plus fail-closed problems.

    Static AST walk covering ``import``/``from`` statements AND literal dynamic imports
    (``importlib.import_module("x")`` under any alias, ``__import__("x")``). A dynamic import
    whose target is not a string literal cannot be resolved statically and is reported as a
    problem — the quarantine fails closed rather than blessing what it cannot see. The same
    applies to a file that cannot be read or parsed (2026-07-16 audit findings A1/A4).
    Problems only fail the check for modules actually reachable from ``--from``.
    """
    targets: set[str] = set()
    problems: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return targets, [f"unreadable file (fail-closed): {exc}"]
    except SyntaxError as exc:
        return targets, [f"cannot parse file (fail-closed): {exc.msg} at line {exc.lineno}"]
    pkg_parts = module.split(".")
    importlib_names: set[str] = set()
    import_module_names: set[str] = {"__import__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                targets.add(alias.name)
                if alias.asname is None and (
                    alias.name == "importlib" or alias.name.startswith("importlib.")
                ):
                    importlib_names.add("importlib")
                elif alias.asname is not None and alias.name == "importlib":
                    importlib_names.add(alias.asname)
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
                if mod == "importlib":
                    for alias in node.names:
                        if alias.name == "import_module":
                            import_module_names.add(alias.asname or "import_module")
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_dynamic_import = (
            isinstance(func, ast.Name) and func.id in import_module_names
        ) or (
            isinstance(func, ast.Attribute)
            and func.attr == "import_module"
            and isinstance(func.value, ast.Name)
            and func.value.id in importlib_names
        )
        if not is_dynamic_import:
            continue
        first_arg = node.args[0] if node.args else None
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            targets.add(first_arg.value)
        else:
            problems.append(
                f"dynamic import with a non-literal target at line {node.lineno} (fail-closed)"
            )
    return targets, problems


def _is_forbidden(target: str, forbid: str) -> bool:
    return target == forbid or target.startswith(forbid + ".")


def find_violations(root: Path, forbid: str, from_pkgs: list[str]) -> list[str]:
    """Return forbidden import chains reachable from ``from_pkgs`` (empty if clean)."""
    root = root.resolve()
    modules: dict[str, Path] = {_module_name(p, root): p for p in _iter_py(root)}
    analysed: dict[str, tuple[set[str], list[str]]] = {
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
        targets, problems = analysed.get(name, (set(), []))
        for problem in problems:
            violations.append(" -> ".join(chain) + f": {problem}")
        for target in sorted(targets):
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
