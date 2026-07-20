"""Stage 2G Slice 3 — DYNAMIC_GLICKO2_V1 (DP1) development evaluation.

Evaluates DP1 (``sport_tennis.glicko2_family.Glicko2Family``) through the
model-independent chronological cross-fit orchestrator (``l4_pricing.crossfit.cross_fit``,
SPEC-031), alongside two baselines: the frozen F2-v1 global Elo (K=24, registered
equation) and the structural null (uniform 1/N). DEVELOPMENT evidence only — see
CLAUDE.md / .claude/rules/stage2-evidence-discipline.md: no betting/ROI/CLV, no
result-driven modelling decisions here, this script only produces pre-registered
proper-scoring and calibration diagnostics.

Hard boundary: every row with Date >= 2026-06-01 is excluded before any model sees it
(``BOUNDARY``). No bookmaker odds column is ever read (only Winner/Loser/Date/Comment/
tour, mirroring the frozen F2 loader). No surface feature is read or constructed.

Design B (mirrors ``docs/evidence/stage2b-f0-f2-runs/scripts/f2_run.py`` for
comparability):
  * warm-up through 2018-12-31 (folds trained on but never scored — cross_fit's
    ``score_only_after``);
  * OOF window 2019-01-01..2025-05-31, produced by ``cross_fit`` (strictly
    out-of-fold, SPEC-031);
  * validation window 2025-06-01..2026-05-31, evaluated PREQUENTIALLY with a
    hand-rolled day-batch incremental replay seeded from the OOF-window deployment
    model — this mirrors what F2 did with its own hand-rolled Elo update (an
    incrementally-updated rating system run forward, not a fresh re-fit every day;
    that is the actual deployment dynamic, not merely a performance shortcut).

DP1 needs per-match state (rating, rating deviation / delta, scale, prior-count,
last-active) that the crossfit ``predict()`` seam does not expose. This script
therefore ALSO runs an independent deterministic prequential replay using DP1's
public state primitives (``rate_player``, ``inactivity_step``, ``PlayerState``,
``INITIAL_PLAYER_STATE`` from ``sport_tennis.glicko2_family``; ``central_win_probability``
/ ``interval_bounds`` from ``sport_tennis.dp1_distribution``). The ONLY thing this
script cannot get from the public API directly is how two ``PlayerState`` values are
combined into the ``(delta, s)`` pair ``central_win_probability``/``interval_bounds``
expect for a two-player choice set.

*** ASSUMPTION REQUIRING LEAD VERIFICATION (``_ASSUMPTION_DELTA_S``) ***
This script assumes the standard published Glicko-2 two-player combination:
    delta = mu_a - mu_b
    s     = sqrt(phi_a**2 + phi_b**2)
where (mu, phi) are the internal natural-scale fields of ``PlayerState`` (as opposed
to the ``rating``/``rating_deviation`` display-scale properties) and a/b are the two
active runners with a = the lower runner_id (this script's fixed "a-side" convention,
matching ``f2_run.py``'s ``first_id = min(...)``). This assumption was NOT verified
against the actual (currently mutation-tested, unreadable) source of
``dp1_distribution.py``/``glicko2_family.py``. It is instead SELF-VERIFIED at runtime:
every OOF race is scored BOTH by ``cross_fit`` (via ``Glicko2Family.fit``/``.predict``,
which does not depend on this assumption at all) and by this script's own replay
(which does). §"crossfit_vs_replay_reconciliation" in each tour's report compares the
two series exactly (tolerance 0) and reports the worst mismatches if any. If the
assumption is wrong, that section will show it plainly — the lead should fix
``_delta_and_scale`` below (the ONLY function this assumption lives in) against the
real source before trusting the validation-window / coverage-diagnostic numbers, which
have no independent check (there is no crossfit-produced ground truth for the
validation window at all, by Design B construction).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

sys.path.insert(0, "/home/user/Moneymaker")
import openpyxl  # type: ignore[import-untyped]  # no stubs available; mirrors f2_run.py
import xlrd  # type: ignore[import-untyped]  # no stubs available; mirrors f2_run.py

from l4_pricing.crossfit import CrossFitResult, cross_fit
from l4_pricing.horizon import HorizonLabel
from l4_pricing.races import FeatureSchema, Race, RunnerRow
from sport_core.clustering import ChronologyKey, calendar_day_assignment
from sport_tennis.elo_family import ELO_INITIAL_RATING, GlobalEloFamily, elo_win_probability
from sport_tennis.identity_bridge import _td_key, normalize_name  # governed normalizer
from sport_tennis.structural_null import StructuralNullFamily

# --- DP1 under evaluation. NOT importable/executable in the drafting session (a
# cosmic-ray mutation run holds these two files in a mutated state on disk); the lead
# runs this script only after that mutation run has completed and the files are back
# to their real, reviewed content. ---
from sport_tennis.glicko2_family import (  # noqa: E402
    INITIAL_PLAYER_STATE,
    Glicko2Family,
    PlayerState,
    inactivity_step,
    rate_player,
)
from sport_tennis.dp1_distribution import (  # noqa: E402
    INTERVAL_Z,
    central_win_probability,
    interval_bounds,
)

SCRATCH = Path("/tmp/claude-0/-home-user-Moneymaker/b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad")
RAW = SCRATCH / "tennis-data" / "raw" / "vintage-2026-07-18"
OUTDIR = SCRATCH / "stage2g-slice3" / "out"

SCRIPT_VERSION = "stage2g-dp1-run-v2"
BOUNDARY = date(2026, 6, 1)
WARMUP_THROUGH = date(2018, 12, 31)
OOF_LO, OOF_HI = date(2019, 1, 1), date(2025, 5, 31)
VAL_LO, VAL_HI = date(2025, 6, 1), date(2026, 5, 31)
# The EXACT frozen F2-v1 comparator (founder pre-result controls §1): per-tour selected_k
# from F2_EVALUATION_REPORT.json under the frozen selection rule; the affine vintage is
# calibration-policy-v2 frozen_parameters. K=24 applied to WTA is
# INVALID_COMPARATOR_CONFIGURATION, never a simplification.
FROZEN_F2_K_BY_TOUR: dict[str, float] = {"ATP": 24.0, "WTA": 32.0}
FROZEN_F2_AFFINE_BY_TOUR: dict[str, dict[str, float]] = {
    "ATP": {"intercept": 0.025399, "temperature": 1.218638},
    "WTA": {"intercept": 0.029204, "temperature": 1.150681},
}
# ROW-TIME VALIDITY (founder control): the vintage above was fitted on ALL pre-June
# outcomes for June deployment. Applying it to any historical evaluation row would be
# retrospective; it therefore appears in reports as reference metadata only.
F2_FROZEN_VINTAGE_APPLICATION = "COMPARATOR_REFERENCE_ONLY_NEVER_APPLIED_TO_HISTORICAL_ROWS"

# Frozen evidence roles for every scorecard table (founder control §1).
EVIDENCE_ROLES: dict[str, str] = {
    "dp1_raw": "RAW_HONEST",
    "f2_v1_frozen_baseline": "RAW_HONEST",
    "structural_null_baseline": "RAW_HONEST",
    "dp1_calibrated_oof": "IN_SAMPLE_CALIBRATION_DIAGNOSTIC",
    "dp1_calibrated_validation": "CALIBRATED_HONEST",
    "f2_calibrated_oof": "QUARANTINED_NOT_PRODUCED (no row-time-valid cheap reproduction of the outer-fold F2 calibration exists; omitted rather than faked)",
    "f2_calibrated_validation": "CALIBRATED_HONEST (affine fitted on F2 OOF-window predictions only, strictly before the validation block; same split as DP1)",
    "paired_oof": "RAW_HONEST (raw-vs-raw only)",
    "paired_validation_raw": "RAW_HONEST",
    "paired_validation_calibrated": "CALIBRATED_HONEST",
}


def assert_frozen_comparator() -> None:
    """Self-refusal: the comparator constants must match the frozen records on disk."""
    repo = Path(__file__).resolve().parents[4]
    frozen = json.loads(
        (repo / "docs/evidence/stage2b-f0-f2-runs/F2_EVALUATION_REPORT.json").read_text()
    )
    for tour in ("ATP", "WTA"):
        recorded = float(frozen[tour]["selected_k"])
        if FROZEN_F2_K_BY_TOUR[tour] != recorded:
            raise AssertionError(
                f"INVALID_COMPARATOR_CONFIGURATION: {tour} K {FROZEN_F2_K_BY_TOUR[tour]!r} "
                f"!= frozen selected_k {recorded!r}"
            )
    policy = (repo / "specs/programme/calibration-policy-v2.yaml").read_text()
    for tour, params in FROZEN_F2_AFFINE_BY_TOUR.items():
        for name, value in params.items():
            if f"{name}: {value!r}" not in policy:
                raise AssertionError(
                    f"INVALID_COMPARATOR_CONFIGURATION: {tour} affine {name}={value!r} not "
                    "found in calibration-policy-v2 frozen_parameters"
                )
SCHEMA = FeatureSchema(names=("unit",))
HORIZON = HorizonLabel("T-5m")
_UNIT_FEATURES: Mapping[str, Decimal] = {"unit": Decimal(1)}

PRIOR_BANDS: list[tuple[int, int, str]] = [
    (0, 0, "0"), (1, 4, "1-4"), (5, 9, "5-9"), (10, 19, "10-19"), (20, 10**9, "20+"),
]
INACTIVITY_BANDS: list[tuple[int, int, str]] = [
    (0, 7, "0-7"), (8, 30, "8-30"), (31, 90, "31-90"), (91, 365, "91-365"), (366, 10**9, ">365"),
]
WORKLOAD_BANDS: list[tuple[int, int, str]] = [
    (0, 3, "0-3"), (4, 8, "4-8"), (9, 10**9, "9+"),
]
WORKLOAD_WINDOW_DAYS = 28
COHORT_MIN_N = 25


# --------------------------------------------------------------------------- loading
# Mirrors docs/evidence/stage2b-f0-f2-runs/scripts/f2_run.py's iter_rows/parse_date/
# load_tour/build_races byte-for-byte in behaviour (only RAW's path differs — this
# script reads the same vintage-2026-07-18 files staged under scratchpad/tennis-data).

def iter_rows(path: str) -> Iterator[tuple[list[str], tuple[object, ...]]]:
    if path.endswith(".xlsx"):
        wb = openpyxl.load_workbook(path, read_only=True)
        rows = wb.active.iter_rows(values_only=True)
        hdr = [str(c) for c in next(rows)]
        for r in rows:
            yield hdr, r
    else:
        wb = xlrd.open_workbook(path)
        ws = wb.sheet_by_index(0)
        hdr = [str(c.value) for c in ws.row(0)]
        for i in range(1, ws.nrows):
            vals: list[object] = []
            for c in ws.row(i):
                if c.ctype == xlrd.XL_CELL_DATE:
                    vals.append(datetime(*xlrd.xldate_as_tuple(c.value, wb.datemode)))
                elif c.ctype == xlrd.XL_CELL_EMPTY:
                    vals.append(None)
                else:
                    vals.append(c.value)
            yield hdr, tuple(vals)


def parse_date(v: object) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        for f in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
            try:
                return datetime.strptime(v.strip(), f).date()
            except ValueError:
                pass
    return None


def load_tour(tour: str) -> tuple[list[tuple[date, tuple[str, str], tuple[str, str]]], dict[str, int]]:
    """(matches, exclusion_funnel) — matches: (date, key_w, key_l); label-policy-v1."""
    excl: dict[str, int] = defaultdict(int)
    rows: list[tuple[date, tuple[str, str], tuple[str, str]]] = []
    for fn in sorted(os.listdir(RAW)):
        if not fn.startswith(tour.lower()):
            continue
        for hdr, row in iter_rows(os.path.join(RAW, fn)):
            cols = {h: (row[i] if i < len(row) else None) for i, h in enumerate(hdr)}
            d = parse_date(cols.get("Date"))
            if d is None:
                excl["unparseable_date"] += 1
                continue
            if d >= BOUNDARY:
                excl["on_or_after_2026_06_01"] += 1
                continue
            cm = str(cols.get("Comment") or "Completed").strip().lower()
            if not cm.startswith("completed"):
                excl[f"label_excluded_{cm.split()[0] if cm else 'blank'}"] += 1
                continue
            w, loser = cols.get("Winner"), cols.get("Loser")
            if not w or not loser:
                excl["missing_winner_or_loser"] += 1
                continue
            kw = _td_key(normalize_name(str(w)))
            kl = _td_key(normalize_name(str(loser)))
            if kw is None or kl is None:
                excl["malformed_identity"] += 1
                continue
            if kw == kl:
                excl["self_match_defect"] += 1
                continue
            rows.append((d, kw, kl))
    seen: dict[tuple[date, tuple[tuple[str, str], tuple[str, str]]], tuple[str, str]] = {}
    dedup: list[tuple[date, tuple[str, str], tuple[str, str]]] = []
    conflicts: set[tuple[date, tuple[tuple[str, str], tuple[str, str]]]] = set()
    for d, kw, kl in rows:
        pair_key: tuple[tuple[str, str], tuple[str, str]] = tuple(sorted((kw, kl)))  # type: ignore[assignment]
        key = (d, pair_key)
        if key in seen:
            if seen[key] != kw:
                conflicts.add(key)
            excl["duplicate_pair_day"] += 1
            continue
        seen[key] = kw
        dedup.append((d, kw, kl))
    if conflicts:
        dedup = [(d, kw, kl) for d, kw, kl in dedup if (d, tuple(sorted((kw, kl)))) not in conflicts]
        excl["conflicting_winner_excluded"] += len(conflicts)
    return dedup, dict(excl)


def build_races(
    matches: Sequence[tuple[date, tuple[str, str], tuple[str, str]]], tour: str
) -> tuple[list[tuple[date, Race]], dict[tuple[str, str], int]]:
    ids: dict[tuple[str, str], int] = {}

    def cid(key: tuple[str, str]) -> int:
        if key not in ids:
            ids[key] = len(ids) + 1
        return ids[key]

    for key in sorted({k for _, kw, kl in matches for k in (kw, kl)}):
        cid(key)
    races: list[tuple[date, Race]] = []
    occ: dict[tuple[date, int, int], int] = defaultdict(int)
    for d, kw, kl in sorted(matches, key=lambda m: (m[0], tuple(sorted((m[1], m[2]))))):
        a, b = cid(kw), cid(kl)
        okey = (d, min(a, b), max(a, b))
        occ[okey] += 1
        rid = f"td:{tour}:{d.isoformat()}:{min(a, b)}v{max(a, b)}:{occ[okey]}"
        races.append(
            (
                d,
                Race(
                    race_id=rid,
                    cluster=calendar_day_assignment("tennis", d),
                    runners=(
                        RunnerRow(runner_id=a, features=_UNIT_FEATURES),
                        RunnerRow(runner_id=b, features=_UNIT_FEATURES),
                    ),
                    winner_id=cid(kw),
                ),
            )
        )
    return races, ids


# --------------------------------------------------------------------- match context
# Schedule-derived (never touches Glicko internals): prior completed-match counts,
# days since last completed match, and trailing-28-day workload, per runner, per race,
# strictly as of that race's date. Shared by every family's cohort breakdowns and by
# the DP1 replay's inactivity-step bookkeeping (single source of truth).

@dataclass(frozen=True)
class MatchContext:
    date: date
    a: int
    b: int
    prior_a: int
    prior_b: int
    gap_a: int | None
    gap_b: int | None
    workload_a: int
    workload_b: int


def build_match_context(races_dated: Sequence[tuple[date, Race]]) -> dict[str, MatchContext]:
    appear: dict[int, list[date]] = defaultdict(list)
    for d, race in races_dated:
        for rr in race.runners:
            appear[rr.runner_id].append(d)
    for dates in appear.values():
        dates.sort()

    def stats(pid: int, d: date) -> tuple[int, int | None, int]:
        dates = appear[pid]
        idx = bisect_left(dates, d)
        prior = idx
        gap = (d - dates[idx - 1]).days if idx > 0 else None
        workload = idx - bisect_left(dates, d - timedelta(days=WORKLOAD_WINDOW_DAYS))
        return prior, gap, workload

    ctx: dict[str, MatchContext] = {}
    for d, race in races_dated:
        a, b = sorted(rr.runner_id for rr in race.runners)
        pa, ga, wa = stats(a, d)
        pb, gb, wb = stats(b, d)
        ctx[race.race_id] = MatchContext(d, a, b, pa, pb, ga, gb, wa, wb)
    return ctx


def prior_band(ctx_row: MatchContext) -> str:
    return _band(min(ctx_row.prior_a, ctx_row.prior_b), PRIOR_BANDS)


def inactivity_band(ctx_row: MatchContext) -> str:
    if ctx_row.gap_a is None or ctx_row.gap_b is None:
        return "never-seen"
    return _band(min(ctx_row.gap_a, ctx_row.gap_b), INACTIVITY_BANDS)


def workload_band(ctx_row: MatchContext) -> str:
    return _band(min(ctx_row.workload_a, ctx_row.workload_b), WORKLOAD_BANDS)


def _band(value: int, bands: Sequence[tuple[int, int, str]]) -> str:
    for lo, hi, label in bands:
        if lo <= value <= hi:
            return label
    return bands[-1][2]


# ------------------------------------------------------------------------- scoring row

@dataclass(frozen=True)
class ScoredRow:
    """One scored choice set, a-side convention (a = lower runner_id)."""

    race_id: str
    date: date
    p_a: float
    y_a: float


def enrich(rows: Sequence[ScoredRow], ctx: Mapping[str, MatchContext]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        c = ctx[row.race_id]
        out.append(
            {
                "race_id": row.race_id,
                "date": row.date.isoformat(),
                "year": row.date.year,
                "p_a": row.p_a,
                "y_a": row.y_a,
                "prior_band": prior_band(c),
                "inactivity_band": inactivity_band(c),
                "workload_band": workload_band(c),
            }
        )
    return out


# ------------------------------------------------------------------------------ metrics

def _clamp(p: float) -> float:
    return min(max(p, 1e-12), 1 - 1e-12)


def calibration_slope(pairs: Sequence[tuple[float, float]]) -> tuple[float, float]:
    """1-D logistic y ~ sigmoid(a + b*logit(p)) via Newton (mirrors f2_run.py)."""
    a, b = 0.0, 1.0
    xs = [math.log(_clamp(p) / (1 - _clamp(p))) for p, _ in pairs]
    ys = [y for _, y in pairs]
    for _ in range(50):
        ga = gb = haa = hab = hbb = 0.0
        for x, y in zip(xs, ys):
            m = 1.0 / (1.0 + math.exp(-max(-700.0, min(700.0, a + b * x))))
            ga += y - m
            gb += (y - m) * x
            w = m * (1 - m)
            haa += w
            hab += w * x
            hbb += w * x * x
        det = haa * hbb - hab * hab
        if det <= 1e-12:
            break
        da = (hbb * ga - hab * gb) / det
        db = (haa * gb - hab * ga) / det
        a += da
        b += db
        if abs(da) + abs(db) < 1e-10:
            break
    return a, b


def reliability_deciles(pairs: Sequence[tuple[float, float]]) -> dict[str, dict[str, float]]:
    bands: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for p, y in pairs:
        bands[min(9, int(p * 10))].append((p, y))
    out: dict[str, dict[str, float]] = {}
    for i in sorted(bands):
        chunk = bands[i]
        n = len(chunk)
        out[f"[{i / 10:.1f},{(i + 1) / 10:.1f})"] = {
            "n": n,
            "mean_p": round(math.fsum(p for p, _ in chunk) / n, 4),
            "obs_rate": round(math.fsum(y for _, y in chunk) / n, 4),
        }
    return out


def metrics(pairs: Sequence[tuple[float, float]]) -> dict[str, Any]:
    """pairs: (p_a, y_a). Choice-set-level proper scoring, dev evidence only."""
    n = len(pairs)
    if n == 0:
        return {"n": 0}
    ll = math.fsum(-math.log(_clamp(p) if y == 1.0 else _clamp(1.0 - p)) for p, y in pairs) / n
    brier = math.fsum((p - y) ** 2 for p, y in pairs) / n
    mean_p = math.fsum(p for p, _ in pairs) / n
    mean_y = math.fsum(y for _, y in pairs) / n
    a, b = calibration_slope(pairs)
    return {
        "n": n,
        "log_loss": round(ll, 6),
        "brier": round(brier, 6),
        "cal_in_large": round(mean_p - mean_y, 6),
        "cal_intercept": round(a, 6),
        "cal_slope": round(b, 6),
        "reliability": reliability_deciles(pairs),
    }


def cohort_metrics(rows: Sequence[dict[str, Any]], key: str) -> dict[str, Any]:
    groups: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for r in rows:
        groups[str(r[key])].append((r["p_a"], r["y_a"]))
    return {k: metrics(v) for k, v in sorted(groups.items()) if len(v) >= COHORT_MIN_N}


def quantile(sorted_vals: Sequence[float], q: float) -> float:
    if not sorted_vals:
        return float("nan")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    if lo == hi:
        return sorted_vals[lo]
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def stdev(vals: Sequence[float]) -> float:
    n = len(vals)
    if n < 2:
        return 0.0
    m = math.fsum(vals) / n
    return math.sqrt(math.fsum((v - m) ** 2 for v in vals) / (n - 1))


def stability_summary(snapshot: Mapping[int, "PlayerState"]) -> dict[str, Any]:
    if not snapshot:
        return {"count": 0}
    ratings = sorted(st.rating for st in snapshot.values())
    rds = sorted(st.rating_deviation for st in snapshot.values())

    def qs(vals: Sequence[float]) -> dict[str, float]:
        return {"p10": round(quantile(vals, 0.10), 4), "p50": round(quantile(vals, 0.50), 4), "p90": round(quantile(vals, 0.90), 4)}

    return {
        "count": len(snapshot),
        "state_basis": "as-of-each-player's-last-active-day (lazy; phi NOT inflated to window end)",
        "rating": {"mean": round(math.fsum(ratings) / len(ratings), 4), "sd": round(stdev(ratings), 4), **qs(ratings)},
        "rating_deviation": {"mean": round(math.fsum(rds) / len(rds), 4), "sd": round(stdev(rds), 4), **qs(rds)},
        "share_rd_gt_250": round(sum(1 for v in rds if v > 250) / len(rds), 4),
    }


# --------------------------------------------------------------------------- coverage

def coverage_diagnostic(interval_rows: Sequence[dict[str, float]]) -> dict[str, Any]:
    """DEVELOPMENT_DIAGNOSTIC ONLY — see module docstring for the exact operationalisation
    (band-average [lower, upper] from interval_bounds vs band observed win frequency).
    No pass/fail threshold is asserted or implied by this function."""
    if not interval_rows:
        return {"method": "DEVELOPMENT_DIAGNOSTIC", "n": 0, "bands": {}}
    bands: dict[int, list[dict[str, float]]] = defaultdict(list)
    for row in interval_rows:
        bands[min(9, int(row["p_a"] * 10))].append(row)
    band_results: dict[str, Any] = {}
    consistent_n = 0
    for i in sorted(bands):
        chunk = bands[i]
        n = len(chunk)
        mean_p = math.fsum(r["p_a"] for r in chunk) / n
        mean_y = math.fsum(r["y_a"] for r in chunk) / n
        mean_lower = math.fsum(r["lower"] for r in chunk) / n
        mean_upper = math.fsum(r["upper"] for r in chunk) / n
        consistent = mean_lower <= mean_y <= mean_upper
        if consistent:
            consistent_n += n
        band_results[f"[{i / 10:.1f},{(i + 1) / 10:.1f})"] = {
            "n": n,
            "mean_p": round(mean_p, 4),
            "observed_rate": round(mean_y, 4),
            "band_mean_interval_lower": round(mean_lower, 4),
            "band_mean_interval_upper": round(mean_upper, 4),
            "observed_rate_within_band_interval": consistent,
        }
    total = len(interval_rows)
    mean_width = math.fsum(r["upper"] - r["lower"] for r in interval_rows) / total
    return {
        "method": "DEVELOPMENT_DIAGNOSTIC",
        "description": (
            "per predicted-p_a decile band: band-mean observed win frequency vs band-mean of "
            "per-match interval_bounds(delta, s) [lower, upper]; NOT a formal coverage guarantee "
            "(intervals are per-match, this reports a band-aggregate consistency check only); "
            "no pass/fail threshold is asserted"
        ),
        "n": total,
        "bands": band_results,
        "weighted_fraction_bands_with_observed_rate_in_band_interval": round(consistent_n / total, 4),
        "mean_interval_width": round(mean_width, 6),
        "interval_z": INTERVAL_Z,
    }


# ------------------------------------------------------------------------- DP1 replay
# *** ASSUMPTION — see module docstring "ASSUMPTION REQUIRING LEAD VERIFICATION" ***
# The ONLY place the delta/s combination formula is assumed. Self-verified at runtime
# against cross_fit's independently-computed OOF fundamentals (see
# `crossfit_vs_replay_reconciliation` in main()).

def _delta_and_scale(state_a: "PlayerState", state_b: "PlayerState") -> tuple[float, float]:
    delta = state_a.mu - state_b.mu
    s = math.sqrt(state_a.phi**2 + state_b.phi**2)
    return delta, s


@dataclass(frozen=True)
class ReplayRow:
    race_id: str
    date: date
    p_a: float
    y_a: float
    delta: float
    s: float
    lower: float
    upper: float


def build_dp1_replay(
    races_dated: Sequence[tuple[date, Race]], ctx: Mapping[str, MatchContext]
) -> tuple[dict[str, ReplayRow], dict[int, "PlayerState"], dict[int, "PlayerState"]]:
    """Single deterministic forward pass over the FULL corpus (from the first row
    through the last row strictly before BOUNDARY), carrying PlayerState per runner_id
    incrementally via the public rate_player/inactivity_step primitives, day-batched
    (all of a day's matches scored from start-of-day state; deltas applied together —
    same semantics as f2_run.py's Elo replay). Produces one ReplayRow per race (a-side
    convention) plus end-of-OOF-window and end-of-validation-window state snapshots for
    the stability diagnostic (item 5)."""
    states: dict[int, PlayerState] = {}
    last_active: dict[int, date] = {}
    replay: dict[str, ReplayRow] = {}
    oof_snapshot: dict[int, PlayerState] = {}
    val_snapshot: dict[int, PlayerState] = {}

    by_day: dict[date, list[Race]] = defaultdict(list)
    for d, race in races_dated:
        by_day[d].append(race)

    for d in sorted(by_day):
        day_races = sorted(by_day[d], key=lambda r: r.race_id)
        start_states: dict[int, PlayerState] = {}
        for race in day_races:
            a, b = sorted(rr.runner_id for rr in race.runners)
            c = ctx[race.race_id]
            for pid, gap in ((a, c.gap_a), (b, c.gap_b)):
                if pid in start_states:
                    continue
                if pid not in states:
                    start_states[pid] = INITIAL_PLAYER_STATE
                    continue
                st = states[pid]
                if gap is not None:
                    for _ in range(max(gap - 1, 0)):
                        st = inactivity_step(st)
                start_states[pid] = st

        for race in day_races:
            a, b = sorted(rr.runner_id for rr in race.runners)
            sa, sb = start_states[a], start_states[b]
            delta, s = _delta_and_scale(sa, sb)
            p_a = central_win_probability(delta, s)
            lower, upper = interval_bounds(delta, s)
            y_a = 1.0 if race.winner_id == a else 0.0
            replay[race.race_id] = ReplayRow(race.race_id, d, p_a, y_a, delta, s, lower, upper)

        games: dict[int, list[tuple[PlayerState, float]]] = defaultdict(list)
        for race in day_races:
            a, b = sorted(rr.runner_id for rr in race.runners)
            sa, sb = start_states[a], start_states[b]
            score_a = 1.0 if race.winner_id == a else 0.0
            games[a].append((sb, score_a))
            games[b].append((sa, 1.0 - score_a))
        for pid, matchups in games.items():
            states[pid] = rate_player(start_states[pid], matchups)
            last_active[pid] = d

        if d <= OOF_HI:
            oof_snapshot = dict(states)
        if d <= VAL_HI:
            val_snapshot = dict(states)

    return replay, oof_snapshot, val_snapshot


# --------------------------------------------------------------------- F2 / null replay

def f2_validation_replay(
    races_dated: Sequence[tuple[date, Race]], deployment_ratings: Mapping[int, float], k: float
) -> list[ScoredRow]:
    """Hand-rolled day-batch Elo update through the validation window, seeded from the
    OOF-window deployment model — byte-identical mechanism to f2_run.py's validation
    section, at the frozen K=24."""
    ratings: dict[int, float] = dict(deployment_ratings)
    val = [(d, r) for d, r in races_dated if VAL_LO <= d <= VAL_HI]
    by_day: dict[date, list[Race]] = defaultdict(list)
    for d, r in val:
        by_day[d].append(r)
    rows: list[ScoredRow] = []
    for d in sorted(by_day):
        deltas: dict[int, float] = defaultdict(float)
        for race in sorted(by_day[d], key=lambda x: x.race_id):
            a, b = sorted(rr.runner_id for rr in race.runners)
            pa = elo_win_probability(ratings.get(a, ELO_INITIAL_RATING), ratings.get(b, ELO_INITIAL_RATING))
            y_a = 1.0 if race.winner_id == a else 0.0
            rows.append(ScoredRow(race.race_id, d, pa, y_a))
            deltas[a] += k * (y_a - pa)
            deltas[b] += k * ((1.0 - y_a) - (1.0 - pa))
        for rid_, dv in deltas.items():
            ratings[rid_] = ratings.get(rid_, ELO_INITIAL_RATING) + dv
    return rows


def null_validation_rows(races_dated: Sequence[tuple[date, Race]]) -> list[ScoredRow]:
    rows: list[ScoredRow] = []
    for d, race in races_dated:
        if not (VAL_LO <= d <= VAL_HI):
            continue
        a, _b = sorted(rr.runner_id for rr in race.runners)
        y_a = 1.0 if race.winner_id == a else 0.0
        rows.append(ScoredRow(race.race_id, d, 0.5, y_a))
    return rows


def crossfit_oof_rows(
    res: CrossFitResult, races_by_id: Mapping[str, Race], date_by_rid: Mapping[str, date]
) -> list[ScoredRow]:
    """One a-side row per scored race from cross_fit's OOF fundamentals."""
    rows: list[ScoredRow] = []
    seen: set[str] = set()
    for row in res.oof:
        if row.race_id in seen:
            continue
        race = races_by_id[row.race_id]
        a, _b = sorted(rr.runner_id for rr in race.runners)
        if row.runner_id != a:
            continue
        d = date_by_rid[row.race_id]
        y_a = 1.0 if race.winner_id == a else 0.0
        rows.append(ScoredRow(row.race_id, d, row.p_fundamental, y_a))
        seen.add(row.race_id)
    return rows


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _affine_apply(p: float, intercept: float, temperature: float) -> float:
    """The registered affine map, a-side canonical + exact complement downstream."""
    p = min(max(p, 1e-12), 1 - 1e-12)
    z = math.log(p / (1.0 - p))
    zc = intercept + z / temperature
    return 1.0 / (1.0 + math.exp(-max(-700.0, min(700.0, zc))))


def _calibrated_rows(
    rows: Sequence[ScoredRow], intercept: float, temperature: float
) -> list[ScoredRow]:
    return [
        ScoredRow(r.race_id, r.date, _affine_apply(r.p_a, intercept, temperature), r.y_a)
        for r in rows
    ]


def paired_delta(
    left: Sequence[ScoredRow], right: Sequence[ScoredRow], label: str
) -> dict[str, Any]:
    """§3.B paired, chronology-aware log-loss delta (left minus right) on the EXACT
    paired population, with a UTC-day-clustered block bootstrap CI (deterministic
    seed). Never an unpaired aggregate."""
    right_by_id = {r.race_id: r for r in right}
    per_day: dict[date, list[float]] = defaultdict(list)
    for row in left:
        other = right_by_id.get(row.race_id)
        if other is None:
            continue
        d_r = -math.log(_clamp(row.p_a) if row.y_a == 1.0 else _clamp(1.0 - row.p_a)) - (
            -math.log(_clamp(other.p_a) if other.y_a == 1.0 else _clamp(1.0 - other.p_a))
        )
        per_day[row.date].append(d_r)
    days = sorted(per_day)
    all_d = [d for day in days for d in per_day[day]]
    n = len(all_d)
    if n == 0:
        return {"label": label, "n_paired": 0}
    mean = math.fsum(all_d) / n
    import random as _random

    rng = _random.Random(20260720)  # frozen seed: deterministic CI
    boots: list[float] = []
    for _ in range(2000):
        sample: list[float] = []
        for _ in range(len(days)):
            sample.extend(per_day[days[rng.randrange(len(days))]])
        boots.append(math.fsum(sample) / len(sample))
    boots.sort()
    return {
        "label": label,
        "n_paired": n,
        "n_days": len(days),
        "mean_paired_delta_nats": round(mean, 8),
        "day_cluster_bootstrap_ci_95": [
            round(quantile(boots, 0.025), 8),
            round(quantile(boots, 0.975), 8),
        ],
        "note": "left minus right; negative favours left",
    }


def main() -> None:
    assert_frozen_comparator()
    OUTDIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()
    input_hashes = {fn: sha256_file(RAW / fn) for fn in sorted(os.listdir(RAW))}

    output_paths: dict[str, Path] = {}
    manifest_body: dict[str, Any] = {
        "script_version": SCRIPT_VERSION,
        "generated_at": generated_at,
        "boundary_date_exclusive": BOUNDARY.isoformat(),
        "warmup_through": WARMUP_THROUGH.isoformat(),
        "oof_window": [OOF_LO.isoformat(), OOF_HI.isoformat()],
        "validation_window": [VAL_LO.isoformat(), VAL_HI.isoformat()],
        "family_ids": {},
        "input_file_sha256": input_hashes,
        "tours": {},
    }

    for tour in ("ATP", "WTA"):
        matches, load_excl = load_tour(tour)
        races_dated, _ids = build_races(matches, tour)
        races_dated.sort(key=lambda t: (t[0], t[1].race_id))
        date_by_rid = {r.race_id: d for d, r in races_dated}
        races_by_id = {r.race_id: r for _d, r in races_dated}
        dev_races = [r for d, r in races_dated if d <= OOF_HI]
        ctx = build_match_context(races_dated)

        # ---- three families through the SAME model-independent orchestrator ----
        dp1_family = Glicko2Family()
        f2_family = GlobalEloFamily(k_factor=FROZEN_F2_K_BY_TOUR[tour])
        null_family = StructuralNullFamily()
        threshold = ChronologyKey.from_date(WARMUP_THROUGH)

        cf_results: dict[str, CrossFitResult] = {
            "dp1_raw": cross_fit(dev_races, SCHEMA, horizon=HORIZON, family=dp1_family, score_only_after=threshold),
            "f2_v1_frozen": cross_fit(dev_races, SCHEMA, horizon=HORIZON, family=f2_family, score_only_after=threshold),
            "structural_null": cross_fit(dev_races, SCHEMA, horizon=HORIZON, family=null_family, score_only_after=threshold),
        }
        manifest_body["family_ids"][tour] = {
            "dp1_raw": dp1_family.family_id,
            "f2_v1_frozen": f2_family.family_id,
            "structural_null": null_family.family_id,
        }

        oof_by_label: dict[str, list[ScoredRow]] = {}
        exclusion_by_label: dict[str, dict[str, int]] = {}
        for label, res in cf_results.items():
            rows = crossfit_oof_rows(res, races_by_id, date_by_rid)
            oof_by_label[label] = [r for r in rows if OOF_LO <= r.date <= OOF_HI]
            reasons: dict[str, int] = defaultdict(int)
            for exc in res.excluded:
                reasons[exc.reason.split(":", 1)[0]] += 1
            exclusion_by_label[label] = dict(reasons)

        # ---- DP1 replay across the FULL corpus (needed for validation + coverage +
        # cohorts + stability; also independently reproduces the OOF window for the
        # crossfit_vs_replay_reconciliation self-check) ----
        dp1_replay, dp1_oof_snapshot, dp1_val_snapshot = build_dp1_replay(races_dated, ctx)

        dp1_oof_rows = [
            ScoredRow(rr.race_id, rr.date, rr.p_a, rr.y_a)
            for rr in dp1_replay.values()
            if OOF_LO <= rr.date <= OOF_HI
        ]
        dp1_val_rows = [
            ScoredRow(rr.race_id, rr.date, rr.p_a, rr.y_a)
            for rr in dp1_replay.values()
            if VAL_LO <= rr.date <= VAL_HI
        ]

        # ---- reconciliation: cross_fit's DP1 OOF fundamentals vs the replay's own
        # OOF-window predictions for the SAME races (the self-check for the
        # delta/s ASSUMPTION documented at module top) ----
        replay_p_by_race = {rr.race_id: rr.p_a for rr in dp1_replay.values()}
        diffs: list[tuple[str, float, float, float]] = []
        for row in oof_by_label["dp1_raw"]:
            rp = replay_p_by_race.get(row.race_id)
            if rp is None:
                continue
            diffs.append((row.race_id, row.p_a, rp, abs(row.p_a - rp)))
        diffs.sort(key=lambda t: -t[3])
        n_compared = len(diffs)
        n_exact = sum(1 for *_r, d in diffs if d == 0.0)
        n_within_1e9 = sum(1 for *_r, d in diffs if d <= 1e-9)
        n_within_1e6 = sum(1 for *_r, d in diffs if d <= 1e-6)
        reconciliation = {
            "assumption": "_delta_and_scale: delta=mu_a-mu_b, s=sqrt(phi_a^2+phi_b^2) — see module docstring",
            "n_compared": n_compared,
            "n_exact_match": n_exact,
            "n_within_1e-9": n_within_1e9,
            "n_within_1e-6": n_within_1e6,
            "max_abs_diff": diffs[0][3] if diffs else None,
            "worst_20_mismatches": [
                {"race_id": rid, "crossfit_p_a": cp, "replay_p_a": rp, "abs_diff": d}
                for rid, cp, rp, d in diffs[:20]
                if d > 0.0
            ],
            "verdict": (
                "EXACT_MATCH_ALL" if n_compared and n_exact == n_compared
                else "MATCH_WITHIN_1e-6_ALL" if n_compared and n_within_1e6 == n_compared
                else "MISMATCH_ASSUMPTION_LIKELY_WRONG_SEE_MODULE_DOCSTRING" if n_compared
                else "NO_OVERLAP_TO_COMPARE"
            ),
        }

        # ---- validation windows for F2 and null (DP1's own replay already covers it) ----
        f2_deployment = cf_results["f2_v1_frozen"].deployment_model
        f2_val_rows = f2_validation_replay(
            races_dated, f2_deployment.ratings, FROZEN_F2_K_BY_TOUR[tour]  # type: ignore[attr-defined]
        )
        null_val_rows = null_validation_rows(races_dated)

        # ---- assemble per-family OOF + validation reports ----
        def block(oof_rows: Sequence[ScoredRow], val_rows: Sequence[ScoredRow]) -> dict[str, Any]:
            oof_enriched = enrich(oof_rows, ctx)
            val_enriched = enrich(val_rows, ctx)
            return {
                "oof_metrics": metrics([(r["p_a"], r["y_a"]) for r in oof_enriched]),
                "validation_metrics": metrics([(r["p_a"], r["y_a"]) for r in val_enriched]),
                "oof_yearly": cohort_metrics(oof_enriched, "year"),
                "validation_yearly": cohort_metrics(val_enriched, "year"),
                "oof_prior_history_cohorts": cohort_metrics(oof_enriched, "prior_band"),
                "validation_prior_history_cohorts": cohort_metrics(val_enriched, "prior_band"),
                "oof_inactivity_cohorts": cohort_metrics(oof_enriched, "inactivity_band"),
                "validation_inactivity_cohorts": cohort_metrics(val_enriched, "inactivity_band"),
                "oof_workload_cohorts": cohort_metrics(oof_enriched, "workload_band"),
                "validation_workload_cohorts": cohort_metrics(val_enriched, "workload_band"),
            }

        # ---- ROW-TIME-VALID calibration (founder control §1). The June-deployment
        # frozen vintage is COMPARATOR REFERENCE ONLY — it was fitted on all pre-June
        # outcomes and may not touch any historical row. Both models are calibrated
        # the same honest way: affine fitted ONLY on that model's leakage-safe
        # crossfit OOF-window predictions (all strictly before 2025-06-01), applied
        # (a) back onto those same OOF rows = IN_SAMPLE_CALIBRATION_DIAGNOSTIC and
        # (b) forward onto the untouched validation block = CALIBRATED_HONEST.
        # There is NO row-time-valid cheap reproduction of F2's historical outer-fold
        # calibration, so no F2-calibrated OOF table is produced at all.
        from sport_tennis.dp1_calibration import fit_affine_logit_calibration

        dp1_cal = fit_affine_logit_calibration(
            dev_races, cf_results["dp1_raw"].oof, horizon=HORIZON, tour=tour.lower()
        )
        dp1_cal_oof_rows = _calibrated_rows(dp1_oof_rows, dp1_cal.intercept, dp1_cal.temperature)
        dp1_cal_val_rows = _calibrated_rows(dp1_val_rows, dp1_cal.intercept, dp1_cal.temperature)
        f2_cal = fit_affine_logit_calibration(
            dev_races, cf_results["f2_v1_frozen"].oof, horizon=HORIZON, tour=tour.lower()
        )
        f2_cal_val_rows = _calibrated_rows(f2_val_rows, f2_cal.intercept, f2_cal.temperature)

        families_report = {
            "dp1_raw": {"evidence_role": EVIDENCE_ROLES["dp1_raw"], **block(dp1_oof_rows, dp1_val_rows)},
            "dp1_calibrated": {
                "evidence_role_oof": EVIDENCE_ROLES["dp1_calibrated_oof"],
                "evidence_role_validation": EVIDENCE_ROLES["dp1_calibrated_validation"],
                **block(dp1_cal_oof_rows, dp1_cal_val_rows),
            },
            "f2_v1_frozen_baseline": {
                "evidence_role": EVIDENCE_ROLES["f2_v1_frozen_baseline"],
                **block(oof_by_label["f2_v1_frozen"], f2_val_rows),
            },
            "f2_v1_calibrated_validation_only": {
                "evidence_role": EVIDENCE_ROLES["f2_calibrated_validation"],
                "oof_omitted": EVIDENCE_ROLES["f2_calibrated_oof"],
                **block([], f2_cal_val_rows),
            },
            "structural_null_baseline": {
                "evidence_role": EVIDENCE_ROLES["structural_null_baseline"],
                **block(oof_by_label["structural_null"], null_val_rows),
            },
        }
        calibration_block = {
            "dp1_affine": {
                "version": "affine-logit-dp1-v1",
                "fit_on": "DP1 leakage-safe crossfit OOF rows only (SPEC-031 re-verified; all < 2025-06-01)",
                "intercept": dp1_cal.intercept,
                "temperature": dp1_cal.temperature,
                "n_rows": dp1_cal.n_rows,
            },
            "f2_affine_evaluation_calibrator": {
                "fit_on": "F2 leakage-safe crossfit OOF rows only (same split as DP1; validation-only application)",
                "intercept": f2_cal.intercept,
                "temperature": f2_cal.temperature,
                "n_rows": f2_cal.n_rows,
            },
            "row_time_validity": F2_FROZEN_VINTAGE_APPLICATION,
        }
        paired = {
            "oof_raw_dp1_minus_f2": {
                "evidence_role": EVIDENCE_ROLES["paired_oof"],
                **paired_delta(dp1_oof_rows, oof_by_label["f2_v1_frozen"], "OOF: DP1 raw - F2 raw"),
            },
            "validation_raw_dp1_minus_f2": {
                "evidence_role": EVIDENCE_ROLES["paired_validation_raw"],
                **paired_delta(dp1_val_rows, f2_val_rows, "VAL: DP1 raw - F2 raw"),
            },
            "validation_calibrated_dp1_minus_f2": {
                "evidence_role": EVIDENCE_ROLES["paired_validation_calibrated"],
                **paired_delta(
                    dp1_cal_val_rows, f2_cal_val_rows,
                    "VAL: DP1 cal - F2 cal (both affines frozen-from-own-OOF, applied forward only)",
                ),
            },
        }

        # ---- DP1 uncertainty-interval coverage diagnostic (item 4) ----
        dp1_oof_interval_rows = [
            {"p_a": rr.p_a, "y_a": rr.y_a, "lower": rr.lower, "upper": rr.upper}
            for rr in dp1_replay.values()
            if OOF_LO <= rr.date <= OOF_HI
        ]
        dp1_val_interval_rows = [
            {"p_a": rr.p_a, "y_a": rr.y_a, "lower": rr.lower, "upper": rr.upper}
            for rr in dp1_replay.values()
            if VAL_LO <= rr.date <= VAL_HI
        ]
        coverage = {
            "oof_window": coverage_diagnostic(dp1_oof_interval_rows),
            "validation_window": coverage_diagnostic(dp1_val_interval_rows),
        }

        # ---- DP1 parameter/state stability (item 5) ----
        stability = {
            "end_of_oof_window": stability_summary(dp1_oof_snapshot),
            "end_of_validation_window": stability_summary(dp1_val_snapshot),
        }

        # ---- universe / exclusion funnel (item 1) ----
        universe = {
            "rows_loaded_raw": len(matches) + sum(load_excl.values()),
            "rows_after_loader_dedup": len(matches),
            "loader_exclusion_funnel": load_excl,
            "dev_window_races": len(dev_races),
            "validation_window_races": sum(1 for d, _r in races_dated if VAL_LO <= d <= VAL_HI),
            "per_family_orchestrator_exclusion_funnel": exclusion_by_label,
            "per_family_oof_scored": {k: len(v) for k, v in oof_by_label.items()},
            "universe_accounting_note": (
                "dev_window_races = orchestrator oof_scored + orchestrator_exclusions "
                "(enforced inside cross_fit itself, SPEC-031). validation_window_races are ALL "
                "scored by the hand-rolled prequential replay/update (no fit-failure refusal "
                "path exists in an online incremental rating update); no validation-window "
                "exclusions are expected or produced."
            ),
        }

        report = {
            "tour": tour,
            "generated_at": generated_at,
            "script_version": SCRIPT_VERSION,
            "boundary_date_exclusive": BOUNDARY.isoformat(),
            "oof_window": [OOF_LO.isoformat(), OOF_HI.isoformat()],
            "validation_window": [VAL_LO.isoformat(), VAL_HI.isoformat()],
            "universe": universe,
            "families": families_report,
            "comparator": {
                "f2_k_by_tour": FROZEN_F2_K_BY_TOUR,
                "f2_k_this_tour": FROZEN_F2_K_BY_TOUR[tour],
                "f2_affine_frozen_vintage_reference": FROZEN_F2_AFFINE_BY_TOUR[tour],
                "f2_affine_frozen_vintage_application": F2_FROZEN_VINTAGE_APPLICATION,
            },
            "calibration": calibration_block,
            "paired_chronology_aware_deltas": paired,
            "crossfit_vs_replay_reconciliation": reconciliation,
            "dp1_uncertainty_interval_coverage": coverage,
            "dp1_state_stability": stability,
        }

        out_path = OUTDIR / f"DP1G2_EVALUATION_REPORT_{tour}.json"
        text = json.dumps(report, indent=1, sort_keys=True, default=str)
        out_path.write_text(text)
        output_paths[out_path.name] = out_path
        manifest_body["tours"][tour] = {
            "rows_loaded_raw": universe["rows_loaded_raw"],
            "dev_window_races": universe["dev_window_races"],
            "validation_window_races": universe["validation_window_races"],
            "oof_scored_dp1": len(dp1_oof_rows),
            "validation_scored_dp1": len(dp1_val_rows),
            "reconciliation_verdict": reconciliation["verdict"],
        }
        print(
            f"[{tour}] dev={len(dev_races)} oof_dp1={len(dp1_oof_rows)} "
            f"val_dp1={len(dp1_val_rows)} recon={reconciliation['verdict']} "
            # RESULT-READ BARRIER (founder §4): no numerical result value on stdout —
            # results live only in the hashed artifact files, opened only after the
            # frozen continuation rule is applied.
            "results=WRITTEN_TO_ARTIFACT_ONLY",
            flush=True,
        )

    manifest_body["output_file_sha256"] = {name: sha256_file(p) for name, p in output_paths.items()}
    manifest_path = OUTDIR / "DP1G2_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest_body, indent=1, sort_keys=True, default=str))
    print(f"wrote manifest: {manifest_path}")


if __name__ == "__main__":
    main()
