/**
 * The ADR 0020 manual-trial governance surface: venue registry + budget arithmetic.
 *
 * TE-0041 #6: the trial is the project's only source of TRUE fill evidence, and it was
 * venue-blind. Recording the venue makes it double as the line-shopping experiment at
 * zero marginal cost. Governance, in code:
 *
 * - The registry admits only venues whose commission the FOUNDER has verified, and a
 *   per-bet commission rate is only meaningful under one-selection-per-market
 *   (SPEC-080: commission is charged on the net market result) — which v1 enforces.
 *   An unregistered venue is a refusal upstream: no verified rate, no row.
 * - `budgetState` is venue-blind by construction: SPEC-103 forbids one venue's balance
 *   funding another, so there is ONE budget over ALL rows, never a per-venue split.
 * - This platform records venues. It does not recommend opening accounts anywhere
 *   (ADR 0015/0020); nothing here places, cancels or amends an order.
 */

interface VenueEntry {
  /** Founder-verified commission rate for this account at this venue. */
  commission: number;
}

/** Founder-verified venues only. Betfair: Basic package 2%, founder-attested
 * (TE-0044; SPEC-081 status ASSUMPTION until read off a settled statement). */
const VENUE_REGISTRY: Record<string, VenueEntry> = {
  betfair_ex_uk: { commission: 0.02 },
};

const DEFAULT_VENUE = "betfair_ex_uk";

/** The recordable identity of a bet's venue, or null for a refusal. An absent venue
 * means the account's own exchange — never a guess at a better price elsewhere. */
export function venueForBet(
  venue: string | undefined,
): { venue: string; commission: number } | null {
  const name = (venue ?? "").trim() || DEFAULT_VENUE;
  const entry = VENUE_REGISTRY[name];
  if (!entry) return null;
  return { venue: name, commission: entry.commission };
}

/** The registered drawdown cap: d_max = 0.30 (TE-0047, founder-accepted; the B5 bound
 * the allocator enforces with probability one). ONE constant, so the recording guard
 * and the staking policy can never disagree about the worst case. A re-pin of the cap
 * is a governed registration change and lands here and in the registration together. */
const D_MAX_NUM = 3;
const D_MAX_DEN = 10;

/** The loss budget, DERIVED from the live bank (founder directive 2026-07-30; ADR 0020
 * Amendment 5): budget = d_max x current bank, floored to the penny. Never a static
 * number. No bank means NO budget — a refusal upstream, never a default. Each bank
 * edit in the app is the deliberate founder act that re-derives it (SPEC-060 spirit). */
export function derivedBudgetPence(bankPence: number | null): number | null {
  if (bankPence === null || !Number.isFinite(bankPence) || bankPence <= 0) return null;
  return Math.floor((bankPence * D_MAX_NUM) / D_MAX_DEN);
}

export interface PlacedBet {
  stake: number;
  status: string;
  pnl: number | null;
}

/** Settled losses against the ADR 0020 budget. Losses decrement; wins do NOT restore
 *  (SPEC-060 semantics) — the budget is a floor on damage, not a rolling balance.
 *  VENUE-BLIND: aggregates over every row regardless of any venue field (SPEC-103). */
export function budgetState(budget: string | null, bets: PlacedBet[]) {
  const lost = bets.filter((b) => b.status === "LOST")
    .reduce((a, b) => a + b.stake, 0);
  const total = budget === null ? null : Number(budget);
  return {
    budget: total,
    settled_losses: Math.round(lost * 100) / 100,
    remaining: total === null ? null : Math.max(0, Math.round((total - lost) * 100) / 100),
    exhausted: total !== null && lost >= total,
  };
}
