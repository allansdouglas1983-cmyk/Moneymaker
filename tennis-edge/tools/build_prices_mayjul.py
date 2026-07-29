"""Build the May-July 2026 exchange price table from the founder-supplied archive.

The v3/v4 pipeline verbatim — same doubles filter, same market_id dedup, same
build_prices join at 600s — over match_odds_mayjul.jsonl only. A NEW file for a NEW
window: the frozen v4 table is never touched, and TE-0034 excludes any market_id that
appears in it. Run from tennis-edge/: ``python tools/build_prices_mayjul.py``.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tennis_edge.betfair_archive import read_extract  # noqa: E402
from tennis_edge.corpus import default_vintage_root, load_corpus  # noqa: E402
from tennis_edge.exchange_prices import build_prices, write_prices  # noqa: E402
from tennis_edge.refresh import latest_vintage  # noqa: E402

BASE = Path("/home/user/tennis_edge_data/betfair_historical")
EXTRACT = BASE / "match_odds_mayjul.jsonl"
OUT = BASE / "exchange_prices_600s_mayjul.jsonl"
SOURCE_DIGEST = ("sha256:4fda22c975ab15e1c1ff64177e008458e98a761195e17d16e93b263b73d62107")


def main() -> int:
    seen: set[str] = set()
    markets = []
    for market in read_extract(EXTRACT):
        if market.market_id in seen or any("/" in r.name for r in market.runners):
            continue
        seen.add(market.market_id)
        markets.append(market)
    print(f"singles markets: {len(markets):,}", flush=True)

    vintage = latest_vintage(default_vintage_root())
    assert vintage is not None
    matches, _stats = load_corpus(vintage.root)
    prices = build_prices(markets, matches, horizon_seconds=600)
    written = write_prices(OUT, prices, horizon_seconds=600,
                           corpus_vintage=vintage.root.name,
                           source_digest=SOURCE_DIGEST)
    print(f"priced matches written: {written:,} -> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
