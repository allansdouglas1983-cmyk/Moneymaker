"""Cross-market feasibility audit DRIVER (STAGE3-0002 §9-§19; audit code version
xmarket-audit-v1).

Reads the June ADVANCED corpus (definition + pre-off book only), the frozen F0 manifest
(committed MO universe + commit_pt_ms + cohort), and the Stage-2D transfer manifest
(outcome-blind market_id -> tour / calendar day), then emits the audit report + immutable
per-match records (§16). NO outcome, settlement, ROI, P&L, CLV, or EV is read or written.
Deterministic: two runs over the same inputs produce a byte-identical report digest (the
wall-clock is never embedded).

Driver, not an imported module: nothing money-critical imports it. Run:
    python -m research.xmarket.run_audit --corpus <ADVANCED_root> --out <report.json>
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

from research.xmarket import audit as A
from research.xmarket import corpus as C
from research.xmarket import redundancy as RD
from research.xmarket.linkage import mo_event_index, unlinked_derivatives
from research.xmarket.parsers import market_role

CUTOFFS_S = [15.0, 30.0, 60.0, 120.0, 300.0]
TICK_GRID = [1, 2, 3, 5, 10]

F0_MANIFEST = "docs/evidence/stage2b-f0-f2-runs/F0_MARKET_YARDSTICK_MANIFEST.jsonl"
TRANSFER_MANIFEST = "docs/evidence/stage2d-june-m1-transfer/JUNE_M1_TRANSFER_MANIFEST.jsonl"


def _load_f0(path: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        if o.get("committed") is True:
            out[o["market_id"]] = {"commit_pt_ms": int(o["commit_pt_ms"]),
                                   "cohort": o.get("cohort", "UNKNOWN")}
    return out


def _load_tour_day(path: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        tour = o.get("tour")
        norm = tour if tour in ("ATP", "WTA") else (tour or A.TOUR_UNRESOLVED)
        out[o["market_id"]] = {"tour": norm, "calendar_day": o.get("calendar_day_cluster")}
    return out


def _market_type_inventory(catalogue: dict[str, Any]) -> dict[str, dict[str, Any]]:
    inv: dict[str, dict[str, Any]] = {}
    for ref in catalogue.values():
        mt = ref.market_type or "MISSING"
        role = market_role(mt) if isinstance(mt, str) and mt != "MISSING" else "UNKNOWN_REQUIRES_REVIEW"
        slot = inv.setdefault(mt, {"markets": 0, "events": set(), "role": role})
        slot["markets"] += 1
        if ref.event_id is not None:
            slot["events"].add(ref.event_id)
    return {mt: {"markets": s["markets"], "events": len(s["events"]), "role": s["role"]}
            for mt, s in sorted(inv.items())}


def run(corpus_root: str, f0_path: str = F0_MANIFEST,
        transfer_path: str = TRANSFER_MANIFEST) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    f0 = _load_f0(f0_path)
    tour_day = _load_tour_day(transfer_path)

    paths = {mid: p for mid, p in C.iter_market_files(corpus_root)}
    catalogue = C.build_corpus_catalogue(corpus_root)

    committed_mo_ids = set(f0) & set(catalogue)
    idx = mo_event_index(catalogue, committed_mo_ids)

    records = []
    per_match: list[dict[str, Any]] = []
    redundancy_ev: list[RD.RedundancyEvidence] = []
    day_counter: Counter[str] = Counter()
    for mo_id in sorted(committed_mo_ids):
        meta = f0[mo_id]
        td = tour_day.get(mo_id, {"tour": A.TOUR_UNRESOLVED, "calendar_day": None})
        rec = A.audit_one_market(
            mo_market_id=mo_id, commit_pt_ms=meta["commit_pt_ms"],
            cohort=meta["cohort"], tour=td["tour"], calendar_day=td["calendar_day"],
            catalogue=catalogue, mo_index=idx,
            message_provider=lambda m: (C.iter_messages(paths[m]) if m in paths else []),
        )
        records.append(rec)
        # §12 redundancy: co-timing of each usable identifying derivative vs its MO sibling
        for d in (rec.total_games, rec.game_handicap):
            if d is not None and d.exclusion_reason is None:
                ev = RD.classify(
                    C.iter_messages(paths[mo_id]) if mo_id in paths else [],
                    C.iter_messages(paths[d.linked_market_id]) if d.linked_market_id in paths else [],
                    mo_id, d.linked_market_id, meta["commit_pt_ms"])
                redundancy_ev.append(ev)
        # §9 UTC-day concentration counts MARKETS (once), not derivatives
        if A.record_has_identifying(rec, 300.0):
            day_counter[rec.calendar_day or "UNKNOWN_DAY"] += 1
        per_match.append(_per_match_record(rec, meta))

    inventory = _market_type_inventory(catalogue)
    n_ident = A.n_primary_identifying(records, CUTOFFS_S)
    funnel = A.refusal_funnel(records)
    unlinked = unlinked_derivatives(catalogue, idx)
    if unlinked:
        funnel["NOT_LINKED_TO_MATCH_ODDS_EVENT"] = len(unlinked)
    coverage = {c: A.coverage_comparison(records, c) for c in CUTOFFS_S}
    tick_sens = {c: A.spread_tick_sensitivity(records, c, TICK_GRID) for c in CUTOFFS_S}
    self_quote = {c: vars(A.independent_update_status(records, c)) for c in CUTOFFS_S}

    tg_only, gh_only, both = _split_coverage(records)
    line_counts, aux_present = _line_and_aux(records)

    report = {
        "audit_code_version": A.AUDIT_CODE_VERSION,
        "denominators": {
            "committed_mo_in_f0": len(f0),
            "committed_mo_matched_in_corpus": len(committed_mo_ids),
            "cohort_split": _count_by(records, lambda r: r.cohort),
            "tour_split": _count_by(records, lambda r: r.tour),
        },
        "raw_market_type_inventory": inventory,
        "n_primary_identifying_by_cutoff": {str(k): v for k, v in n_ident.items()},
        "total_games_only_vs_game_handicap_only_vs_both_at_300s": {
            "total_games_only": tg_only, "game_handicap_only": gh_only, "both": both},
        "refusal_funnel": funnel,
        "selection_bias_coverage_by_cutoff": {str(k): v for k, v in coverage.items()},
        "one_tick_spread_sensitivity_by_cutoff": {str(k): v for k, v in tick_sens.items()},
        "self_quote_observable_by_cutoff": {str(k): v for k, v in self_quote.items()},
        "redundancy_status_distribution": RD.status_distribution(redundancy_ev),
        "line_richness": {
            "usable_identifying_derivatives": len(line_counts),
            "min": line_counts[0] if line_counts else None,
            "median": line_counts[len(line_counts) // 2] if line_counts else None,
            "max": line_counts[-1] if line_counts else None,
        },
        "auxiliary_coverage": {"mo_markets_with_any_auxiliary": aux_present,
                               "denominator": len(records)},
        "utc_day_concentration_at_300s": {
            "distinct_days": len(day_counter),
            "largest_day_count": max(day_counter.values()) if day_counter else 0,
        },
        "tournament_attribution": "NOT_AVAILABLE_OUTCOME_BLIND",  # §9 honest limitation
    }
    report["report_digest"] = _digest(report)
    return report, per_match


def _per_match_record(rec: A.MarketAuditRecord, meta: dict[str, Any]) -> dict[str, Any]:
    def _d(d: A.DerivativeAudit | None) -> dict[str, Any] | None:
        return asdict(d) if d is not None else None
    return {
        "mo_market_id": rec.mo_market_id, "event_id": rec.event_id,
        "commit_pt_ms": rec.commit_pt_ms, "cohort": rec.cohort, "tour": rec.tour,
        "calendar_day": rec.calendar_day,
        "total_games": _d(rec.total_games), "game_handicap": _d(rec.game_handicap),
        "auxiliary_market_ids": list(rec.auxiliary_market_ids),
        "linkage_anomalies": list(rec.linkage_anomalies),
    }


def _split_coverage(records: list[A.MarketAuditRecord]) -> tuple[int, int, int]:
    tg_only = gh_only = both = 0
    for rec in records:
        tg = A.derivative_usable(rec.total_games, 300.0)
        gh = A.derivative_usable(rec.game_handicap, 300.0)
        if tg and gh:
            both += 1
        elif tg:
            tg_only += 1
        elif gh:
            gh_only += 1
    return tg_only, gh_only, both


def _line_and_aux(records: list[A.MarketAuditRecord]) -> tuple[list[int], int]:
    line_counts: list[int] = []
    aux_present = 0
    for rec in records:
        if rec.auxiliary_market_ids:
            aux_present += 1
        for d in (rec.total_games, rec.game_handicap):
            if d is not None and d.exclusion_reason is None:
                line_counts.append(d.lines_offered)
    line_counts.sort()
    return line_counts, aux_present


def _count_by(records: list[Any], key: Any) -> dict[str, int]:
    return dict(Counter(key(r) for r in records))


def _digest(report: dict[str, Any]) -> str:
    payload = {k: v for k, v in report.items() if k != "report_digest"}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--f0", default=F0_MANIFEST)
    ap.add_argument("--transfer", default=TRANSFER_MANIFEST)
    ap.add_argument("--out", required=True)
    ap.add_argument("--records-out", default=None)
    args = ap.parse_args()
    report, per_match = run(args.corpus, args.f0, args.transfer)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if args.records_out:
        with Path(args.records_out).open("w") as fh:
            for r in per_match:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
    print(f"wrote {args.out} digest={report['report_digest']}")


if __name__ == "__main__":
    main()
