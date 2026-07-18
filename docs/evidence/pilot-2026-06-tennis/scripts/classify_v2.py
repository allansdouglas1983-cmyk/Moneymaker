"""Classifier v2 (founder decision 3-5, 2026-07-18).

MatchFormat {SINGLES, DOUBLES, UNKNOWN} is determined by PRIMARY runner
structure alone (the MATCH_ODDS market's own two runner names). Sibling
markets never override a resolvable primary label -- they only raise or
lower confidence, recorded separately as ClassificationEvidence:

  PRIMARY_AND_SIBLING - primary resolvable; >=1 informative sibling market,
                        all informative siblings agree with primary.
  PRIMARY_ONLY        - primary resolvable; no informative sibling data
                        exists (absence never forces UNKNOWN).
  CONFLICT            - primary resolvable; >=1 informative sibling
                        structurally DISAGREES with primary. MatchFormat
                        becomes UNKNOWN here (contradiction, not absence).
  UNCLASSIFIABLE      - primary itself is not resolvable (malformed runner
                        structure on the MATCH_ODDS market itself). MatchFormat
                        is UNKNOWN regardless of any sibling data.

No market-specific code exception exists anywhere in this module: every
market is passed through the identical structural test, keyed only by its
own runner-name strings.
"""
import json
from collections import defaultdict


def slash_structure(name):
    parts = [p for p in name.split("/") if p.strip()]
    return len(parts) if parts else None


def primary_label(runner_names):
    """Returns 'SINGLES' | 'DOUBLES' | None (None = malformed/unclassifiable)."""
    if not runner_names or len(runner_names) != 2:
        return None
    structures = [slash_structure(n) for n in runner_names]
    if any(s is None for s in structures):
        return None
    if all(s == 1 for s in structures):
        return "SINGLES"
    if all(s == 2 for s in structures):
        return "DOUBLES"
    return None


def sibling_label(runner_names):
    if not runner_names or len(runner_names) < 2 or len(runner_names) % 2 != 0:
        return None
    structures = [slash_structure(n) for n in runner_names]
    if any(s is None for s in structures):
        return None
    if all(s == 1 for s in structures):
        return "SINGLES"
    if all(s == 2 for s in structures):
        return "DOUBLES"
    return None


def main():
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
        primary = primary_label(r["runner_names"])
        siblings = [s for s in by_event[r["event_id"]] if s["market_id"] != r["market_id"]]
        sibling_labels = set()
        for s in siblings:
            lbl = sibling_label(s["runner_names"])
            if lbl is not None:
                sibling_labels.add(lbl)

        if primary is None:
            match_format = "UNKNOWN"
            evidence = "UNCLASSIFIABLE"
        elif len(sibling_labels) == 0:
            match_format = primary
            evidence = "PRIMARY_ONLY"
        elif sibling_labels == {primary}:
            match_format = primary
            evidence = "PRIMARY_AND_SIBLING"
        else:
            # sibling_labels has >=1 member that isn't exactly {primary}:
            # either pure disagreement or siblings disagree among themselves.
            match_format = "UNKNOWN"
            evidence = "CONFLICT"

        results.append({
            "market_id": r["market_id"],
            "event_id": r["event_id"],
            "event_name": r["event_name"],
            "path": r["path"],
            "runner_names": r["runner_names"],
            "primary_label": primary,
            "sibling_labels_seen": sorted(sibling_labels),
            "sibling_market_count": len(siblings),
            "match_format": match_format,
            "classification_evidence": evidence,
        })

    with open("audit/match_format_v2.jsonl", "w") as out:
        for r in results:
            out.write(json.dumps(r) + "\n")

    from collections import Counter
    fmt_counts = Counter(r["match_format"] for r in results)
    ev_counts = Counter(r["classification_evidence"] for r in results)
    cross = Counter((r["match_format"], r["classification_evidence"]) for r in results)
    print("MatchFormat counts:", dict(fmt_counts))
    print("ClassificationEvidence counts:", dict(ev_counts))
    print("Cross-tab (format, evidence):")
    for k in sorted(cross):
        print(f"  {k}: {cross[k]}")


if __name__ == "__main__":
    main()
