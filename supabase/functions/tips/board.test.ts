import { assertEquals } from "jsr:@std/assert";
import {
  bestOfFor,
  corpusCandidates,
  normalizeName,
  pickPrices,
  resolvePlayer,
  surfaceFor,
  tourOf,
} from "./board.ts";

Deno.test("tour, best-of and surface derive from the sport key", () => {
  assertEquals(tourOf("tennis_atp_washington_open"), "ATP");
  assertEquals(tourOf("tennis_wta_french_open"), "WTA");
  assertEquals(tourOf("soccer_epl"), null);
  assertEquals(bestOfFor("tennis_atp_wimbledon"), 5);
  assertEquals(bestOfFor("tennis_wta_wimbledon"), 3); // WTA slams are best of three
  assertEquals(bestOfFor("tennis_atp_washington_open"), 3);
  assertEquals(surfaceFor("tennis_atp_french_open"), "Clay");
  assertEquals(surfaceFor("tennis_atp_wimbledon"), "Grass");
  assertEquals(surfaceFor("tennis_atp_washington_open"), "Hard");
});

Deno.test("feed names resolve against real corpus spellings", () => {
  const stateKeys = ["Vukic A.", "Musetti L.", "Wang X.", "De Minaur A.",
                     "Auger-Aliassime F.", "Samsonova L."];
  const index = new Map(stateKeys.map((k) => [normalizeName(k), k]));
  assertEquals(resolvePlayer("Aleksandar Vukic", index), "Vukic A.");
  assertEquals(resolvePlayer("Lorenzo Musetti", index), "Musetti L.");
  assertEquals(resolvePlayer("Xinyu Wang", index), "Wang X.");
  assertEquals(resolvePlayer("Alex de Minaur", index), "De Minaur A.");
  assertEquals(resolvePlayer("Felix Auger-Aliassime", index), "Auger-Aliassime F.");
  assertEquals(resolvePlayer("Félix Auger-Aliassime", index), "Auger-Aliassime F.");
  assertEquals(resolvePlayer("Liudmila Samsonova", index), "Samsonova L.");
  assertEquals(resolvePlayer("Somebody Unknown", index), null);
  assertEquals(resolvePlayer("Mononym", index), null);
});

Deno.test("the exchange is preferred; a one-sided book is an absence", () => {
  const outcomes = (h: number, a: number) => [
    { name: "Home P.", price: h },
    { name: "Away P.", price: a },
  ];
  const feed = [
    { key: "pinnacle", markets: [{ key: "h2h", outcomes: outcomes(1.8, 2.1) }] },
    { key: "betfair_ex_uk", markets: [{ key: "h2h", outcomes: outcomes(1.85, 2.05) }] },
  ];
  const picked = pickPrices(feed, "Home P.", "Away P.");
  assertEquals(picked?.book, "betfair_ex_uk");
  assertEquals(picked?.home, 1.85);

  const oneSided = [{
    key: "betfair_ex_uk",
    markets: [{ key: "h2h", outcomes: [{ name: "Home P.", price: 1.85 }] }],
  }];
  assertEquals(pickPrices(oneSided, "Home P.", "Away P."), null);

  const unpreferred = [
    { key: "coral", markets: [{ key: "h2h", outcomes: outcomes(1.8, 2.1) }] },
  ];
  assertEquals(pickPrices(unpreferred, "Home P.", "Away P."), null);
});

Deno.test("corpus candidates cover particles and family-name-last transcription", () => {
  assertEquals(corpusCandidates("Alex de Minaur"), ["de Minaur A", "Minaur A"]);
  assertEquals(corpusCandidates("Xinyu Wang"), ["Wang X"]);
  assertEquals(corpusCandidates("Mononym"), []);
});

Deno.test("an explicit alias wins over the heuristic, and only for its own tour", () => {
  // The heuristic cannot know that the feed's "Alexander Bublik" is the corpus's
  // "Bublik A." when the corpus spells a player unusually, nor that two tours may
  // hold the same surname. An alias table is the durable fix, and it must be
  // consulted BEFORE the guesswork so a correction sticks permanently.
  const index = new Map([["bublik a", "Bublik A."], ["nadal r", "Nadal R."]]);
  const aliases = new Map([["sascha zverev", "Zverev A."]]);

  // Alias hit: a name the heuristic would resolve to nothing.
  assertEquals(resolvePlayer("Sascha Zverev", index, aliases), "Zverev A.");
  // Heuristic still works where no alias exists.
  assertEquals(resolvePlayer("Alexander Bublik", index, aliases), "Bublik A.");
  // No alias, no heuristic match: still an honest null, never a guess.
  assertEquals(resolvePlayer("Nobody Here", index, aliases), null);
  // Absent alias map behaves exactly as before (back-compatible).
  assertEquals(resolvePlayer("Rafael Nadal", index), "Nadal R.");
});
