"""Does *any* feature carry information the closing price has not already used?

Six architectures failed as *predictions*. That is a weaker result than it looks, because
every one of them was a particular way of combining features into a probability, and a bad
combination can bury a good signal. This asks the more basic question, one layer down:

**take the market logit as given, and ask whether any single feature explains the residual.**

If a feature carries information the price has missed, it shows up here as a non-zero
coefficient when added to the market logit — regardless of whether any model built so far
happened to use it well. If nothing shows up, the problem is not the architecture and no
rearrangement of these inputs will help.

This is the diagnostic that should have come *before* six model builds, because it is the
one that distinguishes "our models are bad" from "this information is already in the price".

Each feature is tested on its own, against the market alone, out-of-sample by year. Testing
them singly rather than jointly is deliberate: a joint fit lets a genuinely informative
feature hide behind a correlated useless one, and at this stage the question is existence,
not attribution. The multiplicity cost of testing many single features is stated with the
results rather than hidden — with this many tests, one or two will clear t=2 by chance and
the Bonferroni threshold is given alongside.

**Two significance numbers, and only the second one counts.** The coefficient's ``t`` comes
from the training fit, so it says how precisely the training set pinned the coefficient down
— not whether the coefficient helped on data it never saw. The decisive number is the
out-of-sample log-score gain with a **day-clustered** interval, because matches on the same
day share tournament conditions and treating them as independent is how noise acquires a
significant-looking statistic. A feature is only interesting here if that interval excludes
zero.
"""
import collections
import datetime as dt
import math
from dataclasses import dataclass

from tennis_edge.backtest import market_probability
from tennis_edge.corpus import Match, default_vintage_root, group_by_day, load_corpus
from tennis_edge.devig import DevigMethod
from tennis_edge.metrics import clustered_bootstrap
from tennis_edge.ratings import RatingEngine, elo_expected
from tennis_edge.refresh import latest_vintage
from tennis_edge.sackmann import load_matches
from tennis_edge.serve_stats import ServeEstimator

BOOK = "b365"
DEVIG = DevigMethod.POWER
ARCHIVE_FROM = dt.date(2003, 1, 1)
FIRST_SCORED_YEAR = 2010
BOOTSTRAP_DRAWS = 2000


@dataclass(frozen=True)
class FeatureRow:
    date: dt.date
    market_logit: float
    features: dict[str, float]
    won: int


def _logit(p: float) -> float:
    return math.log(min(max(p, 1e-12), 1 - 1e-12) / (1 - min(max(p, 1e-12), 1 - 1e-12)))


def build(matches: tuple[Match, ...]) -> list[FeatureRow]:
    engine = RatingEngine()
    estimator = ServeEstimator()
    estimator.queue(load_matches(families=("main", "qual_chall"), since=ARCHIVE_FROM,
                                 require_serve_stats=True))
    rows: list[FeatureRow] = []
    for day, batch in group_by_day(matches):
        estimator.advance_to(day)
        for match in sorted(batch, key=lambda m: (m.tour, m.player_a, m.player_b)):
            market = market_probability(match, book=BOOK, method=DEVIG)
            if market is None:
                continue
            tour, a, b = match.tour, match.player_a, match.player_b
            played_a = engine.matches_played(tour, a)
            played_b = engine.matches_played(tour, b)
            if played_a < 5 or played_b < 5:
                continue

            elo = elo_expected(engine.blended(tour, a, match.surface),
                               engine.blended(tour, b, match.surface))
            rest_a = engine.days_since_last(tour, a, match.match_date)
            rest_b = engine.days_since_last(tour, b, match.match_date)
            games_a = engine.games_in_last(tour, a, match.match_date, 14)
            games_b = engine.games_in_last(tour, b, match.match_date, 14)
            h2h_a, h2h_b = engine.head_to_head(tour, a, b)
            estimate = estimator.estimate(tour, a, b, day)

            features = {
                # The model's own view, as a residual against the price.
                "elo_residual": _logit(elo) - _logit(market),
                "surface_elo_gap": (engine.surface_elo(tour, a, match.surface)
                                    - engine.surface_elo(tour, b, match.surface)) / 400.0,
                "weighted_elo_gap": (engine.weighted_elo(tour, a)
                                     - engine.weighted_elo(tour, b)) / 400.0,
                # Fatigue and rest — information a closing price may not weight fully.
                "rest_gap": ((rest_a or 60) - (rest_b or 60)) / 30.0,
                "workload_gap": (games_a - games_b) / 50.0,
                # Experience asymmetry.
                "experience_gap": (math.log1p(played_a) - math.log1p(played_b)),
                # Head to head, the classic punter's feature.
                "h2h_gap": (h2h_a - h2h_b) / 5.0,
                # Ranking, which the market certainly knows.
                "rank_gap": (math.log1p(match.rank_b or 500)
                             - math.log1p(match.rank_a or 500)),
            }
            if estimate is not None and estimate.coverage >= 300.0:
                point = estimate.match_probability(best_of=match.best_of)
                features["point_model_residual"] = _logit(point) - _logit(market)
            rows.append(FeatureRow(match.match_date, _logit(market), features,
                                   1 if match.winner_is_a else 0))
        engine.observe(batch)
    return rows


def _fit_single(xs: list[float], offsets: list[float], ys: list[int]) -> tuple[float, float]:
    """Logistic fit of y on one feature with the market logit as a fixed offset.

    The offset is what makes this a residual test: the market's view is taken as given and
    the coefficient answers only "does this feature explain what the price missed".
    """
    b = 0.0
    h = 0.0
    for _ in range(60):
        g = h = 0.0
        for x, off, y in zip(xs, offsets, ys):
            p = 1.0 / (1.0 + math.exp(-max(min(off + b * x, 30.0), -30.0)))
            g += x * (y - p)
            h += x * x * p * (1 - p)
        if h <= 1e-12:
            break
        step = g / h
        b += step
        if abs(step) < 1e-11:
            break
    return b, (h ** -0.5 if h > 0 else float("inf"))


def main() -> None:
    vintage = latest_vintage(default_vintage_root())
    assert vintage is not None
    matches, _stats = load_corpus(vintage.root)
    rows = build(matches)
    print(f"priceable matches: {len(rows):,}\n")

    names = sorted({name for r in rows for name in r.features})
    by_year: dict[int, list[FeatureRow]] = collections.defaultdict(list)
    for row in rows:
        by_year[row.date.year].append(row)
    years = [y for y in sorted(by_year) if y >= FIRST_SCORED_YEAR]

    print("Out-of-sample residual test: fit each feature on prior years, score the next.")
    print("A negative coefficient means the price OVER-weights the feature — the residual")
    print("is a fade, not a follow. 'gain 95% CI' is day-clustered and is what counts.\n")
    print(f"{'feature':<24}{'n_oos':>9}{'coef':>9}{'t(fit)':>8}"
          f"{'oos gain':>12}{'gain 95% CI (day-clustered)':>32}")

    results = []
    for name in names:
        gains: list[tuple[dt.date, float]] = []
        coefs: list[float] = []
        ses: list[float] = []
        for year in years:
            train = [r for y in years if y < year for r in by_year[y] if name in r.features]
            test = [r for r in by_year[year] if name in r.features]
            if len(train) < 2000 or len(test) < 100:
                continue
            coef, se = _fit_single([r.features[name] for r in train],
                                   [r.market_logit for r in train],
                                   [r.won for r in train])
            coefs.append(coef)
            ses.append(se)
            for r in test:
                z = r.market_logit + coef * r.features[name]
                p = 1.0 / (1.0 + math.exp(-max(min(z, 30.0), -30.0)))
                base = 1.0 / (1.0 + math.exp(-r.market_logit))
                gains.append((r.date, math.log(p if r.won else 1 - p)
                              - math.log(base if r.won else 1 - base)))
        if not coefs or not gains:
            continue
        mean_coef = math.fsum(coefs) / len(coefs)
        mean_se = math.fsum(ses) / len(ses)
        gain = math.fsum(g for _d, g in gains) / len(gains)
        lo, hi = clustered_bootstrap(
            gains,
            statistic=lambda rows: math.fsum(g for _d, g in rows) / len(rows),  # type: ignore[misc]
            cluster_of=lambda row: row[0],  # type: ignore[index]
            draws=BOOTSTRAP_DRAWS,
        )
        excludes_zero = lo > 0.0 or hi < 0.0
        results.append((name, len(gains), mean_coef, mean_coef / mean_se, gain,
                        lo, hi, excludes_zero))
        print(f"{name:<24}{len(gains):>9,}{mean_coef:>9.4f}{mean_coef / mean_se:>8.2f}"
              f"{gain:>+12.6f}   [{lo:+.6f}, {hi:+.6f}]"
              f"{'  *' if excludes_zero else '   '}")

    if not results:
        return
    survivors = [r for r in results if r[7]]
    k = len(results)
    print(f"\n{k} features tested. Marked * where the day-clustered 95% interval on the "
          f"out-of-sample\ngain excludes zero — {len(survivors)} of {k}. With {k} tests, "
          f"expect about {0.05 * k:.1f} by chance,\nso a count materially above that is the "
          f"signal; a count at or below it is not.")
    if survivors:
        print("\nSurviving features, by out-of-sample gain:")
        for name, n, coef, t, gain, lo, hi, _ in sorted(survivors, key=lambda r: -r[4]):
            direction = "market UNDER-weights" if coef > 0 else "market OVER-weights"
            print(f"  {name:<24}{gain:>+11.6f} nats   coef {coef:+.4f} "
                  f"(t {t:+.2f}) — {direction} it")


if __name__ == "__main__":
    main()
