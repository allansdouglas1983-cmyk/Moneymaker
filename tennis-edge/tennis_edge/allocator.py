"""Bank allocation: how much to stake on each of today's tips, given the bank.

THE PROBLEM THIS SOLVES. Four tips arrive. The bank is GBP 100. A flat stake ignores
everything that matters — that a 1.4 edge at 1.8 is not the same bet as a 1.4 edge at 6.0,
that four bets at once is four times the exposure of one, and that a bank of 60 after a bad
week should not be betting what a bank of 100 bets. This module answers the actual
question: *given this bank, today, what goes on each tip?*

THE RULE, in order. Every step has a reason and a source.

1. **Conservative edge.** Edge is computed from the LOWER bound of the probability
   distribution, never the point estimate (SPEC-034). Chopra-Ziemba, reproduced in Ziemba
   (2005): errors in estimated MEANS are 5-20x more damaging than errors in variance. The
   edge is a mean. It gets the pessimistic input.

2. **Kelly fraction, commission-aware.** For a back bet at decimal odds O with commission
   c charged on winnings, net odds are b = (O-1)(1-c) and the growth-optimal fraction is

       f_kelly = p - (1 - p) / b

   This is where odds-dependence enters for free: at the same edge, a longshot gets a
   smaller fraction than a favourite, because b is larger and the loss branch is more
   likely. No separate rule needed.

3. **Shrink hard.** f = LAMBDA * f_kelly. Chu, Wu & Swartz (2018, J. Quantitative Analysis
   in Sports 14(1)) report their modified Kelly variants at 0.018-0.039 against a plain
   Kelly of 0.067 on the same problem — a third to a half. In 1,000 simulated 200-bet
   seasons their shrunk rule was profitable in 65% of runs against 53% for full Kelly.
   Hakobyan & Lototsky (2025, arXiv:2503.17927) prove the general form: growth is concave
   in f while variance rises monotonically, so ANY reduction below full Kelly improves the
   Sharpe ratio. Shrinking is not timidity; it is the better risk-adjusted bet.

4. **Cap each bet.** No single tip may exceed MAX_SINGLE of the bank however good it looks.
   A capped bet is the defence against a probability estimate that is simply wrong.

5. **Cap the day.** Four simultaneous bets are not one bet four times. If the day's stakes
   sum above MAX_DAILY they are scaled down proportionally, preserving their relative
   sizes. Correlation across same-day matches is unmeasured, so the cap is deliberately
   conservative.

6. **Reserve.** Only bank above RESERVE_FLOOR is stakeable. The floor is what keeps the
   system alive to bet next week; hitting it stops betting rather than betting the last
   pound.

7. **Drawdown brake.** Below DRAWDOWN_BRAKE of the peak bank, LAMBDA is halved. MacLean,
   Thorp & Ziemba (2010): betting twice Kelly drives the growth rate to zero. Estimation
   error means the true Kelly is unknown, so a drawdown — evidence the estimate may be
   optimistic — reduces exposure automatically rather than waiting for a human to notice.

8. **Granularity, honestly.** Exchange minimum is MIN_STAKE. A stake below it is SKIPPED,
   never rounded up. Rounding up is how a careful plan silently becomes a flat stake at
   several times the intended risk — the single most dangerous thing this module could do.
   Stakes are rounded DOWN to the penny.

WHAT THIS DOES NOT DO. It does not create an edge. Every fraction here is proportional to
the edge, so if the edge is zero the stakes are zero and if the edge is negative the bets
are skipped. Fed an optimistic probability it will bet more, not less — which is why step 1
takes the lower bound and step 7 exists. SPEC-060 currently mandates a fixed minimum stake;
activating this module is a governed change and LAMBDA = 0 reproduces the flat rule exactly.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

__all__ = [
    "AllocationPolicy",
    "Tip",
    "Allocation",
    "kelly_fraction",
    "allocate",
]


def _d(value: object) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


@dataclass(frozen=True)
class AllocationPolicy:
    """Every dial, in one frozen place. Changing one is a governed decision."""

    #: Multiplier on full Kelly. 1/3 follows Chu/Wu/Swartz's shrinkage band. ZERO
    #: reproduces the flat-stake rule exactly, which is the honest default until an edge
    #: is established.
    kelly_fraction: Decimal = Decimal("0")
    #: Hard ceiling on any single bet, as a fraction of the stakeable bank.
    max_single: Decimal = Decimal("0.02")
    #: Hard ceiling on the sum of one day's bets.
    max_daily: Decimal = Decimal("0.05")
    #: Bank below this is not stakeable — it is what keeps the system alive.
    reserve_floor: Decimal = Decimal("0.20")
    #: Below this fraction of peak bank, halve the Kelly fraction.
    drawdown_brake: Decimal = Decimal("0.80")
    #: Exchange minimum. A stake below this is skipped, never rounded up.
    min_stake: Decimal = Decimal("2.00")
    commission: Decimal = Decimal("0.05")


@dataclass(frozen=True)
class Tip:
    match_key: str
    odds: Decimal
    #: The CONSERVATIVE probability — the lower bound of the distribution, never the
    #: point estimate. Passing the point estimate here overstates every stake.
    probability_lower: Decimal


@dataclass(frozen=True)
class Allocation:
    match_key: str
    stake: Decimal
    fraction: Decimal
    reason: str


def break_even(odds: Decimal, commission: Decimal) -> Decimal:
    """1 / (1 + (O-1)(1-c)) — the probability at which a back bet breaks even."""
    return Decimal(1) / (Decimal(1) + (odds - 1) * (Decimal(1) - commission))


def kelly_fraction(odds: Decimal, probability: Decimal, commission: Decimal) -> Decimal:
    """Growth-optimal fraction for a single back bet, net of commission.

    f = p - (1-p)/b with b = (O-1)(1-c). Negative when the bet is not worth taking; the
    caller treats any non-positive value as a refusal rather than clamping it to zero,
    so "no edge" and "tiny edge" stay distinguishable.
    """
    net_odds = (odds - 1) * (Decimal(1) - commission)
    if net_odds <= 0:
        return Decimal(0)
    return probability - (Decimal(1) - probability) / net_odds


def allocate(
    tips: list[Tip],
    bank: Decimal,
    peak_bank: Decimal,
    policy: AllocationPolicy | None = None,
) -> list[Allocation]:
    """Today's stake for each tip, or a typed refusal with its reason.

    `peak_bank` is the highest bank ever reached, which is what the drawdown brake reads.
    Passing the current bank as the peak disables the brake, so it is required explicitly
    rather than defaulted.
    """
    policy = policy or AllocationPolicy()
    bank, peak_bank = _d(bank), _d(peak_bank)

    stakeable = bank - (peak_bank * policy.reserve_floor)
    if stakeable <= 0:
        return [Allocation(t.match_key, Decimal(0), Decimal(0),
                           "RESERVE_FLOOR_REACHED") for t in tips]

    lam = policy.kelly_fraction
    braked = peak_bank > 0 and bank < peak_bank * policy.drawdown_brake
    if braked:
        lam = lam / 2

    raw: list[tuple[Tip, Decimal, str]] = []
    for tip in tips:
        edge = tip.probability_lower - break_even(tip.odds, policy.commission)
        if edge <= 0:
            raw.append((tip, Decimal(0), "NO_EDGE"))
            continue
        f = kelly_fraction(tip.odds, tip.probability_lower, policy.commission) * lam
        if f <= 0:
            raw.append((tip, Decimal(0), "NO_EDGE"))
            continue
        capped = min(f, policy.max_single)
        raw.append((tip, capped, "CAPPED_SINGLE" if capped < f else "KELLY"))

    total = sum((f for _t, f, _r in raw), Decimal(0))
    scale = Decimal(1)
    if total > policy.max_daily:
        scale = policy.max_daily / total

    out: list[Allocation] = []
    for tip, f, reason in raw:
        if f <= 0:
            out.append(Allocation(tip.match_key, Decimal(0), Decimal(0), reason))
            continue
        final = f * scale
        stake = (stakeable * final).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        if stake < policy.min_stake:
            # Skipped, NOT rounded up. Rounding up is how a plan silently becomes a flat
            # stake at several times the intended risk.
            out.append(Allocation(tip.match_key, Decimal(0), final, "BELOW_MIN_STAKE"))
            continue
        if scale < 1:
            reason = "SCALED_DAILY_CAP"
        elif braked:
            reason = "DRAWDOWN_BRAKE"
        out.append(Allocation(tip.match_key, stake, final, reason))
    return out
