"""The candidate model: fit the market's *residual*, including what it cannot see.

Six architectures failed and the fitted combination gave the model a weight indistinguishable
from zero. The single-feature residual diagnostic (``serve_features.py``) then said something
those six builds could not have discovered, because every one of them combined a model
probability with the market in one direction:

**the market's errors do not all point the same way.** Ranking and rating gaps came back with
*negative* coefficients — the closing price over-extrapolates them — while the serve-based
point model came back *positive*. Bundle those into a single composite probability and they
cancel, which is exactly the ``alpha ~ 0`` that TE-0004 reported.

So this fits them as what they are: separate corrections to the price, each free to take its
own sign. Two things are new here beyond that.

**Pyramid features.** :mod:`tennis_edge.pyramid` supplies rating, workload and tier features
built from the whole professional pyramid rather than the priced main-tour corpus. A market
that prices a qualifier has less to go on than one pricing a top-20 player, and this is the
only input in the programme the price plausibly has not already absorbed.

**Money at a price someone would actually get.** Reported at Pinnacle — the sharp price that
is always available and never limits an account — and at Max, the best quote across books,
which is what a personal punter with several accounts gets and also what gets them limited
soonest. Both, because the gap between them *is* the result when the edge is small.

Everything is out-of-sample by year, the staking rule is parameter-free (bet whenever the
model's probability clears the break-even implied by the quoted price, flat stakes), and
every interval is day-clustered. The L2 penalty is fixed a priori and never tuned against
the result — with this many correlated features an unpenalised fit would chase noise, and a
penalty chosen by looking at the answer would be the same thing wearing a hat.
"""
import collections
import datetime as dt
import math
from dataclasses import dataclass
from typing import Sequence, cast

from tennis_edge.backtest import market_probability
from tennis_edge.corpus import Match, default_vintage_root, group_by_day, load_corpus
from tennis_edge.devig import DevigMethod
from tennis_edge.metrics import BetResult, clustered_bootstrap, summarise_bets
from tennis_edge.pyramid import PyramidRatings, pyramid_features
from tennis_edge.ratings import RatingEngine, elo_expected
from tennis_edge.refresh import latest_vintage
from tennis_edge.sackmann import load_matches
from tennis_edge.serve_stats import ServeEstimator

PRICING_BOOK = "b365"
DEVIG = DevigMethod.POWER
ARCHIVE_FROM = dt.date(2003, 1, 1)
FIRST_SCORED_YEAR = 2012
BOOTSTRAP_DRAWS = 2000

#: Ridge penalty on the residual coefficients. Fixed before any result was seen. The market
#: logit enters as an offset and is never penalised — the penalty shrinks *corrections to*
#: the price toward zero, which is the correct prior: absent evidence, the price is right.
L2 = 25.0

#: Books the money test settles at, in the order reported. Pinnacle first because it is the
#: conservative one: sharp, always available, and it does not close winning accounts.
SETTLE_BOOKS = ("pinnacle", "b365", "max")

#: Betfair charges commission on net market winnings; a bookmaker charges none, its margin
#: being already inside the quoted price. Settling bookmaker bets at 0% is therefore correct
#: and not a favour to the strategy.
BOOKMAKER_COMMISSION = 0.0


@dataclass(frozen=True)
class Row:
    date: dt.date
    tour: str
    player_a: str
    player_b: str
    market_logit: float
    features: dict[str, float]
    won: int
    odds_a: dict[str, float]
    odds_b: dict[str, float]


def _logit(p: float) -> float:
    q = min(max(p, 1e-12), 1 - 1e-12)
    return math.log(q / (1 - q))


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(min(z, 30.0), -30.0)))


def build(matches: tuple[Match, ...]) -> list[Row]:
    engine = RatingEngine()
    pyramid = PyramidRatings()
    estimator = ServeEstimator()
    estimator.queue(load_matches(families=("main", "qual_chall"), since=ARCHIVE_FROM,
                                 require_serve_stats=True))
    pyramid.queue(load_matches(families=("main", "qual_chall", "futures"),
                               since=ARCHIVE_FROM))
    rows: list[Row] = []
    for day, batch in group_by_day(matches):
        estimator.advance_to(day)
        pyramid.advance_to(day)
        for match in sorted(batch, key=lambda m: (m.tour, m.player_a, m.player_b)):
            market = market_probability(match, book=PRICING_BOOK, method=DEVIG)
            if market is None:
                continue
            tour, a, b = match.tour, match.player_a, match.player_b
            if engine.matches_played(tour, a) < 5 or engine.matches_played(tour, b) < 5:
                continue

            elo = elo_expected(engine.blended(tour, a, match.surface),
                               engine.blended(tour, b, match.surface))
            features = {
                "elo_residual": _logit(elo) - _logit(market),
                "surface_elo_gap": (engine.surface_elo(tour, a, match.surface)
                                    - engine.surface_elo(tour, b, match.surface)) / 400.0,
                "weighted_elo_gap": (engine.weighted_elo(tour, a)
                                     - engine.weighted_elo(tour, b)) / 400.0,
                "rank_gap": (math.log1p(match.rank_b or 500)
                             - math.log1p(match.rank_a or 500)),
            }
            estimate = estimator.estimate(tour, a, b, day)
            if estimate is not None and estimate.coverage >= 300.0:
                point = estimate.match_probability(best_of=match.best_of)
                features["point_model_residual"] = _logit(point) - _logit(market)
            features.update(pyramid_features(pyramid, tour, a, b, day, match.surface))

            odds_a, odds_b = {}, {}
            for book in SETTLE_BOOKS:
                pair = match.odds.pair(book)
                if pair is not None:
                    odds_a[book], odds_b[book] = float(pair[0]), float(pair[1])
            rows.append(Row(match.match_date, tour, a, b, _logit(market), features,
                            1 if match.winner_is_a else 0, odds_a, odds_b))
        engine.observe(batch)
    return rows


def _compile(rows: list[Row], names: list[str]) -> list[tuple[float, int, list[tuple[int, float]]]]:
    """Rows as ``(offset, outcome, [(feature index, value)])``, present features only.

    The fit is a Python inner loop over tens of millions of row-feature pairs, and hashing a
    feature name on every one of them dominates the cost. Compiling once to positional
    indices makes a full walk-forward minutes rather than hours, which is the difference
    between an experiment that can be re-run after a correction and one that cannot.

    Only present features are emitted, which is also what keeps a partially-covered feature
    honest: a row without the point model contributes nothing to that coefficient rather
    than contributing an imputed zero.
    """
    index = {name: i for i, name in enumerate(names)}
    return [
        (row.market_logit, row.won,
         [(index[n], v) for n, v in row.features.items() if n in index])
        for row in rows
    ]


def fit(rows: list[Row], names: list[str]) -> dict[str, float]:
    """Ridge logistic on the residual, with the market logit as an unpenalised offset.

    Newton with a fixed penalty. Rows missing a feature contribute nothing to it, which is
    how a feature available on only part of the sample (the point model needs serve
    coverage) is used where it exists without imputing a value where it does not.
    """
    compiled = _compile(rows, names)
    width = len(names)
    beta = [0.0] * width
    for _ in range(50):
        gradient = [-L2 * b for b in beta]
        hessian = [L2] * width
        for offset, won, pairs in compiled:
            z = offset
            for i, x in pairs:
                z += beta[i] * x
            p = 1.0 / (1.0 + math.exp(-max(min(z, 30.0), -30.0)))
            residual, weight = won - p, p * (1 - p)
            for i, x in pairs:
                gradient[i] += x * residual
                hessian[i] += x * x * weight
        steps = [g / h for g, h in zip(gradient, hessian)]
        for i, delta in enumerate(steps):
            beta[i] += delta
        if max(abs(s) for s in steps) < 1e-10:
            break
    return dict(zip(names, beta))


def predict(row: Row, beta: dict[str, float]) -> float:
    return _sigmoid(row.market_logit + math.fsum(
        b * row.features[n] for n, b in beta.items() if n in row.features))


def walk_forward(rows: list[Row], names: list[str]) -> list[tuple[Row, float]]:
    """Fit on every prior year, predict the next. Never on data the fit has seen."""
    by_year: dict[int, list[Row]] = collections.defaultdict(list)
    for row in rows:
        by_year[row.date.year].append(row)
    ordered = sorted(by_year)
    years = [y for y in ordered if y >= FIRST_SCORED_YEAR]
    out: list[tuple[Row, float]] = []
    # The training set only ever grows, so it is extended year by year rather than rebuilt.
    train: list[Row] = [r for y in ordered if y < years[0] for r in by_year[y]]
    for year in years:
        if len(train) >= 5000:
            beta = fit(train, names)
            for row in by_year[year]:
                out.append((row, predict(row, beta)))
            print(f"  {year}: trained on {len(train):,}, scored {len(by_year[year]):,}",
                  flush=True)
        train.extend(by_year[year])
    return out


def _mean_gain(rows: Sequence[object]) -> float:
    """Mean per-match log-score gain over a bootstrap resample of whole days."""
    return math.fsum(cast(tuple[dt.date, float], r)[1] for r in rows) / len(rows)


def _day_of(row: object) -> dt.date:
    return cast(tuple[dt.date, float], row)[0]


def report_forecast(scored: list[tuple[Row, float]]) -> None:
    print(f"\nFORECAST QUALITY, out-of-sample ({len(scored):,} matches)")
    gains = [(row.date,
              math.log(p if row.won else 1 - p)
              - math.log(_sigmoid(row.market_logit) if row.won
                         else 1 - _sigmoid(row.market_logit)))
             for row, p in scored]
    mean = math.fsum(g for _d, g in gains) / len(gains)
    lo, hi = clustered_bootstrap(gains, statistic=_mean_gain, cluster_of=_day_of,
                                 draws=BOOTSTRAP_DRAWS)
    verdict = "beats the price" if lo > 0 else (
        "worse than the price" if hi < 0 else "indistinguishable from the price")
    print(f"  log-score gain over the market  {mean:+.6f} nats  "
          f"95% CI [{lo:+.6f}, {hi:+.6f}]  -> {verdict}")


def report_money(scored: list[tuple[Row, float]]) -> None:
    """Flat stakes, no buffer: bet whenever the model clears the quoted break-even.

    A required-edge threshold is the classic place to launder an overfit — every threshold
    is a parameter, and the best one is always found after the fact. There is none here.
    """
    print("\nMONEY, settled at the actual quoted price (flat 1u, no required-edge buffer)")
    for book in SETTLE_BOOKS:
        results: list[BetResult] = []
        for row, p in scored:
            # (probability of this side, its price, whether it won). Carried together so
            # the side a bet is on can never drift apart from the outcome it settles by.
            for probability, odds, won in (
                (p, row.odds_a.get(book), bool(row.won)),
                (1.0 - p, row.odds_b.get(book), not row.won),
            ):
                if odds is None or odds <= 1.0 or probability * odds <= 1.0:
                    continue
                results.append(BetResult(cluster=row.date, odds=odds, stake=1.0,
                                         won=won, commission=BOOKMAKER_COMMISSION))
        if len(results) < 100:
            print(f"  {book:<10} {len(results)} bets — too few to score")
            continue
        print("  " + summarise_bets(results, bootstrap=BOOTSTRAP_DRAWS).report(book))


def main() -> None:
    vintage = latest_vintage(default_vintage_root())
    assert vintage is not None
    matches, _stats = load_corpus(vintage.root)
    rows = build(matches)
    names = sorted({n for r in rows for n in r.features})
    coverage = {n: sum(1 for r in rows if n in r.features) for n in names}
    print(f"priceable matches: {len(rows):,}")
    print("feature coverage: " + ", ".join(f"{n} {coverage[n]:,}" for n in names))

    print("\nwalk-forward:")
    scored = walk_forward(rows, names)
    if not scored:
        print("no out-of-sample years")
        return
    # `max` hoisted out of the comprehension deliberately: leaving it inside re-scans every
    # row for every row, which on 96,162 rows is nine billion comparisons and looks exactly
    # like a hung process.
    last_year = max(r.date.year for r in rows)
    final = fit([r for r in rows if r.date.year < last_year], names)
    print("\nCOEFFICIENTS on the final fit (sign is the market's error, not the feature's)")
    for name, value in sorted(final.items(), key=lambda kv: -abs(kv[1])):
        direction = "market under-weights" if value > 0 else "market over-weights"
        print(f"  {name:<24}{value:>+10.4f}   {direction}")

    report_forecast(scored)
    report_money(scored)


if __name__ == "__main__":
    main()
