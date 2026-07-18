"""Deterministic SINGLES/DOUBLES/UNKNOWN classifier for MATCH_ODDS markets.

Two independent signals, both required to agree for a CONFIRMED classification:
  1. PRIMARY (runner-name structure): each of the two MATCH_ODDS runner names is
     split on "/". Both runners having exactly 1 part (no slash) => singles
     candidate. Both having exactly 2 non-empty parts => doubles candidate.
     Anything else (mixed, odd part counts, wrong runner count) => UNKNOWN.
  2. CORROBORATION (event-level homogeneity): every OTHER market belonging to the
     same event_id (any market type, e.g. SET_WINNER/HANDICAP/SET_BETTING) is
     checked with the same slash-structure test on ITS runners. If any sibling
     market disagrees with the MATCH_ODDS candidate label, the classification is
     downgraded to UNKNOWN and flagged CLASSIFIER_DISAGREEMENT.

Not a slash heuristic alone: the corroboration step is a genuinely separate
data source (different market records, different runner sets, e.g. 4 runners
for SET_BETTING) that must independently agree.
"""
import json
from collections import defaultdict


def slash_structure(name: str) -> int | None:
    """Number of non-empty '/'-separated parts, or None if malformed (empty)."""
    parts = [p for p in name.split("/") if p.strip()]
    return len(parts) if parts else None


def candidate_label(runner_names: list) -> str:
    if not runner_names or len(runner_names) != 2:
        return "UNKNOWN"
    structures = [slash_structure(n) for n in runner_names]
    if any(s is None for s in structures):
        return "UNKNOWN"
    if all(s == 1 for s in structures):
        return "SINGLES_CANDIDATE"
    if all(s == 2 for s in structures):
        return "DOUBLES_CANDIDATE"
    return "UNKNOWN"


def sibling_label(runner_names: list) -> str | None:
    """Same structural test applied to a sibling market's runners (any count,
    must be even and consistent to signal something), returns None if not
    informative (odd count, single runner, etc.)."""
    if not runner_names or len(runner_names) < 2 or len(runner_names) % 2 != 0:
        return None
    structures = [slash_structure(n) for n in runner_names]
    if any(s is None for s in structures):
        return None
    if all(s == 1 for s in structures):
        return "SINGLES_CANDIDATE"
    if all(s == 2 for s in structures):
        return "DOUBLES_CANDIDATE"
    return None


def main() -> None:
    all_records = []
    with open("audit/full_corpus_metadata.jsonl") as f:
        for line in f:
            all_records.append(json.loads(line))

    by_event = defaultdict(list)
    for r in all_records:
        by_event[r["event_id"]].append(r)

    match_odds = [r for r in all_records if r["market_type"] == "MATCH_ODDS"]

    results = []
    for r in match_odds:
        primary = candidate_label(r["runner_names"])
        siblings = [s for s in by_event[r["event_id"]] if s["market_id"] != r["market_id"]]
        sibling_labels = set()
        for s in siblings:
            lbl = sibling_label(s["runner_names"])
            if lbl is not None:
                sibling_labels.add(lbl)

        if primary == "UNKNOWN":
            final = "UNKNOWN"
            reason = "primary_structure_ambiguous"
        elif len(sibling_labels) == 0:
            # No corroborating sibling data available; primary alone insufficient
            # per founder instruction -> UNKNOWN (not silently trusted).
            final = "UNKNOWN"
            reason = "no_corroborating_sibling_markets"
        elif len(sibling_labels) > 1:
            final = "UNKNOWN"
            reason = "sibling_markets_disagree_with_each_other"
        elif list(sibling_labels)[0] != primary:
            final = "UNKNOWN"
            reason = "CLASSIFIER_DISAGREEMENT_primary_vs_sibling"
        else:
            final = "SINGLES_CONFIRMED" if primary == "SINGLES_CANDIDATE" else "DOUBLES_CONFIRMED"
            reason = "primary_and_sibling_agree"

        results.append({
            "market_id": r["market_id"],
            "event_id": r["event_id"],
            "event_name": r["event_name"],
            "path": r["path"],
            "runner_names": r["runner_names"],
            "primary_candidate": primary,
            "sibling_labels_seen": sorted(sibling_labels),
            "sibling_market_count": len(siblings),
            "final_classification": final,
            "reason": reason,
        })

    with open("audit/match_format_classification.jsonl", "w") as out:
        for r in results:
            out.write(json.dumps(r) + "\n")

    from collections import Counter
    counts = Counter(r["final_classification"] for r in results)
    print("Final classification counts:", dict(counts))
    reason_counts = Counter(r["reason"] for r in results if r["final_classification"] == "UNKNOWN")
    print("UNKNOWN reasons:", dict(reason_counts))


if __name__ == "__main__":
    main()
