"""Link exchange markets to pyramid identities, graded by Betfair's own settlement.

TE-0001 closed the Challenger/ITF thesis as **untestable on free data**: the tiers where a
9% yield is claimed had no transactable prices anywhere we could reach, only an OddsPortal
aggregate that no one quotes and no one can bet into. That conclusion was correct on the
evidence then available and it is now out of date, for a reason nobody noticed at the time.

**The June ADVANCED corpus is mostly lower-tier tennis.** Its event names are Challenger and
ITF players, not the main tour, and the existing link into the priced Tennis-Data corpus was
therefore discarding most of it as ``NO_MATCH_ON_DATE`` — the markets were fine, the corpus
being joined to simply had no main-tour match to find. What was read as sparse data was a
main-tour lens over a lower-tier sample.

Two facts make the thesis testable through this door where it was not through the other:

1. **A Betfair market grades itself.** The settlement carries each runner's WINNER/LOSER
   status, so outcomes come from the exchange and no results feed is needed. This matters
   more than it sounds: Sackmann's archive stops in May 2026 for ATP and 2024 for WTA, so
   there is *no* results source for June 2026 lower-tier tennis other than Betfair itself.
2. **The prices are real and two-sided,** with commission on winnings rather than a 7–8%
   bookmaker overround, which is the cost structure TE-0001 found made the tier expensive.

**Identity is the thing that can go wrong, and it is worse here than on the main tour.** ITF
draws contain thousands of players, surnames repeat, and Betfair truncates first names
("Ma van der Merwe"), so a (surname, initial) key collides far more often than it does among
a hundred-odd tour regulars. Every resolution below refuses rather than guesses: a wrong
player is a wrong rating, a wrong prediction and a wrong settlement simultaneously, and none
of that is visible in the output. Nothing in a Betfair market definition states the tour
either, so the tour is inferred from the players and refused when both tours could claim
them.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import Enum, unique
from typing import Mapping, Protocol, Sequence

from sport_tennis.identity_bridge import _betfair_keys, normalize_name
from tennis_edge.betfair import GradingView, MarketHistory
from tennis_edge.serve_stats import PlayerKey

__all__ = [
    "PyramidLinkOutcome",
    "RatingLookup",
    "ExcludedExchangeMarket",
    "LinkedExchangeMarket",
    "ExchangeLinkResult",
    "betfair_player_key",
    "resolve_tour",
    "link_to_pyramid",
]


class RatingLookup(Protocol):
    """The read-only slice of a rating state that linking needs.

    A protocol rather than the concrete engine, because linking must work equally against
    the live walk-forward engine and against a frozen snapshot of it — and, more to the
    point, because everything linking is allowed to do to a rating state is *read* it. A
    parameter typed as the full engine would carry ``advance_to`` into a function that has
    no business absorbing a result.
    """

    def known_players(self, tour: str) -> set[PlayerKey]: ...

    def matches_for(self, tour: str, key: PlayerKey) -> int: ...


@unique
class PyramidLinkOutcome(Enum):
    """Every way a market can fail to become a scored observation.

    One name per reason, so the exclusion counts add up to the markets read. A bare
    ``continue`` inside a benchmark has already cost this programme a silent loss of 416
    rows once; every drop here is counted.
    """

    NOT_MATCH_ODDS = "NOT_MATCH_ODDS"
    NOT_TWO_RUNNERS = "NOT_TWO_RUNNERS"
    UNRESOLVED_NAME = "UNRESOLVED_NAME"
    AMBIGUOUS_TOUR = "AMBIGUOUS_TOUR"
    NO_SETTLEMENT = "NO_SETTLEMENT"
    AMBIGUOUS_SETTLEMENT = "AMBIGUOUS_SETTLEMENT"
    NO_PRICE_AT_HORIZON = "NO_PRICE_AT_HORIZON"
    THIN_RATING_HISTORY = "THIN_RATING_HISTORY"


@dataclass(frozen=True)
class ExcludedExchangeMarket:
    market_id: str
    event_name: str
    outcome: PyramidLinkOutcome
    detail: str


@dataclass(frozen=True)
class LinkedExchangeMarket:
    """A market resolved to two rated players, with the exchange's own verdict."""

    market: MarketHistory
    tour: str
    key_a: PlayerKey
    key_b: PlayerKey
    name_a: str
    name_b: str
    selection_a: int
    selection_b: int
    #: 1 when the runner mapped to ``key_a`` was settled WINNER by Betfair.
    won_a: int
    off_date: dt.date


@dataclass(frozen=True)
class ExchangeLinkResult:
    linked: tuple[LinkedExchangeMarket, ...]
    excluded: tuple[ExcludedExchangeMarket, ...]

    def counts(self) -> dict[str, int]:
        tally: dict[str, int] = {}
        for row in self.excluded:
            tally[row.outcome.value] = tally.get(row.outcome.value, 0) + 1
        return tally


def betfair_player_key(name: str) -> PlayerKey | None:
    """``(surname, initial)`` for a Betfair singles runner name, or ``None``.

    Betfair writes a runner as an abbreviated forename plus a surname, and abbreviates
    inconsistently — "F Auger-Aliassime", "Caterina Odorizzi", "Ma van der Merwe" are all the
    same shape once only the first letter of the forename is kept.

    Refused, rather than guessed at, in three cases: a bare surname (no initial to
    disambiguate thousands of ITF players), a doubles pairing (a different sport for these
    purposes), and anything that does not split into forename and surname.
    """
    if "/" in name:
        return None
    normalized = normalize_name(name)
    if not normalized:
        return None
    candidates = _betfair_keys(normalized)
    if not candidates:
        return None
    surname, initials = candidates[0]
    if not initials or not surname:
        return None
    return (surname, initials[:1])


def resolve_tour(
    key_a: PlayerKey, key_b: PlayerKey, known: Mapping[str, set[PlayerKey]]
) -> str | None:
    """The one tour whose rating pool contains both players, or ``None``.

    A Betfair market definition does not say whether it is men's or women's tennis, so the
    tour has to come from the players. Returning ``None`` when both tours could claim them —
    or when the two players appear to come from different tours, which cannot happen in a
    singles match and therefore means the keys are wrong — keeps an uncertain identity out
    of the sample instead of assigning it a rating from the wrong population.
    """
    candidates = [tour for tour, pool in sorted(known.items())
                  if key_a in pool and key_b in pool]
    return candidates[0] if len(candidates) == 1 else None


def _settled_winner(grading: GradingView, selections: Sequence[int]) -> int | None:
    """The single selection Betfair settled as WINNER, or ``None``.

    ``None`` covers both an unsettled market and a market with no unique winner — a void,
    an abandoned match, or a corrupt settlement. Those are different events but they share
    the only property that matters here: there is no outcome to score against.
    """
    winners = [s for s in selections if grading.runner_status.get(s, "").upper() == "WINNER"]
    return winners[0] if len(winners) == 1 else None


def link_to_pyramid(
    markets: Sequence[MarketHistory],
    gradings: Mapping[str, GradingView],
    ratings: RatingLookup,
    *,
    minimum_matches: int = 10,
    tours: Sequence[str] = ("ATP", "WTA"),
) -> ExchangeLinkResult:
    """Resolve markets to rated players and Betfair's settled winner.

    ``ratings`` must already have been advanced past every market's date — the caller owns
    the walk-forward, because only the caller knows what "before this market" means for the
    experiment being run. The parameter is typed as :class:`RatingLookup`, which has no way
    to advance anything, so this cannot accidentally supply a rating built from a result it
    is about to be scored on.
    """
    pools = {tour: ratings.known_players(tour) for tour in tours}
    linked: list[LinkedExchangeMarket] = []
    excluded: list[ExcludedExchangeMarket] = []

    def drop(market: MarketHistory, outcome: PyramidLinkOutcome, detail: str) -> None:
        excluded.append(ExcludedExchangeMarket(
            market.market_id, market.event_name, outcome, detail))

    for market in markets:
        if market.market_type and market.market_type.upper() not in {"MATCH_ODDS", ""}:
            drop(market, PyramidLinkOutcome.NOT_MATCH_ODDS, market.market_type)
            continue
        active = [r for r in market.runners if r.status.upper() in {"ACTIVE", "WINNER",
                                                                   "LOSER"}]
        if len(active) != 2:
            drop(market, PyramidLinkOutcome.NOT_TWO_RUNNERS, f"{len(active)} runners")
            continue

        keys = [betfair_player_key(r.name) for r in active]
        if any(k is None for k in keys) or keys[0] == keys[1]:
            drop(market, PyramidLinkOutcome.UNRESOLVED_NAME,
                 f"{[r.name for r in active]}")
            continue
        key_a, key_b = keys[0], keys[1]
        assert key_a is not None and key_b is not None

        tour = resolve_tour(key_a, key_b, pools)
        if tour is None:
            drop(market, PyramidLinkOutcome.AMBIGUOUS_TOUR,
                 f"{[r.name for r in active]} not uniquely in one tour")
            continue

        if min(ratings.matches_for(tour, key_a),
               ratings.matches_for(tour, key_b)) < minimum_matches:
            drop(market, PyramidLinkOutcome.THIN_RATING_HISTORY,
                 f"fewer than {minimum_matches} pyramid matches")
            continue

        grading = gradings.get(market.market_id)
        if grading is None:
            drop(market, PyramidLinkOutcome.NO_SETTLEMENT, "no grading view")
            continue
        winner = _settled_winner(grading, [r.selection_id for r in active])
        if winner is None:
            drop(market, PyramidLinkOutcome.AMBIGUOUS_SETTLEMENT,
                 "no unique WINNER — void, abandoned, or unsettled")
            continue

        linked.append(LinkedExchangeMarket(
            market=market, tour=tour, key_a=key_a, key_b=key_b,
            name_a=active[0].name, name_b=active[1].name,
            selection_a=active[0].selection_id, selection_b=active[1].selection_id,
            won_a=1 if winner == active[0].selection_id else 0,
            off_date=dt.datetime.fromtimestamp(
                market.market_time_ms / 1000, tz=dt.timezone.utc).date(),
        ))

    return ExchangeLinkResult(tuple(linked), tuple(excluded))
