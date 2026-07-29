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
