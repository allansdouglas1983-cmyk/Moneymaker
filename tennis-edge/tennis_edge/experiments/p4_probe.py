"""P4 — the coherence probe. One test, one stop rule, then done (TE-0017 §3 P4).

The precondition passed (5,473 probe-eligible events on 1,290 UTC days; see
p4_precondition.py, run 2026-07-29). This harness is the probe itself. Everything below is
declared BEFORE the first measurement run; nothing is re-sliced afterwards.

THE ONE FITTING DEFINITION (§2.3 principle: one definition, frozen, no contest)
-------------------------------------------------------------------------------
COMBINED_TOTAL was disqualified on inspection of the extract's *structure* (moving-line
market; per-selection lines were never captured), before any probability was computed.
The derivative complex is therefore SET_BETTING + SET_WINNER:

- Side A is the priced table's ``player_a``. Betfair runner names resolve to corpus names
  through the same day-scoped bridge the price link used (exchange_link._resolve_names);
  an unresolved or ambiguous attribution refuses the event (typed).
- T1 = SET_BETTING-implied P(A wins the match): every runner of the chosen SET_BETTING
  market must have printed strictly before the snapshot and within RECENCY_SECONDS of it;
  q_i proportional to 1/LTP_i, normalised; T1 sums q over A's scorelines. Among multiple
  SET_BETTING markets the one with most pre-snapshot prints wins (tie: lowest market_id).
- T2 = SET_WINNER-implied P(A wins set 1), same print/recency rules, two runners
  normalised. GOVERNED PLUMBING CORRECTION (first run, 2026-07-29, zero rows scored, no
  outcome observed): the archive stores duplicate copies of market members, and events
  list SET_WINNER in per-set pairs of which only the set-1 market trades pre-off. The
  original "exactly one SET_WINNER market" rule therefore refused every event on
  duplicate copies alone. Corrected rule: markets deduplicate by market_id (keeping the
  copy with the most observations, as the S2 cache does); the candidate set is the
  DISTINCT SET_WINNER markets passing the T-600 completeness/recency read; exactly one
  candidate is required. DECLARED ASSUMPTION (unchanged): that sole pre-off-priced
  SET_WINNER market is the set-1 market — its per-event siblings show zero pre-off
  prints. More than one distinct candidate still refuses as ambiguous.
- Format comes from the corpus (best_of; §2.1 — never from prices): 3 maps to
  BO3_AD_TB7_ALL_SETS, 5 to BO5_AD_TB10_FINAL_AT_6_6. DECLARED APPROXIMATION: WTA-slam
  deciders use a TB10 the BO3 mapping renders as TB7 — the difference lives only in the
  6-6-decider tail. The SET_BETTING runner scoreline set must agree with the corpus
  format (four scorelines for best-of-3, six for best-of-5) or the event refuses.
- The latent step: (p_a, p_b) must exist. Residual surfaces MW(p_a,p_b) = P(A wins match)
  and S1(p_a,p_b) = P(A wins set 1) come from the STAGE3 dual-generator-verified
  primitives (match_distribution, set_distribution), precomputed once per format on a
  fixed 121x121 grid over the tested domain (0.35, 0.90), both first-server assignments
  (§2.4: no 50/50 prior; feasibility under EITHER assignment suffices — every root
  reproduces T1, so p_coherence does not depend on the assignment). The event is
  COHERENT iff the MW = T1 level curve — traced at the 121 grid abscissae by bisection
  in the opponent coordinate on the bilinear interpolant (MW is monotone in each
  argument) — carries a point where S1 - T2 changes sign or |S1 - T2| < TOL = 0.002;
  otherwise the complex admits no serve model and the event refuses
  (INCOHERENT_COMPLEX). p_coherence = T1 exactly (the fit is exact on the match-win
  target at convergence); the solve contributes the screen.
- gap = logit(T1) - logit(p_MO), p_MO from the priced v4 odds (T-600, LTP), normalised
  across the two sides. Probabilities clipped to (1e-6, 1-1e-6) before logit.

THE TWO PRE-REGISTERED QUESTIONS — the P4 screening round holds exactly these two, so
each is judged at a Bonferroni-adjusted 97.5% CI (alpha 0.05/2), day-clustered bootstrap
(seed 20260725, 2000 draws), clusters = UTC market days.

(A) Does the gap add out-of-sample log-score value for the final outcome conditional on
    contemporaneous Match Odds? Expanding-year walk-forward from the second present year:
    base  y ~ sigmoid(b0 + b1*logit(p_MO)),
    aug   y ~ sigmoid(b0 + b1*logit(p_MO) + b2*gap),
    both fitted by deterministic Newton-IRLS on training years only. The statistic is the
    mean paired per-row log-loss difference (base - aug) on scored rows. PASS iff the
    97.5% CI clears zero from above.

(B) Does the gap predict short-horizon derivative convergence toward Match Odds? On (A)'s
    scored rows with a complete SET_BETTING re-read at T-120 (same completeness/recency
    rules): conv = logit(T1@T-120) - logit(T1@T-600), regressed on
    x = logit(p_MO@T-600) - logit(T1@T-600) (= -gap). B SUCCEEDS iff the OLS slope's
    97.5% day-clustered CI clears zero from above (derivatives close toward the match
    market — the stale-quote signature).

THE STOP RULE, verbatim from the registration: if (A) fails to clear, the layer is dead.
If (B) succeeds while (A) fails, the layer is dead — the gap was staleness, not
information. The negative is recorded (TE-0030), the test is never re-sliced, and the
solver remains unused. Surviving both earns a follow-up REGISTRATION only, and
NO_GO_UNPROVEN_INFORMATION_ORIGIN stays closed regardless of this probe's outcome.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from collections import defaultdict
from pathlib import Path

from tennis_edge.betfair_archive import read_extract
from tennis_edge.corpus import load_corpus
from tennis_edge.exchange_link import _resolve_names
from tennis_edge.exchange_prices import read_prices
from tennis_edge.metrics import clustered_bootstrap

from sport_tennis.coherence.formats import MatchFormat, format_spec
from sport_tennis.coherence.match import match_distribution
from sport_tennis.coherence.scoring import set_distribution

DATA_DIR = Path("/home/user/tennis_edge_data/betfair_historical")
PRICES = DATA_DIR / "exchange_prices_600s_v4.jsonl"
MO_EXTRACT = DATA_DIR / "match_odds_tail.jsonl"
DERIVATIVES = DATA_DIR / "derivatives_tail.jsonl"
GRID_CACHE = DATA_DIR / "p4_surfaces_v1.json"

SNAPSHOT = 600
LATER = 120
RECENCY_SECONDS = 3600
DOMAIN = (0.35, 0.90)
GRID_N = 121
TOL = 0.002
CLIP = 1e-6
ALPHA = 0.05 / 2  # two questions in the P4 screening round

BO3_SCORES = {"2-0", "2-1", "0-2", "1-2"}
BO5_SCORES = {"3-0", "3-1", "3-2", "0-3", "1-3", "2-3"}
FMT_BY_BEST_OF = {3: MatchFormat.BO3_AD_TB7_ALL_SETS,
                  5: MatchFormat.BO5_AD_TB10_FINAL_AT_6_6}


def _logit(p: float) -> float:
    p = min(max(p, CLIP), 1.0 - CLIP)
    return math.log(p / (1.0 - p))


# ---------------------------------------------------------------- residual surfaces

def _surfaces(fmt: MatchFormat) -> dict[str, list[list[float]]]:
    """MW and S1 on the grid for the A-serves-first assignment. The B-serves-first values
    follow by symmetry at lookup time: MW_B(pa,pb) = 1 - MW_A(pb,pa) applied to the
    opponent-first solve, i.e. evaluate the same surfaces at transposed coordinates."""
    spec = format_spec(fmt)
    axis = [DOMAIN[0] + (DOMAIN[1] - DOMAIN[0]) * i / (GRID_N - 1) for i in range(GRID_N)]
    mw = [[0.0] * GRID_N for _ in range(GRID_N)]
    s1 = [[0.0] * GRID_N for _ in range(GRID_N)]
    for i, pa in enumerate(axis):
        for j, pb in enumerate(axis):
            dist = match_distribution(pa, pb, fmt, a_serves_first_match=True)
            mw[i][j] = dist.match_win_a
            s1[i][j] = set_distribution(pa, pb, spec, is_final_set=False).first_server_wins
    return {"axis": axis, "mw": mw, "s1": s1}


def load_surfaces() -> dict[str, dict[str, list[list[float]]]]:
    if GRID_CACHE.exists():
        cached = json.loads(GRID_CACHE.read_text())
        if cached.get("domain") == list(DOMAIN) and cached.get("grid_n") == GRID_N:
            return cached["surfaces"]
    print("precomputing residual surfaces (two formats, 121x121)...", flush=True)
    surfaces = {fmt.value: _surfaces(fmt) for fmt in FMT_BY_BEST_OF.values()}
    GRID_CACHE.write_text(json.dumps(
        {"domain": list(DOMAIN), "grid_n": GRID_N, "surfaces": surfaces}))
    return surfaces


def _interp(grid: list[list[float]], x: float, y: float) -> float:
    """Bilinear interpolation on the unit-indexed grid; x, y in [0, GRID_N-1]."""
    i0 = min(int(x), GRID_N - 2)
    j0 = min(int(y), GRID_N - 2)
    fx, fy = x - i0, y - j0
    return (grid[i0][j0] * (1 - fx) * (1 - fy) + grid[i0 + 1][j0] * fx * (1 - fy)
            + grid[i0][j0 + 1] * (1 - fx) * fy + grid[i0 + 1][j0 + 1] * fx * fy)


def coherent(surf: dict[str, list[list[float]]], t1: float, t2: float) -> bool:
    """Feasibility along the MW level curve, both first-server assignments.

    A-first: does the curve {MW(pa,pb) = t1} carry a point with S1 = t2? MW is monotone
    increasing in pa and decreasing in pb, so within each grid column (fixed pa index x)
    the curve's pb is found by bisection on the bilinear interpolant. B-first: by the
    mirror identities MW_Bfirst(pa,pb) = 1 - MW_Afirst(pb,pa) and likewise for S1,
    feasibility under B-first equals A-first feasibility of the complemented targets
    (1-t1, 1-t2). Coherent when S1 - t2 changes sign along the curve or comes within
    TOL of zero.
    """
    mw, s1 = surf["mw"], surf["s1"]
    for ta, tb in ((t1, t2), (1.0 - t1, 1.0 - t2)):
        prev_sign = 0
        for i in range(GRID_N):
            x = float(min(i, GRID_N - 1 - 1e-9))
            lo_v = _interp(mw, x, GRID_N - 1 - 1e-9)   # highest pb -> lowest MW
            hi_v = _interp(mw, x, 0.0)                 # lowest pb  -> highest MW
            if not (lo_v <= ta <= hi_v):
                prev_sign = 0
                continue
            lo, hi = 0.0, GRID_N - 1 - 1e-9            # y in grid units; MW decreasing in y
            for _ in range(40):
                mid = (lo + hi) / 2.0
                if _interp(mw, x, mid) > ta:
                    lo = mid
                else:
                    hi = mid
            y = (lo + hi) / 2.0
            resid = _interp(s1, x, y) - tb
            if abs(resid) < TOL:
                return True
            sign = 1 if resid > 0 else -1
            if prev_sign and sign != prev_sign:
                return True
            prev_sign = sign
    return False


# ---------------------------------------------------------------- market reads

def _last_ltp(prints: list[tuple[int, float]], cutoff_ms: int) -> tuple[int, float] | None:
    """Latest (time, price) strictly before cutoff, or None."""
    best = None
    for ts, price in prints:
        if ts < cutoff_ms and (best is None or ts > best[0]):
            best = (ts, price)
    return best


def _implied(runner_prints: dict[str, list[tuple[int, float]]], cutoff_ms: int,
             ) -> dict[str, float] | None:
    """Normalised 1/LTP across ALL runners; None unless every runner printed before the
    cutoff and within RECENCY_SECONDS of it."""
    raw: dict[str, float] = {}
    for name, prints in runner_prints.items():
        last = _last_ltp(prints, cutoff_ms)
        if last is None or last[0] < cutoff_ms - RECENCY_SECONDS * 1000:
            return None
        if last[1] <= 1.0:
            return None
        raw[name] = 1.0 / last[1]
    total = sum(raw.values())
    if total <= 0:
        return None
    return {name: v / total for name, v in raw.items()}


# ---------------------------------------------------------------- main

def main() -> None:  # noqa: PLR0915 — one registered procedure, linear on purpose
    priced = {p.market_id: p for p in read_prices(PRICES)}
    matches, _stats = load_corpus()
    by_pair_day: dict[tuple[str, str, str], object] = {}
    for m in matches:
        by_pair_day[(m.match_date.isoformat(), m.player_a, m.player_b)] = m

    # Match Odds side attribution via the governed bridge.
    mo_markets = [m for m in read_extract(MO_EXTRACT) if m.market_id in priced]
    resolved = _resolve_names(mo_markets, matches)
    print(f"MO markets in priced table: {len(mo_markets):,}")

    events: dict[str, dict] = {}
    excl = defaultdict(int)
    for market in mo_markets:
        active = [r for r in market.runners if r.status.upper() == "ACTIVE"]
        if len(active) != 2:
            excl["MO_NOT_TWO_ACTIVE"] += 1
            continue
        day = dt.datetime.fromtimestamp(
            market.market_time_ms / 1000, tz=dt.timezone.utc).date()
        names = {r.name: resolved.get((day, r.name)) for r in active}
        row = priced[market.market_id]
        a_names = [bf for bf, corp in names.items() if corp == row.player_a]
        b_names = [bf for bf, corp in names.items() if corp == row.player_b]
        if len(a_names) != 1 or len(b_names) != 1:
            excl["SIDE_ATTRIBUTION_FAILED"] += 1
            continue
        corpus_match = by_pair_day.get((row.date.isoformat(), row.player_a, row.player_b))
        if corpus_match is None or corpus_match.best_of not in FMT_BY_BEST_OF:
            excl["NO_CORPUS_FORMAT"] += 1
            continue
        events[market.event_id] = {
            "market_id": market.market_id, "row": row, "bf_a": a_names[0],
            "off_ms": market.market_time_ms, "best_of": corpus_match.best_of,
            "day": day.isoformat(),
        }
    print(f"events with attributed sides and formats: {len(events):,}")

    # Derivative complexes for those events. The archive stores duplicate copies of
    # market members: deduplicate by market_id, keeping the copy with most observations.
    by_market: dict[str, dict[str, dict]] = defaultdict(dict)
    with DERIVATIVES.open(encoding="utf-8") as handle:
        handle.readline()
        for line in handle:
            drow = json.loads(line)
            if drow["market_type"] not in ("SET_BETTING", "SET_WINNER"):
                continue
            event = str(drow.get("event_id"))
            if event not in events:
                continue
            seen = by_market[event].get(drow["market_id"])
            if seen is not None and seen["n_obs"] >= len(drow["ltp"]):
                continue
            prints: dict[int, list[tuple[int, float]]] = defaultdict(list)
            for ts, sel, price in drow["ltp"]:
                prints[sel].append((ts, float(price)))
            by_market[event][drow["market_id"]] = {
                "market_id": drow["market_id"],
                "market_type": drow["market_type"],
                "n_obs": len(drow["ltp"]),
                "runners": {r["id"]: r["name"] for r in drow["runners"]},
                "prints": prints,
            }
    complexes: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for event, markets_of in by_market.items():
        for mkt in markets_of.values():
            complexes[event][mkt["market_type"]].append(mkt)

    rows = []
    for event, info in events.items():
        cx = complexes.get(event)
        if not cx or "SET_BETTING" not in cx:
            excl["NO_SET_BETTING"] += 1
            continue
        if "SET_WINNER" not in cx:
            excl["NO_SET_WINNER"] += 1
            continue
        cutoff = info["off_ms"] - SNAPSHOT * 1000

        # Candidate = distinct SET_WINNER market passing the T-600 completeness read.
        sw_candidates = [
            m for m in cx["SET_WINNER"]
            if len(m["runners"]) == 2
            and _implied({str(sel): m["prints"].get(sel, []) for sel in m["runners"]},
                         cutoff) is not None
        ]
        if not sw_candidates:
            excl["SET_WINNER_INCOMPLETE"] += 1
            continue
        if len(sw_candidates) != 1:
            excl["AMBIGUOUS_SET_WINNER"] += 1
            continue

        # SET_BETTING selection: most pre-snapshot prints, tie -> lowest market_id.
        def _n_pre(mkt: dict) -> int:
            return sum(1 for p in mkt["prints"].values() for ts, _ in p if ts < cutoff)
        sb = sorted(cx["SET_BETTING"], key=lambda m: (-_n_pre(m), m["market_id"]))[0]

        # Scoreline shape must agree with the corpus format.
        parsed = {}
        ok = True
        for sel, name in sb["runners"].items():
            part = name.rsplit(" ", 1)
            if len(part) != 2:
                ok = False
                break
            parsed[sel] = (part[0], part[1])
        scores = {s for _, s in parsed.values()} if ok else set()
        expected = BO3_SCORES if info["best_of"] == 3 else BO5_SCORES
        if not ok or scores != expected:
            excl["SET_BETTING_SHAPE"] += 1
            continue

        sb_named = {sel: parsed[sel] for sel in sb["runners"]}
        q = _implied({str(sel): sb["prints"].get(sel, []) for sel in sb["runners"]}, cutoff)
        if q is None:
            excl["SET_BETTING_INCOMPLETE"] += 1
            continue
        bf_a = info["bf_a"]
        a_sels = [sel for sel, (nm, _s) in sb_named.items() if nm == bf_a]
        if len(a_sels) != len(expected) // 2:
            excl["SET_BETTING_NAME_MISMATCH"] += 1
            continue
        t1 = sum(q[str(sel)] for sel in a_sels)

        sw = sw_candidates[0]
        if bf_a not in sw["runners"].values():
            excl["SET_WINNER_NAME_MISMATCH"] += 1
            continue
        p = _implied({str(sel): sw["prints"].get(sel, []) for sel in sw["runners"]}, cutoff)
        if p is None:  # unreachable by construction of the candidate set
            excl["SET_WINNER_INCOMPLETE"] += 1
            continue
        t2 = sum(v for sel, v in ((s, p[str(s)]) for s in sw["runners"])
                 if sw["runners"][sel] == bf_a)

        row = info["row"]
        inv_a = 1.0 / float(row.odds_a)
        inv_b = 1.0 / float(row.odds_b)
        p_mo = inv_a / (inv_a + inv_b)

        # T-120 re-read for question (B) BEFORE the screen so its coverage is a data
        # fact, not a screen artifact; only screened rows enter (B) regardless.
        cutoff_late = info["off_ms"] - LATER * 1000
        q_late = _implied({str(sel): sb["prints"].get(sel, []) for sel in sb["runners"]},
                          cutoff_late)
        t1_late = sum(q_late[str(sel)] for sel in a_sels) if q_late is not None else None

        rows.append({
            "event": event, "day": info["day"], "year": info["day"][:4],
            "fmt": FMT_BY_BEST_OF[info["best_of"]].value,
            "t1": t1, "t2": t2, "p_mo": p_mo, "y": 1.0 if row.won_a else 0.0,
            "t1_late": t1_late,
        })

    print(f"\nrows with a complete derivative complex: {len(rows):,}")
    for reason in sorted(excl):
        print(f"  excluded {reason:<28} {excl[reason]:>7,}")

    surfaces = load_surfaces()
    screened = []
    incoherent = 0
    for r in rows:
        if coherent(surfaces[r["fmt"]], r["t1"], r["t2"]):
            screened.append(r)
        else:
            incoherent += 1
    print(f"coherence screen: {len(screened):,} kept, {incoherent:,} INCOHERENT_COMPLEX "
          f"(tol {TOL})")
    for r in screened:
        r["gap"] = _logit(r["t1"]) - _logit(r["p_mo"])
        r["mo_logit"] = _logit(r["p_mo"])

    # ---------------- question (A)
    years = sorted({r["year"] for r in screened})
    scored = []
    for year in years[1:]:
        train = [r for r in screened if r["year"] < year]
        test = [r for r in screened if r["year"] == year]
        if len(train) < 200 or not test:
            continue
        base = _fit_logistic(train, use_gap=False)
        aug = _fit_logistic(train, use_gap=True)
        for r in test:
            lb = _predict(base, r, use_gap=False)
            la = _predict(aug, r, use_gap=True)
            scored.append({**r, "d": _log_loss(lb, r["y"]) - _log_loss(la, r["y"])})
        print(f"  {year}: trained {len(train):,}, scored {len(test):,}")
    print(f"scored out-of-sample: {len(scored):,}")

    if scored:
        mean_d = sum(r["d"] for r in scored) / len(scored)
        lo, hi = clustered_bootstrap(
            scored, statistic=lambda xs: sum(r["d"] for r in xs) / len(xs),
            cluster_of=lambda r: r["day"], alpha=ALPHA)
        a_pass = lo > 0
        print(f"\n(A) gap value conditional on MO   n={len(scored):,}  "
              f"{mean_d:+.6f} nats  CI97.50=[{lo:+.6f},{hi:+.6f}]  "
              f"{'clears zero' if a_pass else 'FAILS to clear'}")
    else:
        a_pass = False
        print("\n(A) no scored rows — fails by construction")

    # ---------------- question (B)
    brows = [r for r in scored if r["t1_late"] is not None]
    if brows:
        def _slope(xs) -> float:
            xv = [_logit(r["p_mo"]) - _logit(r["t1"]) for r in xs]
            yv = [_logit(r["t1_late"]) - _logit(r["t1"]) for r in xs]
            mx = sum(xv) / len(xv)
            my = sum(yv) / len(yv)
            sxx = sum((x - mx) ** 2 for x in xv)
            if sxx == 0:
                return 0.0
            return sum((x - mx) * (y - my) for x, y in zip(xv, yv)) / sxx
        slope = _slope(brows)
        blo, bhi = clustered_bootstrap(
            brows, statistic=_slope, cluster_of=lambda r: r["day"], alpha=ALPHA)
        b_pass = blo > 0
        print(f"(B) convergence toward MO         n={len(brows):,}  slope {slope:+.4f}  "
              f"CI97.50=[{blo:+.4f},{bhi:+.4f}]  "
              f"{'SUCCEEDS' if b_pass else 'does not clear'}")
    else:
        b_pass = False
        print("(B) no rows with a T-120 re-read")

    print("\nSTOP RULE (fixed in advance):")
    if a_pass and not b_pass:
        print("  (A) clears and (B) does not: the probe SURVIVES. This earns a follow-up")
        print("  REGISTRATION only — no deployment; NO_GO_UNPROVEN_INFORMATION_ORIGIN")
        print("  stays closed.")
    elif a_pass and b_pass:
        print("  (A) clears but (B) also succeeds: the gap carries value AND behaves like")
        print("  staleness. The registered rule kills only B-succeeds-WHILE-A-FAILS; this")
        print("  outcome survives the screen but the staleness mechanism is recorded and")
        print("  any follow-up registration must separate the two before anything else.")
    elif b_pass:
        print("  (B) succeeds while (A) fails: the layer is DEAD — the gap was stale")
        print("  derivative quotes catching up, not information. Never re-sliced.")
    else:
        print("  (A) fails to clear: the layer is DEAD. Never re-sliced.")


def _fit_logistic(rows, *, use_gap: bool) -> list[float]:
    """Deterministic Newton-IRLS, 25 iterations, ridge 1e-9."""
    k = 3 if use_gap else 2
    beta = [0.0] * k
    for _ in range(25):
        g = [0.0] * k
        h = [[1e-9 if i == j else 0.0 for j in range(k)] for i in range(k)]
        for r in rows:
            x = [1.0, r["mo_logit"]] + ([r["gap"]] if use_gap else [])
            z = sum(b * v for b, v in zip(beta, x))
            mu = 1.0 / (1.0 + math.exp(-max(min(z, 35.0), -35.0)))
            w = mu * (1.0 - mu)
            e = r["y"] - mu
            for i in range(k):
                g[i] += e * x[i]
                for j in range(k):
                    h[i][j] += w * x[i] * x[j]
        step = _solve(h, g)
        beta = [b + s for b, s in zip(beta, step)]
        if max(abs(s) for s in step) < 1e-10:
            break
    return beta


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        m[col], m[piv] = m[piv], m[col]
        d = m[col][col]
        for r in range(n):
            if r != col and m[r][col] != 0.0:
                f = m[r][col] / d
                for c in range(col, n + 1):
                    m[r][c] -= f * m[col][c]
    return [m[i][n] / m[i][i] for i in range(n)]


def _predict(beta: list[float], r: dict, *, use_gap: bool) -> float:
    x = [1.0, r["mo_logit"]] + ([r["gap"]] if use_gap else [])
    z = sum(b * v for b, v in zip(beta, x))
    return 1.0 / (1.0 + math.exp(-max(min(z, 35.0), -35.0)))


def _log_loss(p: float, y: float) -> float:
    p = min(max(p, CLIP), 1.0 - CLIP)
    return -(y * math.log(p) + (1.0 - y) * math.log(1.0 - p))


if __name__ == "__main__":
    main()
