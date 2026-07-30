import { assertEquals } from "jsr:@std/assert";
import { surfaceFor, surfaceIsKnown } from "./board.ts";

Deno.test("the slams keep their surfaces, by explicit override", () => {
  // Their keys carry no city, so they can only be resolved by name.
  assertEquals(surfaceFor("tennis_atp_australian_open"), "Hard");
  assertEquals(surfaceFor("tennis_atp_french_open"), "Clay");
  assertEquals(surfaceFor("tennis_wta_french_open"), "Clay");
  assertEquals(surfaceFor("tennis_atp_wimbledon"), "Grass");
  assertEquals(surfaceFor("tennis_atp_us_open"), "Hard");
});

Deno.test("tour venues resolve by city, and the two tours can disagree", () => {
  // Derived from the corpus (>= 2019, >= 98% one surface, >= 20 matches), not recalled.
  // Stuttgart is the case that proves the mapping must be tour-aware: the ATP event is
  // on grass and the WTA event on clay, at the same city, in the same month. A single
  // city-to-surface table would get one of them wrong every year.
  assertEquals(surfaceFor("tennis_atp_stuttgart_open"), "Grass");
  assertEquals(surfaceFor("tennis_wta_stuttgart_open"), "Clay");

  assertEquals(surfaceFor("tennis_atp_washington_open"), "Hard");
  assertEquals(surfaceFor("tennis_wta_washington_open"), "Hard");
  assertEquals(surfaceFor("tennis_atp_monte_carlo_masters"), "Clay");
  assertEquals(surfaceFor("tennis_atp_rome_masters"), "Clay");
  assertEquals(surfaceFor("tennis_atp_halle_open"), "Grass");
  assertEquals(surfaceFor("tennis_atp_indian_wells_masters"), "Hard");
});

Deno.test("an unresolved tournament is reported as unknown, not quietly called Hard", () => {
  // Hard is still SERVED for an unknown tournament — every alternative needs a scoring
  // change, and the surface features fall back to the overall rating on an empty string
  // anyway. What changes is that the guess is no longer invisible: surfaceIsKnown marks
  // it so the refresh can record the tournament and the gap can be closed from data
  // instead of being discovered by a wrong prediction.
  assertEquals(surfaceFor("tennis_atp_some_new_event"), "Hard");
  assertEquals(surfaceIsKnown("tennis_atp_some_new_event"), false);
  assertEquals(surfaceIsKnown("tennis_atp_french_open"), true);
  assertEquals(surfaceIsKnown("tennis_wta_stuttgart_open"), true);

  // Genuinely ambiguous cities are deliberately NOT in the table. London hosts Queen's
  // on grass and the ATP Finals on indoor hard; Paris hosts Roland Garros on clay and
  // the Masters on hard. Guessing either would be a confident false claim.
  assertEquals(surfaceIsKnown("tennis_atp_london_event"), false);
  assertEquals(surfaceIsKnown("tennis_atp_paris_masters"), false);
});
