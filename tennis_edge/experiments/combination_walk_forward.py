"""Walk-forward stage-two combination, and the stress tests that decide whether to believe it.

The frozen policy asserts a 10% weight on the model. This asks the data instead: fit
``alpha`` and ``beta`` by MLE on everything strictly *before* each evaluation year, then
score the year out-of-sample. If the model adds nothing, alpha comes back at zero and the
combination collapses to the market — which is the honest outcome, not a failure of method.

Everything here is out-of-sample by construction:

* the rating engine and serve estimator are day-batched, so no same-day result informs a
  prediction;
* the combination weights are refitted per year on prior years only, and a year is scored
  with weights that never saw it;
* the market probability is the de-vigged closing price for that match, which is an input
  and never a training target.

Stress tests, because a single pooled number hides everything that matters:

* **per-year stability** — an edge that exists in one year and reverses in the next is noise
  wearing a trend's clothes;
* **day-clustered bootstrap** — matches on the same day share tournament, surface and
  conditions, so treating them as independent overstates significance;
* **cohort splits** — surface, best-of, and odds band, because a pooled mean can hide a real
  effect confined to one corner or a spurious one driven by it;
* **Diebold-Mariano** on the paired log-loss difference, the same statistic used for every
  other architecture in this package so the numbers are comparable.
"""
import collections
import datetime as dt
import math
from dataclasses import dataclass

from tennis_edge.backtest import market_probability
from tennis_edge.combine import Combination, apply_combination, fit_combination
from tennis_edge.corpus import Match, default_vintage_root, group_by_day, load_corpus
from tennis_edge.devig import DevigMethod
from tennis_edge.ratings import RatingEngine, elo_expected
from tennis_edge.refresh import latest_vintage
from tennis_edge.sackmann import load_matches
from tennis_edge.serve_stats import ServeEstimator

BOOK = "b365"
DEVIG = DevigMethod.POWER
MIN_PRIOR_MATCHES = 5
MIN_SERVE_POINTS = 300.0
ARCHIVE_FROM = dt.date(2003, 1, 1)
FIRST_SCORED_YEAR = 2010


@dataclass(frozen=True)
class Row:
    """One out-of-sample match with every probability needed to score it."""

    date: dt.date
    p_model: float
    p_market: float
    won: int
    surface: str
    best_of: int
    tour: str


def _logit(p: float) -> float:
    clipped = min(max(p, 1e-12), 1.0 - 1e-12)
    return math.log(clipped / (1.0 - clipped))


def _model_view(
    engine: RatingEngine, estimator: ServeEstimator, match: Match, day: dt.date
) -> float | None:
    """Rating blend, averaged in logit space with the point model where serve data allows."""
    if engine.matches_played(match.tour, match.player_a) < MIN_PRIOR_MATCHES:
        return None
    if engine.matches_played(match.tour, match.player_b) < MIN_PRIOR_MATCHES:
        return None
    elo = elo_expected(
        engine.blended(match.tour, match.player_a, match.surface),
        engine.blended(match.tour, match.player_b, match.surface),
    )
    estimate = estimator.estimate(match.tour, match.player_a, match.player_b, day)
    if estimate is None or estimate.coverage < MIN_SERVE_POINTS:
        return elo
    point = estimate.match_probability(best_of=match.best_of)
    return 1.0 / (1.0 + math.exp(-0.5 * (_logit(elo) + _logit(point))))


def build_rows() -> list[Row]:
    """Walk the corpus forward once, emitting a row per priceable match."""
    vintage = latest_vintage(default_vintage_root())
    if vintage is None:
        raise RuntimeError("no Tennis-Data vintage")
    matches, _stats = load_corpus(vintage.root)

    engine = RatingEngine()
    estimator = ServeEstimator()
    estimator.queue(load_matches(families=("main", "qual_chall"), since=ARCHIVE_FROM,
                                 require_serve_stats=True))

    rows: list[Row] = []
    for day, batch in group_by_day(matches):
        estimator.advance_to(day)
        for match in sorted(batch, key=lambda m: (m.tour, m.player_a, m.player_b)):
            market = market_probability(match, book=BOOK, method=DEVIG)
            model = _model_view(engine, estimator, match, day)
            if market is not None and model is not None:
                rows.append(Row(date=match.match_date, p_model=model, p_market=market,
                                won=1 if match.winner_is_a else 0, surface=match.surface,
                                best_of=match.best_of, tour=match.tour))
        engine.observe(batch)          # only AFTER every decision for the day
    return rows


def walk_forward(rows: list[Row]) -> tuple[list[tuple[Row, float, Combination]], dict[int, Combination]]:
    """Score each year with weights fitted only on strictly earlier years."""
    by_year: dict[int, list[Row]] = collections.defaultdict(list)
    for row in rows:
        by_year[row.date.year].append(row)

    scored: list[tuple[Row, float, Combination]] = []
    fits: dict[int, Combination] = {}
    for year in sorted(by_year):
        if year < FIRST_SCORED_YEAR:
            continue
        train = [(r.p_model, r.p_market, r.won) for y in sorted(by_year) if y < year
                 for r in by_year[y]]
        if len(train) < 500:
            continue
        try:
            fit = fit_combination(train)
        except ValueError:
            continue
        fits[year] = fit
        for row in by_year[year]:
            scored.append((row, apply_combination(fit, row.p_model, row.p_market), fit))
    return scored, fits


def _log_loss(pairs: list[tuple[float, int]]) -> float:
    return -math.fsum(math.log(p if y else 1.0 - p) for p, y in pairs) / len(pairs)


def _paired(scored: list[tuple[Row, float, Combination]]) -> list[float]:
    """Per-match log-loss advantage of the combination over the market. Positive is better."""
    out = []
    for row, blended, _fit in scored:
        y = row.won
        out.append(-math.log(row.p_market if y else 1 - row.p_market)
                   + math.log(blended if y else 1 - blended))
    return out


def _bootstrap_by_day(scored: list[tuple[Row, float, Combination]],
                      draws: int = 2000) -> tuple[float, float]:
    """Day-clustered bootstrap CI on the mean advantage.

    Matches on the same day share tournament, surface and conditions. Resampling matches
    independently would treat those as independent observations and overstate significance.
    """
    by_day: dict[dt.date, list[float]] = collections.defaultdict(list)
    for (row, blended, _fit), diff in zip(scored, _paired(scored)):
        by_day[row.date].append(diff)
    days = sorted(by_day)
    totals = [math.fsum(by_day[d]) for d in days]
    counts = [len(by_day[d]) for d in days]
    n_days = len(days)
    means = []
    state = 88172645463325252          # xorshift64, deterministic: no RNG dependency
    for _ in range(draws):
        total = count = 0.0
        for _ in range(n_days):
            state ^= (state << 13) & 0xFFFFFFFFFFFFFFFF
            state ^= state >> 7
            state ^= (state << 17) & 0xFFFFFFFFFFFFFFFF
            i = state % n_days
            total += totals[i]
            count += counts[i]
        means.append(total / count)
    means.sort()
    return means[int(0.025 * draws)], means[int(0.975 * draws)]


def main() -> None:
    rows = build_rows()
    print(f"priceable matches: {len(rows):,} "
          f"({rows[0].date.isoformat()} .. {rows[-1].date.isoformat()})\n")

    scored, fits = walk_forward(rows)
    print(f"scored out-of-sample: {len(scored):,} over {len(fits)} years\n")

    print(f"{'year':<6}{'n':>7}{'alpha':>9}{'beta':>8}{'model share':>13}"
          f"{'market LL':>11}{'combined':>10}{'gain':>10}")
    for year in sorted(fits):
        block = [(r, b, f) for r, b, f in scored if r.date.year == year]
        market = _log_loss([(r.p_market, r.won) for r, _b, _f in block])
        combined = _log_loss([(b, r.won) for r, b, _f in block])
        fit = fits[year]
        print(f"{year:<6}{len(block):>7,}{fit.alpha:>9.4f}{fit.beta:>8.4f}"
              f"{fit.model_share:>12.1%}{market:>11.5f}{combined:>10.5f}"
              f"{market - combined:>+10.5f}")

    diffs = _paired(scored)
    n = len(diffs)
    mean = math.fsum(diffs) / n
    var = math.fsum((d - mean) ** 2 for d in diffs) / (n - 1)
    se = math.sqrt(var / n)
    lo, hi = _bootstrap_by_day(scored)
    market_all = _log_loss([(r.p_market, r.won) for r, _b, _f in scored])
    combined_all = _log_loss([(b, r.won) for r, b, _f in scored])

    print(f"\npooled market   log loss {market_all:.5f}")
    print(f"pooled combined log loss {combined_all:.5f}")
    print(f"mean advantage {mean:+.5f} nats   naive SE {se:.5f}   naive t {mean/se:+.2f}")
    print(f"day-clustered bootstrap 95% CI [{lo:+.5f}, {hi:+.5f}]"
          f"  -> {'EXCLUDES' if lo > 0 or hi < 0 else 'INCLUDES'} zero")

    print("\ncohort breakdown (advantage in nats, positive = combination better)")
    cohorts: dict[str, list[float]] = collections.defaultdict(list)
    for (row, _b, _f), diff in zip(scored, diffs):
        cohorts[f"surface={row.surface}"].append(diff)
        cohorts[f"best_of={row.best_of}"].append(diff)
        cohorts[f"tour={row.tour}"].append(diff)
        band = ("fav<0.3" if row.p_market < 0.3 else
                "0.3-0.7" if row.p_market < 0.7 else "fav>0.7")
        cohorts[f"market_{band}"].append(diff)
    for name in sorted(cohorts):
        values = cohorts[name]
        if len(values) < 200:
            continue
        m = math.fsum(values) / len(values)
        v = math.fsum((x - m) ** 2 for x in values) / (len(values) - 1)
        print(f"  {name:<22}{len(values):>8,}{m:>+10.5f}"
              f"{m / math.sqrt(v / len(values)):>+8.2f} t")


if __name__ == "__main__":
    main()
