"""STK-HARNESS-V1: the head-to-head mechanics on top of the replay engine.

Implements the four additions DR-TENNIS-STAKING-006-PROTOCOL specifies beyond
:mod:`tennis_edge.staking.engine`:

**Stress scenarios by win-payout haircut** (§4). The mean is shifted by scaling winning
payouts — never by inventing, flipping or deleting an outcome. ``h = -Δ·n / Σ b_i`` over
winners, exact Decimal. Losses are untouched in every scenario, so max-loss = stake and
every floor guarantee in the candidate set remains valid in the counterfactual world.
A positive shift is refused outright: this axis only degrades.

**Day-level reservation** (§1.6). Bets are granted sequentially in canonical order
(scheduled start, then market id — here input order, which the loader preserves), each
taking ``min(stake, remaining)``. Explicitly NOT proportional rescaling: floor
guarantees are proved under ``Σ same-day stakes ≤ day budget``, and rescaling would
break the skip rule. A truncated grant is ``CLAMP_RESERVE``; a grant below the minimum
is ``SKIP_RESERVE``.

**Absorbing ruin states** (§5). ``DEAD_FLOOR`` — end-of-day bank below the founder
floor — is the primary ruin definition: wealth freezes at the breach value and no later
day is played. ``DEAD_HARD`` — bank below the minimum stake — is the exchange-lattice
absorption. ``SILENT_DEATH`` is a flag with an onset date, not an absorption: a rule
that demands below the minimum on every eligible bet for the configured run of days has
switched itself off, and a rule that stops betting stops buying evidence.

**Paired draws** (§3.4). Deterministic seeded stationary-bootstrap day sequences,
generated once and replayed through every rule, so cross-rule differences isolate the
staking policy rather than draw noise.
"""
from __future__ import annotations

import datetime as dt
import enum
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from tennis_edge.staking.engine import Candidate, DayState, LedgerRow

__all__ = [
    "HarnessConfig",
    "Ruin",
    "RunPath",
    "haircut_factor",
    "day_sequence_draws",
    "reserve_day",
    "replay_run",
]

_PENNY = Decimal(1)


class Ruin(enum.Enum):
    #: End-of-day bank below the founder floor (protocol §5 R2) — the PRIMARY ruin
    #: definition, SPEC-060-shaped. Wealth frozen at breach value.
    DEAD_FLOOR = "DEAD_FLOOR"
    #: Bank can no longer fund the minimum legal stake (§5 R1).
    DEAD_HARD = "DEAD_HARD"


@dataclass(frozen=True)
class HarnessConfig:
    start_bank_pence: int
    #: The founder floor W0 - LOSS_BUDGET. Breach is a governance stop, not a nuance.
    founder_floor_pence: int
    min_stake_pence: int
    commission: Decimal
    #: Consecutive eligible days of sub-minimum demands before the SILENT_DEATH flag.
    silent_death_days: int


@dataclass
class RunPath:
    rows: list[LedgerRow] = field(default_factory=list)
    final_bank_pence: int = 0
    peak_bank_pence: int = 0
    ruin: Ruin | None = None
    ruined_on: dt.date | None = None
    silent_death_onset: dt.date | None = None


def haircut_factor(candidates: Sequence[Candidate], delta: Decimal,
                   *, commission: Decimal) -> Decimal:
    """The exact §4.3 identity: h = -Δ·n / Σ_{winners} b_i, with b = (O-1)(1-c).

    Δ is the target shift of the equal-weight per-unit-stake mean return. Zero means no
    haircut. A positive Δ — improving the world — is refused rather than clamped: this
    axis exists to degrade, and a silent improvement is a different study.
    """
    if delta > 0:
        raise ValueError(
            f"delta={delta} would IMPROVE payouts; the scenario axis only degrades. "
            "Refusing rather than clamping — a silently improved world is a different "
            "study wearing this one's name.")
    if delta == 0:
        return Decimal(0)
    winner_net = sum(((c.odds - 1) * (Decimal(1) - commission)
                      for c in candidates if c.won), Decimal(0))
    if winner_net == 0:
        raise ValueError("no winning bets: the haircut identity is undefined")
    return -delta * len(candidates) / winner_net


def day_sequence_draws(days: Sequence[dt.date], *, draws: int, seed: int,
                       expected_block_length: int = 10) -> list[list[dt.date]]:
    """Stationary-bootstrap day sequences (Politis-Romano), deterministic in the seed.

    Each draw is a full-length resampled sequence of whole days. Generated once; the
    caller replays the SAME draws through every rule (§3.4) so every cross-rule
    comparison is paired — both rules face identical odds and outcomes in each draw,
    and their difference isolates the staking policy.
    """
    ordered = list(days)
    count = len(ordered)
    rng = random.Random(seed)
    continue_probability = 1.0 - 1.0 / expected_block_length
    out: list[list[dt.date]] = []
    for _ in range(draws):
        sequence: list[dt.date] = []
        index = rng.randrange(count)
        while len(sequence) < count:
            sequence.append(ordered[index])
            if rng.random() < continue_probability:
                index = (index + 1) % count
            else:
                index = rng.randrange(count)
        out.append(sequence)
    return out


StakingRule = Callable[[Sequence[Candidate], DayState], Sequence[int]]


def reserve_day(requested: Sequence[int], *, bank_pence: int,
                min_stake_pence: int) -> list[tuple[int, str]]:
    """§1.6 day-level reservation as a pure function: (granted stake, reason) per request.

    Sequential in canonical order, each grant taking ``min(want, remaining)`` against the
    feasibility bound (the unreserved bank) — never proportional rescaling. A truncated
    grant is ``CLAMP_RESERVE``; a grant pushed below the exchange minimum is
    ``SKIP_RESERVE``; a request already below the minimum is ``SKIP_MIN``; zero is
    ``NO_STAKE``. This is the ONE implementation: :func:`replay_run` consumes it, and the
    serving-path golden vectors are emitted from it, so the number the site displays and
    the number the study measured cannot drift apart.
    """
    for value in requested:
        if value < 0:
            raise ValueError("negative stake: a lay bet, prohibited platform-wide")
    remaining = bank_pence
    out: list[tuple[int, str]] = []
    for want in requested:
        grant = min(want, remaining)
        if want <= 0:
            size, reason = 0, "NO_STAKE"
        elif grant < min_stake_pence:
            size, reason = 0, ("SKIP_RESERVE" if want >= min_stake_pence
                               else "SKIP_MIN")
        elif grant < want:
            size, reason = grant, "CLAMP_RESERVE"
        else:
            size, reason = grant, "STAKED"
        remaining -= size
        out.append((size, reason))
    return out


def _settle(stake_pence: int, odds: Decimal, won: bool, commission: Decimal,
            haircut: Decimal) -> int:
    """Profit in pence. The haircut multiplies credited winnings AFTER commission and
    BEFORE pence quantisation (§4.3); a loss is untouched in every scenario (§4.4)."""
    if not won:
        return -stake_pence
    gross = Decimal(stake_pence) * (odds - 1)
    charge = (gross * commission).quantize(_PENNY, rounding=ROUND_CEILING)
    credited = (gross - charge) * (Decimal(1) - haircut)
    return int(credited.quantize(_PENNY, rounding=ROUND_FLOOR))


def replay_run(candidates: Sequence[Candidate], rule: StakingRule,
               config: HarnessConfig, *, haircut: Decimal) -> RunPath:
    """One rule, one scenario, one pass over the sequence, under the harness mechanics."""
    path = RunPath(final_bank_pence=config.start_bank_pence,
                   peak_bank_pence=config.start_bank_pence)
    bank = config.start_bank_pence
    peak = config.start_bank_pence
    settled = 0
    quiet_days = 0

    by_day: dict[dt.date, list[Candidate]] = {}
    for candidate in candidates:
        by_day.setdefault(candidate.date, []).append(candidate)

    for day_index, day in enumerate(sorted(by_day)):
        todays = by_day[day]

        if bank < config.min_stake_pence:
            path.ruin = Ruin.DEAD_HARD
            path.ruined_on = day
            break

        state = DayState(
            opening_bank_pence=bank, peak_bank_pence=peak,
            floor_pence=config.founder_floor_pence,
            min_stake_pence=config.min_stake_pence,
            commission=config.commission, day_index=day_index,
            bets_settled=settled,
        )
        requested = list(rule(todays, state))
        if len(requested) != len(todays):
            raise ValueError("staking rule must return one stake per candidate")

        # Sequential reservation in canonical order (§1.6) — never proportional. The
        # budget here is the FEASIBILITY bound (§1.5: the unreserved bank; a back bet's
        # max loss is its stake, so there is no leverage). The founder floor is NOT a
        # stake constraint — it is a ruin DEFINITION (§5 R2): a plain rule is free to
        # breach it, and P(DEAD_FLOOR) is precisely the measurement of how often it
        # does. Floor RULES protect the floor through their own day budget; conflating
        # the two here would make every rule a floor rule and erase the comparison.
        granted = reserve_day(requested, bank_pence=bank,
                              min_stake_pence=config.min_stake_pence)
        placed_today = 0
        day_rows: list[LedgerRow] = []
        for candidate, want, (size, reason) in zip(todays, requested, granted,
                                                   strict=True):
            if size == 0:
                day_rows.append(LedgerRow(
                    date=day, market_id=candidate.market_id, side=candidate.side,
                    odds=candidate.odds, requested_pence=want, stake_pence=0,
                    won=candidate.won, commission_pence=0, profit_pence=0,
                    closing_bank_pence=bank, reason=reason))
                continue
            placed_today += 1
            profit = _settle(size, candidate.odds, candidate.won,
                             config.commission, haircut)
            bank += profit
            settled += 1
            day_rows.append(LedgerRow(
                date=day, market_id=candidate.market_id, side=candidate.side,
                odds=candidate.odds, requested_pence=want, stake_pence=size,
                won=candidate.won, commission_pence=0, profit_pence=profit,
                closing_bank_pence=bank, reason=reason))
        peak = max(peak, bank)
        path.rows.extend(day_rows)

        # Silent death (§5 R3): a flag with an onset, never an absorption.
        if todays and placed_today == 0:
            quiet_days += 1
            if quiet_days == config.silent_death_days and path.silent_death_onset is None:
                path.silent_death_onset = day
        elif placed_today > 0:
            quiet_days = 0

        if bank < config.founder_floor_pence:
            path.ruin = Ruin.DEAD_FLOOR
            path.ruined_on = day
            break

    path.final_bank_pence = bank
    path.peak_bank_pence = peak
    return path
