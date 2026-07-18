"""Full-corpus packaging-duplication audit (founder decision item 7, 2026-07-18).

For every combined ({eventId}.bz2) file, group its 'mc' entries by market_id
(preserving order, exactly as delivered). For each market_id found, compare
against the co-located standalone ({marketId}.bz2) file if one exists.

Classification per (combined_file, market_id):
  REDUNDANT     - standalone exists and its ordered mc-entry list is == the
                  combined file's ordered mc-entry list for that market_id.
                  Standalone is canonical; combined-file copy excluded from replay.
  COMBINED_ONLY - no standalone file exists anywhere in the event dir for this
                  market_id. Include once via the combined file, with provenance.
  CONFLICT      - standalone exists but content differs. FAIL HARD: this script
                  does not resolve conflicts, it reports them.

Metadata only in spirit: this reads full mc entries (including price/volume
sub-fields) ONLY to test byte-for-byte structural equality between two raw
deliveries of the same vendor data. No price, volume, or outcome value is
computed, aggregated, displayed, or used for anything except an equality
test. This is a corpus-integrity check, not a market analysis.
"""
from __future__ import annotations

import bz2
import json
import os
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor


def audit_combined_file(combined_path: str) -> dict:
    event_dir = os.path.dirname(combined_path)
    combined_groups: dict[str, list] = defaultdict(list)
    try:
        with bz2.open(combined_path, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                for mc in obj.get("mc", []):
                    mid = mc.get("id")
                    if mid is None:
                        continue
                    combined_groups[mid].append(mc)
    except Exception as e:  # noqa: BLE001
        return {"combined_path": combined_path, "error": str(e), "markets": []}

    results = []
    for market_id, entries in combined_groups.items():
        standalone_path = os.path.join(event_dir, f"{market_id}.bz2")
        if os.path.exists(standalone_path):
            try:
                standalone_entries = []
                with bz2.open(standalone_path, "rt", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        obj = json.loads(line)
                        for mc in obj.get("mc", []):
                            if mc.get("id") == market_id:
                                standalone_entries.append(mc)
            except Exception as e:  # noqa: BLE001
                results.append(
                    {
                        "market_id": market_id,
                        "combined_path": combined_path,
                        "standalone_path": standalone_path,
                        "classification": "ERROR",
                        "error": str(e),
                    }
                )
                continue
            if entries == standalone_entries:
                results.append(
                    {
                        "market_id": market_id,
                        "combined_path": combined_path,
                        "standalone_path": standalone_path,
                        "classification": "REDUNDANT",
                        "combined_entry_count": len(entries),
                        "standalone_entry_count": len(standalone_entries),
                    }
                )
            else:
                results.append(
                    {
                        "market_id": market_id,
                        "combined_path": combined_path,
                        "standalone_path": standalone_path,
                        "classification": "CONFLICT",
                        "combined_entry_count": len(entries),
                        "standalone_entry_count": len(standalone_entries),
                    }
                )
        else:
            results.append(
                {
                    "market_id": market_id,
                    "combined_path": combined_path,
                    "standalone_path": None,
                    "classification": "COMBINED_ONLY",
                    "entry_count": len(entries),
                }
            )
    return {"combined_path": combined_path, "error": None, "markets": results}


def main() -> None:
    audit_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(audit_dir, "combined_files.txt")) as f:
        paths = [line.strip() for line in f if line.strip()]

    out_path = os.path.join(audit_dir, "dedup_audit_output.jsonl")
    n_files = 0
    n_markets = 0
    n_redundant = 0
    n_combined_only = 0
    n_conflict = 0
    n_error = 0
    file_errors = []

    with ProcessPoolExecutor(max_workers=4) as pool, open(out_path, "w") as out:
        for result in pool.map(audit_combined_file, paths, chunksize=8):
            n_files += 1
            if result["error"] is not None:
                n_error += 1
                file_errors.append(result)
                out.write(json.dumps(result) + "\n")
                continue
            for m in result["markets"]:
                n_markets += 1
                out.write(json.dumps(m) + "\n")
                if m["classification"] == "REDUNDANT":
                    n_redundant += 1
                elif m["classification"] == "COMBINED_ONLY":
                    n_combined_only += 1
                elif m["classification"] == "CONFLICT":
                    n_conflict += 1
                elif m["classification"] == "ERROR":
                    n_error += 1

    print(f"combined files processed: {n_files}")
    print(f"file-level errors: {len(file_errors)}")
    print(f"market_id x combined_file rows: {n_markets}")
    print(f"REDUNDANT: {n_redundant}")
    print(f"COMBINED_ONLY: {n_combined_only}")
    print(f"CONFLICT: {n_conflict}")
    print(f"ERROR (row-level): {n_error}")
    if file_errors:
        print("FILE ERRORS:")
        for fe in file_errors:
            print(f"  {fe['combined_path']}: {fe['error']}")


if __name__ == "__main__":
    main()
