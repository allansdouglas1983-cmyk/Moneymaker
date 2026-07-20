"""OUTCOME_RECONCILIATION_V1 (Stage 2F §3) — Betfair recovery artifact vs Tennis-Data June.

Exact governed-identity join only (td-norm-v1 via sport_tennis.identity_bridge): a TD row
matches a market iff the tour matches, the unordered player-key pair is EQUAL, and the TD match
date is within +/-1 calendar day of the market's UTC cluster day (deltas reported). No fuzzy
join, no guessed identity correction, no silent conflict resolution: 0 candidates -> unmatched,
>1 -> ambiguous, disagreement -> conflict, all itemised. The 59 both-REMOVED Betfair exclusions
remain exclusions (their TD comment is reported for context only). No odds columns are read.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, "/home/user/Moneymaker")
SCRATCH = Path("/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad")
sys.path.insert(0, str(SCRATCH / "tennis-data"))

from eligibility_and_designs import iter_rows, parse_date  # type: ignore[import-not-found]  # governed TD readers  # noqa: E402

from sport_tennis.identity_bridge import _td_key, normalize_name  # noqa: E402

REPO = Path("/home/user/Moneymaker")
BUNDLE = REPO / "docs/evidence/stage2e-june-m1-bundle/JUNE_M1_PREDICTION_BUNDLE.jsonl"
ARTIFACT = REPO / "docs/evidence/stage2e-june-m1-artifact/RECOVERY_OUTCOME_ARTIFACT.json"
OUT = REPO / "docs/evidence/stage2f-post-failure/RECONCILIATION.json"
_NS = {"ATP": "td-atp", "WTA": "td-wta"}


def td_key(tour: str, raw_name: str) -> str | None:
    parsed = _td_key(normalize_name(raw_name))
    if parsed is None:
        return None
    surname, initials = parsed
    return f"{_NS[tour]}:{surname}|{initials}"


def main() -> None:
    bundle = [json.loads(ln) for ln in BUNDLE.read_text(encoding="utf-8").splitlines() if ln.strip()]
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    winner_by_market = {o["market_id"]: int(o["winner_selection_id"]) for o in art["outcomes"]}
    excluded = {e["market_id"]: e["reason"] for e in art["exclusions"]}

    # TD June rows via the governed reader + td-norm-v1 keys.
    td_rows: dict[tuple[str, frozenset[str]], list[dict[str, Any]]] = defaultdict(list)
    raw_dir = SCRATCH / "tennis-data/raw/vintage-2026-07-18"
    for fn in sorted(p.name for p in raw_dir.iterdir()):
        tour = "ATP" if fn.startswith("atp") else "WTA"
        for hdr, row in iter_rows(str(raw_dir / fn)):
            cols = {h: (row[i] if i < len(row) else None) for i, h in enumerate(hdr)}
            d = parse_date(cols.get("Date"))
            if d is None or not (date(2026, 5, 31) <= d <= date(2026, 7, 2)):
                continue
            w_raw, l_raw = cols.get("Winner"), cols.get("Loser")
            if not w_raw or not l_raw:
                continue
            wk, lk = td_key(tour, str(w_raw)), td_key(tour, str(l_raw))
            if wk is None or lk is None:
                continue
            td_rows[(tour, frozenset((wk, lk)))].append(
                {"date": d, "winner_key": wk, "loser_key": lk,
                 "comment": str(cols.get("Comment") or "Completed").strip()})

    matched: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    excl_td_comment: Counter[str] = Counter()
    date_deltas: Counter[int] = Counter()
    agreement = 0

    for p in bundle:
        mid = p["market_id"]
        tour = p["tour"]
        pair = frozenset((p["competitor_designated"], p["competitor_other"]))
        cluster = date.fromisoformat(p["cluster_day"])
        cands = [r for r in td_rows.get((tour, pair), [])
                 if abs((r["date"] - cluster).days) <= 1]
        bf_status = "EXCLUDED" if mid in excluded else "SCORED"
        bf_winner: str | None = None
        if mid in winner_by_market:
            sel = winner_by_market[mid]
            bf_winner = (p["competitor_designated"] if sel == int(p["selection_id_designated"])
                         else p["competitor_other"])
        base = {"market_id": mid, "tour": tour, "cluster_day": p["cluster_day"],
                "betfair_status": bf_status, "betfair_winner_key": bf_winner}
        if not cands:
            unmatched.append({**base, "reason": "NO_TD_ROW_FOR_PAIR_WITHIN_1_DAY"})
            continue
        if len(cands) > 1:
            ambiguous.append({**base, "reason": "MULTIPLE_TD_ROWS_FOR_PAIR_WITHIN_1_DAY",
                              "candidates": [{"date": r["date"].isoformat(),
                                              "winner_key": r["winner_key"],
                                              "comment": r["comment"]} for r in cands]})
            continue
        r = cands[0]
        date_deltas[(r["date"] - cluster).days] += 1
        rec = {**base, "td_date": r["date"].isoformat(), "td_winner_key": r["winner_key"],
               "td_comment": r["comment"]}
        if bf_status == "EXCLUDED":
            excl_td_comment[r["comment"]] += 1
            rec["agreement"] = "N/A_BETFAIR_EXCLUSION_REMAINS_EXCLUSION"
            matched.append(rec)
            continue
        if bf_winner == r["winner_key"]:
            agreement += 1
            rec["agreement"] = "AGREE"
            matched.append(rec)
        else:
            rec["agreement"] = "CONFLICT"
            conflicts.append(rec)

    result: dict[str, Any] = {
        "diagnostic": "OUTCOME_RECONCILIATION_V1",
        "join_rule": "exact td-norm-v1 pair equality + same tour + |td_date - cluster_day| <= 1 day",
        "inputs": {"bundle_n": len(bundle), "scored_n": len(winner_by_market),
                   "excluded_n": len(excluded)},
        "counts": {
            "reconciled_matched": len(matched),
            "scored_matched": sum(1 for m in matched if m["betfair_status"] == "SCORED"),
            "agreement": agreement,
            "conflict": len(conflicts),
            "ambiguous": len(ambiguous),
            "unmatched": len(unmatched),
            "excluded_matched": sum(1 for m in matched if m["betfair_status"] == "EXCLUDED"),
        },
        "date_delta_distribution": {str(k): v for k, v in sorted(date_deltas.items())},
        "exclusion_td_comment_distribution": dict(sorted(excl_td_comment.items())),
        "conflicts": conflicts,
        "ambiguous": ambiguous,
        "unmatched": unmatched[:200],
        "unmatched_total": len(unmatched),
    }
    body = json.dumps(result, indent=1, sort_keys=True)
    OUT.write_text(body, encoding="utf-8")
    digest = "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()
    print(json.dumps({**result["counts"], "reconciliation_digest": digest}, indent=1))
    print("exclusion TD comments:", dict(excl_td_comment))
    print("date deltas:", dict(date_deltas))
    if conflicts:
        print("CONFLICTS PRESENT — STOP BEFORE FURTHER DIAGNOSTICS")
        for c in conflicts[:20]:
            print("  ", json.dumps(c))


if __name__ == "__main__":
    main()
