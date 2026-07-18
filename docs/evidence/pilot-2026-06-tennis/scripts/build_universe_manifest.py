"""Build the versioned, hash-bound PRIMARY_JUNE_ANALYSIS_UNIVERSE manifest.

Founder decision (2026-07-18), point 6: "Freeze rules, not copied counts." This script
computes every field from the underlying rule application against the corpus metadata —
it does not hard-code any previously-reported count. Re-running it against an unchanged
corpus must reproduce identical rows and an identical digest.

Rules applied (all founder-approved):
  - date membership: earliest valid marketDefinition.marketTime in
    [2026-06-01T00:00:00Z, 2026-07-01T00:00:00Z); folder path is never authoritative.
  - v1 analytical market unit: MATCH_ODDS only.
  - match format: classify_v2.py's MatchFormat (SINGLES/DOUBLES/UNKNOWN) determined from
    primary-runner structure alone, plus ClassificationEvidence
    (PRIMARY_AND_SIBLING/PRIMARY_ONLY/CONFLICT/UNCLASSIFIABLE).
  - packaging: dedup_audit.py's per-market_id classification against combined
    ({eventId}.bz2) files. Canonical source is the standalone file whenever one exists;
    a combined-file copy of the same market is redundant and excluded from replay.
    A market present ONLY in a combined file is included once with explicit provenance.
    A CONFLICT anywhere is a hard stop, not something this script silently resolves.

No price, volume, outcome, settlement, closing-price or P&L field is read or referenced
by this script. Only marketDefinition-level metadata and the classifier/dedup outputs
already produced under that same discipline.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone

MANIFEST_VERSION = "PRIMARY_JUNE_ANALYSIS_UNIVERSE-v1"
WINDOW_START = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)


def parse_iso(s):
    if s is None:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def pt_to_dt(pt):
    if pt is None:
        return None
    return datetime.fromtimestamp(pt / 1000, tz=timezone.utc)


def date_membership(earliest_market_time: str | None) -> tuple[str, datetime | None]:
    mt = parse_iso(earliest_market_time)
    if mt is None:
        return "DATE_MEMBERSHIP_UNKNOWN", None
    if not (WINDOW_START <= mt < WINDOW_END):
        return "EXCLUDED_OUT_OF_WINDOW", mt
    return "INCLUDED", mt


def cross_boundary_start(membership: str, first_in_play_pt) -> bool:
    if membership != "INCLUDED":
        return False
    fip = pt_to_dt(first_in_play_pt)
    if fip is None:
        return False
    return fip >= WINDOW_END


def main() -> None:
    # 1. Full corpus metadata, MATCH_ODDS only (the approved v1 analytical market unit).
    match_odds: dict[str, dict] = {}
    with open("audit/full_corpus_metadata.jsonl") as f:
        for line in f:
            r = json.loads(line)
            if r.get("market_type") == "MATCH_ODDS":
                match_odds[r["market_id"]] = r

    # 2. classify_v2 MatchFormat / ClassificationEvidence.
    classification: dict[str, dict] = {}
    with open("audit/match_format_v2.jsonl") as f:
        for line in f:
            r = json.loads(line)
            classification[r["market_id"]] = r

    # 3. dedup_audit packaging classification, keyed by market_id.
    #    A market_id can only appear in ONE combined file's grouping (each event's
    #    combined file packages that event's own markets), so a single dict entry per
    #    market_id is expected; if the corpus ever violated that, .setdefault below
    #    would silently keep only the first — so assert uniqueness instead of assuming.
    packaging: dict[str, dict] = {}
    dupe_market_across_combined = []
    with open("audit/dedup_audit_output.jsonl") as f:
        for line in f:
            r = json.loads(line)
            mid = r.get("market_id")
            if mid is None:
                continue  # file-level error row, not a market row
            if mid in packaging:
                dupe_market_across_combined.append(mid)
            packaging[mid] = r

    if dupe_market_across_combined:
        raise RuntimeError(
            f"FAIL HARD: market_id(s) appear in more than one combined file's grouping, "
            f"packaging policy is ambiguous: {dupe_market_across_combined}"
        )

    conflicts = [r for r in packaging.values() if r["classification"] == "CONFLICT"]
    if conflicts:
        raise RuntimeError(f"FAIL HARD: {len(conflicts)} packaging CONFLICT(s) found: {conflicts}")

    # Sanity: no MATCH_ODDS market may be COMBINED_ONLY (would mean full_corpus_metadata.jsonl,
    # built from standalone files only, is missing MATCH_ODDS markets entirely).
    combined_only_match_odds = [
        mid for mid, r in packaging.items()
        if r["classification"] == "COMBINED_ONLY" and mid in match_odds
    ]
    if combined_only_match_odds:
        raise RuntimeError(
            f"FAIL HARD: MATCH_ODDS market(s) exist only in combined files, invisible to "
            f"the standalone-file scan: {combined_only_match_odds}"
        )
    combined_only_non_match_odds = [
        mid for mid, r in packaging.items()
        if r["classification"] == "COMBINED_ONLY" and mid not in match_odds
    ]

    rows = []
    for market_id, rec in sorted(match_odds.items()):
        membership, mt = date_membership(rec.get("earliest_market_time"))
        cbs = cross_boundary_start(membership, rec.get("first_in_play_pt"))
        cls = classification.get(market_id)
        if cls is None:
            raise RuntimeError(f"FAIL HARD: MATCH_ODDS market {market_id} has no classify_v2 record")
        match_format = cls["match_format"]
        evidence = cls["classification_evidence"]

        pkg = packaging.get(market_id)
        if pkg is None:
            packaging_status = "STANDALONE_ONLY_NO_COMBINED_COPY"
            redundant_combined_path = None
        elif pkg["classification"] == "REDUNDANT":
            packaging_status = "STANDALONE_CANONICAL_COMBINED_REDUNDANT"
            redundant_combined_path = pkg["combined_path"]
        else:
            raise RuntimeError(f"FAIL HARD: unexpected packaging classification for MATCH_ODDS {market_id}: {pkg}")

        cohort_tags = []
        if match_format == "UNKNOWN":
            universe_membership = "EXCLUDED_UNKNOWN_FORMAT" if membership == "INCLUDED" else membership
        elif membership == "INCLUDED" and match_format == "SINGLES":
            universe_membership = "PRIMARY_JUNE_SINGLES_UNIVERSE"
            cohort_tags.append("PRIMARY_JUNE_SINGLES_UNIVERSE")
            if evidence == "PRIMARY_AND_SIBLING":
                cohort_tags.append("STRICT_SIBLING_CORROBORATED_SENSITIVITY_COHORT")
        elif membership == "INCLUDED" and match_format == "DOUBLES":
            universe_membership = "DOUBLES_DESCRIPTIVE_COHORT"
            cohort_tags.append("DOUBLES_DESCRIPTIVE_COHORT")
        else:
            universe_membership = membership  # EXCLUDED_OUT_OF_WINDOW / DATE_MEMBERSHIP_UNKNOWN

        rows.append(
            {
                "market_id": market_id,
                "event_id": rec.get("event_id"),
                "event_name": rec.get("event_name"),
                "earliest_market_time": rec.get("earliest_market_time"),
                "date_membership": membership,
                "cross_boundary_start": cbs,
                "match_format": match_format,
                "classification_evidence": evidence,
                "packaging_status": packaging_status,
                "redundant_combined_path": redundant_combined_path,
                "universe_membership": universe_membership,
                "cohort_tags": cohort_tags,
            }
        )

    # 4. Serialize deterministically (sorted keys, sorted rows by market_id already) and hash.
    body_lines = [json.dumps(row, sort_keys=True) for row in rows]
    body = "\n".join(body_lines) + "\n"
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()

    with open("audit/PRIMARY_JUNE_ANALYSIS_UNIVERSE_MANIFEST.jsonl", "w") as f:
        f.write(body)

    counts = Counter(r["universe_membership"] for r in rows)
    cohort_counts = Counter(tag for r in rows for tag in r["cohort_tags"])
    packaging_counts = Counter(r["packaging_status"] for r in rows)

    header = {
        "manifest_version": MANIFEST_VERSION,
        "generated_from": {
            "full_corpus_metadata": "audit/full_corpus_metadata.jsonl",
            "match_format_classification": "audit/match_format_v2.jsonl",
            "packaging_dedup_audit": "audit/dedup_audit_output.jsonl",
        },
        "rules": {
            "date_window": "[2026-06-01T00:00:00Z, 2026-07-01T00:00:00Z)",
            "date_window_field": "marketDefinition.marketTime (earliest valid, never folder path)",
            "v1_analytical_market_unit": "MATCH_ODDS only",
            "match_format_rule": "classify_v2.py: primary runner structure -> MatchFormat; sibling markets -> ClassificationEvidence, absence never forces UNKNOWN",
            "packaging_rule": "standalone canonical when present; combined-file copy excluded from replay as redundant; combined-only market included once with provenance; conflicting duplicate representation fails hard",
        },
        "row_count": len(rows),
        "universe_membership_counts": dict(counts),
        "cohort_counts": dict(cohort_counts),
        "packaging_status_counts": dict(packaging_counts),
        "combined_only_non_match_odds_count": len(combined_only_non_match_odds),
        "body_sha256": digest,
    }
    with open("audit/PRIMARY_JUNE_ANALYSIS_UNIVERSE_MANIFEST_header.json", "w") as f:
        json.dump(header, f, indent=2, sort_keys=True)
        f.write("\n")

    print(json.dumps(header, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
