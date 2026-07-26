"""Canonical Betfair tick ladder and integer tick-index arithmetic (SPEC-053).

Price is an **integer index** into a canonical, non-linear ladder — never a float. The ladder
is built once with exact ``Decimal`` arithmetic. ``price_of``/``index_of`` are exact inverses,
and lookup is by numeric value (``Decimal`` hashes by value, so ``2``, ``2.0`` and ``2.00`` all
resolve to the same tick).

The Betfair ladder (SPECIFICATION.md §6.6):
1.01–2 by .01; 2–3 by .02; 3–4 by .05; 4–6 by .1; 6–10 by .2; 10–20 by .5; 20–30 by 1;
30–50 by 2; 50–100 by 5; 100–1000 by 10.  Band tops belong to the next band (so 2.00 is the
first tick of the .02 band, not the last of the .01 band); 1000 is the final tick. Total 350.

BETFAIR-SCOPED BY DESIGN (conceptual audit F-16): this is THE Betfair exchange ladder, shared
by every Betfair sport (racing, tennis, football alike) — but it is a venue fact, not a
universal one. A non-Betfair venue (e.g. a cent-priced prediction market) is a different
ladder and therefore a different, separately governed price-contract version; nothing in this
module may be stretched to fit one.
"""
from __future__ import annotations

from decimal import Decimal

# (band low inclusive, band high, step). For every band except the last the high is the start
# of the next band and is therefore excluded; the final band includes its high (1000).
_BANDS: tuple[tuple[Decimal, Decimal, Decimal], ...] = (
    (Decimal("1.01"), Decimal("2"), Decimal("0.01")),
    (Decimal("2"), Decimal("3"), Decimal("0.02")),
    (Decimal("3"), Decimal("4"), Decimal("0.05")),
    (Decimal("4"), Decimal("6"), Decimal("0.1")),
    (Decimal("6"), Decimal("10"), Decimal("0.2")),
    (Decimal("10"), Decimal("20"), Decimal("0.5")),
    (Decimal("20"), Decimal("30"), Decimal("1")),
    (Decimal("30"), Decimal("50"), Decimal("2")),
    (Decimal("50"), Decimal("100"), Decimal("5")),
    (Decimal("100"), Decimal("1000"), Decimal("10")),
)


def _build_ladder() -> tuple[Decimal, ...]:
    prices: list[Decimal] = []
    last_band = len(_BANDS) - 1
    for band_idx, (low, high, step) in enumerate(_BANDS):
        include_high = band_idx == last_band
        k = 0
        while True:
            price = low + step * k
            if price > high or (price == high and not include_high):
                break
            prices.append(price)
            k += 1
    return tuple(prices)


LADDER: tuple[Decimal, ...] = _build_ladder()
TICK_COUNT: int = len(LADDER)
MIN_PRICE: Decimal = LADDER[0]
MAX_PRICE: Decimal = LADDER[-1]

# Value-keyed reverse index. Decimal hashes/compares by value, so scale is irrelevant.
_INDEX_OF: dict[Decimal, int] = {price: i for i, price in enumerate(LADDER)}


def _is_real_int(value: object) -> bool:
    # Reject bool (an int subclass) and float — a tick index is a plain integer.
    return isinstance(value, int) and not isinstance(value, bool)


def is_valid_index(index: object) -> bool:
    # Inline isinstance so the type checker narrows `index` to int for the range comparison.
    return isinstance(index, int) and not isinstance(index, bool) and 0 <= index < TICK_COUNT


def is_on_ladder(price: object) -> bool:
    return isinstance(price, Decimal) and price in _INDEX_OF


def price_of(index: int) -> Decimal:
    """Decimal price at ``index``. Raises ``TypeError`` for a non-int/bool/float index and
    ``ValueError`` for an out-of-range index."""
    if not _is_real_int(index):
        raise TypeError(f"tick index must be a plain int, got {type(index).__name__}")
    if not 0 <= index < TICK_COUNT:
        raise ValueError(f"tick index {index} out of range [0, {TICK_COUNT})")
    return LADDER[index]


def index_of(price: Decimal) -> int:
    """Integer tick index for ``price``. Raises ``TypeError`` if ``price`` is not a ``Decimal``
    (floats must not represent price) and ``ValueError`` if it is not on the ladder."""
    if not isinstance(price, Decimal):
        raise TypeError(f"price must be a Decimal, got {type(price).__name__}")
    try:
        return _INDEX_OF[price]
    except KeyError:
        raise ValueError(f"price {price} is not on the canonical ladder") from None
