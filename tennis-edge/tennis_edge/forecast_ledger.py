"""The automatic forecast ledger: the served model graded on every completed match.

The manual tip ledger grows only when a price is typed into the site; a month after
going live it held zero rows, so the scorecard was measuring nothing. This module makes
the predictor's own performance record accumulate without anyone's help: each weekly
refresh, BEFORE rebuilding the state, the previous run's committed ``live-state.json``
scores every corpus match completed since it was built. That file's pre-match existence
is enforced by git history — the state provably could not contain the results it is being
graded on.

The row's probability must be exactly what the site would have served: the same
:func:`live_features`, the same :meth:`ResidualModel.probability`, no re-derivation.
Absences are typed, never defaulted — the aggregate reader needs to see the denominator
(SPEC-038's discipline, applied to the personal scorecard).
"""
from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Sequence

from tennis_edge.corpus import Completion, Match
from tennis_edge.live_state import StateSnapshot, live_features
from tennis_edge.residual_model import ResidualModel

FORECASTS_KIND = "tennis-edge-forecasts-v1"

#: Completions whose winner field grades a win probability. WALKOVER/ABANDONED and the
#: rest carry no gradeable result for a match-winner forecast.
_GRADEABLE = frozenset({Completion.COMPLETED, Completion.RETIRED, Completion.AWARDED,
                        Completion.DISQUALIFIED})

Key = tuple[str, str, str, str]


def row_key(row: dict[str, object]) -> Key:
    return (str(row["date"]), str(row["tour"]),
            str(row["player_a"]), str(row["player_b"]))


def weekly_forecasts(
    snapshot: StateSnapshot,
    model: ResidualModel,
    matches: Sequence[Match],
    existing: Iterable[Key],
) -> tuple[list[dict[str, object]], dict[str, int]]:
    """Score the snapshot's model view on matches it could not have absorbed.

    Returns (new rows, typed exclusion counts). A match dated before ``snapshot.as_of``
    is refused: the state walk absorbed results strictly before that date, so grading it
    would let the model see its own answer. Everything else that cannot produce a row
    says why, by name, so the scorecard's denominator stays honest.
    """
    seen = set(existing)
    rows: list[dict[str, object]] = []
    exclusions: dict[str, int] = defaultdict(int)

    for m in matches:
        key = (m.match_date.isoformat(), m.tour, m.player_a, m.player_b)
        if key in seen:
            exclusions["ALREADY_RECORDED"] += 1
            continue
        if m.match_date < snapshot.as_of:
            exclusions["STATE_ALREADY_ABSORBED"] += 1
            continue
        if m.completion not in _GRADEABLE:
            exclusions["NOT_GRADEABLE"] += 1
            continue
        odds_a, odds_b = m.odds.b365_a, m.odds.b365_b
        if odds_a is None or odds_b is None or odds_a <= 1.0 or odds_b <= 1.0:
            exclusions["NO_MARKET_PRICE"] += 1
            continue
        inv_a, inv_b = 1.0 / odds_a, 1.0 / odds_b
        p_market = inv_a / (inv_a + inv_b)
        features = live_features(
            snapshot, m.tour, m.player_a, m.player_b,
            surface=m.surface, best_of=m.best_of, market_probability=p_market,
            match_date=m.match_date, rank_a=m.rank_a, rank_b=m.rank_b)
        if not features:
            exclusions["INSUFFICIENT_STATE"] += 1
            continue
        p_model = model.probability(math.log(p_market / (1.0 - p_market)), features)
        seen.add(key)
        rows.append({
            "date": m.match_date.isoformat(),
            "tour": m.tour,
            "player_a": m.player_a,
            "player_b": m.player_b,
            "surface": m.surface,
            "p_model": p_model,
            "p_market": p_market,
            "won_a": m.winner_is_a,
            "completion": m.completion.value,
            "state_as_of": snapshot.as_of.isoformat(),
            "model_digest": model.digest,
        })
    return rows, dict(exclusions)
