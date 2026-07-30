"""Replay one staking rule over one settled bet sequence, in integer pence.

THE ENGINE IS THE MEASURING INSTRUMENT. It contains no strategy and no staking rule. Its
only job is to apply a rule's requested stakes to a real sequence of settled bets under
the exchange's actual mechanics, and to record what happened precisely enough that two
rules can be compared and the difference is theirs, not the instrument's.

Four mechanics carry the weight, and each is a place where the plausible alternative
quietly favours some rules over others:

**Same-day bets are sized off the bank the day opened on.** Every bet on a card is placed
before any of them settles, so none can be funded by another's winnings. An engine that
compounded within the day would make a proportional rule's result depend on the order rows
happen to sit in the export file — an artefact of the data reported as performance.

**A stake below the exchange minimum is skipped, never rounded up.** The minimum is
GBP 1.00. Rounding 40p up to GBP 1 is a 150% increase in risk on that bet, applied
silently, and it does the most violence to the most conservative rules — the worst
possible bias in a study whose whole purpose is to compare degrees of conservatism.

**Commission is charged on net winnings per market, never on turnover.** A losing market
pays nothing. One selection per market means the net market result IS that bet's profit.
Charging turnover would tax high-turnover rules for a cost that does not exist.

**Rounding goes against the bettor in both directions.** Gross profit is floored to the
penny, commission is ceilinged. No path can report money the exchange would not have paid,
so a rule cannot win the comparison on rounding.

Ruin is defined as *cannot fund the minimum legal stake*, which on a GBP 1 lattice happens
strictly before the bank reaches zero. That is the honest stopping condition, and the day
it happens is recorded because time-to-ruin is one of the objectives being compared.
"""
from __future__ import annotations

import datetime as dt
import enum
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

__all__ = [
    "Candidate",
    "EngineConfig",
    "DayState",
    "LedgerRow",
    "Halt",
    "Path",
    "StakingRule",
    "replay",
]

_PENNY = Decimal(1)


class Halt(enum.Enum):
    """Why a replay stopped before the sequence ran out."""

    #: The bank can no longer fund the smallest legal bet. This is ruin on a lattice with
    #: a hard minimum: it arrives strictly before the bank reaches zero, and a study that
    #: waits for zero systematically understates every rule's ruin probability.
    CANNOT_FUND_MINIMUM = "CANNOT_FUND_MINIMUM"


@dataclass(frozen=True)
class Candidate:
    """One side of one market, with its outcome already known to the harness.

    The rule never sees ``won`` — the engine settles with it after the rule has committed
    a stake. Keeping the outcome on the same record as the price is deliberate: rejoining
    it later is an opportunity to transpose a result onto the wrong bet, and nothing
    downstream would be able to tell.
    """

    date: dt.date
    market_id: str
    side: str
    odds: Decimal
    p_model: Decimal
    p_market: Decimal
    won: bool
    support: str
    stratum: str


@dataclass(frozen=True)
class EngineConfig:
    start_bank_pence: int
    #: Bank below this is not stakeable. What keeps the programme alive to bet next week.
    floor_pence: int
    #: Betfair Exchange minimum, GBP 1.00 = 100p since 7 February 2022.
    min_stake_pence: int
    #: Charged on net winnings per market. 0.05 tennis base rate, 0.02 on Basic.
    commission: Decimal


@dataclass(frozen=True)
class DayState:
    """What a staking rule may read. Deliberately narrow.

    A rule sees the bank, the peak, the floor and how far it has come — never the
    outcomes of the bets it is being asked to size, and never a future price. Widening
    this is how look-ahead gets in.
    """

    opening_bank_pence: int
    peak_bank_pence: int
    floor_pence: int
    min_stake_pence: int
    commission: Decimal
    day_index: int
    bets_settled: int


#: A staking rule: given today's candidates and today's state, return one stake in
#: integer pence per candidate. Zero means abstain. The engine applies the minimum, the
#: floor and the bank constraint afterwards, so a rule never has to know about them —
#: which is what keeps the rules comparable.
StakingRule = Callable[[Sequence[Candidate], DayState], Sequence[int]]


@dataclass(frozen=True)
class LedgerRow:
    date: dt.date
    market_id: str
    side: str
    odds: Decimal
    #: What the rule asked for, before the minimum, the floor and the bank were applied.
    #: Kept so that a skip is visible as a skip rather than as an abstention.
    requested_pence: int
    stake_pence: int
    won: bool
    commission_pence: int
    profit_pence: int
    closing_bank_pence: int
    reason: str


@dataclass
class Path:
    rows: list[LedgerRow] = field(default_factory=list)
    final_bank_pence: int = 0
    peak_bank_pence: int = 0
    total_commission_pence: int = 0
    total_staked_pence: int = 0
    halt: Halt | None = None
    halted_on: dt.date | None = None


def _settle(stake_pence: int, odds: Decimal, won: bool,
            commission: Decimal) -> tuple[int, int]:
    """Return ``(profit_pence, commission_pence)`` for one settled market.

    A loss costs exactly the stake and pays no commission — commission falls on net
    winnings, and a losing market has none. A win pays ``stake * (odds - 1)`` gross,
    floored to the penny, less commission on that profit, ceilinged to the penny. Both
    roundings favour the exchange, so no rule can win the comparison on arithmetic that
    would not have survived contact with a real account.
    """
    if not won:
        return -stake_pence, 0
    gross = (Decimal(stake_pence) * (odds - 1)).quantize(_PENNY, rounding=ROUND_FLOOR)
    charge = (gross * commission).quantize(_PENNY, rounding=ROUND_CEILING)
    return int(gross - charge), int(charge)


def replay(candidates: Sequence[Candidate], rule: StakingRule,
           config: EngineConfig) -> Path:
    """Trade ``rule`` over ``candidates`` and return the full path.

    Days are replayed in chronological order regardless of input order, because a rule
    that reads bank state is order-sensitive by construction and the export carries no
    ordering guarantee.
    """
    path = Path(final_bank_pence=config.start_bank_pence,
                peak_bank_pence=config.start_bank_pence)
    bank = config.start_bank_pence
    peak = config.start_bank_pence
    settled = 0

    by_day: dict[dt.date, list[Candidate]] = {}
    for candidate in candidates:
        by_day.setdefault(candidate.date, []).append(candidate)

    for day_index, day in enumerate(sorted(by_day)):
        todays = by_day[day]

        # Ruin check BEFORE sizing: a bank that cannot fund the smallest legal bet is
        # finished, and the day it became finished is what time-to-ruin measures.
        stakeable = bank - config.floor_pence
        if stakeable < config.min_stake_pence:
            path.halt = Halt.CANNOT_FUND_MINIMUM
            path.halted_on = day
            break

        state = DayState(
            opening_bank_pence=bank,
            peak_bank_pence=peak,
            floor_pence=config.floor_pence,
            min_stake_pence=config.min_stake_pence,
            commission=config.commission,
            day_index=day_index,
            bets_settled=settled,
        )
        requested = list(rule(todays, state))
        if len(requested) != len(todays):
            raise ValueError(
                f"staking rule must return one stake per candidate: got {len(requested)} "
                f"for {len(todays)} candidates on {day}")
        for value in requested:
            if value < 0:
                raise ValueError(
                    f"negative stake {value} on {day}: a negative stake is a lay bet, and "
                    "lay betting is prohibited platform-wide. Refusing rather than "
                    "clamping, which would hide the defect and score it as an abstention.")

        # The day's request may exceed what is stakeable. Scale every stake by the same
        # factor so the RELATIVE sizing the rule asked for survives; truncating one bet
        # instead would quietly turn the rule into a different rule.
        scaled = list(requested)
        scale_applied = False
        total = sum(scaled)
        if total > stakeable and total > 0:
            scale_applied = True
            scaled = [int((Decimal(value) * stakeable / total)
                          .quantize(_PENNY, rounding=ROUND_FLOOR)) for value in scaled]

        rows: list[LedgerRow] = []
        for candidate, want, size in zip(todays, requested, scaled, strict=True):
            if want <= 0:
                reason = "NO_STAKE"
                size = 0
            elif size < config.min_stake_pence:
                # Skipped, NOT rounded up. Rounding up is how a shrunk plan silently
                # becomes a flat stake at several times the intended risk.
                reason = "BELOW_MIN_STAKE"
                size = 0
            else:
                reason = "SCALED_TO_BANK" if scale_applied else "STAKED"

            if size == 0:
                rows.append(LedgerRow(
                    date=day, market_id=candidate.market_id, side=candidate.side,
                    odds=candidate.odds, requested_pence=want, stake_pence=0,
                    won=candidate.won, commission_pence=0, profit_pence=0,
                    closing_bank_pence=bank, reason=reason))
                continue

            profit, charge = _settle(size, candidate.odds, candidate.won,
                                     config.commission)
            bank += profit
            peak = max(peak, bank)
            settled += 1
            path.total_commission_pence += charge
            path.total_staked_pence += size
            rows.append(LedgerRow(
                date=day, market_id=candidate.market_id, side=candidate.side,
                odds=candidate.odds, requested_pence=want, stake_pence=size,
                won=candidate.won, commission_pence=charge, profit_pence=profit,
                closing_bank_pence=bank, reason=reason))

        path.rows.extend(rows)

    path.final_bank_pence = bank
    path.peak_bank_pence = peak
    return path
