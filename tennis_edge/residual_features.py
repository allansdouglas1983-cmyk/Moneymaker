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
from tennis_edge.serve_stats import ServeEstimator

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

#: Books whose quotes ride along on each row so a money test can settle at them later.
#: Betfair is the venue that matters — the only one charging commission rather than burying
#: its margin in the quote, and the only one that cannot limit a winning account.
SETTLE_BOOKS = ("pinnacle", "b365", "max", "betfair")

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
    estimator.queue(load_matches(families=("main", "qual_chall"), since=ARCHIVE_FROM,
                                 require_serve_stats=True))
    pyramid.queue(load_matches(families=("main", "qual_chall", "futures"),
                               since=ARCHIVE_FROM))
    rows: list[FeatureRow] = []
    for day, batch in group_by_day(matches):
        estimator.advance_to(day)
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
    vintage = latest_vintage(default_vintage_root())
    if vintage is None:
        raise RuntimeError("no corpus vintage on disk — run the refresh first")
    path = Path(cache_path) if cache_path is not None else default_cache_path()
    key = _cache_key(vintage)

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
