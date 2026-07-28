"""TE-0017 S5 reading (1): does the model's gain over the exchange grow with anchor age?

A stale last-traded price is an old opinion. When the model "disagrees" with it, some of
the measured gain is the anchor being out of date rather than the model being right — the
phantom-edge signature TE-0014's silent stratum showed in money form. This reading asks
the question in log-loss, on identical rows, before any money is looked at.

**Declared before the run:**

- Rows banded by :func:`~tennis_edge.exchange_prices.row_band` — the OLDER of the two
  sides' LTP ages, in the pre-registered bands {<60s, 60-600s, >600s} (the <60s band is
  cadence-quantised; sub-minute staleness is unobservable in BASIC).
- Per-row gain: log-score of the exchange-anchored walk-forward model minus log-score of
  the bare exchange price — the same fits, offsets and MIN_TRAIN as the frozen
  exchange_anchor harness, byte for byte.
- **Primary endpoint, single and pre-registered: T = mean gain(>600s) − mean gain(<60s)**,
  day-clustered bootstrap at the four-family Bonferroni bar (98.75%). Positive T is the
  phantom-edge signature. Per-band CIs are descriptive; nothing else in this module is
  confirmatory.
- Binding amendments carried: the ltp-age × post-horizon-prints cross-tabulation is
  printed (the same thinness variable either side of the horizon — NEVER independent
  evidence), and band composition by odds band, tour and year (a stale-band effect must
  not be an odds-band effect in disguise).
- **No money is read here.** The staleness-gate rule is frozen from these log-loss strata
  first; reading (2) runs after that freeze, in a separate harness.
"""
from __future__ import annotations

import collections
import datetime as dt
import math
from decimal import Decimal
from pathlib import Path
from typing import cast

from tennis_edge.exchange_prices import STALENESS_BANDS, ExchangePrice, read_prices, row_band
from tennis_edge.experiments.exchange_anchor import (
    MIN_TRAIN,
    _log_score,
    _paired,
    _predict,
    _swap_offset,
    exchange_logit,
)
from tennis_edge.experiments.residual_edge import _sigmoid, fit
from tennis_edge.feature_cache import FeatureRow as Row
from tennis_edge.fill_evidence import stratify
from tennis_edge.metrics import clustered_bootstrap
from tennis_edge.residual_features import build_residual_features

PRICES = Path("/home/user/tennis_edge_data/betfair_historical/"
              "exchange_prices_600s_v4.jsonl")

#: The S5 trend statistic is one of the four confirmatory families TE-0017 §5 fixed for
#: this round, so it reads at the four-family Bonferroni bar: alpha 0.05/4 (CI 98.75%).
ADJUSTED_ALPHA = 0.0125


def main() -> None:
    rows = build_residual_features()
    names = sorted({n for r in rows for n in r.features})
    prices = {(p.date, p.tour, p.player_a, p.player_b): p for p in read_prices(PRICES)}
    print(f"prices: {len(prices):,} from {PRICES.name}")

    covered = [(r, prices[(r.date, r.tour, r.player_a, r.player_b)]) for r in rows
               if (r.date, r.tour, r.player_a, r.player_b) in prices]
    by_year: dict[int, list[tuple[Row, ExchangePrice]]] = collections.defaultdict(list)
    for row, price in covered:
        by_year[row.date.year].append((row, price))

    scored: list[tuple[Row, ExchangePrice, float, float]] = []
    train: list[tuple[Row, ExchangePrice]] = []
    for year in sorted(by_year):
        if len(train) >= MIN_TRAIN:
            exch_rows = [_swap_offset(r, exchange_logit(p)) for r, p in train]
            beta = fit(exch_rows, names)
            for row, price in by_year[year]:
                offset = exchange_logit(price)
                scored.append((row, price, _sigmoid(offset),
                               _predict(row, offset, beta)))
            print(f"  {year}: trained on {len(train):,}, scored {len(by_year[year]):,}",
                  flush=True)
        train.extend(by_year[year])
    print(f"scored out-of-sample: {len(scored):,}")

    banded: dict[str, list[tuple[dt.date, float]]] = {b: [] for b in STALENESS_BANDS}
    unbanded = 0
    for row, price, bare, model in scored:
        gain = _log_score(model, row.won) - _log_score(bare, row.won)
        band = row_band(price)
        if band is None:
            unbanded += 1
            continue
        banded[band].append((row.date, gain))

    print(f"\nPER-BAND GAIN, exchange+features over bare exchange (descriptive CIs)"
          f"{'' if not unbanded else f'  [unbanded rows: {unbanded}]'}")
    for band in STALENESS_BANDS:
        if banded[band]:
            _paired(f"band {band} (n={len(banded[band]):,})", banded[band])

    # The primary endpoint. Day-clustered over the union of the two extreme bands; the
    # statistic recomputes both band means inside each resample.
    extreme = ([(day, gain, STALENESS_BANDS[2]) for day, gain in banded[STALENESS_BANDS[2]]]
               + [(day, gain, STALENESS_BANDS[0]) for day, gain in banded[STALENESS_BANDS[0]]])

    def trend(items: object) -> float:
        triples = [cast(tuple[dt.date, float, str], t) for t in items]  # type: ignore[union-attr]
        stale = [g for _d, g, b in triples if b == STALENESS_BANDS[2]]
        fresh = [g for _d, g, b in triples if b == STALENESS_BANDS[0]]
        if not stale or not fresh:
            return 0.0
        return (math.fsum(stale) / len(stale)) - (math.fsum(fresh) / len(fresh))

    point = trend(extreme)
    lo, hi = clustered_bootstrap(
        extreme, statistic=trend,  # type: ignore[arg-type]
        cluster_of=lambda t: cast(tuple[dt.date, float, str], t)[0],  # type: ignore[union-attr]
        alpha=ADJUSTED_ALPHA)
    verdict = "clears zero" if lo > 0 else ("below zero" if hi < 0 else "spans zero")
    print(f"\nPRIMARY: T = mean gain(>600s) - mean gain(<60s) = {point:+.6f} nats  "
          f"CI{100 * (1 - ADJUSTED_ALPHA):.2f}=[{lo:+.6f},{hi:+.6f}]  {verdict}")
    print("  positive T is the phantom-edge signature: the apparent model gain grows")
    print("  with the age of the opinion it is beating.")

    print("\nLTP-AGE x POST-HORIZON-PRINTS CROSS-TAB (same thinness variable either side")
    print("of the horizon; NEVER cited as independent evidence)")
    cross: dict[tuple[str, str], int] = collections.Counter()
    for _row, price, _bare, _model in scored:
        band = row_band(price)
        if band is not None:
            cross[(band, stratify(min(price.prints_a, price.prints_b)).value)] += 1
    strata = sorted({s for _b, s in cross})
    print(f"  {'':<10}" + "".join(f"{s:>14}" for s in strata))
    for band in STALENESS_BANDS:
        print(f"  {band:<10}" + "".join(f"{cross.get((band, s), 0):>14,}"
                                        for s in strata))

    print("\nBAND COMPOSITION (a stale-band effect must not be an odds-band effect in "
          "disguise)")
    for band in STALENESS_BANDS:
        members = [(row, price) for row, price, _b, _m in scored
                   if row_band(price) == band]
        if not members:
            continue
        odds = collections.Counter(
            "fav<=1.5" if min(price.odds_a, price.odds_b) <= Decimal("1.5")
            else "fav<=2.5" if min(price.odds_a, price.odds_b) <= Decimal("2.5")
            else "fav>2.5"
            for _r, price in members)
        tours = collections.Counter(row.tour for row, _p in members)
        years = collections.Counter(row.date.year for row, _p in members)
        span = f"{min(years)}-{max(years)}"
        print(f"  {band:<10} odds {dict(odds)}  tours {dict(tours)}  years {span}")


if __name__ == "__main__":
    main()
