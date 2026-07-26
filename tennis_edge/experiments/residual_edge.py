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
from dataclasses import dataclass, replace
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

#: Books the money test settles at, with the commission each charges, in report order.
#:
#: Pinnacle first because it is the conservative one: sharp, always available, and it does
#: not close winning accounts. ``betfair`` last because it is the venue that actually
#: matters for a personal bettor — it is the only one here that charges commission rather
#: than burying its margin in the quote, and it is the only one that cannot limit a winner.
#: Its coverage in this corpus starts in 2025, so its sample is small and its row must be
#: read as an indication rather than a measurement.
#:
#: A bookmaker's margin is already inside its quoted price, so settling those at 0%
#: commission is correct and not a favour to the strategy.
SETTLE_BOOKS = ("pinnacle", "b365", "max", "betfair")
COMMISSIONS = {"pinnacle": 0.0, "b365": 0.0, "max": 0.0, "betfair": 0.02}


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


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Solve ``matrix @ x = vector`` by Gaussian elimination with partial pivoting.

    Small and dense — one row and column per feature — so an explicit solve is cheap and
    exact enough. Partial pivoting because the penalised Hessian is well conditioned but not
    diagonally dominant when features are near-copies of each other, which they are.
    """
    width = len(vector)
    augmented = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
    for column in range(width):
        pivot = max(range(column, width), key=lambda r: abs(augmented[r][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            raise ValueError("singular Hessian — features are exactly collinear")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        scale = augmented[column][column]
        for r in range(width):
            if r == column:
                continue
            factor = augmented[r][column] / scale
            if factor == 0.0:
                continue
            for c in range(column, width + 1):
                augmented[r][c] -= factor * augmented[column][c]
    return [augmented[i][width] / augmented[i][i] for i in range(width)]


def _penalised_loglik(
    compiled: list[tuple[float, int, list[tuple[int, float]]]], beta: list[float]
) -> float:
    total = -0.5 * L2 * math.fsum(b * b for b in beta)
    for offset, won, pairs in compiled:
        z = offset + math.fsum(beta[i] * x for i, x in pairs)
        z = max(min(z, 30.0), -30.0)
        # log sigmoid(z) for a win, log sigmoid(-z) for a loss, written to avoid overflow.
        total += -math.log1p(math.exp(-z)) if won else -math.log1p(math.exp(z))
    return total


def fit(rows: list[Row], names: list[str]) -> dict[str, float]:
    """Ridge logistic on the residual, with the market logit as an unpenalised offset.

    Full Newton — the whole Hessian, not just its diagonal — with a backtracking line
    search. Both parts are there for the same reason.

    The first implementation updated each coefficient by its own second derivative and
    applied all the updates at once. That is Jacobi iteration: it ignores the off-diagonal
    curvature, and it diverges as soon as features are correlated. These features are
    strongly correlated — ranking, Elo and surface Elo all measure roughly the same thing —
    so it diverged to coefficients in the thousands and a log score nine nats *worse* than
    the market it was meant to be correcting. That looked like a finding and was a bug.

    The line search is the guard rather than the cure: a Newton step on a well-posed
    penalised problem is almost always accepted whole, and halving it when the penalised
    likelihood fails to improve means the fit can no longer walk away from its own optimum
    without that showing up as a refusal to converge.

    Rows missing a feature contribute nothing to it, which is how a feature available on
    only part of the sample (the point model needs serve coverage) is used where it exists
    without imputing a value where it does not.
    """
    compiled = _compile(rows, names)
    width = len(names)
    beta = [0.0] * width
    current = _penalised_loglik(compiled, beta)
    for _ in range(50):
        gradient = [-L2 * b for b in beta]
        hessian = [[L2 if i == j else 0.0 for j in range(width)] for i in range(width)]
        for offset, won, pairs in compiled:
            z = offset
            for i, x in pairs:
                z += beta[i] * x
            p = 1.0 / (1.0 + math.exp(-max(min(z, 30.0), -30.0)))
            residual, weight = won - p, p * (1 - p)
            for i, x in pairs:
                gradient[i] += x * residual
                wx = weight * x
                for j, y in pairs:
                    hessian[i][j] += wx * y
        try:
            step = _solve(hessian, gradient)
        except ValueError:
            break
        scale = 1.0
        for _attempt in range(20):
            candidate = [b + scale * s for b, s in zip(beta, step)]
            value = _penalised_loglik(compiled, candidate)
            if value >= current:
                beta, current = candidate, value
                break
            scale *= 0.5
        else:
            break
        if max(abs(scale * s) for s in step) < 1e-10:
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


def _settle_at(scored: list[tuple[Row, float]], book: str,
               use_model: bool) -> list[BetResult]:
    results: list[BetResult] = []
    for row, p in scored:
        probability = p if use_model else _sigmoid(row.market_logit)
        # (probability of this side, its price, whether it won). Carried together so the
        # side a bet is on can never drift apart from the outcome it settles by.
        for side, odds, won in (
            (probability, row.odds_a.get(book), bool(row.won)),
            (1.0 - probability, row.odds_b.get(book), not row.won),
        ):
            # Commission applies to winnings, so the break-even price is above 1/p. Using
            # 1/p on the exchange would credit the strategy with money Betfair keeps.
            net = 1.0 + (odds - 1.0) * (1.0 - COMMISSIONS[book]) if odds else 0.0
            if odds is None or odds <= 1.0 or side * net <= 1.0:
                continue
            results.append(BetResult(cluster=row.date, odds=odds, stake=1.0,
                                     won=won, commission=COMMISSIONS[book]))
    return results


def report_money(scored: list[tuple[Row, float]]) -> None:
    """Flat stakes, no buffer: bet whenever the model clears the quoted break-even.

    A required-edge threshold is the classic place to launder an overfit — every threshold
    is a parameter, and the best one is always found after the fact. There is none here.

    **The control is the point of this function, not an ornament on it.** ``max`` is the
    best quote across roughly twenty books, so a rule that bets whenever a probability
    clears the break-even *at the best quote* is partly a price-selection strategy no matter
    what supplies the probability — it fires wherever some book is out of line with the one
    used for pricing. The control runs the identical rule driven by the **market's own**
    de-vigged probability, with no model correction at all. Whatever it earns is
    attributable to shopping between books; only the difference between the two rows can be
    credited to the model, and if the control earns as much then none of it can.

    This is also why Pinnacle is reported. It is a single sharp book rather than an
    envelope, so its row cannot be manufactured by cross-book selection, and it is the
    conservative number.
    """
    print("\nMONEY, settled at the actual quoted price (flat 1u, no required-edge buffer)")
    print("  Each book: the model's rule, then the identical rule driven by the market's")
    print("  own probability. The control's return is price selection, not skill.")
    for book in SETTLE_BOOKS:
        model = _settle_at(scored, book, use_model=True)
        control = _settle_at(scored, book, use_model=False)
        if len(model) < 100:
            print(f"\n  {book:<10} {len(model)} bets — too few to score")
            continue
        print()
        print("  " + summarise_bets(model, bootstrap=BOOTSTRAP_DRAWS).report(book))
        if len(control) < 100:
            print(f"  {'control':<28}{len(control)} bets — the market's own rule fires "
                  f"too rarely to compare")
            continue
        print("  " + summarise_bets(control, bootstrap=BOOTSTRAP_DRAWS)
              .report(f"{book} CONTROL"))


def placebo(rows: list[Row], names: list[str]) -> None:
    """Re-run the entire procedure with the features detached from their matches.

    The control in :func:`report_money` asks whether the *money* could come from shopping
    between books. This asks the prior question: whether the **procedure** can manufacture a
    forecast gain out of nothing.

    Each row keeps its market price, its odds and its result, and is given another row's
    feature vector from the same season. Every genuine link between a feature and the match
    it describes is destroyed; everything else — sample size, feature correlations, the
    penalty, the walk-forward, the day-clustered interval — is identical. A procedure that
    reports a gain here is reporting one it can also report from noise, and the real number
    means nothing.

    Shuffling *features* rather than *outcomes* is deliberate. TE-0001 recorded that
    shuffling outcomes is invalid: it breaks the price-outcome coupling, and with asymmetric
    payoffs that inflates returns mechanically. That test was run once, proved nothing, and
    is not repeated here.

    The permutation is a fixed rotation within each season rather than a random draw — it
    needs no seed, it is exactly reproducible, and it cannot accidentally leave a row
    holding its own features.
    """
    print("\nPLACEBO: the same procedure, features detached from their matches")
    by_year: dict[int, list[Row]] = collections.defaultdict(list)
    for row in rows:
        by_year[row.date.year].append(row)
    scrambled: list[Row] = []
    for _year, block in sorted(by_year.items()):
        if len(block) < 2:
            continue
        for index, row in enumerate(block):
            donor = block[(index + 1) % len(block)]
            scrambled.append(replace(row, features=donor.features))
    scrambled.sort(key=lambda r: r.date)
    scored = walk_forward(scrambled, names)
    if not scored:
        print("  no out-of-sample years")
        return
    report_forecast(scored)


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
    placebo(rows, names)


if __name__ == "__main__":
    main()
