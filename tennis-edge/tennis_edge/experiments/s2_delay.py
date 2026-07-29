"""TE-0017 S2: intended-order CLV — what the picked price does after the pick.

CLV is near-deterministic given the pick, so ~20k picks resolve drifts an order of
magnitude smaller than money could. The bet list is frozen from T-600s state only; the
same markets' own print series then say what the picked side's price did by T-300 and
T-120. SPEC-095 discipline: signal/intended-order CLV only — realised-fill CLV is never
claimed for any bet, later prices never enter features or training, CLV is never a
training target.

**Declared before the run (TE-0017 §S2, binding):**

- Primary statistic: MEAN signed logit drift of the picked side per horizon, family 1 at
  the four-family bar (98.75%). Median is secondary. Controls: the market-probability
  control's picks and an always-back-A placebo on the same rows.
- **The selection-on-bounce null is named:** bets fire when the T-600 LTP is generous, so
  pure regression to the mid appears as adverse drift up to ~half the effective spread.
  Only drift IN EXCESS of the Roll band is steam evidence.
- Three-branch verdict, fixed in advance: (i) adverse drift in excess of the band → steam;
  the P1 headline interval is formally widened by the measured delay cost; (ii) drift
  adverse but within the band → band-consistent execution cost, nothing strengthens and
  nothing widens beyond the band; (iii) drift ≈ 0 → the SUPPORTED class gains force.
- Coverage discipline: a horizon counts only where the selection PRINTED in the window
  after T-600s — from the timestamped series, never `ltp_at` carry-forward. Uncovered
  rows are typed exclusions and the verdict is scoped per coverage class.
- Roll-refusal counts are reported alongside the band: refusals concentrate exactly where
  drift is largest, and that blindness is disclosed, not patched.
- (b) the paired per-day ROI difference of the identical bet list settled at the T-600s
  LTP vs the later LTP — both sides share the fill assumption, so the pair isolates
  delay cost.

Run ``build`` once to cache later-horizon prices from the extracts; then the measurement.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path
from typing import cast

from tennis_edge.betfair_archive import read_extract
from tennis_edge.exchange_prices import read_prices
from tennis_edge.experiments.exchange_settlement import Bet, settle
from tennis_edge.experiments.residual_edge import walk_forward
from tennis_edge.experiments.roll_band import read_spreads
from tennis_edge.fill_evidence import stratify
from tennis_edge.metrics import clustered_bootstrap
from tennis_edge.residual_features import build_residual_features

HORIZONS = (300, 120)
DELAY_KIND = "tennis-edge-delay-horizons-v1"
FAMILY_ALPHA = 0.0125

DATA_DIR = Path("/home/user/tennis_edge_data/betfair_historical")
EXTRACTS = ("match_odds_tail.jsonl", "match_odds2.jsonl")
PRICES = DATA_DIR / "exchange_prices_600s_v4.jsonl"
CACHE = DATA_DIR / "delay_horizons_v1.jsonl"


def build_cache() -> None:
    """One extract scan caching each priced market's later-horizon state.

    A horizon's price is recorded ONLY when the selection actually printed strictly after
    T-600s and on or before that horizon; otherwise the later LTP would be the same stale
    opinion carried forward and the drift would be manufactured zeros.
    """
    wanted = {p.market_id for p in read_prices(PRICES)}
    best: dict[str, dict] = {}
    for name in EXTRACTS:
        for market in read_extract(DATA_DIR / name):
            if market.market_id not in wanted:
                continue
            seen = best.get(market.market_id)
            if seen is not None and seen["observations"] >= len(market.observations):
                continue
            cutoff_600 = market.market_time_ms - 600 * 1000
            row: dict = {"observations": len(market.observations), "horizons": {}}
            for horizon in HORIZONS:
                cutoff = market.market_time_ms - horizon * 1000
                per_side: dict[str, dict] = {}
                for runner in market.runners:
                    printed = any(
                        cutoff_600 < o.publish_time_ms <= cutoff
                        for o in market.observations
                        if o.selection_id == runner.selection_id)
                    price = market.ltp_at(runner.selection_id,
                                          seconds_before_off=horizon)
                    per_side[str(runner.selection_id)] = {
                        "printed": printed,
                        "ltp": None if price is None else str(price),
                    }
                row["horizons"][str(horizon)] = per_side
            row["ltp600"] = {
                str(r.selection_id): (None if (p := market.ltp_at(
                    r.selection_id, seconds_before_off=600)) is None else str(p))
                for r in market.runners
            }
            best[market.market_id] = row
    with CACHE.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({"kind": DELAY_KIND, "horizons": list(HORIZONS)}) + "\n")
        for market_id in sorted(best):
            row = dict(best[market_id])
            row.pop("observations")
            row["market_id"] = market_id
            handle.write(json.dumps(row) + "\n")
    print(f"cached {len(best):,}/{len(wanted):,} priced markets -> {CACHE.name}",
          flush=True)


def read_cache() -> dict[str, dict]:
    with CACHE.open(encoding="utf-8") as handle:
        header = json.loads(handle.readline())
        assert header.get("kind") == DELAY_KIND
        return {row["market_id"]: row
                for line in handle if (row := json.loads(line.strip()))}


def _logit(p: float) -> float:
    q = min(max(p, 1e-12), 1 - 1e-12)
    return math.log(q / (1 - q))


def _side_probability(own: float, other: float) -> float:
    implied_own, implied_other = 1.0 / own, 1.0 / other
    return implied_own / (implied_own + implied_other)


def _paired(name: str, pairs: list[tuple[dt.date, float]], *, alpha: float) -> None:
    mean = math.fsum(v for _d, v in pairs) / len(pairs)
    lo, hi = clustered_bootstrap(
        pairs, statistic=lambda items: math.fsum(  # type: ignore[arg-type,misc]
            v for _d, v in items) / len(items),  # type: ignore[union-attr]
        cluster_of=lambda item: cast(tuple[dt.date, float], item)[0],
        alpha=alpha)
    level = 100 * (1 - alpha)
    verdict = "clears zero" if lo > 0 else ("below zero" if hi < 0 else "spans zero")
    print(f"  {name:<46} n={len(pairs):6,}  {mean:+.6f}  "
          f"CI{level:.2f}=[{lo:+.6f},{hi:+.6f}]  {verdict}")


def main() -> None:
    cache = read_cache()
    spreads = read_spreads()
    prices = {(p.date, p.tour, p.player_a, p.player_b): p for p in read_prices(PRICES)}
    by_market = {p.market_id: p for p in prices.values()}
    print(f"cache: {len(cache):,} markets;  prices: {len(prices):,}", flush=True)

    rows = build_residual_features()
    names = sorted({n for r in rows for n in r.features})
    scored = walk_forward(rows, names)
    covered = [(r, p) for r, p in scored
               if (r.date, r.tour, r.player_a, r.player_b) in prices]

    model = settle(covered, prices, use_model=True)
    control = settle(covered, prices, use_model=False)
    placebo = [Bet(date=r.date, profit=0.0, support=p.support_a,
                   stratum=stratify(p.prints_a), odds=float(p.odds_a),
                   market_id=p.market_id, side="a", won=p.won_a)
               for r, _mp in covered
               for p in (prices[(r.date, r.tour, r.player_a, r.player_b)],)]

    def market_roll(market_id: str) -> float | None:
        entry = spreads.get(market_id)
        if entry is None:
            return None
        measured = [float(v) for v in entry["spreads"].values() if v is not None]
        return max(measured) if measured else None

    for label, bets in (("model picks", model), ("control picks", control),
                        ("always-back-A placebo", placebo)):
        print(f"\n=== {label} ===")
        for horizon in HORIZONS:
            drifts: list[tuple[dt.date, float]] = []
            roi_pairs: list[tuple[dt.date, float]] = []
            excess = 0
            with_band = 0
            band_refused = 0
            uncovered = 0
            for bet in bets:
                entry = cache.get(bet.market_id)
                price = by_market.get(bet.market_id)
                if entry is None or price is None:
                    uncovered += 1
                    continue
                sides = entry["horizons"][str(horizon)]
                ltp600 = entry["ltp600"]
                ids = list(ltp600)
                own_id = None
                want = str(price.odds_a if bet.side == "a" else price.odds_b)
                matches = [sid for sid in ids if ltp600.get(sid) == want]
                if len(matches) != 1:
                    uncovered += 1
                    continue
                own_id = matches[0]
                other_id = next(s for s in ids if s != own_id)
                own = sides[own_id]
                other = sides[other_id]
                if not own["printed"] or own["ltp"] is None or other["ltp"] is None:
                    uncovered += 1
                    continue
                p600 = _side_probability(bet.odds, float(price.odds_b if bet.side == "a"
                                                         else price.odds_a))
                p_later = _side_probability(float(own["ltp"]), float(other["ltp"]))
                drift = _logit(p_later) - _logit(p600)
                drifts.append((bet.date, drift))

                roll = market_roll(bet.market_id)
                if roll is None:
                    band_refused += 1
                elif -drift > roll / 2.0:
                    excess += 1
                else:
                    with_band += 1

                if label != "always-back-A placebo":
                    gross_later = float(own["ltp"]) - 1.0
                    later_profit = gross_later * 0.98 if bet.won else -1.0
                    roi_pairs.append((bet.date, bet.profit - later_profit))

            print(f"-- T-600 -> T-{horizon}  (covered {len(drifts):,}, typed "
                  f"exclusions {uncovered:,})")
            if drifts:
                _paired("mean signed logit drift (PRIMARY)", drifts,
                        alpha=FAMILY_ALPHA)
                ordered = sorted(v for _d, v in drifts)
                print(f"  median drift (secondary): "
                      f"{ordered[len(ordered) // 2]:+.6f}")
                total = excess + with_band
                if total:
                    print(f"  adverse drift beyond half-Roll: {excess:,} of {total:,} "
                          f"({100 * excess / total:.1f}%)  band refusals alongside: "
                          f"{band_refused:,}")
            if roi_pairs:
                _paired("ROI(T-600 fill) - ROI(later fill), paired", roi_pairs,
                        alpha=0.05)

    print("\nTHREE-BRANCH VERDICT (fixed in advance) is read from the MODEL picks'")
    print("primary drift against the band shares above. SPEC-095: intended-order CLV")
    print("only; no realised-fill CLV exists for any of these rows.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        build_cache()
    else:
        main()
