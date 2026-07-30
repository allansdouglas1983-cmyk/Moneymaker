/**
 * The page's firing check must mirror tennis_edge.staking.selection.SelectionRule
 * EXACTLY: a bet fires when p − break_even(O, c) is STRICTLY greater than min_edge
 * (0.02, probability scale), break_even = 1/(1+(O−1)(1−c)), c = 0.02. Strict, because
 * ">= and > give different bet counts and the difference shows up in no summary."
 *
 * Integer form: fires ⇔ (pNano − 20_000_000) · b1 > 10^13, b1 = (oddsC−100)·98 + 10000.
 * Boundary pairs below are hand-computed one nanoprobability step either side.
 */
import { assertEquals } from "jsr:@std/assert@1";
import { isFired } from "../../../docs/staking.js";

Deno.test("isFired mirrors the Python SelectionRule strictly", () => {
  // O = 2.00: break_even = 1/1.98 = 0.505050…; bar = 0.525050…
  assertEquals(isFired(525_100_000n, 200n), true, "p=0.5251 at 2.00 clears the bar");
  assertEquals(isFired(525_000_000n, 200n), false, "p=0.5250 at 2.00 is under it");
  // O = 1.50: break_even = 10000/14900 = 0.671140…; bar = 0.691140…
  assertEquals(isFired(691_200_000n, 150n), true, "p=0.6912 at 1.50 clears the bar");
  assertEquals(isFired(691_100_000n, 150n), false, "p=0.6911 at 1.50 is under it");
  // Strictness at an exact representable bar: O such that the bar lands on a
  // nanoprobability integer — (pN − 2e7)·b1 == 1e13 exactly must NOT fire.
  // b1 = 20000 (oddsC = 202.04… not integer) — instead verify via algebra at
  // oddsC = 350: b1 = 250*98+10000 = 34500; 1e13/34500 is not integer, so take the
  // ceiling boundary: floor(1e13/34500) = 289855072; pN = 2e7 + 289855072 gives
  // product 34500*289855072 = 9,999,999,984,000 < 1e13 → false; +1 → > 1e13 → true.
  assertEquals(isFired(309_855_072n, 350n), false);
  assertEquals(isFired(309_855_073n, 350n), true);
  // No net return at 1.00 or below: never fires.
  assertEquals(isFired(999_000_000n, 100n), false);
  // Plain-number inputs are accepted (the page passes quantised Numbers).
  assertEquals(isFired(525_100_000, 200), true);
});
