"""Is the exchange price a better anchor than the bookmaker's closing price?

The residual model's whole design is "the market is nearly right; fit the corrections". The
market it has been anchored to was the de-vigged Bet365 closing price — not by choice but by
coverage, because that was the only price spanning the corpus. The de-vig itself is an
assumption (a power-law share of the overround), and the anchor is a bookmaker's opinion
with its margin removed, not a price anyone transacts at.

The archive changes what is available. For 27,209 matches there is now an exchange price at
T-600s: no margin to remove (two last-traded prices are normalised, not de-vigged), and the
number a bet would actually be struck against. If the exchange price is sharper, anchoring
to it should beat anchoring to Bet365 **on the same matches with the same features** — and
if it is not, that is worth knowing before any re-anchoring is shipped.

**The comparison is paired or it is nothing.** Everything is restricted to the covered
matches, the walk-forward split is identical, the features are identical; the ONE difference
is the offset the corrections are added to. Four models:

    b365 alone        the de-vigged closing price, no features
    exchange alone    the normalised T-600s exchange price, no features
    b365 + features   the deployed architecture, refit on the covered rows
    exchange + features

``b365 alone`` versus ``exchange alone`` asks which anchor is sharper. The feature rows ask
whether the corrections still add anything on top of the sharper one — the exchange may
already contain what the features know, in which case their gain shrinks and honesty
requires reporting that too.

**An asymmetry stated rather than hidden.** The deployed model trains on ~96,000 rows; both
refits here train only on covered rows inside the walk-forward, a fraction of that. So this
experiment measures the *anchor*, holding data constant — it does not measure the deployed
model, which has seen far more. Per-year training sizes are printed so nobody mistakes one
for the other.

Timing note: the exchange price is T-600s, the Bet365 price is a closing price captured
later. The exchange anchor therefore runs at an information *disadvantage* — if it wins
anyway, the result is conservative, and if it loses, staleness is one candidate reason and
is said so.
"""
from __future__ import annotations

import collections
import datetime as dt
import math
from decimal import Decimal
from pathlib import Path
from typing import Sequence, cast

from tennis_edge.exchange import COMMISSION as _EXCH_COMMISSION  # noqa: F401 (doc link)
from tennis_edge.exchange_prices import ExchangePrice, read_prices
from tennis_edge.experiments.residual_edge import _sigmoid, fit
from tennis_edge.feature_cache import FeatureRow as Row
from tennis_edge.metrics import clustered_bootstrap
from tennis_edge.residual_features import build_residual_features

BOOTSTRAP_DRAWS = 2000

#: The smallest training set a fit is attempted on. The covered corpus is a quarter the
#: size of the full one, so the full harness's 5,000 floor would push the first scored year
#: to 2018 and discard three seasons; 3,000 keeps 2017 scoreable. Chosen before any result
#: was seen, and the per-year sizes are printed either way.
MIN_TRAIN = 3000

DEFAULT_PRICES = ("/home/user/tennis_edge_data/betfair_historical/"
                  "exchange_prices_600s.jsonl")


def _logit(p: float) -> float:
    q = min(max(p, 1e-12), 1 - 1e-12)
    return math.log(q / (1 - q))


def exchange_logit(price: ExchangePrice) -> float:
    """The normalised two-sided exchange probability for player A, as a logit.

    Two last-traded prices are separate trades at separate moments; their implied
    probabilities can sum above or below one, and both states are normal. Normalising is
    not de-vigging — there is no margin to remove — it is making a probability out of two
    marginals.
    """
    implied_a = 1.0 / float(price.odds_a)
    implied_b = 1.0 / float(price.odds_b)
    return _logit(implied_a / (implied_a + implied_b))


def _predict(row: Row, offset: float, beta: dict[str, float]) -> float:
    return _sigmoid(offset + math.fsum(
        b * row.features[n] for n, b in beta.items() if n in row.features))


def _log_score(p: float, won: int) -> float:
    q = min(max(p, 1e-12), 1 - 1e-12)
    return math.log(q if won else 1.0 - q)


def _mean_diff(rows: Sequence[object]) -> float:
    pairs = [cast(tuple[dt.date, float], r) for r in rows]
    return math.fsum(d for _day, d in pairs) / len(pairs)


def _day_of(row: object) -> dt.date:
    return cast(tuple[dt.date, float], row)[0]


def _paired(name: str, gains: list[tuple[dt.date, float]]) -> None:
    mean = math.fsum(g for _d, g in gains) / len(gains)
    lo, hi = clustered_bootstrap(gains, statistic=_mean_diff, cluster_of=_day_of,
                                 draws=BOOTSTRAP_DRAWS)
    verdict = "clears zero" if lo > 0 else ("below zero" if hi < 0 else "spans zero")
    print(f"  {name:<44} {mean:+.6f} nats  CI95=[{lo:+.6f},{hi:+.6f}]  {verdict}")


def _swap_offset(row: Row, offset: float) -> Row:
    """A row with the exchange logit standing where the market logit stood.

    The fit and the predictor read ``row.market_logit`` as the unpenalised offset; giving
    them a row whose offset is the exchange logit re-anchors both without forking either
    function — the same code fits both models, so the comparison cannot drift.
    """
    from dataclasses import replace
    return replace(row, market_logit=offset)


def main() -> None:
    rows = build_residual_features()
    names = sorted({n for r in rows for n in r.features})

    prices = {(p.date, p.tour, p.player_a, p.player_b): p
              for p in read_prices(Path(DEFAULT_PRICES))}
    covered = [(r, prices[(r.date, r.tour, r.player_a, r.player_b)]) for r in rows
               if (r.date, r.tour, r.player_a, r.player_b) in prices]
    print(f"covered matches: {len(covered):,} of {len(rows):,} corpus rows")

    by_year: dict[int, list[tuple[Row, ExchangePrice]]] = collections.defaultdict(list)
    for row, price in covered:
        by_year[row.date.year].append((row, price))
    years = sorted(by_year)
    print("per-year coverage: " + ", ".join(f"{y}:{len(by_year[y]):,}" for y in years))

    # The deployment comparison needs the b365 model at its REAL training size: every
    # corpus row before the scored year, not merely the covered ones. The anchor rows hold
    # data constant to isolate the anchor; this row asks the question deployment actually
    # faces — does the re-anchored fit on a quarter of the data beat the deployed fit on
    # all of it?
    full_by_year: dict[int, list[Row]] = collections.defaultdict(list)
    for r in rows:
        full_by_year[r.date.year].append(r)

    scored: list[tuple[Row, tuple[float, float, float, float, float]]] = []
    train: list[tuple[Row, ExchangePrice]] = []
    for year in years:
        if len(train) >= MIN_TRAIN:
            b365_rows = [r for r, _p in train]
            exch_rows = [_swap_offset(r, exchange_logit(p)) for r, p in train]
            beta_b365 = fit(b365_rows, names)
            beta_exch = fit(exch_rows, names)
            full_train = [r for y, block in full_by_year.items() if y < year
                          for r in block]
            beta_full = fit(full_train, names)
            print(f"  {year}: full-corpus training rows for the deployment row: "
                  f"{len(full_train):,}", flush=True)
            for row, price in by_year[year]:
                off_exch = exchange_logit(price)
                scored.append((row, (
                    _sigmoid(row.market_logit),                # b365 alone
                    _sigmoid(off_exch),                        # exchange alone
                    _predict(row, row.market_logit, beta_b365),
                    _predict(row, off_exch, beta_exch),
                    _predict(row, row.market_logit, beta_full),  # deployed-size b365
                )))
            print(f"  {year}: trained on {len(train):,}, scored {len(by_year[year]):,}",
                  flush=True)
        else:
            print(f"  {year}: skipped scoring (train={len(train):,} < {MIN_TRAIN:,})",
                  flush=True)
        train.extend(by_year[year])

    if not scored:
        raise SystemExit("nothing scored — coverage too thin for the walk-forward")
    print(f"\nscored out-of-sample: {len(scored):,} matches")

    def gains(index_a: int, index_b: int) -> list[tuple[dt.date, float]]:
        return [(row.date,
                 _log_score(preds[index_a], row.won)
                 - _log_score(preds[index_b], row.won))
                for row, preds in scored]

    print("\nWHICH ANCHOR IS SHARPER (bare prices, no features)")
    _paired("exchange T-600s over b365 closing", gains(1, 0))

    print("\nDO THE FEATURES STILL ADD ANYTHING ON EACH ANCHOR")
    _paired("features over bare b365", gains(2, 0))
    _paired("features over bare exchange", gains(3, 1))

    print("\nTHE DECISION ROW: exchange-anchored model over b365-anchored model")
    _paired("exchange+features over b365+features", gains(3, 2))

    print("\nTHE DEPLOYMENT ROW: re-anchored (covered rows) vs deployed (full corpus)")
    _paired("exchange+features(24k) over b365+features(90k)", gains(3, 4))

    print("\nREADING")
    print("  The exchange price is T-600s and the Bet365 price is a later closing price,")
    print("  so the exchange anchor runs at an information disadvantage. If it wins here")
    print("  it wins conservatively. Both refits train only on covered rows — this")
    print("  measures the anchor, not the deployed model, which trains on far more.")


if __name__ == "__main__":
    main()
