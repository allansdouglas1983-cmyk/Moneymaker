"""Everything pricing needs about each player at a date, snapshotted so fixtures are cheap.

This is the module that turns the model into a usable tool. Before it, a fixture could only
be priced with features handed over by hand, which is a demonstration rather than a product;
computing them properly meant walking the whole corpus and archive, ten minutes per run.

The state a prediction actually needs is small: a few scalars per player. So the walk happens
once, the scalars are written to disk with the date they describe, and pricing an upcoming
match is a dictionary lookup.

**The features here must match the ones the model was fitted on, expression for expression.**
:mod:`tennis_edge.residual_features` builds them over a whole corpus with live engines;
this rebuilds the same quantities from frozen scalars. Any drift between the two is a
predictor quietly using a different feature set than the harness that validated it, which
would be invisible in the output — so the expressions are kept side by side and
``RESIDUAL_FEATURE_NAMES`` bounds what either may emit.

**Pricing backwards is refused.** A snapshot taken on the 20th contains ratings that already
absorbed everything up to the 20th, so pricing a match from the 19th with it would be scoring
a result the state has already seen. That is the single easiest way to manufacture a
spectacular backtest, and it raises rather than warns.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from tennis_edge.point_model import match_probability
from tennis_edge.ratings import elo_expected

__all__ = [
    "PlayerState",
    "StateSnapshot",
    "live_features",
    "save_state",
    "load_state",
]

_KIND = "tennis-edge-live-state-v1"

#: Mirrors ``residual_features``. Kept as separate constants rather than imported so a
#: change to one is a visible divergence rather than a silent shared edit.
MIN_MAIN_TOUR_MATCHES = 5
MIN_SERVE_COVERAGE = 300.0
MIN_PYRAMID_MATCHES = 5
WORKLOAD_DAYS = 14
#: Mirrors durability.MIN_H2H_MEETINGS. Below this the pairwise record is noise wearing a
#: ratio, and the feature is reported absent rather than as an even split.
MIN_H2H_MEETINGS = 2
#: Mirrors durability.H2H_PRIOR: pseudo-meetings of "even" mixed into the rate.
H2H_PRIOR = 3.0
LONG_WORKLOAD_DAYS = 28


@dataclass(frozen=True)
class PlayerState:
    """One player's frozen scalars. Everything a feature needs and nothing else."""

    elo: float
    weighted_elo: float
    surface_elo: Mapping[str, float]
    matches: int
    last_played: str | None
    #: Shrunk serve and return rates at the snapshot date, plus their coverage. Stored
    #: post-shrinkage because the shrinkage is time-dependent (recency decay) and
    #: re-deriving it later from raw counts would silently use the wrong date.
    serve_rate: float
    return_rate: float
    serve_points: float
    serve_matches: int
    pyramid_elo: float
    pyramid_surface_elo: Mapping[str, float]
    pyramid_matches: int
    pyramid_tour_share: float
    pyramid_last_played: str | None
    pyramid_recent_14d: int
    #: The decomposed serve/return layer, already shrunk toward the tour baseline at the
    #: snapshot date. Stored post-shrinkage for the same reason as ``serve_rate``: the
    #: shrinkage depends on how much the player had played *by then*, and re-deriving it
    #: later would quietly use the wrong denominator.
    serve_detail: Mapping[str, float] = field(default_factory=dict)
    #: Durability. ``retirement_rate`` is shrunk toward the tour rate; the workload figures
    #: are raw counts over their windows, because "no matches in a fortnight" is an
    #: observation and not a missing value.
    retirement_rate: float = 0.0
    workload_minutes_14d: float = 0.0
    workload_long_28d: int = 0
    last_surface: str = ""
    #: Latest-known ranking, from the player's most recent corpus match that carried one.
    #: Knowledge-time safe: published with a strictly earlier match than anything priced
    #: from this snapshot. ``None`` when no match ever carried a rank — served through the
    #: same ``or 500`` imputation training used, never dropped (TE-0017 S3).
    rank: int | None = None
    #: The date of the match that supplied ``rank``, for staleness diagnostics.
    rank_date: str | None = None

    def surface_rating(self, surface: str) -> float:
        """Surface rating, falling back to the overall one for an unplayed surface.

        A player's first match on clay is not a claim that they are average on clay; the
        overall rating is the honest prior and it is what the training-time engine uses.
        """
        return self.surface_elo.get(surface or "Hard", self.elo)

    def pyramid_surface_rating(self, surface: str) -> float:
        return self.pyramid_surface_elo.get(surface or "Hard", self.pyramid_elo)


@dataclass(frozen=True)
class StateSnapshot:
    """Per-player state as of one date, with the corpus vintage it came from."""

    as_of: dt.date
    corpus_vintage: str
    players: Mapping[tuple[str, str], PlayerState]
    tour_serve_baseline: Mapping[str, float]
    #: Tour-wide retirement rate, the target every player rate is shrunk toward.
    tour_retirement_baseline: Mapping[str, float] = field(default_factory=dict)
    #: Head-to-head counts, keyed by (tour, first-sorted name, second-sorted name).
    head_to_head: Mapping[tuple[str, str, str], tuple[int, int]] = field(
        default_factory=dict)

    def days_old(self, today: dt.date) -> int:
        return (today - self.as_of).days

    def get(self, tour: str, player: str) -> PlayerState | None:
        return self.players.get((tour, player))

    def meetings(self, tour: str, player_a: str, player_b: str) -> tuple[int, int] | None:
        """Wins by A then by B, or ``None`` when the pair has not met enough times.

        Stored once under the sorted pair, so the caller gets the same record whichever way
        round the fixture is written.
        """
        first, second = sorted((player_a, player_b))
        record = self.head_to_head.get((tour, first, second))
        if record is None or sum(record) < MIN_H2H_MEETINGS:
            return None
        return record if player_a == first else (record[1], record[0])


def _logit(p: float) -> float:
    q = min(max(p, 1e-12), 1 - 1e-12)
    return math.log(q / (1 - q))


def _days_since(stamp: str | None, when: dt.date) -> int | None:
    if stamp is None:
        return None
    return (when - dt.date.fromisoformat(stamp)).days


def live_features(
    snapshot: StateSnapshot,
    tour: str,
    player_a: str,
    player_b: str,
    *,
    surface: str,
    best_of: int,
    market_probability: float,
    match_date: dt.date | None = None,
    rank_a: int | None = None,
    rank_b: int | None = None,
) -> dict[str, float]:
    """Residual features for an upcoming match, or ``{}`` when the state cannot support them.

    Returning nothing rather than zeros is the same discipline as everywhere else: a zero gap
    claims the two players are equal, and absence claims nothing. A debutant priced with
    zeros would sit at the exact centre of every distribution, which is both false and
    systematically so.

    ``rank_gap`` is always served (TE-0017 S3): training built it on every row via the
    ``or 500`` imputation, so the coefficients were fitted jointly with it, and serving the
    rank-absent branch scores a feature set nobody measured. A caller-supplied rank is
    fixture-time and wins; the snapshot's latest-known rank is the fallback; a player with
    no known rank imputes 500 exactly as training did.
    """
    when = match_date or snapshot.as_of
    if when < snapshot.as_of:
        raise ValueError(
            f"cannot price {when} from a snapshot taken on {snapshot.as_of}: the match is "
            f"before the snapshot, so the state has already absorbed its result"
        )
    a = snapshot.get(tour, player_a)
    b = snapshot.get(tour, player_b)
    if a is None or b is None:
        return {}
    if a.matches < MIN_MAIN_TOUR_MATCHES or b.matches < MIN_MAIN_TOUR_MATCHES:
        return {}

    market_logit = _logit(market_probability)
    blended_a = 0.5 * (a.elo + a.surface_rating(surface))
    blended_b = 0.5 * (b.elo + b.surface_rating(surface))
    features = {
        "elo_residual": _logit(elo_expected(blended_a, blended_b)) - market_logit,
        "surface_elo_gap": (a.surface_rating(surface)
                            - b.surface_rating(surface)) / 400.0,
        "weighted_elo_gap": (a.weighted_elo - b.weighted_elo) / 400.0,
    }
    effective_rank_a = rank_a if rank_a is not None else a.rank
    effective_rank_b = rank_b if rank_b is not None else b.rank
    # `or 500` and not `if None`: the training expression treats 0 the same way, and this
    # must be that expression to the character (residual_features builds it identically).
    features["rank_gap"] = (math.log1p(effective_rank_b or 500)
                            - math.log1p(effective_rank_a or 500))

    baseline = snapshot.tour_serve_baseline.get(tour, 0.62)
    if min(a.serve_points, b.serve_points) >= MIN_SERVE_COVERAGE:
        # f_ij = f_t + (f_i - f_av) - (g_j - g_av), as in serve_stats.estimate.
        return_average = 1.0 - baseline
        p_a = min(max(baseline + (a.serve_rate - baseline)
                      - (b.return_rate - return_average), 0.30), 0.90)
        p_b = min(max(baseline + (b.serve_rate - baseline)
                      - (a.return_rate - return_average), 0.30), 0.90)
        point = match_probability(p_a, 1.0 - p_b, best_of=best_of)
        features["point_model_residual"] = _logit(point) - market_logit

    # The decomposed serve/return layer. Both players need the rates or the whole layer is
    # absent — a gap computed against a default is a claim about a player nobody measured.
    if a.serve_detail and b.serve_detail:
        for component in sorted(set(a.serve_detail) & set(b.serve_detail)):
            features[f"{component}_gap"] = a.serve_detail[component] - b.serve_detail[component]

    # Durability. Unlike the layers above these are always available: "no matches in the
    # last fortnight" is an observation about a player, not a missing one.
    features.update({
        "retirement_risk_gap": a.retirement_rate - b.retirement_rate,
        "workload_minutes_gap": (a.workload_minutes_14d - b.workload_minutes_14d) / 60.0,
        "workload_long_gap": float(a.workload_long_28d - b.workload_long_28d),
        "surface_switch_gap": float(_switched(a, surface) - _switched(b, surface)),
    })
    meetings = snapshot.meetings(tour, player_a, player_b)
    if meetings is not None:
        wins_a, wins_b = meetings
        rate = (wins_a + 0.5 * H2H_PRIOR) / (wins_a + wins_b + H2H_PRIOR)
        features["h2h_gap"] = math.log(rate / (1.0 - rate))

    if (a.pyramid_matches >= MIN_PYRAMID_MATCHES
            and b.pyramid_matches >= MIN_PYRAMID_MATCHES):
        rest_a = _days_since(a.pyramid_last_played, when)
        rest_b = _days_since(b.pyramid_last_played, when)
        if rest_a is not None and rest_b is not None:
            features.update({
                "pyramid_elo_gap": (a.pyramid_elo - b.pyramid_elo) / 400.0,
                "pyramid_surface_gap": (a.pyramid_surface_rating(surface)
                                        - b.pyramid_surface_rating(surface)) / 400.0,
                "pyramid_workload_gap": float(a.pyramid_recent_14d - b.pyramid_recent_14d),
                "pyramid_rest_gap": (min(rest_a, 180) - min(rest_b, 180)) / 30.0,
                "pyramid_tier_gap": a.pyramid_tour_share - b.pyramid_tour_share,
            })
    return features


def _switched(state: PlayerState, surface: str) -> int:
    """1 when this player's last match was on a different surface, else 0.

    A player arriving from clay onto grass has had no competitive match on the surface. The
    surface Elo knows their history there; it does not know they have just changed.
    """
    if not state.last_surface or not surface:
        return 0
    return int(state.last_surface != surface)


def save_state(path: Path | str, snapshot: StateSnapshot) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "kind": _KIND,
        "as_of": snapshot.as_of.isoformat(),
        "corpus_vintage": snapshot.corpus_vintage,
        "tour_serve_baseline": dict(snapshot.tour_serve_baseline),
        "tour_retirement_baseline": dict(snapshot.tour_retirement_baseline),
        "players": [
            {"tour": tour, "name": name, **_player_payload(state)}
            for (tour, name), state in sorted(snapshot.players.items())
        ],
        "head_to_head": [
            {"tour": t, "first": f, "second": s, "wins": list(w)}
            for (t, f, s), w in sorted(snapshot.head_to_head.items())
        ],
    }
    scratch = target.with_suffix(target.suffix + ".partial")
    scratch.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
                       encoding="utf-8")
    scratch.replace(target)


def _player_payload(state: PlayerState) -> dict[str, object]:
    return {
        "elo": state.elo, "weighted_elo": state.weighted_elo,
        "surface_elo": dict(state.surface_elo), "matches": state.matches,
        "last_played": state.last_played, "serve_rate": state.serve_rate,
        "return_rate": state.return_rate, "serve_points": state.serve_points,
        "serve_matches": state.serve_matches, "pyramid_elo": state.pyramid_elo,
        "pyramid_surface_elo": dict(state.pyramid_surface_elo),
        "pyramid_matches": state.pyramid_matches,
        "pyramid_tour_share": state.pyramid_tour_share,
        "pyramid_last_played": state.pyramid_last_played,
        "pyramid_recent_14d": state.pyramid_recent_14d,
        "serve_detail": dict(state.serve_detail),
        "retirement_rate": state.retirement_rate,
        "workload_minutes_14d": state.workload_minutes_14d,
        "workload_long_28d": state.workload_long_28d,
        "last_surface": state.last_surface,
        "rank": state.rank,
        "rank_date": state.rank_date,
    }


def load_state(path: Path | str) -> StateSnapshot:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("kind") != _KIND:
        raise ValueError(f"not a state snapshot: {path}")
    players = {
        (entry["tour"], entry["name"]): PlayerState(
            **{k: v for k, v in entry.items() if k not in {"tour", "name"}}
        )
        for entry in raw["players"]
    }
    head_to_head = {
        (entry["tour"], entry["first"], entry["second"]): (entry["wins"][0],
                                                           entry["wins"][1])
        for entry in raw.get("head_to_head", [])
    }
    return StateSnapshot(
        as_of=dt.date.fromisoformat(raw["as_of"]),
        corpus_vintage=raw["corpus_vintage"],
        players=players,
        tour_serve_baseline=raw["tour_serve_baseline"],
        tour_retirement_baseline=raw.get("tour_retirement_baseline", {}),
        head_to_head=head_to_head,
    )





def build_state(as_of: dt.date | None = None) -> StateSnapshot:
    """Walk the corpus and archive once and freeze what pricing needs.

    Every engine is advanced exactly as :mod:`tennis_edge.residual_features` advances it, and
    the walk observes each day's results only after that day is done — so the snapshot
    describes the state *entering* ``as_of`` rather than after it. That is the same boundary
    the model was fitted against, and getting it wrong by one day is the difference between a
    forecast and a memory.
    """
    from tennis_edge.corpus import default_vintage_root, group_by_day, load_corpus
    from tennis_edge.durability import DurabilityEstimator
    from tennis_edge.pyramid import PyramidRatings
    from tennis_edge.ratings import RatingEngine
    from tennis_edge.refresh import latest_vintage
    from tennis_edge.sackmann import load_matches
    from tennis_edge.serve_detail import DetailEstimator
    from tennis_edge.serve_stats import ServeEstimator, td_player_key

    vintage = latest_vintage(default_vintage_root())
    if vintage is None:
        raise RuntimeError("no corpus vintage on disk — run the refresh first")
    cutoff = as_of or dt.date.today()

    matches, _stats = load_corpus(vintage.root)
    engine = RatingEngine()
    pyramid = PyramidRatings()
    estimator = ServeEstimator()
    detail = DetailEstimator()
    durability = DurabilityEstimator()
    serve_rows = list(load_matches(families=("main", "qual_chall"),
                                   since=dt.date(2003, 1, 1), require_serve_stats=True))
    estimator.queue(serve_rows)
    detail.queue(serve_rows)
    # Durability sees every match, retirements included: a retirement is the event the
    # layer exists to count, and the serve-stat filter above would drop all of them.
    durability.queue(load_matches(families=("main", "qual_chall"), since=dt.date(2003, 1, 1)))
    pyramid.queue(load_matches(families=("main", "qual_chall", "futures"),
                               since=dt.date(2003, 1, 1)))

    seen: set[tuple[str, str]] = set()
    # Latest-known rank per player, from the most recent match row that carried one. The
    # walk stops strictly before the cutoff, so every rank here was published with an
    # earlier match than anything this snapshot will price (TE-0017 S3).
    latest_rank: dict[tuple[str, str], tuple[int, str]] = {}
    for day, batch in group_by_day(matches):
        if day >= cutoff:
            break
        estimator.advance_to(day)
        detail.advance_to(day)
        durability.advance_to(day)
        pyramid.advance_to(day)
        engine.observe(batch)
        for match in batch:
            seen.add((match.tour, match.player_a))
            seen.add((match.tour, match.player_b))
            if match.rank_a is not None:
                latest_rank[(match.tour, match.player_a)] = (match.rank_a,
                                                             day.isoformat())
            if match.rank_b is not None:
                latest_rank[(match.tour, match.player_b)] = (match.rank_b,
                                                             day.isoformat())
    estimator.advance_to(cutoff)
    detail.advance_to(cutoff)
    durability.advance_to(cutoff)
    pyramid.advance_to(cutoff)

    baselines = {tour: estimator.tour_serve_average(tour) for tour in ("ATP", "WTA")}
    retirement_baselines = {tour: durability.retirement_baseline(tour)
                            for tour in ("ATP", "WTA")}
    players: dict[tuple[str, str], PlayerState] = {}
    for tour, name in sorted(seen):
        key = td_player_key(name)
        if key is None:
            continue
        serve, returned, points, serve_matches = estimator.shrunk_for(tour, key, cutoff)
        rest = engine.days_since_last(tour, name, cutoff)
        pyramid_rest = pyramid.days_since_last(tour, name, cutoff)
        known_rank = latest_rank.get((tour, name))
        players[(tour, name)] = PlayerState(
            elo=engine.elo(tour, name),
            weighted_elo=engine.weighted_elo(tour, name),
            surface_elo={s: engine.surface_elo(tour, name, s)
                         for s in ("Hard", "Clay", "Grass")},
            matches=engine.matches_played(tour, name),
            last_played=None if rest is None
            else (cutoff - dt.timedelta(days=rest)).isoformat(),
            serve_rate=serve, return_rate=returned, serve_points=points,
            serve_matches=serve_matches,
            pyramid_elo=pyramid.elo(tour, name),
            pyramid_surface_elo={s: pyramid.surface_elo(tour, name, s)
                                 for s in ("Hard", "Clay", "Grass")},
            pyramid_matches=pyramid.matches_played(tour, name),
            pyramid_tour_share=pyramid.tour_level_share(tour, name) or 0.0,
            pyramid_last_played=None if pyramid_rest is None
            else (cutoff - dt.timedelta(days=pyramid_rest)).isoformat(),
            pyramid_recent_14d=pyramid.matches_in_last(tour, name, cutoff, WORKLOAD_DAYS),
            serve_detail=_detail_rates(detail, tour, name),
            retirement_rate=durability.record(tour, name).retirement_rate(
                baseline=retirement_baselines.get(tour, 0.03)),
            workload_minutes_14d=float(
                durability.record(tour, name).minutes_within(cutoff, WORKLOAD_DAYS)),
            workload_long_28d=durability.record(tour, name).long_matches_within(
                cutoff, LONG_WORKLOAD_DAYS),
            last_surface=durability.record(tour, name).last_surface,
            rank=None if known_rank is None else known_rank[0],
            rank_date=None if known_rank is None else known_rank[1],
        )
    # Head-to-head is stored once under the sorted pair, so a fixture written either way
    # round resolves to the same record. Pairs below the minimum are left out entirely
    # rather than stored as an even split nobody observed.
    meetings: dict[tuple[str, str, str], tuple[int, int]] = {}
    by_key = {(tour, td_player_key(name)): name for tour, name in players}
    for (tour, key_a, key_b), record in durability.pairs():
        name_a = by_key.get((tour, key_a))
        name_b = by_key.get((tour, key_b))
        if name_a is None or name_b is None or sum(record) < MIN_H2H_MEETINGS:
            continue
        first, second = sorted((name_a, name_b))
        wins = (record[0], record[1]) if name_a == first else (record[1], record[0])
        meetings[(tour, first, second)] = wins

    return StateSnapshot(as_of=cutoff, corpus_vintage=vintage.vintage_id,
                         players=players, tour_serve_baseline=baselines,
                         tour_retirement_baseline=retirement_baselines,
                         head_to_head=meetings)


def _detail_rates(detail: object, tour: str, name: str) -> dict[str, float]:
    """The seven decomposed serve/return rates, already shrunk toward the tour baseline.

    Empty when the player has too little coverage to shrink honestly — the same threshold
    the training-time builder uses, so a match the fit would have left without the layer is
    also left without it here.
    """
    from tennis_edge.serve_detail import MIN_POINTS

    profile = detail.profile(tour, name)  # type: ignore[attr-defined]
    if profile.serve_points < MIN_POINTS:
        return {}
    base = detail.baselines(tour)  # type: ignore[attr-defined]
    return {
        "first_serve_rate": profile.first_serve_rate(baseline=base.first_serve),
        "first_win_rate": profile.first_win_rate(baseline=base.first_win),
        "second_win_rate": profile.second_win_rate(baseline=base.second_win),
        "ace_rate": profile.ace_rate(baseline=base.ace),
        "double_fault_rate": profile.double_fault_rate(baseline=base.double_fault),
        "break_save_rate": profile.break_point_save_rate(baseline=base.break_save),
        "return_rate": profile.return_rate(baseline=base.return_won),
    }
