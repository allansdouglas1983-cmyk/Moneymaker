"""The one residual feature builder, shared by every experiment and by the predictor.

Previously each experiment carried its own copy of the build loop. That is how two of them
drifted apart without anyone noticing, and it is why a ten-minute build was paid four times
in a single session — a divergence fix, a control, a venue and a placebo, each re-walking the
whole archive. There is now one definition, and it comes back from cache when the inputs are
unchanged.

Distinct from :mod:`tennis_edge.features`, which builds a *standalone* feature vector for a
model that predicts on its own. Everything here is a **correction to the market logit**,
which enters downstream as an unpenalised offset. Nothing in this module is a probability;
the market's view is taken as given and these say only what it missed. The two coexist
because they answer different questions, and merging them would blur which one a number came
from.

The price-leakage guard from :mod:`tennis_edge.features` applies to these names too, and is
called at import. A feature named after a book or a price would mean the model is being
shown the answer, and the fact that this set is *defined* as a residual against a price
makes the distinction easier to lose, not harder.

**The five ``pyramid_*`` features are what this programme added.** Every earlier rating was
fed only the priced main-tour corpus and was therefore blind below the main tour: a qualifier
with fifty Challenger matches looked like a debutant, and a player who had just played five
Futures matches in a week looked rested. See :mod:`tennis_edge.pyramid`.

**No-lookahead by construction rather than by care.** The rating engine observes a day's
results only after every match in that day has been priced. The serve and pyramid states
hold each tournament back until its week has certainly closed, because the archive dates a
match by the Monday of its tournament week and splitting inside a tournament would let its
own later rounds inform it.
"""
from __future__ import annotations

import datetime as dt
import math
from pathlib import Path

from tennis_edge.backtest import market_probability
from tennis_edge.corpus import Match, default_vintage_root, group_by_day, load_corpus
from tennis_edge.devig import DevigMethod
from tennis_edge.feature_cache import (
    FEATURE_SET_VERSION,
    CacheKey,
    FeatureRow,
    archive_digest,
    load_cache,
    write_cache,
)
from tennis_edge.features import assert_no_price_features
from tennis_edge.pyramid import PyramidRatings, pyramid_features
from tennis_edge.ratings import RatingEngine, elo_expected
from tennis_edge.refresh import Vintage, latest_vintage
from tennis_edge.sackmann import available_files, load_matches
from tennis_edge.durability import DurabilityEstimator, durability_features
from tennis_edge.serve_detail import DetailEstimator, serve_detail_features
from tennis_edge.serve_stats import ServeEstimator
from tennis_edge.venues import benchmark_keys, uk_settlement_keys

__all__ = [
    "PRICING_BOOK",
    "DEVIG",
    "SETTLE_BOOKS",
    "RESIDUAL_FEATURE_NAMES",
    "default_cache_path",
    "build_residual_features",
]

#: The book whose de-vigged closing price is the offset every feature corrects.
PRICING_BOOK = "b365"
DEVIG = DevigMethod.POWER
ARCHIVE_FROM = dt.date(2003, 1, 1)

#: Quotes carried on each row so a money test can settle at them later. Order matters to
#: every report that iterates it: the venues a UK resident can actually bet into come first
#: (Betfair Exchange, Bet365, Ladbrokes, Unibet), then the columns that are not places this
#: account can reach — Pinnacle, closed to the UK since 2016, and the panel maximum and
#: average, which are statistics over the table rather than counterparties. See
#: :mod:`tennis_edge.venues`; a report that headlines a benchmark as a return is a defect.
SETTLE_BOOKS = uk_settlement_keys() + benchmark_keys()

#: Every feature this builder can emit. Declared rather than discovered so the leakage guard
#: has something to check and so a downstream fit can refuse an unexpected column.
RESIDUAL_FEATURE_NAMES: tuple[str, ...] = (
    "elo_residual",
    "surface_elo_gap",
    "weighted_elo_gap",
    "rank_gap",
    "point_model_residual",
    "pyramid_elo_gap",
    "pyramid_surface_gap",
    "pyramid_tier_gap",
    "pyramid_workload_gap",
    "pyramid_rest_gap",
    # The decomposed serve/return layer. The aggregate estimator above collapses nine
    # archive fields into one ratio; these are the components it discards, and first/second
    # serve split and break-point performance are the two the literature cites most.
    "first_serve_rate_gap",
    "first_win_rate_gap",
    "second_win_rate_gap",
    "ace_rate_gap",
    "double_fault_rate_gap",
    "break_save_rate_gap",
    "return_rate_gap",
    # Three things a scalar rating cannot hold: who beats whom regardless of rating, who
    # hands the market a settled loss without being beaten, and who arrives tired or on a
    # surface they have not competed on since the last event.
    "h2h_gap",
    "retirement_risk_gap",
    "workload_minutes_gap",
    "workload_long_gap",
    "surface_switch_gap",
)

#: Minimum main-tour matches per player before a row is priceable. Below this the rating is
#: a prior wearing a number.
MIN_MAIN_TOUR_MATCHES = 5

#: Serve points of coverage before the point model's view is admitted.
MIN_SERVE_COVERAGE = 300.0


def default_cache_path() -> Path:
    """Beside the corpus vintages, since the vintage is what the cache is keyed to."""
    return default_vintage_root() / "residual-feature-cache.jsonl"


def _logit(p: float) -> float:
    q = min(max(p, 1e-12), 1 - 1e-12)
    return math.log(q / (1 - q))


def _cache_key(vintage: Vintage) -> CacheKey:
    return CacheKey(
        feature_set_version=FEATURE_SET_VERSION,
        corpus_vintage=vintage.vintage_id,
        corpus_manifest_digest=vintage.manifest_digest,
        archive_digest=archive_digest(
            available_files(families=("main", "qual_chall", "futures"))
        ),
    )


def _build(matches: tuple[Match, ...]) -> list[FeatureRow]:
    engine = RatingEngine()
    pyramid = PyramidRatings()
    estimator = ServeEstimator()
    detail = DetailEstimator()
    durability = DurabilityEstimator()
    serve_rows = list(load_matches(families=("main", "qual_chall"), since=ARCHIVE_FROM,
                                   require_serve_stats=True))
    estimator.queue(serve_rows)
    detail.queue(serve_rows)
    # Durability sees every match, retirements included: a retirement is the event this
    # layer exists to count, and the serve-stat filter above would drop all of them.
    durability.queue(load_matches(families=("main", "qual_chall"), since=ARCHIVE_FROM))
    pyramid.queue(load_matches(families=("main", "qual_chall", "futures"),
                               since=ARCHIVE_FROM))
    rows: list[FeatureRow] = []
    for day, batch in group_by_day(matches):
        estimator.advance_to(day)
        detail.advance_to(day)
        durability.advance_to(day)
        pyramid.advance_to(day)
        for match in sorted(batch, key=lambda m: (m.tour, m.player_a, m.player_b)):
            market = market_probability(match, book=PRICING_BOOK, method=DEVIG)
            if market is None:
                continue
            tour, a, b = match.tour, match.player_a, match.player_b
            if (engine.matches_played(tour, a) < MIN_MAIN_TOUR_MATCHES
                    or engine.matches_played(tour, b) < MIN_MAIN_TOUR_MATCHES):
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
            if estimate is not None and estimate.coverage >= MIN_SERVE_COVERAGE:
                point = estimate.match_probability(best_of=match.best_of)
                features["point_model_residual"] = _logit(point) - _logit(market)
            features.update(pyramid_features(pyramid, tour, a, b, day, match.surface))
            features.update(serve_detail_features(detail, tour, a, b))
            features.update(durability_features(durability, tour, a, b,
                                                surface=match.surface, when=day))

            odds_a: dict[str, float] = {}
            odds_b: dict[str, float] = {}
            for book in SETTLE_BOOKS:
                pair = match.odds.pair(book)
                if pair is not None:
                    odds_a[book], odds_b[book] = float(pair[0]), float(pair[1])
            rows.append(FeatureRow(
                date=match.match_date, tour=tour, player_a=a, player_b=b,
                market_logit=_logit(market), features=features,
                won=1 if match.winner_is_a else 0, odds_a=odds_a, odds_b=odds_b,
            ))
        engine.observe(batch)
    return rows


def build_residual_features(
    *, cache_path: Path | str | None = None, refresh: bool = False, quiet: bool = False
) -> list[FeatureRow]:
    """Features for the whole priced corpus, from cache when the inputs are unchanged.

    ``refresh=True`` rebuilds and overwrites. That is the escape hatch for the one change
    the key cannot see: an edit to this file that nobody remembered to record in
    ``FEATURE_SET_VERSION``.
    """
    root = default_vintage_root()
    vintage = latest_vintage(root)
    if vintage is None:
        raise RuntimeError("no corpus vintage on disk — run the refresh first")
    path = Path(cache_path) if cache_path is not None else default_cache_path()
    key = _cache_key(vintage)
    # Which root supplied the data is decided by an environment variable and was, until this
    # was printed, invisible. Two roots existed on one machine with different vintages AND
    # different Sackmann archives; a run against the wrong one produced a plausible table
    # from a corpus the deployed model had never seen. The cache key catches a stale cache,
    # but nothing caught the wrong root, because both were internally consistent. So the
    # provenance is stated on every build.
    if not quiet:
        print(f"corpus: {root} :: {vintage.vintage_id} "
              f"(manifest {vintage.manifest_digest[:19]}…)", flush=True)

    if not refresh:
        cached = load_cache(path, key=key)
        if cached is not None:
            if not quiet:
                print(f"features: {len(cached):,} rows from cache ({path.name})",
                      flush=True)
            return cached

    if not quiet:
        print("features: cache miss — building (walks the whole archive, ~10 min)",
              flush=True)
    matches, _stats = load_corpus(vintage.root)
    rows = _build(matches)
    write_cache(path, rows, key=key)
    if not quiet:
        print(f"features: {len(rows):,} rows built and cached -> {path}", flush=True)
    return rows


assert_no_price_features(RESIDUAL_FEATURE_NAMES)
