"""Today's matches and their prices — the front of the chain that did not exist.

Everything downstream of this worked and none of it was reachable without a person writing a
JSON file by hand. A tool you have to hand-feed the day's matches to is a demonstration, not
a product, and this is the piece that closes that.

**Two sources, one shape.** Manual entry stays first-class: it always works, needs no
account, no key and no network, and it is the path SPEC-112 names. The delayed-key adapter is
the automated route and is deliberately built to the same output, so authenticating it later
changes nothing downstream — the same ``Fixture`` objects through the same validation.

**Every refusal here is a match that must not silently become a prediction.** A missing
price, a price at or below evens, the same player twice, an unsupported format, a date
already played. One bad entry fails the whole file rather than being dropped, because a
silently skipped fixture is one nobody notices is missing — and the one you wanted a price on
is exactly the one most likely to be malformed.

**Prices are read as exact decimals from strings.** A float literal damages a price before it
is ever used, and the damage is invisible: 2.10 becomes 2.0999999999999996 and every
break-even computed from it is fractionally wrong in the same direction.
"""
from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal, InvalidOperation
from enum import Enum, unique
from pathlib import Path
from typing import Any, Mapping, Sequence

from tennis_edge.upcoming import Fixture

__all__ = [
    "FixtureSource",
    "parse_fixture",
    "load_fixture_file",
]


@unique
class FixtureSource(Enum):
    """Where a price came from. Recorded per fixture so a ledger row can be audited.

    A source nobody declared cannot be checked later, so an unrecognised one is refused
    rather than stored as free text.
    """

    #: Typed in from the Betfair site. Always available, needs nothing.
    MANUAL_BETFAIR_UI = "MANUAL_BETFAIR_UI"
    #: The free Delayed App Key, observation only. SPEC-102 makes real money impossible on
    #: it by construction, which is why it is the safe automated route.
    DELAYED_KEY = "DELAYED_KEY"


def _price(entry: Mapping[str, Any], field: str) -> Decimal:
    if field not in entry:
        raise ValueError(f"missing {field}")
    raw = entry[field]
    try:
        value = Decimal(str(raw))
    except InvalidOperation as error:
        raise ValueError(f"{field} is not a decimal price: {raw!r}") from error
    if value <= 1:
        raise ValueError(f"{field} must be above 1, got {value}")
    return value


def parse_fixture(entry: Mapping[str, Any]) -> tuple[Fixture, FixtureSource]:
    """One validated fixture and the source of its prices."""
    raw_source = str(entry.get("source", FixtureSource.MANUAL_BETFAIR_UI.value))
    try:
        source = FixtureSource(raw_source)
    except ValueError as error:
        raise ValueError(
            f"unknown source {raw_source!r}; declared sources are "
            f"{[s.value for s in FixtureSource]}"
        ) from error

    player_a = str(entry["player_a"]).strip()
    player_b = str(entry["player_b"]).strip()
    if player_a == player_b:
        raise ValueError(f"the same player appears on both sides: {player_a!r}")

    best_of = int(entry.get("best_of", 3))
    if best_of not in (3, 5):
        raise ValueError(f"best_of must be 3 or 5, got {best_of}")

    return Fixture(
        date=dt.date.fromisoformat(str(entry["date"])),
        tour=str(entry["tour"]).strip(),
        player_a=player_a,
        player_b=player_b,
        surface=str(entry.get("surface", "Hard")).strip(),
        best_of=best_of,
        odds_a=_price(entry, "odds_a"),
        odds_b=_price(entry, "odds_b"),
    ), source


def load_fixture_file(
    path: Path | str, *, today: dt.date | None = None
) -> list[tuple[Fixture, FixtureSource, Mapping[str, Any]]]:
    """Every fixture in a JSON file, with its source and its original entry.

    The original entry rides along because it carries optional per-fixture inputs the
    ``Fixture`` type does not model — rankings, an explicit feature override — and losing
    them here would mean the caller had to re-read the file.

    ``today`` enables the date check. Supplying it refuses a match already played, which is
    not a prediction whatever the model says about it. Omitting it allows reproducing an old
    prediction deliberately; the point is that doing so by accident is impossible.
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a list of fixtures")
    out: list[tuple[Fixture, FixtureSource, Mapping[str, Any]]] = []
    for index, entry in enumerate(payload, start=1):
        try:
            fixture, source = parse_fixture(entry)
        except (ValueError, KeyError, TypeError) as error:
            raise ValueError(f"fixture {index}: {error}") from error
        if today is not None and fixture.date < today:
            raise ValueError(
                f"fixture {index}: {fixture.date} has already been played — a settled "
                f"match is not a prediction"
            )
        out.append((fixture, source, entry))
    return out


def summarise(fixtures: Sequence[tuple[Fixture, FixtureSource, Mapping[str, Any]]]) -> str:
    if not fixtures:
        return "no fixtures"
    sources = sorted({source.value for _f, source, _e in fixtures})
    days = sorted({fixture.date for fixture, _s, _e in fixtures})
    return (f"{len(fixtures)} fixtures, {days[0]}..{days[-1]}, "
            f"prices from {', '.join(sources)}")
