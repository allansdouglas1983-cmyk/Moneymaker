"""Which quoted prices a person in the UK could actually have taken.

Tennis-Data publishes fourteen price columns. Three of them are not places at all, and six
of the eleven that are places cannot be reached from the UK. Nothing in the column layout
says so, and a return settled at a column nobody can bet into is a number about a
counterfactual, not about money. This module is where that distinction is written down once,
in data, so that a reporting function cannot quietly headline an unreachable venue again.

**The two questions are separate and both matter.**

*Can I place the bet?* A UK resident bets at a firm licensed by the Gambling Commission.
Pinnacle stopped accepting UK customers on 1 November 2014, ahead of the point-of-consumption
tax, and abandoned its 2016 licence application; Centrebet, Expekt, Gamebookers,
Interwetten, Sportingbet and Stan James are, for one reason or another, not UK-facing books
today. Their columns still measure something — whether a forecast beats a sharp price is a
real question — but the answer is a diagnostic and can never be a return.

*Can I keep placing it?* A traditional bookmaker prices to a margin and manages its risk by
restricting the accounts that win. Bet365 and Ladbrokes are open to a UK customer and will
both limit a consistent winner; a strategy validated only there has an expiry date it cannot
control. Betfair Exchange charges commission on winnings instead of burying a margin in the
quote and does not close accounts for winning, which is why it is the venue every money
conclusion in this project is finally judged at — and, unhelpfully, the one this data covers
for two seasons out of twenty-four.

``Max`` and ``Avg`` are the maximum and mean across the whole panel. They are summaries of
the table, not counters anyone stands at: to take ``Max`` you would need an open account at
whichever of twenty books happened to be best on that match, at that moment, before the
price moved. They are kept because the spread between ``Max`` and a single book measures how
much of an apparent return is price shopping rather than forecasting, and that control is
worth having. They are never a venue.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = [
    "Kind",
    "Access",
    "Venue",
    "VENUES",
    "by_key",
    "uk_settlement_keys",
    "benchmark_keys",
    "parsed_keys",
]


class Kind(Enum):
    """What sort of thing the column is."""

    BOOKMAKER = "BOOKMAKER"
    EXCHANGE = "EXCHANGE"
    #: A statistic over the other columns. Not a counterparty.
    SYNTHETIC = "SYNTHETIC"


class Access(Enum):
    """Whether a person in the UK can place this bet today."""

    #: Licensed by the Gambling Commission and open to UK customers.
    UK_OPEN = "UK_OPEN"
    #: A real venue, but one a UK customer cannot use.
    CLOSED_TO_UK = "CLOSED_TO_UK"
    #: Not a place. No account exists to open.
    NOT_A_VENUE = "NOT_A_VENUE"


@dataclass(frozen=True)
class Venue:
    """One price column, and everything that decides whether it may carry a conclusion."""

    #: Attribute prefix on :class:`~tennis_edge.corpus.OddsQuotes` and the key used in
    #: ``FeatureRow.odds_a`` / ``odds_b``.
    key: str
    #: Tennis-Data column prefix; the file carries ``{column}W`` and ``{column}L``.
    column: str
    name: str
    kind: Kind
    access: Access
    #: Whether the operator restricts or closes accounts that win consistently. ``None``
    #: where the question does not apply (a synthetic column has no account).
    restricts_winners: bool | None
    #: Why the access verdict is what it is. Kept next to the verdict so that a change of
    #: fact is a change of text, not a silent re-classification.
    note: str
    #: Whether the loader carries this column through onto every feature row. Columns that
    #: no reachable venue and no control needs are not parsed; the registry still records
    #: them so the omission is visible rather than accidental.
    parsed: bool


#: Every price column Tennis-Data publishes, in descending order of usefulness here.
VENUES: tuple[Venue, ...] = (
    Venue(
        key="betfair", column="BFE", name="Betfair Exchange",
        kind=Kind.EXCHANGE, access=Access.UK_OPEN, restricts_winners=False,
        note="UK exchange. Charges commission on net winnings rather than pricing to a "
             "margin, and does not close an account for winning — the only venue in this "
             "table where a proven edge could be used repeatedly. Prices appear in the "
             "data from 2025 only, which is the whole difficulty.",
        parsed=True,
    ),
    Venue(
        key="b365", column="B365", name="Bet365",
        kind=Kind.BOOKMAKER, access=Access.UK_OPEN, restricts_winners=True,
        note="UK bookmaker, open, and the only column covering the corpus end to end "
             "(2002 onward). Restricts winning accounts, so a return here is real money "
             "for as long as the account lasts and no longer.",
        parsed=True,
    ),
    Venue(
        key="ladbrokes", column="LB", name="Ladbrokes",
        kind=Kind.BOOKMAKER, access=Access.UK_OPEN, restricts_winners=True,
        note="UK high-street bookmaker, still open. Prices run 2008-2018 in this data, so "
             "it settles a decade of history but nothing recent — a second UK reading over "
             "a different window, not a substitute for Bet365.",
        parsed=True,
    ),
    Venue(
        key="unibet", column="UB", name="Unibet",
        kind=Kind.BOOKMAKER, access=Access.UK_OPEN, restricts_winners=True,
        note="UK-licensed and open, but the column stops in 2009 — before the walk-forward "
             "begins scoring in 2012, so it settles exactly zero bets. Carried so the "
             "registry is complete and so that emptiness is a visible fact rather than an "
             "absence nobody looked for.",
        parsed=True,
    ),
    Venue(
        key="pinnacle", column="PS", name="Pinnacle",
        kind=Kind.BOOKMAKER, access=Access.CLOSED_TO_UK, restricts_winners=False,
        note="Closed to UK customers on 1 November 2014 ahead of the point-of-consumption "
             "tax, applied for a UK licence in 2016 and withdrew the application. Retained "
             "purely as a difficulty benchmark: a low-margin book that famously does not "
             "limit winners, so beating it is evidence the forecast is sharp. It is NOT a "
             "place this account can bet and its return is not money.",
        parsed=True,
    ),
    Venue(
        key="max", column="Max", name="Best of panel",
        kind=Kind.SYNTHETIC, access=Access.NOT_A_VENUE, restricts_winners=None,
        note="The maximum quote across the whole panel on each match. Taking it requires "
             "an open account at whichever book was best that day, before the price moved. "
             "Kept as the price-shopping control: the gap between this and a single book "
             "is how much of a return is shopping rather than forecasting.",
        parsed=True,
    ),
    Venue(
        key="avg", column="Avg", name="Panel average",
        kind=Kind.SYNTHETIC, access=Access.NOT_A_VENUE, restricts_winners=None,
        note="The mean quote across the panel. A description of the market's level, not "
             "an offer anyone made.",
        parsed=True,
    ),
    Venue(
        key="bwin", column="B&W", name="bwin",
        kind=Kind.BOOKMAKER, access=Access.UK_OPEN, restricts_winners=True,
        note="UK-licensed and open, but the column exists for 2003 alone (about a thousand "
             "matches). Not parsed: a single season two decades ago cannot settle anything "
             "and carrying it would invite someone to try.",
        parsed=False,
    ),
    Venue(
        key="expekt", column="EX", name="Expekt",
        kind=Kind.BOOKMAKER, access=Access.CLOSED_TO_UK, restricts_winners=True,
        note="Not a UK-facing book. Column ends 2018. Not parsed.",
        parsed=False,
    ),
    Venue(
        key="stan_james", column="SJ", name="Stan James",
        kind=Kind.BOOKMAKER, access=Access.CLOSED_TO_UK, restricts_winners=True,
        note="The brand was retired and its UK business absorbed elsewhere; there is no "
             "Stan James to open an account with. Column ends 2014. Not parsed.",
        parsed=False,
    ),
    Venue(
        key="centrebet", column="CB", name="Centrebet",
        kind=Kind.BOOKMAKER, access=Access.CLOSED_TO_UK, restricts_winners=True,
        note="Australian book, absorbed into another operator and not UK-facing. Column "
             "ends 2007. Not parsed.",
        parsed=False,
    ),
    Venue(
        key="interwetten", column="IW", name="Interwetten",
        kind=Kind.BOOKMAKER, access=Access.CLOSED_TO_UK, restricts_winners=True,
        note="No UK offering. Column ends 2005. Not parsed.",
        parsed=False,
    ),
    Venue(
        key="sportingbet", column="SB", name="Sportingbet",
        kind=Kind.BOOKMAKER, access=Access.CLOSED_TO_UK, restricts_winners=True,
        note="Withdrew its UK-facing brand. Column ends 2003. Not parsed.",
        parsed=False,
    ),
    Venue(
        key="gamebookers", column="GB", name="Gamebookers",
        kind=Kind.BOOKMAKER, access=Access.CLOSED_TO_UK, restricts_winners=True,
        note="Defunct as a UK-facing brand. Column ends 2002. Not parsed.",
        parsed=False,
    ),
)


def by_key(key: str) -> Venue:
    for venue in VENUES:
        if venue.key == key:
            return venue
    raise KeyError(f"unknown venue {key!r}")


def uk_settlement_keys() -> tuple[str, ...]:
    """Columns a UK resident could actually have bet into, best evidence first.

    This is the list a money report is allowed to headline. Everything else is a diagnostic
    and has to be labelled as one.
    """
    return tuple(v.key for v in VENUES
                 if v.parsed and v.access is Access.UK_OPEN)


def benchmark_keys() -> tuple[str, ...]:
    """Parsed columns that are NOT bettable from here: sharp-price and shopping controls."""
    return tuple(v.key for v in VENUES
                 if v.parsed and v.access is not Access.UK_OPEN)


def parsed_keys() -> tuple[str, ...]:
    """Every column the corpus loader carries onto a match."""
    return tuple(v.key for v in VENUES if v.parsed)
