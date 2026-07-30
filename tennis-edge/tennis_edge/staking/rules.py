"""The rule catalogue: verified formulas from DR-TENNIS-STAKING-006, as pure functions.

Every rule is a `StakingRule`: ``(candidates, DayState) -> stakes in pence``. Rules are
built by factory functions whose parameters are FROZEN in the study config before any
replay output is observed — nothing here is fitted, tuned, or updated from the replay it
is scored on (protocol §1.1). All arithmetic is integer pence and exact Decimal.

Most rules here are edge-free: they read bank state, the odds ladder and declared
policy only. ONE edge-consuming rule exists — `conservative_kelly` — and it is a
MEASURED OBJECT ONLY, withdrawn as policy by ADR 0020 Amendment 3 (2026-07-30): its
shrink construction ("Kelly × pooled TE-0043 ratio") is not from the research — matrix
§5.7 forbids folklore multipliers — and per-bet sizing of a same-day card violates
matrix §4. It stays in the catalogue so its frontier measurements remain reproducible;
nothing derived from it may be served or size a stake.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from decimal import ROUND_FLOOR, Decimal

from tennis_edge.staking.engine import Candidate, DayState

__all__ = [
    "StakingRule",
    "flat",
    "proportional",
    "fixed_profit_net",
    "variance_ladder",
    "sqrt_profit",
    "cppi",
    "tipp",
    "hb_cap",
    "conservative_kelly",
    "d7_conservative_bound",
]

StakingRule = Callable[[Sequence[Candidate], DayState], list[int]]

_PENNY = Decimal(1)


def _pence(value: Decimal) -> int:
    return int(value.quantize(_PENNY, rounding=ROUND_FLOOR))


def flat(unit_pence: int) -> StakingRule:
    """A1 FLAT — the incumbent and SPEC-060 twin. deff = 1, uniquely estimator-optimal."""
    def rule(candidates: Sequence[Candidate], state: DayState) -> list[int]:  # noqa: ARG001
        return [unit_pence for _ in candidates]
    return rule


def proportional(fraction: Decimal) -> StakingRule:
    """B1 PROP-F — fixed fraction of the morning bank. The multiplicative baseline."""
    def rule(candidates: Sequence[Candidate], state: DayState) -> list[int]:
        stake = _pence(Decimal(state.opening_bank_pence) * fraction)
        return [stake for _ in candidates]
    return rule


def fixed_profit_net(target_pence: int) -> StakingRule:
    """A2 FP-NET — stake to win the target NET of commission: s = T/((O-1)(1-c))."""
    def rule(candidates: Sequence[Candidate], state: DayState) -> list[int]:
        out = []
        for candidate in candidates:
            net = (candidate.odds - 1) * (Decimal(1) - state.commission)
            out.append(_pence(Decimal(target_pence) / net) if net > 0 else 0)
        return out
    return rule


def variance_ladder(unit_pence: int) -> StakingRule:
    """A6 VE-LADDER — equalise per-bet risk: s(O) = u / sd, sd = sqrt((O-1)(1-c)).

    The corrected closed form from the verification round. A 5.00 shot carries exactly
    twice the per-unit standard deviation of a 2.00 shot at the market-implied
    probability, so it gets exactly half the stake.
    """
    def rule(candidates: Sequence[Candidate], state: DayState) -> list[int]:
        out = []
        for candidate in candidates:
            net = (candidate.odds - 1) * (Decimal(1) - state.commission)
            if net <= 0:
                out.append(0)
                continue
            out.append(_pence(Decimal(unit_pence) / net.sqrt()))
        return out
    return rule


def sqrt_profit(base_pence: int, start_bank_pence: int) -> StakingRule:
    """A7 SQRT — u0 + sqrt(banked profit). Escalation funded ONLY from profit: at or
    below the starting bank the rule is exactly flat, so the initial bank is never
    escalated into."""
    def rule(candidates: Sequence[Candidate], state: DayState) -> list[int]:
        profit = max(state.opening_bank_pence - start_bank_pence, 0)
        stake = base_pence + _pence(Decimal(profit).sqrt())
        return [stake for _ in candidates]
    return rule


def cppi(multiplier: Decimal, floor_pence: int) -> StakingRule:
    """B2 CPPI — s = m*(W - F). Reads the CUSHION, never the bank; zero at or below the
    floor, never negative. With m <= 1 and day-level reservation the floor holds almost
    surely for back bets (max loss = stake)."""
    def rule(candidates: Sequence[Candidate], state: DayState) -> list[int]:
        cushion = max(state.opening_bank_pence - floor_pence, 0)
        stake = _pence(Decimal(cushion) * multiplier)
        return [stake for _ in candidates]
    return rule


def tipp(multiplier: Decimal, base_floor_pence: int, ratchet: Decimal) -> StakingRule:
    """B4 TIPP — CPPI whose floor ratchets with the high-water mark: F = max(F0, phi*HWM).

    The floor never falls back when the bank does — which is the protection, and also
    the documented cash-lock failure mode the harness's SILENT_DEATH flag exists to
    catch."""
    def rule(candidates: Sequence[Candidate], state: DayState) -> list[int]:
        floor = max(Decimal(base_floor_pence),
                    Decimal(state.peak_bank_pence) * ratchet)
        cushion = max(Decimal(state.opening_bank_pence) - floor, Decimal(0))
        stake = _pence(cushion * multiplier)
        return [stake for _ in candidates]
    return rule


def hb_cap(base: StakingRule, max_drawdown: Decimal) -> StakingRule:
    """B5 HB-CAP — Hsieh-Barmish: stake <= W - (1-d_max)*HWM, applied over any base rule.

    The strongest guarantee in the candidate set: a probability-ONE bound on maximum
    drawdown needing no distribution, no independence and no edge. The cap reaches zero
    exactly at the bound, so the bound cannot be crossed by betting."""
    def rule(candidates: Sequence[Candidate], state: DayState) -> list[int]:
        cap = max(_pence(Decimal(state.opening_bank_pence)
                         - (Decimal(1) - max_drawdown) * Decimal(state.peak_bank_pence)),
                  0)
        return [min(stake, cap) for stake in base(candidates, state)]
    return rule


def conservative_kelly(*, shrink: Decimal, commission: Decimal) -> StakingRule:
    """WITHDRAWN AS POLICY (ADR 0020 Amendment 3) — measured object only.

    f_i = shrink * kelly(p_i, O_i, c) of the live bank, per bet. Kept solely so the
    TE-0046 Addendum 2 frontier measurements remain reproducible. The construction is
    off-research: DR-TENNIS-STAKING-006 matrix §5.7 requires a fractional rule's
    fraction to be derived from pre-registered drawdown tolerances (the RCK way) or the
    per-bet conservative quantile (D7), never a pooled multiplier; and §4 requires
    joint same-day sizing. MUST NOT be served or used to size a real stake.
    """
    def rule(candidates: Sequence[Candidate], state: DayState) -> list[int]:
        out = []
        for candidate in candidates:
            net = (candidate.odds - 1) * (Decimal(1) - commission)
            if net <= 0:
                out.append(0)
                continue
            fraction = candidate.p_model - (Decimal(1) - candidate.p_model) / net
            if fraction <= 0:
                out.append(0)
                continue
            out.append(_pence(Decimal(state.opening_bank_pence) * fraction * shrink))
        return out
    return rule


def d7_conservative_bound(*, delta_e: Decimal, commission: Decimal,
                          max_drawdown: Decimal) -> StakingRule:
    """TE-0047 registered form — matrix D7 K-LCB: Kelly at the conservative bound.

    Per bet: b = (O-1)(1-c); e = p(b+1)-1; e_c = e - delta_e; f = e_c/b if e_c > 0
    else 0 (the "not yet" refusal — DR-003's warning lives inside the formula). Stake
    request = floor(W * f / k), k the FULL selected card size (a refused member still
    counts: it was selected, the perfectly-correlated charge stands, matrix §4 /
    DR-004 / SPEC-090). Then the multi-bet B5 HB-CAP day budget, pathwise: grants in
    canonical order against cap = floor(W - (1-d_max)*HWM), so the day's total stakes
    can never take the bank below (1-d_max) of its high-water mark — probability ONE,
    no distribution, no edge assumption. Engine reservation and the £1 skip apply
    downstream, unchanged.

    No parameter has a default: delta_e is the TE-0043 interval displacement (0.0249
    at the operative threshold), pinned by the caller with its provenance, so a stale
    or invented displacement cannot hide behind a signature.
    """
    def rule(candidates: Sequence[Candidate], state: DayState) -> list[int]:
        card_size = len(candidates)
        if card_size == 0:
            return []
        bank = Decimal(state.opening_bank_pence)
        cap = max(_pence(bank - (Decimal(1) - max_drawdown)
                         * Decimal(state.peak_bank_pence)), 0)
        out = []
        remaining = cap
        for candidate in candidates:
            net = (candidate.odds - 1) * (Decimal(1) - commission)
            if net <= 0:
                out.append(0)
                continue
            conservative = candidate.p_model * (net + 1) - 1 - delta_e
            if conservative <= 0:
                out.append(0)
                continue
            want = _pence(bank * (conservative / net) / card_size)
            grant = min(want, remaining)
            remaining -= grant
            out.append(grant)
        return out
    return rule
