"""SPEC-101 Gate -1 licensing check — standalone CI tool.

Thin CLI over ``governance.licensed_sources``: load the registry, require every operational
source to be ``permitted`` with the full required rights, exit 0/1. A missing or malformed
registry fails closed. (2026-07-16 audit finding A5: enforcement previously rode on one unit
test; this gives the licensing rule the same dedicated-checker shape as SPEC-100.)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from governance.licensed_sources import (
    LicensingError,
    assert_operational_sources_licensed,
    load_registry,
)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="SPEC-101 licensed-sources gate check.")
    parser.add_argument("--registry", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        sources = load_registry(args.registry)
        checked = assert_operational_sources_licensed(sources)
    except (OSError, LicensingError) as exc:
        print(f"[licensed-sources] FAIL: {exc}")
        return 1
    print(
        f"[licensed-sources] OK: {len(sources)} source(s) in registry, "
        f"{len(checked)} operational and fully licensed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
