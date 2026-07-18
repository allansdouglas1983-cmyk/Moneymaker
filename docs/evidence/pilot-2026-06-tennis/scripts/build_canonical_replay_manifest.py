"""Canonical replay manifest (founder pre-analysis record, 2026-07-18).

Every UNIQUE market in the deduped corpus appears exactly once, bound to a single
canonical source and content hash, so a deterministic replay can never ingest a market
twice. Built directly from the frozen packaging-audit output — no counts are copied.

Canonical source per market:
  - standalone-canonical markets: the {marketId}.bz2 file. Its content hash is the
    per-file SHA-256 already recorded in SHA256SUMS.txt (no recompute).
  - combined-only markets: the {eventId}.bz2 combined file, filtered to that market_id.
    Its content hash is sha256 over the ordered mc-entries JSON for that market extracted
    from the combined file (the exact bytes that would enter replay).

The manifest body is a sorted, deterministic serialization; its SHA-256 is the
"canonical replay manifest digest". A market that is REDUNDANT in a combined file
contributes its standalone canonical entry only — the redundant combined copy is
recorded as excluded provenance, never as a second replay row.
"""
from __future__ import annotations

import bz2
import hashlib
import json
import os

AUDIT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(AUDIT)


def load_sha256sums() -> dict[str, str]:
    m = {}
    with open(os.path.join(ROOT, "SHA256SUMS.txt")) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            digest, path = line.split("  ", 1)
            m[path] = digest
    return m


def combined_only_market_hash(combined_path: str, market_id: str) -> tuple[str, int]:
    entries = []
    with bz2.open(combined_path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            for mc in obj.get("mc", []):
                if mc.get("id") == market_id:
                    entries.append(mc)
    body = json.dumps(entries, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest(), len(entries)


def main() -> None:
    sha = load_sha256sums()

    # Standalone-canonical markets = every record in full_corpus_metadata (built from the
    # 16,955 standalone {marketId}.bz2 files).
    standalone_rows = []
    standalone_ids = set()
    with open(os.path.join(AUDIT, "full_corpus_metadata.jsonl")) as f:
        for line in f:
            r = json.loads(line)
            mid = r["market_id"]
            rel = r["path"]  # e.g. extracted/ADVANCED/.../{marketId}.bz2
            if rel not in sha:
                raise RuntimeError(f"FAIL HARD: no SHA256SUMS entry for canonical file {rel}")
            standalone_ids.add(mid)
            standalone_rows.append(
                {
                    "market_id": mid,
                    "market_type": r["market_type"],
                    "canonical_source": rel,
                    "canonical_provenance": "STANDALONE_FILE",
                    "canonical_sha256": sha[rel],
                }
            )

    # Combined-only markets from the packaging audit.
    combined_only_rows = []
    with open(os.path.join(AUDIT, "dedup_audit_output.jsonl")) as f:
        for line in f:
            r = json.loads(line)
            if r.get("classification") != "COMBINED_ONLY":
                continue
            mid = r["market_id"]
            if mid in standalone_ids:
                raise RuntimeError(f"FAIL HARD: {mid} is both standalone and combined-only")
            combined_path = r["combined_path"]
            digest, n_entries = combined_only_market_hash(combined_path, mid)
            rel = os.path.relpath(combined_path, ROOT)
            combined_only_rows.append(
                {
                    "market_id": mid,
                    "market_type": None,  # non-MATCH_ODDS by construction (verified separately)
                    "canonical_source": rel,
                    "canonical_provenance": "COMBINED_FILE_FILTERED",
                    "canonical_sha256": digest,
                    "combined_entry_count": n_entries,
                }
            )

    all_rows = standalone_rows + combined_only_rows
    # Deterministic: sort by market_id.
    all_rows.sort(key=lambda x: x["market_id"])

    # Uniqueness guard: never twice.
    seen = set()
    for row in all_rows:
        if row["market_id"] in seen:
            raise RuntimeError(f"FAIL HARD: market {row['market_id']} appears twice in canonical replay manifest")
        seen.add(row["market_id"])

    body = "\n".join(json.dumps(row, sort_keys=True) for row in all_rows) + "\n"
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()

    with open(os.path.join(AUDIT, "CANONICAL_REPLAY_MANIFEST.jsonl"), "w") as f:
        f.write(body)

    # MATCH_ODDS analytical subset count (the markets this pilot actually reconstructs).
    match_odds_count = sum(1 for r in all_rows if r["market_type"] == "MATCH_ODDS")

    header = {
        "manifest_version": "CANONICAL_REPLAY_MANIFEST-v1",
        "canonical_unique_market_count": len(all_rows),
        "standalone_canonical_markets": len(standalone_rows),
        "combined_only_markets": len(combined_only_rows),
        "match_odds_analytical_markets": match_odds_count,
        "packaging_audit_digest": hashlib.sha256(
            open(os.path.join(AUDIT, "dedup_audit_output.jsonl"), "rb").read()
        ).hexdigest(),
        "universe_manifest_digest": "ce9a147e64df0db5865dade4d78f0ae02cb93532c2f81518e9da313115029049",
        "corpus_sha256sums_digest": hashlib.sha256(
            open(os.path.join(ROOT, "SHA256SUMS.txt"), "rb").read()
        ).hexdigest(),
        "canonical_replay_manifest_digest": digest,
    }
    with open(os.path.join(AUDIT, "CANONICAL_REPLAY_MANIFEST_header.json"), "w") as f:
        json.dump(header, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps(header, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
