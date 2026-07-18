import json
from collections import Counter
from datetime import datetime, timezone

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


def date_membership(rec):
    mt = parse_iso(rec["earliest_market_time"])
    if mt is None:
        return "DATE_MEMBERSHIP_UNKNOWN", None
    if not (WINDOW_START <= mt < WINDOW_END):
        return "EXCLUDED_OUT_OF_WINDOW", mt
    return "INCLUDED", mt


def main():
    all_records = {}
    with open("audit/full_corpus_metadata.jsonl") as f:
        for line in f:
            r = json.loads(line)
            all_records[r["market_id"]] = r

    match_odds = {mid: r for mid, r in all_records.items() if r["market_type"] == "MATCH_ODDS"}

    classification = {}
    with open("audit/match_format_classification.jsonl") as f:
        for line in f:
            r = json.loads(line)
            classification[r["market_id"]] = r["final_classification"]

    # --- 1. All 65 boundary-market (Jul/1, Jul/2 folder) classifications ---
    with open("audit/market_level_files.txt") as f:
        market_files = [l.strip() for l in f]
    jul_paths_market_level = sorted(p for p in market_files if "/Jul/" in p)
    boundary_records = []
    for path in jul_paths_market_level:
        rec = next(r for r in all_records.values() if r["path"] == path)
        membership, mt = date_membership(rec)
        cross_boundary = False
        if membership == "INCLUDED":
            fip = pt_to_dt(rec["first_in_play_pt"])
            if fip is not None and fip.month == 7:
                cross_boundary = True
        boundary_records.append({
            "path": rec["path"],
            "market_id": rec["market_id"],
            "event_id": rec["event_id"],
            "event_name": rec["event_name"],
            "competition_name": rec["competition_name"],
            "market_type": rec["market_type"],
            "earliest_market_time": rec["earliest_market_time"],
            "open_date": rec["open_date"],
            "market_time_revisions_count": len(rec["market_time_revisions"]),
            "first_in_play_utc": fip_iso if (fip_iso := (pt_to_dt(rec["first_in_play_pt"]).isoformat() if rec["first_in_play_pt"] else None)) else None,
            "status_transitions": rec["status_transitions"],
            "runner_names": rec["runner_names"],
            "runner_count": rec["runner_count"],
            "date_membership": membership,
            "cross_boundary_start": cross_boundary,
        })

    # the 5 redundant combined event-level files in Jul folder, cross-referenced
    with open("filelist.txt") as f:
        all_paths = [l.strip() for l in f]
    jul_all = [p for p in all_paths if p.startswith("ADVANCED/2026/Jul/")]
    jul_combined = sorted(p for p in jul_all if not p.rsplit("/", 1)[-1].startswith("1."))

    print("=" * 100)
    print("DELIVERABLE 1: All 65 boundary-folder (Jul/1, Jul/2) file classifications")
    print("=" * 100)
    print(f"Market-level files (individually audited): {len(boundary_records)}")
    for r in boundary_records:
        print(f"\n  {r['path']}")
        print(f"    market_id={r['market_id']} event_id={r['event_id']} event_name={r['event_name']!r}")
        print(f"    market_type={r['market_type']} runner_count={r['runner_count']} runners={r['runner_names']}")
        print(f"    earliest_market_time={r['earliest_market_time']}  open_date={r['open_date']}")
        print(f"    market_time_revisions={r['market_time_revisions_count']}  first_in_play_utc={r['first_in_play_utc']}")
        print(f"    status_transitions={r['status_transitions']}")
        print(f"    => date_membership={r['date_membership']}  cross_boundary_start={r['cross_boundary_start']}")
    print(f"\nCombined event-level files (redundant packaging, content already covered above): {len(jul_combined)}")
    for p in jul_combined:
        print(f"  {p}  [redundant with per-market siblings in same folder]")

    membership_counts = Counter(r["date_membership"] for r in boundary_records)
    cross_boundary_count = sum(1 for r in boundary_records if r["cross_boundary_start"])
    print(f"\n--- Summary (65-file / 60-market boundary scope) ---")
    print(f"date_membership counts: {dict(membership_counts)}")
    print(f"cross_boundary_start count: {cross_boundary_count}")

    # --- broader corpus-wide date membership on MATCH_ODDS (the honest full picture) ---
    print()
    print("=" * 100)
    print("SUPPLEMENTARY: corpus-wide date-membership on ALL 3521 MATCH_ODDS markets")
    print("(folder path is not authoritative -- this is required to build PRIMARY_JUNE_ANALYSIS_UNIVERSE honestly)")
    print("=" * 100)
    corpus_membership = Counter()
    cross_boundary_corpus = 0
    out_of_window_examples = []
    for mid, rec in match_odds.items():
        membership, mt = date_membership(rec)
        corpus_membership[membership] += 1
        if membership == "INCLUDED":
            fip = pt_to_dt(rec["first_in_play_pt"])
            if fip is not None and fip.month == 7 and mt.month == 6:
                cross_boundary_corpus += 1
        elif membership == "EXCLUDED_OUT_OF_WINDOW":
            if len(out_of_window_examples) < 10:
                out_of_window_examples.append((rec["path"], rec["earliest_market_time"]))
    print(f"corpus-wide date_membership counts (MATCH_ODDS only): {dict(corpus_membership)}")
    print(f"corpus-wide cross_boundary_start count: {cross_boundary_corpus}")
    print(f"sample of out-of-window markets NOT in the 65 Jul-folder set:")
    for p, mt in out_of_window_examples:
        in_jul_folder = "/Jul/" in p
        print(f"  {p}  marketTime={mt}  (in_Jul_folder={in_jul_folder})")

    # --- 4. singles/doubles/unknown counts for full corpus (MATCH_ODDS scope) ---
    print()
    print("=" * 100)
    print("DELIVERABLE 4: singles/doubles/unknown counts (MATCH_ODDS markets, full corpus, N=3521)")
    print("=" * 100)
    format_counts = Counter(classification.values())
    print(dict(format_counts))

    # --- PRIMARY_JUNE_ANALYSIS_UNIVERSE size ---
    print()
    print("=" * 100)
    print("PRIMARY_JUNE_ANALYSIS_UNIVERSE construction (MATCH_ODDS, INCLUDED date membership, SINGLES_CONFIRMED)")
    print("=" * 100)
    primary_universe = [
        mid for mid, rec in match_odds.items()
        if date_membership(rec)[0] == "INCLUDED" and classification.get(mid) == "SINGLES_CONFIRMED"
    ]
    print(f"PRIMARY_JUNE_ANALYSIS_UNIVERSE (singles, in-window MATCH_ODDS) size: {len(primary_universe)}")

    # --- exclusion funnel ---
    print()
    print("=" * 100)
    print("DELIVERABLE 6: exclusion funnel (starting from all MATCH_ODDS markets)")
    print("=" * 100)
    total = len(match_odds)
    step1_in_window = sum(1 for r in match_odds.values() if date_membership(r)[0] == "INCLUDED")
    step1_excluded_window = sum(1 for r in match_odds.values() if date_membership(r)[0] == "EXCLUDED_OUT_OF_WINDOW")
    step1_unknown_window = sum(1 for r in match_odds.values() if date_membership(r)[0] == "DATE_MEMBERSHIP_UNKNOWN")
    step2_singles = sum(1 for mid in match_odds if date_membership(match_odds[mid])[0] == "INCLUDED" and classification.get(mid) == "SINGLES_CONFIRMED")
    step2_doubles = sum(1 for mid in match_odds if date_membership(match_odds[mid])[0] == "INCLUDED" and classification.get(mid) == "DOUBLES_CONFIRMED")
    step2_unknown_format = sum(1 for mid in match_odds if date_membership(match_odds[mid])[0] == "INCLUDED" and classification.get(mid) == "UNKNOWN")
    print(f"  Total purchased corpus (all files, all market types): 20482")
    print(f"  Distinct markets (per-market files, de-duplicated vs redundant combined files): 16955")
    print(f"  MATCH_ODDS markets (only enabled MarketKind under platform V1_MARKET_KIND_POLICY): {total}")
    print(f"    -> date membership EXCLUDED_OUT_OF_WINDOW (marketTime outside [Jun1,Jul1)): {step1_excluded_window}")
    print(f"    -> date membership DATE_MEMBERSHIP_UNKNOWN: {step1_unknown_window}")
    print(f"    -> date membership INCLUDED: {step1_in_window}")
    print(f"       -> of INCLUDED: SINGLES_CONFIRMED (PRIMARY UNIVERSE): {step2_singles}")
    print(f"       -> of INCLUDED: DOUBLES_CONFIRMED (separate descriptive cohort): {step2_doubles}")
    print(f"       -> of INCLUDED: UNKNOWN format (excluded from primary cohort): {step2_unknown_format}")

    # persist derived objects
    with open("audit/PRIMARY_JUNE_ANALYSIS_UNIVERSE.txt", "w") as out:
        for mid in sorted(primary_universe):
            out.write(mid + "\n")

    with open("audit/exclusion_ledger.jsonl", "w") as out:
        for mid, rec in match_odds.items():
            membership, mt = date_membership(rec)
            fmt = classification.get(mid)
            out.write(json.dumps({
                "market_id": mid,
                "event_id": rec["event_id"],
                "path": rec["path"],
                "date_membership": membership,
                "earliest_market_time": rec["earliest_market_time"],
                "match_format": fmt,
                "in_primary_universe": (membership == "INCLUDED" and fmt == "SINGLES_CONFIRMED"),
            }) + "\n")

    print()
    print("Wrote audit/PRIMARY_JUNE_ANALYSIS_UNIVERSE.txt and audit/exclusion_ledger.jsonl")


if __name__ == "__main__":
    main()
