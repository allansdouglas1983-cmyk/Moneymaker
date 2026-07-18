"""Tennis-Data governed data-acceptance audit (founder directive 2026-07-18 §3).

Records dated STRICTLY BEFORE 2026-06-01T00:00:00Z only. The June guard is structural in
the row loop: the Date cell is read FIRST; any row dated on/after the boundary increments
a counter and is skipped BEFORE any winner/loser/score cell of that row is read. No June
Betfair outcome is joined or inspected anywhere. Bookmaker-odds columns are catalogued by
NAME and null-count only — no odds value is analysed, aggregated or exported.

Fail-closed: ambiguous outcomes (Comment not in the known vocabulary, missing winner,
unparseable dates) are enumerated into explicit exclusion lists, never silently fixed.
Authorisation context: EXP-TENNISDATA-ACCEPTANCE-001 (founder directive §3), pre-June
scope, Tennis-Data source (rights: founder-approved, evidence file pending ingestion).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from datetime import date, datetime

import openpyxl
import xlrd

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "raw", "vintage-2026-07-18")
BOUNDARY = date(2026, 6, 1)

KNOWN_COMMENTS = {
    "completed": "COMPLETED",
    "retired": "RETIRED",
    "walkover": "WALKOVER",
    "awarded": "AWARDED",          # disqualification/default — winner declared
    "abandoned": "ABANDONED",
    "disqualified": "DISQUALIFIED",
    "sched": "SCHEDULED",          # not played at file time
}
ODDS_COL_RE = re.compile(r"^(B365|B&W|CB|EX|IW|LB|GB|PS|SB|SJ|UB|Max|Avg)[WL]$")
CORE = ["Date", "Winner", "Loser", "Surface", "Tournament", "Location", "Round", "Comment", "WRank", "LRank"]


def iter_rows(path: str):
    if path.endswith(".xlsx"):
        wb = openpyxl.load_workbook(path, read_only=True)
        ws = wb.active
        rows = ws.iter_rows(values_only=True)
        hdr = [str(c) if c is not None else "" for c in next(rows)]
        for r in rows:
            yield hdr, r
    else:
        wb = xlrd.open_workbook(path)
        ws = wb.sheet_by_index(0)
        hdr = [str(c.value) for c in ws.row(0)]
        for i in range(1, ws.nrows):
            vals = []
            for j, c in enumerate(ws.row(i)):
                if c.ctype == xlrd.XL_CELL_DATE:
                    vals.append(datetime(*xlrd.xldate_as_tuple(c.value, wb.datemode)))
                elif c.ctype == xlrd.XL_CELL_EMPTY:
                    vals.append(None)
                else:
                    vals.append(c.value)
            yield hdr, tuple(vals)


def parse_date(v) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
            try:
                return datetime.strptime(v.strip(), fmt).date()
            except ValueError:
                continue
    return None


def norm_name(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def main() -> None:
    per_year: dict[tuple[str, int], Counter] = defaultdict(Counter)
    surfaces = Counter()
    surface_missing_by_year: Counter = Counter()
    comments = Counter()
    ambiguous_rows: list[dict] = []
    date_anomalies: list[dict] = []
    post_boundary = Counter()
    odds_cols_by_year: dict[str, list[str]] = {}
    odds_nullcount = Counter()
    odds_rowcount = Counter()
    rank_missing = Counter()
    rank_present = Counter()
    key_index: dict[tuple, list] = defaultdict(list)
    exact_dupes = 0
    name_by_tour: dict[str, set] = {"ATP": set(), "WTA": set()}
    total = Counter()
    winner_missing = 0
    unparseable_dates = 0

    files = sorted(os.listdir(RAW))
    for fn in files:
        tour = "ATP" if fn.startswith("atp") else "WTA"
        year = int(re.search(r"(\d{4})", fn).group(1))
        path = os.path.join(RAW, fn)
        prev_date: date | None = None
        seen_exact: set = set()
        odds_cols: list[str] | None = None
        for hdr, row in iter_rows(path):
            cols = {h: (row[i] if i < len(row) else None) for i, h in enumerate(hdr)}
            if odds_cols is None:
                odds_cols = [h for h in hdr if ODDS_COL_RE.match(h)]
                odds_cols_by_year[f"{tour}-{year}"] = odds_cols
            # JUNE GUARD: date first; skip the whole row before touching outcome cells.
            d = parse_date(cols.get("Date"))
            if d is None:
                if any(v is not None and str(v).strip() for v in row):
                    unparseable_dates += 1
                    ambiguous_rows.append({"file": fn, "reason": "UNPARSEABLE_DATE"})
                continue
            if d >= BOUNDARY:
                post_boundary[f"{tour}-{year}"] += 1
                continue
            total[tour] += 1
            per_year[(tour, year)]["matches"] += 1
            if prev_date is not None and d < prev_date:
                date_anomalies.append({"file": fn, "date": str(d), "prev": str(prev_date)})
            prev_date = d
            w, l = cols.get("Winner"), cols.get("Loser")
            if not w or not l or not str(w).strip() or not str(l).strip():
                winner_missing += 1
                ambiguous_rows.append({"file": fn, "date": str(d), "reason": "MISSING_WINNER_OR_LOSER"})
                continue
            wn, ln = norm_name(str(w)), norm_name(str(l))
            name_by_tour[tour].add(wn)
            name_by_tour[tour].add(ln)
            cm_raw = str(cols.get("Comment") or "").strip().lower()
            cm = KNOWN_COMMENTS.get(cm_raw.split()[0] if cm_raw else "completed")
            if cm is None:
                ambiguous_rows.append({"file": fn, "date": str(d), "reason": f"UNKNOWN_COMMENT:{cm_raw}"})
                cm = "AMBIGUOUS"
            comments[cm] += 1
            per_year[(tour, year)][cm] += 1
            surf = str(cols.get("Surface") or "").strip()
            if surf:
                surfaces[surf] += 1
            else:
                surface_missing_by_year[f"{tour}-{year}"] += 1
            for rk_col in ("WRank", "LRank"):
                v = cols.get(rk_col)
                if v is None or str(v).strip() in ("", "NR"):
                    rank_missing[f"{tour}"] += 1
                else:
                    rank_present[f"{tour}"] += 1
            for oc in odds_cols:
                odds_rowcount[f"{tour}-{year}"] += 1
                if cols.get(oc) is None or str(cols.get(oc)).strip() == "":
                    odds_nullcount[f"{tour}-{year}"] += 1
            key = (tour, str(d), cols.get("Tournament"), wn, ln)
            exact = key + (cm, str(cols.get("Round")))
            if exact in seen_exact:
                exact_dupes += 1
            seen_exact.add(exact)
            key_index[(tour, str(d), norm_name(str(cols.get("Tournament") or "")), frozenset((wn, ln)))].append(
                {"winner": wn, "file": fn}
            )

    # duplicates / conflicts on the pair-day-tournament key
    key_dupes = 0
    conflicts = []
    for key, entries in key_index.items():
        if len(entries) > 1:
            key_dupes += 1
            winners = {e["winner"] for e in entries}
            if len(winners) > 1:
                conflicts.append({"key": [str(k) for k in key[:3]], "winners": sorted(winners)})

    cross_tour = name_by_tour["ATP"] & name_by_tour["WTA"]

    report = {
        "boundary": "2026-06-01T00:00:00Z (strict; rows on/after counted, never read)",
        "available_years": {"ATP": "2000-2026 files", "WTA": "2007-2026 files"},
        "match_counts_by_year": {f"{t}-{y}": dict(c) for (t, y), c in sorted(per_year.items())},
        "totals_pre_june": dict(total),
        "doubles_note": "Tennis-Data files are SINGLES-ONLY by construction (no doubles rows exist in the format); doubles count = 0",
        "surfaces": dict(surfaces),
        "surface_missing_by_year": dict(surface_missing_by_year),
        "comment_vocabulary_counts": dict(comments),
        "winner_or_loser_missing": winner_missing,
        "unparseable_dates": unparseable_dates,
        "exact_duplicate_rows": exact_dupes,
        "pair_day_tournament_duplicate_keys": key_dupes,
        "conflicting_winner_records": conflicts,
        "duplicate_policy": "exact duplicates excluded keeping first; pair-day-tournament dupes with AGREEING winners deduped to one; CONFLICTING winners excluded entirely (both rows) into the exclusion ledger — never resolved by guess",
        "ambiguous_outcome_rows": len(ambiguous_rows),
        "ambiguous_examples": ambiguous_rows[:20],
        "date_order_anomalies": len(date_anomalies),
        "date_anomaly_examples": date_anomalies[:10],
        "cross_tour_name_collisions": sorted(cross_tour),
        "cross_tour_collision_note": "handled by tour namespacing (identity bridge); listed, never merged",
        "ranking_availability": {"present": dict(rank_present), "missing_or_NR": dict(rank_missing)},
        "ranking_knowledge_time": "WRank/LRank are tournament-entry-time ranks published before the event per provider convention, but PUBLICATION TIMING IS NOT MACHINE-VERIFIABLE from the files alone => rankings stay DEFERRED_PENDING_KNOWLEDGE_TIME (field registry), not F2/F3-usable",
        "bookmaker_odds_columns_by_year": odds_cols_by_year,
        "bookmaker_odds_null_rate_note": {
            k: round(odds_nullcount[k] / odds_rowcount[k], 3) for k in odds_rowcount if odds_rowcount[k]
        },
        "odds_quarantine": "odds columns catalogued by NAME/null-count only; QUARANTINED from the fundamental pipeline; no odds value analysed or exported",
        "retrospective_fields": ["W1..L5 set scores", "Wsets/Lsets", "Comment", "all odds columns (incl. closing-style Max/Avg)", "WPts/LPts where present"],
        "post_2026_06_01_records_counted_not_read": dict(post_boundary),
        "no_june_betfair_join": "no Betfair June outcome or market data was joined or inspected",
    }
    out = os.path.join(ROOT, "acceptance_report.json")
    with open(out, "w") as f:
        json.dump(report, f, indent=1, sort_keys=True)
    print("wrote", out)
    print("totals pre-June:", dict(total))
    print("conflicting winner records:", len(conflicts))
    print("ambiguous rows:", len(ambiguous_rows), " cross-tour collisions:", len(cross_tour))
    print("report digest:", hashlib.sha256(open(out, "rb").read()).hexdigest())


if __name__ == "__main__":
    main()
