"""Complete structural field inventory of the Tennis ADVANCED corpus (Stage-2A Task 2).

Catalogues every distinct key at every nesting level and the market-status context in
which it appears (OPEN / SUSPENDED / CLOSED), plus its JSON type. Records NO outcome
VALUES — this is a structural catalogue of field NAMES/positions used to classify them,
not an extraction of results. (Legitimate pre-lockbox: the lockbox is being designed in
this slice; nothing here is used for any model or analysis.)

Scans a broad, deterministic sample across market types and both event folders.
"""
from __future__ import annotations

import bz2
import json
import os
from collections import defaultdict

ROOT = "/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data"


def jtype(v):
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "str"
    if isinstance(v, list):
        return "list"
    if isinstance(v, dict):
        return "dict"
    if v is None:
        return "null"
    return type(v).__name__


def main():
    # deterministic broad sample: walk the extracted tree, take files across all dirs
    all_files = []
    for dirpath, _, filenames in os.walk(os.path.join(ROOT, "extracted")):
        for fn in filenames:
            if fn.endswith(".bz2"):
                all_files.append(os.path.join(dirpath, fn))
    all_files.sort()
    # sample every Nth to span the whole month & all event types, plus force-include
    # combined files (which carry every market type multiplexed)
    step = max(1, len(all_files) // 1200)
    sample = all_files[::step]

    # key -> {status_context set, jtypes set, count}
    top = defaultdict(lambda: {"status": set(), "types": set(), "n": 0})
    mc = defaultdict(lambda: {"status": set(), "types": set(), "n": 0})
    md = defaultdict(lambda: {"status": set(), "types": set(), "n": 0})
    runner = defaultdict(lambda: {"status": set(), "types": set(), "n": 0})
    rc = defaultdict(lambda: {"status": set(), "types": set(), "n": 0})
    market_types_seen = set()

    def note(store, k, v, status):
        e = store[k]
        e["status"].add(status)
        e["types"].add(jtype(v))
        e["n"] += 1

    n_files = 0
    for path in sample:
        n_files += 1
        try:
            with bz2.open(path, "rt", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    msg = json.loads(line)
                    for k, v in msg.items():
                        note(top, k, v, "-")
                    for m in msg.get("mc", []):
                        status = "?"
                        mdef = m.get("marketDefinition")
                        if mdef is not None:
                            status = mdef.get("status", "?")
                        for k, v in m.items():
                            note(mc, k, v, status)
                        if mdef is not None:
                            market_types_seen.add(mdef.get("marketType"))
                            for k, v in mdef.items():
                                note(md, k, v, status)
                            for r in mdef.get("runners", []):
                                if isinstance(r, dict):
                                    for k, v in r.items():
                                        note(runner, k, v, status)
                        for rcentry in m.get("rc", []):
                            if isinstance(rcentry, dict):
                                for k, v in rcentry.items():
                                    note(rc, k, v, status)
        except Exception as e:  # noqa: BLE001
            print("ERR", path, e)

    def dump(name, store):
        print(f"\n===== {name} ({len(store)} distinct keys) =====")
        for k in sorted(store):
            e = store[k]
            print(f"  {k:24s} types={sorted(e['types'])!s:26s} status={sorted(e['status'])} n={e['n']}")

    print(f"scanned {n_files} files; market_types_seen={sorted(x for x in market_types_seen if x)}")
    dump("TOP-LEVEL (mcm message)", top)
    dump("mc[] (market change)", mc)
    dump("marketDefinition", md)
    dump("marketDefinition.runners[]", runner)
    dump("rc[] (runner change / prices)", rc)


if __name__ == "__main__":
    main()
