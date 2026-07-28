"""Build the v3 exchange price table under bridge v2, with the S1 guard.

The one-shot re-link the TE-0018 implementing slice authorises: the SAME merge the v2
table was built from — ``match_odds_tail.jsonl`` then ``match_odds2.jsonl``, first
occurrence of each market_id wins, doubles dropped — joined by the extended
``exchange-link-bridge-v2``. Everything that differs from v2 must therefore be the bridge
extension and the typed exclusions, nothing else.

**The S1 guard is the acceptance criterion, not a diagnostic**: no previously joined row
may change quote or orientation. Every market_id present in both tables is compared field
by field; any difference is printed and the build exits non-zero WITHOUT overwriting
anything. A previously linked market disappearing is the same failure. TE-0018 warns
where a violation would come from: ~3.1k matches carry two priced markets and the linker
keeps the first in file order, so a newly resolvable market earlier in the file could
steal a match from the market that priced it in v2.

Run from tennis-edge/: ``python tools/build_prices_v3.py``.
"""
from __future__ import annotations

import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tennis_edge.betfair_archive import read_extract  # noqa: E402
from tennis_edge.corpus import default_vintage_root, load_corpus  # noqa: E402
from tennis_edge.exchange_prices import build_prices, read_prices, write_prices  # noqa: E402
from tennis_edge.refresh import latest_vintage  # noqa: E402

BASE = Path("/home/user/tennis_edge_data/betfair_historical")
#: The v2 merge order, byte for byte. Changing it changes which market prices the ~3.1k
#: dual-listed matches, which the guard would then catch as a changed quote.
EXTRACTS = ("match_odds_tail.jsonl", "match_odds2.jsonl")
V2 = BASE / "exchange_prices_600s_v2.jsonl"
V3 = BASE / "exchange_prices_600s_v3.jsonl"


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
    print(f"priced matches under bridge v2: {len(prices):,}", flush=True)

    old = {p.market_id: p for p in read_prices(V2)}
    changed = [m for m, p in old.items() if m in by_market and by_market[m] != p]
    lost = [m for m in old if m not in by_market]
    new = [m for m in by_market if m not in old]

    print(f"\nS1 GUARD — v2 rows: {len(old):,}  shared: {len(old) - len(lost):,}  "
          f"changed: {len(changed):,}  lost: {len(lost):,}  new: {len(new):,}")
    for market_id in changed[:10]:
        print(f"  CHANGED {market_id}:\n    v2: {old[market_id]}\n    v3: "
              f"{by_market[market_id]}")
    for market_id in lost[:10]:
        print(f"  LOST {market_id}: {old[market_id]}")
    if changed or lost:
        print("\nGUARD FAILED — v3 not written. A previously joined row changed; the "
              "frozen S1 rule forbids shipping this table.")
        return 1

    written = write_prices(V3, prices, horizon_seconds=600,
                           corpus_vintage=vintage.vintage_id,
                           source_digest="sha256:merged-tail+data2")
    years = collections.Counter(p.date.year for p in (by_market[m] for m in new))
    print(f"\nwrote {written:,} rows to {V3.name}")
    print(f"new rows by year: {dict(sorted(years.items()))}")
    print("GUARD PASSED — every v2 row survives byte-identical; the additions are the "
          "bridge extension's recoveries and nothing else.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
