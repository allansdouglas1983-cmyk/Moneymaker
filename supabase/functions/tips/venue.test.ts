import { assertEquals, assertThrows } from "jsr:@std/assert";
import { venueOf } from "./board.ts";

Deno.test("a price source maps to its exchange, and an unknown one refuses", () => {
  // Recorded on the prediction because `fixtures` is UPDATE-in-place: once the next
  // refresh overwrites a fixture, the prediction is the only place that still knows
  // which exchange priced the decision.
  assertEquals(venueOf("ODDS_API_BETFAIR_EX_UK"), "betfair_ex_uk");
  assertEquals(venueOf("MANUAL_BETFAIR_UI"), "betfair_ex_uk");
  assertEquals(venueOf("DELAYED_KEY"), "betfair_ex_uk");
  assertEquals(venueOf("ODDS_API_SMARKETS"), "smarkets");
  assertEquals(venueOf("ODDS_API_MATCHBOOK"), "matchbook");

  // The whole point. Defaulting an unrecognised source to Betfair would manufacture
  // exactly the venue mixing the column exists to prevent — a Smarkets decision price
  // silently compared against a Betfair close reads as closing-line value when it is
  // really a fixed cross-venue quote difference. Refusing is the only safe behaviour.
  assertThrows(() => venueOf("ODDS_API_PINNACLE"));
  assertThrows(() => venueOf("SOME_FUTURE_FEED"));
  assertThrows(() => venueOf(""));
});
