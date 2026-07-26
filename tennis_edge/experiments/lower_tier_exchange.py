"""The Challenger/ITF thesis, at real exchange prices. TE-0001's blocker, reopened.

TE-0001 closed task #72 as **untestable on free data**. Published operator figures put the
achievable yield at roughly 9% in Challenger/ITF against 2.4% on the main tour, and the one
corpus with those tiers priced them entirely off an OddsPortal aggregate — an average across
books and across time that nobody quotes and nobody can transact at. The verdict was that
testing it properly needed exchange historical data, which was unreachable.

**It is reachable, and it has been on this machine the whole time.** The June ADVANCED
corpus is not a main-tour sample with gaps; it is *mostly lower-tier tennis*. Its event names
are ITF and Challenger players. The reason it looked sparse is that the only link built for
it joined into the main-tour Tennis-Data corpus, so the lower-tier markets — the majority —
were correctly reported as having no corpus match and then quietly forgotten.

This scores them directly. Three things it establishes that TE-0001 could not:

1. **What the tier actually costs on an exchange.** TE-0001 measured 7.3–8.0% bookmaker
   overround at Challenger and ITF against 4.4% on the main tour, and concluded the tier is
   expensive rather than cheap. That was a statement about *bookmakers*. The exchange's
   two-sided book gives the real number.
2. **Whether the market is beatable there.** Pyramid Elo — which knows a player's Challenger
   and Futures record, and is the only rating here that does — scored against the exchange
   price at the same horizon, out-of-sample by construction.
3. **Whether it pays after commission**, settled at the actual best-back price.

**Where the outcomes come from, and why that matters.** Betfair grades its own markets. The
settlement carries each runner's WINNER/LOSER status, so this needs no results feed — which
is decisive, because Sackmann's archive ends in May 2026 for ATP and 2024 for WTA, and there
is no other source of June 2026 ITF results anywhere in reach.

**Why there is no lookahead, structurally rather than by care.** The rating state is built
from an archive that *stops before the scored period begins*. Not held back by a cutoff that
could be got wrong — the data simply does not exist past it. Every June prediction is made
from end-of-May ratings. That also means the ratings go stale across the month, and WTA
ratings are 18 months stale, so the two tours are reported separately and never pooled.
"""
import collections
import datetime as dt
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, cast

from tennis_edge.exchange import COMMISSION
from tennis_edge.metrics import BetResult, clustered_bootstrap, summarise_bets
from tennis_edge.pyramid import PyramidRatings, RatingSnapshot
from tennis_edge.pyramid_link import LinkedExchangeMarket, link_to_pyramid
from tennis_edge.ratings import elo_expected
from tennis_edge.sackmann import load_matches

ROOT = ("/tmp/claude-0/-home-user-Moneymaker/"
        "b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted")
ARCHIVE_FROM = dt.date(2005, 1, 1)
HORIZONS = (21_600, 3_600, 600)
BOOTSTRAP_DRAWS = 2000
#: Minimum pyramid matches per player. Higher than the main-tour threshold because an ITF
#: draw is full of players with a handful of recorded results, and a rating built on three
#: matches is a prior wearing a number.
MIN_HISTORY = 20
WORKERS = 3


MONTHS = {name: number for number, name in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), start=1)}


@dataclass(frozen=True)
class Observation:
    """One market at one horizon: the price, the model's view, and the settled result."""

    date: dt.date
    tour: str
    horizon: int
    model_p: float
    market_p: float
    back_a: float
    back_b: float
    won_a: int
    overround: float


def _logit(p: float) -> float:
    q = min(max(p, 1e-9), 1 - 1e-9)
    return math.log(q / (1 - q))


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(min(z, 30.0), -30.0)))


def day_directories(root: str) -> list[Path]:
    """Day directories in true chronological order.

    Betfair lays these out as ``<tier>/<year>/<Mon>/<day>``, and the month is a name. Sorting
    those as text puts July before June, which would walk the rating state backwards — the
    walk-forward refuses that, so this is a crash rather than a silent leak, but it is a
    crash worth not having.
    """
    days: list[Path] = []
    for tier in sorted(Path(root).iterdir()):
        for year in sorted(p for p in tier.iterdir() if p.is_dir()):
            for month in sorted(p for p in year.iterdir() if p.is_dir()):
                days.extend(p for p in month.iterdir() if p.is_dir())
    return sorted(days, key=lambda p: (int(p.parent.parent.name),
                                       MONTHS.get(p.parent.name, 0), int(p.name)))


_SNAPSHOT: RatingSnapshot | None = None


def _set_snapshot(frozen: RatingSnapshot) -> None:
    """Worker initialiser. Each process gets the same frozen state, once."""
    global _SNAPSHOT
    _SNAPSHOT = frozen


def one_day(path_text: str) -> tuple[str, int, int, list[Observation], dict[str, int]]:
    """Read, link and score a single day against the frozen rating state."""
    from tennis_edge.betfair import read_markets

    assert _SNAPSHOT is not None
    day = Path(path_text)
    markets = read_markets(day)
    if not markets:
        return path_text, 0, 0, [], {}
    gradings = {m.market_id: g for m in markets if (g := m.grading_view()) is not None}
    result = link_to_pyramid(markets, gradings, _SNAPSHOT,
                             minimum_matches=MIN_HISTORY)
    observations = _score(result.linked, _SNAPSHOT)
    counts = dict(result.counts())
    return path_text, len(markets), len(result.linked), observations, counts


def _score(linked: Sequence[LinkedExchangeMarket],
           frozen: RatingSnapshot) -> list[Observation]:
    observations: list[Observation] = []
    for row in linked:
        # The rating is read once per market, not once per horizon: it is the same frozen
        # state either way, and reading it inside the horizon loop would invite someone
        # later to make it horizon-dependent, which it must never be.
        model_p = elo_expected(frozen.elo_for(row.tour, row.key_a),
                               frozen.elo_for(row.tour, row.key_b))
        for horizon in HORIZONS:
            back_a = row.market.best_back_at(row.selection_a, seconds_before_off=horizon)
            back_b = row.market.best_back_at(row.selection_b, seconds_before_off=horizon)
            lay_a = row.market.best_lay_at(row.selection_a, seconds_before_off=horizon)
            lay_b = row.market.best_lay_at(row.selection_b, seconds_before_off=horizon)
            if back_a is None or back_b is None or lay_a is None or lay_b is None:
                continue
            imp_a = (1 / float(back_a.price) + 1 / float(lay_a.price)) / 2
            imp_b = (1 / float(back_b.price) + 1 / float(lay_b.price)) / 2
            observations.append(Observation(
                date=row.off_date, tour=row.tour, horizon=horizon,
                model_p=model_p,
                market_p=imp_a / (imp_a + imp_b),
                back_a=float(back_a.price), back_b=float(back_b.price),
                won_a=row.won_a,
                overround=1 / float(back_a.price) + 1 / float(back_b.price),
            ))
    return observations


def collect() -> tuple[list[Observation], dict[str, int]]:
    """Freeze the rating state, prove it is constant across the window, then fan out.

    The parallelism rests on one fact, and the fact is **checked rather than assumed**: the
    archive ends before the scored period, so no result arrives during it and every day is
    scored from identical state. :meth:`PyramidRatings.pending_after` is asked directly, and
    a non-zero answer aborts — because if evidence did arrive mid-window, days would no
    longer be independent and running them in parallel would score some of them against
    state that had already absorbed their own results.
    """
    ratings = PyramidRatings()
    ratings.queue(load_matches(families=("main", "qual_chall", "futures"),
                               since=ARCHIVE_FROM))
    days = day_directories(ROOT)
    if not days:
        return [], {}
    first = dt.date(int(days[0].parent.parent.name),
                    MONTHS[days[0].parent.name], int(days[0].name))
    last = dt.date(int(days[-1].parent.parent.name),
                   MONTHS[days[-1].parent.name], int(days[-1].name))
    ratings.advance_to(first)
    arriving = ratings.pending_after(last)
    if arriving:
        raise RuntimeError(
            f"{arriving} archive matches fall inside the scored window {first}..{last}. "
            f"Days are not independent and must be walked in order, not in parallel."
        )
    print(f"rating state frozen at {ratings.absorbed_through}; "
          f"0 archive matches arrive between {first} and {last}", flush=True)
    frozen = ratings.snapshot()

    observations: list[Observation] = []
    excluded: collections.Counter[str] = collections.Counter()
    with ProcessPoolExecutor(max_workers=WORKERS, initializer=_set_snapshot,
                             initargs=(frozen,)) as pool:
        for text, markets, linked, produced, counts in pool.map(
            one_day, [str(d) for d in days], chunksize=1
        ):
            observations.extend(produced)
            excluded.update(counts)
            day = Path(text)
            print(f"  {day.parent.parent.name}-{day.parent.name}-{day.name}: "
                  f"{markets:>4} markets, {linked:>3} linked, "
                  f"{len(observations):>5} observations", flush=True)
            sys.stdout.flush()
    return observations, dict(excluded)


def _first(row: object) -> dt.date:
    """Cluster key: the match day. Matches on one day share tournament conditions."""
    return cast(tuple[dt.date, float], row)[0]


def _mean_ci(rows: list[tuple[dt.date, float]]) -> tuple[float, float, float]:
    mean = math.fsum(v for _d, v in rows) / len(rows)

    def statistic(sample: object) -> float:
        pairs = cast(list[tuple[dt.date, float]], sample)
        return math.fsum(v for _d, v in pairs) / len(pairs)

    lo, hi = clustered_bootstrap(rows, statistic=statistic,
                                 cluster_of=_first, draws=BOOTSTRAP_DRAWS)
    return mean, lo, hi


def report(observations: list[Observation], horizon: int) -> None:
    at_horizon = [o for o in observations if o.horizon == horizon]
    print(f"\n{'=' * 78}\nT-{horizon}s — {len(at_horizon):,} scored markets")
    for tour in ("ATP", "WTA"):
        block = [o for o in at_horizon if o.tour == tour]
        if len(block) < 50:
            print(f"\n{tour}: {len(block)} markets — too few to score")
            continue
        overround = math.fsum(o.overround for o in block) / len(block)
        market_ll = -math.fsum(math.log(o.market_p if o.won_a else 1 - o.market_p)
                               for o in block) / len(block)
        model_ll = -math.fsum(math.log(o.model_p if o.won_a else 1 - o.model_p)
                              for o in block) / len(block)
        print(f"\n{tour}  ({len(block):,} markets)")
        print(f"  exchange overround (best-back both sides)  {overround:.4f}  "
              f"= {100 * (overround - 1):.2f}% cost of crossing both sides")
        print(f"  exchange log loss                          {market_ll:.5f}")
        print(f"  pyramid Elo log loss                       {model_ll:.5f}"
              f"   ({'better' if model_ll < market_ll else 'worse'} than the price)")

        # Residual test: does the model explain what the exchange price missed?
        gains: list[tuple[dt.date, float]] = []
        for weight in (0.1,):
            for o in block:
                z = _logit(o.market_p) + weight * (_logit(o.model_p) - _logit(o.market_p))
                p = _sigmoid(z)
                gains.append((o.date,
                              math.log(p if o.won_a else 1 - p)
                              - math.log(o.market_p if o.won_a else 1 - o.market_p)))
        mean, lo, hi = _mean_ci(gains)
        verdict = ("adds information" if lo > 0 else
                   "destroys information" if hi < 0 else "adds nothing measurable")
        print(f"  10% weight on the model                    {mean:+.6f} nats  "
              f"[{lo:+.6f}, {hi:+.6f}] -> {verdict}")

        results: list[BetResult] = []
        for o in block:
            for probability, price, won in ((o.model_p, o.back_a, bool(o.won_a)),
                                            (1 - o.model_p, o.back_b, not o.won_a)):
                if price <= 1.0:
                    continue
                if probability * (1 + (price - 1) * (1 - float(COMMISSION))) <= 1.0:
                    continue
                results.append(BetResult(cluster=o.date, odds=price, stake=1.0,
                                         won=won, commission=float(COMMISSION)))
        if len(results) < 30:
            print(f"  money: {len(results)} bets — too few to score")
            continue
        print("  " + summarise_bets(results, bootstrap=BOOTSTRAP_DRAWS).report("money"))


def main() -> None:
    print("collecting (one pass, every horizon)")
    observations, excluded = collect()
    print(f"\nexclusions: {dict(sorted(excluded.items()))}")
    if not observations:
        print("nothing scored")
        return
    for horizon in HORIZONS:
        report(observations, horizon)


if __name__ == "__main__":
    main()
