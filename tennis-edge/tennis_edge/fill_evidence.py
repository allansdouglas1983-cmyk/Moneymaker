"""Did anyone actually get matched at the price this backtest just paid itself?

Betfair Historical BASIC is a **last-trade trace**. Each observation says that somebody was
matched at a price at a moment; none of them says that price was available to us, in our
size, when we wanted it. A settlement loop that reads those prices and reports a return has
made an assumption — every claimed fill happened — and the assumption is invisible in the
output. It looks precisely like a return that was earned.

Depth would settle it, and depth is not in this data and is not being bought. So the response
is not to assume, and not to give up, but to **falsify**: take each claimed fill and ask what
the rest of the trace says about it.

A claimed back at price ``P`` is:

* **SUPPORTED** when the market later trades at ``P`` or better before the off. Somebody was
  demonstrably matched there after we say we were, so the claim survives contact with the
  record. Backing is better at longer odds, so "better" means a *higher* decimal price: if
  3.2 was matched, 3.0 was reachable.
* **UNSUPPORTED** when later trades exist and every one of them is worse. The price shortened
  and never came back; nothing in the record puts anyone at our price after us.
* **NO_EVIDENCE** when nothing traded afterwards at all.

**That third state is the point of the module.** It is not a polite word for UNSUPPORTED and
it is not a shy SUPPORTED. A market that goes quiet has told us nothing, and the two ways of
collapsing the state are both wrong in a way that biases the headline: folding it into
UNSUPPORTED punishes illiquidity nobody observed, folding it into SUPPORTED credits fills
nobody witnessed. It stays separate, it stays in the denominator, and a report that does not
show its size is not reporting the thing it claims to.

None of this recovers order-book depth, and this module says so rather than implying
otherwise. What it does is convert an unstated assumption into a stated, falsifiable one,
which is the most a trace can honestly carry — and considerably more than an unqualified
return.

Prices are exact :class:`~decimal.Decimal` values on the canonical Betfair ladder. A float is
refused rather than coerced (SPEC-053): a comparison that decides whether money is credited
must not turn on a representation error.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from price_contracts.ladder import is_on_ladder
from tennis_edge.betfair import InPlayRefusedError, MarketHistory

__all__ = [
    "FillSupport",
    "LiquidityStratum",
    "FillEvidence",
    "traded_through",
    "stratify",
]


class FillSupport(Enum):
    """What the rest of the trace says about one claimed fill."""

    #: A later pre-off trade at the claim price or better. Somebody was matched there.
    SUPPORTED = "SUPPORTED"
    #: Later pre-off trades exist and all are worse. Nobody is witnessed at our price.
    UNSUPPORTED = "UNSUPPORTED"
    #: Nothing traded afterwards. Not a verdict — the absence of one.
    NO_EVIDENCE = "NO_EVIDENCE"


class LiquidityStratum(Enum):
    """How much trading the verdict was decided on, in ascending order.

    A verdict from one print and a verdict from forty are different verdicts, and averaging
    them into a single return is how a fragile subset disappears into a headline. The
    boundaries are round numbers chosen before any return was computed; they are reporting
    buckets, not thresholds anything is allowed to depend on.
    """

    SILENT = "SILENT"          # 0 prints
    THIN = "THIN"              # 1-4
    MODERATE = "MODERATE"      # 5-19
    ACTIVE = "ACTIVE"          # 20-99
    HEAVY = "HEAVY"            # 100+


@dataclass(frozen=True)
class FillEvidence:
    """One claimed fill, and what the record says about it."""

    support: FillSupport
    #: The best price seen after the claim, or ``None`` if nothing traded. "Best" is the
    #: highest decimal price: this is a back-only platform and a backer wants longer odds.
    best_subsequent: Decimal | None
    #: Pre-off prints for this selection strictly after the claim instant.
    subsequent_prints: int

    @property
    def creditable(self) -> bool:
        """The only predicate a settlement loop may branch on.

        Exposed as one property precisely so that ``NO_EVIDENCE`` cannot be folded into the
        credited side by a caller writing ``!= UNSUPPORTED`` and not thinking about it.
        """
        return self.support is FillSupport.SUPPORTED

    @property
    def stratum(self) -> LiquidityStratum:
        return stratify(self.subsequent_prints)


def stratify(prints: int) -> LiquidityStratum:
    """Bucket a print count. Every non-negative count lands in exactly one stratum, so a
    stratified report cannot silently drop a row it had no bucket for."""
    if prints < 0:
        raise ValueError(f"print count cannot be negative: {prints}")
    if prints == 0:
        return LiquidityStratum.SILENT
    if prints < 5:
        return LiquidityStratum.THIN
    if prints < 20:
        return LiquidityStratum.MODERATE
    if prints < 100:
        return LiquidityStratum.ACTIVE
    return LiquidityStratum.HEAVY


def traded_through(
    market: MarketHistory,
    selection_id: int,
    claim_price: Decimal,
    *,
    seconds_before_off: int,
) -> FillEvidence:
    """Ask the trade record whether a back at ``claim_price`` survives contact with it.

    Only prints for ``selection_id`` count. Match Odds has two runners whose prices move in
    opposite directions, so reading the other side would report support at exactly the
    moments the market moved against us.

    Only prints **strictly after** the claim instant count. The claim price is normally the
    price that printed at the horizon, so letting that print vouch for itself would make
    every fill self-certifying and the whole test vacuous.

    Only **pre-off** prints count. The reader drops in-play observations as it parses, but
    nothing stops a caller assembling a history that contains one, and a post-off print must
    never rescue a pre-off claim.
    """
    if seconds_before_off < 0:
        raise InPlayRefusedError(
            f"seconds_before_off={seconds_before_off} is at or after the off; "
            "this platform is pre-off only and does not serve in-play prices"
        )
    if not isinstance(claim_price, Decimal):
        raise TypeError(
            f"claim price must be Decimal, not {type(claim_price).__name__}; a float "
            "comparison here would decide whether money is credited by rounding"
        )
    if not is_on_ladder(claim_price):
        raise ValueError(
            f"{claim_price} is not on the Betfair ladder; a claim at an unquotable price "
            "is a defect upstream and answering it would hide that defect"
        )

    claim_ms = market.market_time_ms - seconds_before_off * 1000
    best: Decimal | None = None
    prints = 0
    for observation in market.observations:
        if observation.selection_id != selection_id:
            continue
        if observation.publish_time_ms <= claim_ms:
            continue
        if observation.publish_time_ms >= market.market_time_ms:
            continue
        prints += 1
        if best is None or observation.price > best:
            best = observation.price

    if prints == 0:
        return FillEvidence(support=FillSupport.NO_EVIDENCE, best_subsequent=None,
                            subsequent_prints=0)
    assert best is not None
    support = (FillSupport.SUPPORTED if best >= claim_price
               else FillSupport.UNSUPPORTED)
    return FillEvidence(support=support, best_subsequent=best, subsequent_prints=prints)
