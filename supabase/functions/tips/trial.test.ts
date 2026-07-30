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
import { budgetState, venueForBet } from "./trial.ts";

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
