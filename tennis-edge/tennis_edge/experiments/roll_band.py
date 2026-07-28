"""The Roll execution-cost band around the TE-0019 supported-only money number.

TE-0019's strict reading — supported fills only, +2.63% [+0.94%, +4.29%] on 24,886 bets —
still assumes the fill costs nothing to take: the bet is credited at the last-traded print
itself. DR-TENNIS-MICROSTRUCTURE-001's standard says a trace-only money number is quoted
with an execution-cost sensitivity band or it is not quoted, and the defensible
transaction-only estimator is Roll's spread from each market's own prints.

**Declared before any number was computed:**

- The spread is estimated per selection over the market's full pre-off print series
  (:func:`~tennis_edge.execution_cost.selection_spreads`). Spreads tighten toward the off,
  so the full series overstates the cost near the off — the conservative direction for a
  band.
- **The fired-bet set is fixed.** The firing decision was made at quoted odds; the band
  asks what those same bets return when taking them costs something. Re-filtering at
  haircut odds would quietly re-run the policy, which is a different experiment.
- Winning returns are recomputed at ``odds * exp(-f * spread)`` for f = 1/2 (the symmetric
  dealer-model cost of crossing) and f = 1 (the pessimistic bound). Losses stay -1: the
  stake is the stake.
- A side without a measured spread receives the **pooled median of measured fired-bet
  sides**, labelled, with coverage reported. Refusals are not zero-cost fills.
- **The verdict question: does the supported-only reading still clear zero at the
  half-Roll haircut?** The band runs from the full-Roll haircut to the uncosted number.

The baseline is re-derived in-process and must reproduce TE-0019's supported-only row
exactly (same seed, same rule, same table) before any banded row is printed. A band around
a number that no longer reproduces is a band around nothing.
"""
from __future__ import annotations

import json
import statistics
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from tennis_edge.betfair_archive import read_extract
from tennis_edge.exchange_link import DEFAULT_HORIZON_SECONDS
from tennis_edge.exchange_prices import ExchangePrice, read_prices
from tennis_edge.execution_cost import haircut_odds, selection_spreads
from tennis_edge.experiments.exchange_settlement import COMMISSION, Bet, report, settle
from tennis_edge.experiments.residual_edge import walk_forward
from tennis_edge.fill_evidence import FillSupport
from tennis_edge.residual_features import build_residual_features

SPREADS_KIND = "tennis-edge-roll-spreads-v1"

DATA_DIR = Path("/home/user/tennis_edge_data/betfair_historical")
EXTRACTS = ("match_odds.jsonl", "match_odds2.jsonl", "match_odds_tail.jsonl")
DEFAULT_SPREADS = DATA_DIR / "roll_spreads_v2.jsonl"
DEFAULT_PRICES = DATA_DIR / "exchange_prices_600s_v2.jsonl"

#: TE-0019's supported-only row. The band refuses to print unless it reproduces these.
BASELINE_BETS = 24_886


def build_spreads(out_path: Path | str = DEFAULT_SPREADS) -> None:
    """Scan the extracts once and cache per-selection spreads for every priced market.

    A market appearing in more than one extract (the archives overlap) keeps the version
    with the most observations — the fullest trace estimates the spread; the others are
    truncated copies of the same market.
    """
    wanted = {p.market_id for p in read_prices(DEFAULT_PRICES)}
    best: dict[str, dict[str, object]] = {}
    for name in EXTRACTS:
        scanned = 0
        for market in read_extract(DATA_DIR / name):
            scanned += 1
            if market.market_id not in wanted:
                continue
            count = len(market.observations)
            seen = best.get(market.market_id)
            if seen is not None and int(seen["observations"]) >= count:  # type: ignore[call-overload]
                continue
            spreads = selection_spreads(market)
            best[market.market_id] = {
                "observations": count,
                "spreads": {str(sid): value for sid, value in spreads.items()},
                "ltp": {
                    str(sid): (None if price is None else str(price))
                    for sid, price in (
                        (sid, market.ltp_at(
                            sid, seconds_before_off=DEFAULT_HORIZON_SECONDS))
                        for sid in spreads
                    )
                },
            }
        print(f"{name}: {scanned:,} markets scanned; "
              f"{len(best):,}/{len(wanted):,} priced markets covered", flush=True)

    target = Path(out_path)
    with target.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "kind": SPREADS_KIND,
            "horizon_seconds": DEFAULT_HORIZON_SECONDS,
            "prices": DEFAULT_PRICES.name,
            "extracts": list(EXTRACTS),
        }) + "\n")
        for market_id in sorted(best):
            row = dict(best[market_id])
            row["market_id"] = market_id
            handle.write(json.dumps(row) + "\n")
    print(f"wrote {len(best):,} markets to {target}", flush=True)


def read_spreads(path: Path | str = DEFAULT_SPREADS) -> dict[str, dict[str, object]]:
    target = Path(path)
    with target.open(encoding="utf-8") as handle:
        header = json.loads(handle.readline())
        if not isinstance(header, dict) or header.get("kind") != SPREADS_KIND:
            raise ValueError(f"{target} is not a {SPREADS_KIND} table")
        table: dict[str, dict[str, object]] = {}
        for line in handle:
            line = line.strip()
            if line:
                row = json.loads(line)
                table[str(row["market_id"])] = row
    return table


def side_spread(bet: Bet, price: ExchangePrice,
                entry: dict[str, object] | None) -> tuple[float | None, str]:
    """The Roll spread for the selection this bet backed, and how it was resolved.

    The spread table is keyed by Betfair selection id; the bet knows only the corpus side.
    The two meet through the horizon price: the selection whose T-600s LTP equals the
    side's table odds is that side's runner. Where both runners printed the same price the
    assignment is ambiguous and the LARGER spread is taken — a band errs toward cost.
    """
    if entry is None:
        return None, "no_market"
    ltp = entry["ltp"]
    spreads = entry["spreads"]
    assert isinstance(ltp, dict) and isinstance(spreads, dict)
    want = str(price.odds_a if bet.side == "a" else price.odds_b)
    matches = [sid for sid, value in ltp.items() if value == want]
    if not matches:
        # The spread table kept a different (fuller) copy of the market than the price
        # build saw, and its horizon price disagrees. Rare, counted, never guessed at.
        return None, "unmatched"
    if len(matches) == 1:
        value = spreads.get(matches[0])
        return (float(value) if value is not None else None), "matched"
    measured = [float(v) for v in (spreads.get(sid) for sid in matches)
                if v is not None]
    return (max(measured) if measured else None), "ambiguous"


def banded(bets: list[Bet], spreads_of: dict[int, float], *, fraction: float) -> list[Bet]:
    """The same bets with winning returns recomputed at haircut odds."""
    rate = float(COMMISSION)
    out: list[Bet] = []
    for index, bet in enumerate(bets):
        if not bet.won:
            out.append(bet)
            continue
        effective = haircut_odds(Decimal(str(bet.odds)), spreads_of[index],
                                 fraction=fraction)
        out.append(replace(bet, profit=(effective - 1.0) * (1.0 - rate)))
    return out


def main() -> None:
    spreads = read_spreads()
    prices = {(p.date, p.tour, p.player_a, p.player_b): p
              for p in read_prices(DEFAULT_PRICES)}
    by_market = {p.market_id: p for p in prices.values()}
    print(f"spread table: {len(spreads):,} markets; prices: {len(prices):,}", flush=True)

    rows = build_residual_features()
    names = sorted({n for r in rows for n in r.features})
    print("walk-forward:", flush=True)
    scored = walk_forward(rows, names)
    covered = [(r, p) for r, p in scored
               if (r.date, r.tour, r.player_a, r.player_b) in prices]

    model = settle(covered, prices, use_model=True)
    supported = [b for b in model if b.support is FillSupport.SUPPORTED]

    print("\nBASELINE REPRODUCTION — must equal TE-0019 before the band means anything")
    report("supported only, uncosted", supported)
    if len(supported) != BASELINE_BETS:
        raise SystemExit(
            f"baseline does not reproduce TE-0019 ({len(supported):,} bets vs "
            f"{BASELINE_BETS:,}); refusing to band a number that no longer exists")

    resolved = [side_spread(b, by_market[b.market_id], spreads.get(b.market_id))
                for b in supported]
    measured = [s for s, _how in resolved if s is not None]
    pooled_median = statistics.median(measured)
    counts: dict[str, int] = {}
    for spread, how in resolved:
        key = how if spread is not None else f"{how}_unmeasured"
        counts[key] = counts.get(key, 0) + 1

    print("\nSPREAD COVERAGE OVER THE SUPPORTED FIRED BETS")
    for key in sorted(counts):
        print(f"  {key:<24} {counts[key]:6,}  ({100 * counts[key] / len(supported):5.1f}%)")
    quartiles = statistics.quantiles(measured, n=4)
    print(f"  measured spreads: median {pooled_median:.4f}  "
          f"IQR [{quartiles[0]:.4f}, {quartiles[2]:.4f}]  "
          f"(relative, i.e. fraction of the price)")
    print("  unmeasured sides take the pooled median of measured fired-bet sides, "
          "labelled, never zero")

    spreads_of = {i: (s if s is not None else pooled_median)
                  for i, (s, _how) in enumerate(resolved)}

    print("\nTHE BAND — same bets, worse fills")
    report("supported only, half-Roll haircut", banded(supported, spreads_of,
                                                       fraction=0.5))
    report("supported only, full-Roll haircut", banded(supported, spreads_of,
                                                       fraction=1.0))

    print("\nREADING")
    print("  The declared question: does the supported-only reading still clear zero at")
    print("  the half-Roll haircut? The band runs from the full haircut to the uncosted")
    print("  number. All rows are hypothetical returns under the trade-through rule; the")
    print("  haircut prices the assumption that a print equals a free fill.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        build_spreads()
    else:
        main()
