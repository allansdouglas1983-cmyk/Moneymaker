"""Reject facts-registry entries that are stale or misconfigured (SPECIFICATION.md §13.5).

An unpopulated fact (null value AND null recheck_by) is not yet in use and passes. A fact
with a value but no recheck_by is a misconfiguration. A recheck_by before the as-of date is
stale. See docs/decisions/0001-verification-tooling.md.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def check_registry(facts: list[dict[str, Any]], as_of: date) -> list[str]:
    """Return a list of problems; empty means the registry is fresh and well-formed."""
    errors: list[str] = []
    for fact in facts:
        fid = fact.get("fact_id", "<unknown>")
        value = fact.get("value")
        recheck_raw = fact.get("recheck_by")
        if recheck_raw is None:
            if value is not None:
                errors.append(
                    f"{fid}: has a value but no recheck_by (a populated fact must set recheck_by)"
                )
            continue
        recheck = _as_date(recheck_raw)
        if recheck is None:
            errors.append(f"{fid}: recheck_by is not a valid ISO date: {recheck_raw!r}")
            continue
        if recheck < as_of:
            errors.append(
                f"{fid}: stale (recheck_by {recheck.isoformat()} < as-of {as_of.isoformat()})"
            )
    return errors


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Check the facts registry for stale or misconfigured entries."
    )
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--as-of", default=None, help="ISO date; defaults to today (UTC).")
    args = parser.parse_args(argv)

    as_of = date.fromisoformat(args.as_of) if args.as_of else datetime.now(timezone.utc).date()

    raw: Any = yaml.safe_load(Path(args.registry).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        print(f"[facts-freshness] FAIL: {args.registry} is not a YAML list")
        return 1
    facts: list[dict[str, Any]] = [f for f in raw if isinstance(f, dict)]

    errors = check_registry(facts, as_of)
    if errors:
        print(f"[facts-freshness] FAIL ({len(errors)} problem(s)):")
        for err in errors:
            print(f"  - {err}")
        return 1
    print(f"[facts-freshness] OK: {len(facts)} fact(s) fresh as of {as_of.isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
