"""Build the v4 exchange price table: v3's exact join, plus the S5 LTP ages.

Same merge, same bridge, same horizon as v3 — the ONLY difference is the v2 table kind
carrying ``ltp_age_a/b``. The guard therefore demands every v3 row reappear identical on
every v1 field; the ages are additive or the build refuses. Never an in-place edit: v3
stays exactly the bytes TE-0022's interim look was computed from.

Run from tennis-edge/: ``python tools/build_prices_v4.py``.
"""
from __future__ import annotations

import collections
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tennis_edge.betfair_archive import read_extract  # noqa: E402
from tennis_edge.corpus import default_vintage_root, load_corpus  # noqa: E402
from tennis_edge.exchange_prices import (  # noqa: E402
    build_prices,
    read_prices,
    row_band,
    write_prices,
)
from tennis_edge.refresh import latest_vintage  # noqa: E402

BASE = Path("/home/user/tennis_edge_data/betfair_historical")
EXTRACTS = ("match_odds_tail.jsonl", "match_odds2.jsonl")
V3 = BASE / "exchange_prices_600s_v3.jsonl"
V4 = BASE / "exchange_prices_600s_v4.jsonl"


def main() -> int:
    seen: set[str] = set()
    markets = []
    for name in EXTRACTS:
        for market in read_extract(BASE / name):
            if market.market_id in seen or any("/" in r.name for r in market.runners):
                continue
            seen.add(market.market_id)
            markets.append(market)
    print(f"merged singles markets: {len(markets):,}", flush=True)

    vintage = latest_vintage(default_vintage_root())
    assert vintage is not None
    matches, _stats = load_corpus(vintage.root)
    prices = build_prices(markets, matches, horizon_seconds=600)
    by_market = {p.market_id: p for p in prices}
    print(f"priced matches: {len(prices):,}", flush=True)

    old = {p.market_id: p for p in read_prices(V3)}
    changed = [m for m, p in old.items()
               if m not in by_market
               or replace(by_market[m], ltp_age_a=None, ltp_age_b=None) != p]
    if len(by_market) != len(old) or changed:
        print(f"GUARD FAILED — rows {len(by_market):,} vs {len(old):,}, "
              f"changed-or-missing {len(changed):,}; v4 not written.")
        for market_id in changed[:5]:
            print(f"  {market_id}: v3={old.get(market_id)} v4={by_market.get(market_id)}")
        return 1

    written = write_prices(V4, prices, horizon_seconds=600,
                           corpus_vintage=vintage.vintage_id,
                           source_digest="sha256:merged-tail+data2")
    bands = collections.Counter(row_band(p) for p in prices)
    ages = sorted(max(p.ltp_age_a, p.ltp_age_b) for p in prices
                  if p.ltp_age_a is not None and p.ltp_age_b is not None)
    print(f"\nwrote {written:,} rows to {V4.name}")
    print(f"band composition (older side): {dict(bands)}")
    print(f"older-side age: median {ages[len(ages) // 2]}s  "
          f"p90 {ages[int(0.9 * len(ages))]}s")
    print("GUARD PASSED — v4 is v3 plus ages, nothing else.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
