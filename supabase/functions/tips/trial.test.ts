/**
 * TE-0041 #6 — the real-bet record gains venue provenance, under governance:
 *
 * - Only venues in the founder-verified registry may be recorded; anything else is a
 *   refusal (the endpoint 409s and writes no row). The registry holds each venue's
 *   founder-verified commission and asserts the one-selection-per-market precondition
 *   that makes a per-bet commission rate valid at all (SPEC-080: Betfair charges the
 *   NET MARKET result).
 * - The loss budget stays VENUE-BLIND: multiple venues must never become multiple
 *   budgets — one venue's balance funding another is exactly what SPEC-103 forbids.
 * - This platform records venues; it does not recommend opening accounts anywhere
 *   (ADR 0015/0020 governance).
 *
 * Committed RED: trial.ts does not exist yet.
 */
import { assertEquals } from "jsr:@std/assert@1";
import { budgetState, derivedBudgetPence, venueForBet } from "./trial.ts";

Deno.test("only registry venues are recordable, with founder-verified commission", () => {
  const betfair = venueForBet("betfair_ex_uk");
  assertEquals(betfair, { venue: "betfair_ex_uk", commission: 0.02 });
  // Default: an absent venue means the account's own exchange, not a guess.
  assertEquals(venueForBet(undefined), { venue: "betfair_ex_uk", commission: 0.02 });
  assertEquals(venueForBet(""), { venue: "betfair_ex_uk", commission: 0.02 });
  // Unregistered venues are refusals — no founder-verified commission, no row.
  assertEquals(venueForBet("smarkets"), null);
  assertEquals(venueForBet("pinnacle"), null);
  assertEquals(venueForBet("made_up_exchange"), null);
});

Deno.test("the loss budget DERIVES from the live bank — never a static number", () => {
  // Founder directive 2026-07-30: the budget is computed from the bank at any time,
  // with the bank entered and edited in the app. It derives as d_max x current bank —
  // the SAME 30% cap the registered allocator enforces with probability one (TE-0047),
  // so the recording guard and the staking policy can never disagree about worst case.
  // Each bank edit is the deliberate founder act that re-derives it (SPEC-060 spirit:
  // no code path changes the budget without a human act; editing the bank IS the act).
  assertEquals(derivedBudgetPence(20_000), 6_000);   // GBP 200 bank -> GBP 60
  assertEquals(derivedBudgetPence(50_000), 15_000);  // GBP 500 -> GBP 150
  assertEquals(derivedBudgetPence(333), 99);         // floors to the penny, never rounds up
  // No bank means NO budget — a refusal upstream, never a default.
  assertEquals(derivedBudgetPence(null), null);
  assertEquals(derivedBudgetPence(0), null);
  assertEquals(derivedBudgetPence(-5), null);
});

Deno.test("the loss budget is venue-blind (SPEC-103: one budget, never per-venue)", () => {
  const bets = [
    { stake: 10, status: "LOST", pnl: -10, venue: "betfair_ex_uk" },
    { stake: 10, status: "LOST", pnl: -10, venue: "somewhere_else" },
    { stake: 10, status: "WON", pnl: 9, venue: "betfair_ex_uk" },
  ];
  const spread = budgetState("25", bets);
  const oneVenue = budgetState("25", bets.map((b) => ({ ...b, venue: "betfair_ex_uk" })));
  const noVenue = budgetState("25", bets.map(({ venue: _v, ...rest }) => rest));
  assertEquals(spread, oneVenue);
  assertEquals(spread, noVenue);
  assertEquals(spread.settled_losses, 20);
  assertEquals(spread.remaining, 5);
  assertEquals(spread.exhausted, false);
});
