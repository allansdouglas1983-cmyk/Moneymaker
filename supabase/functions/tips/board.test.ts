import { assertEquals } from "jsr:@std/assert";
import {
  allVenueQuotes,
  BOOK_PREFERENCE,
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

Deno.test("every venue's two-sided quote is extracted, one-sided ones dropped", () => {
  // Line shopping and closing-line value both need the SAME thing: a price series per
  // match per venue. The feed already carries ~35 venues in every response at no extra
  // credit cost; discarding 34 of them discards the evidence for both. Capture is
  // assumption-free — which venue is actually better after commission is a separate,
  // governed decision that needs verified commission rates.
  const feed = [
    { key: "betfair_ex_uk", markets: [{ key: "h2h", outcomes: [
      { name: "Home P.", price: 1.85 }, { name: "Away P.", price: 2.05 }] }] },
    { key: "pinnacle", markets: [{ key: "h2h", outcomes: [
      { name: "Home P.", price: 1.80 }, { name: "Away P.", price: 2.10 }] }] },
    // One-sided: cannot be de-vigged, so it is an absence not a quote.
    { key: "coral", markets: [{ key: "h2h", outcomes: [{ name: "Home P.", price: 1.9 }] }] },
    // Wrong market type entirely.
    { key: "betway", markets: [{ key: "totals", outcomes: [
      { name: "Over", price: 1.9 }, { name: "Under", price: 1.9 }] }] },
  ];
  const quotes = allVenueQuotes(feed, "Home P.", "Away P.");
  assertEquals(quotes.length, 2);
  assertEquals(quotes[0], { venue: "betfair_ex_uk", home: 1.85, away: 2.05, lastUpdate: null });
  assertEquals(quotes[1], { venue: "pinnacle", home: 1.80, away: 2.10, lastUpdate: null });
});

Deno.test("each venue's own quote timestamp is captured verbatim (TE-0041 #1)", () => {
  // Line shopping selects the MAX price across venues; when venues update
  // asynchronously the max is systematically the STALEST quote — adverse selection
  // wearing edge's clothes. Without each venue's own timestamp the shopping gain and
  // the staleness artefact are inseparable, even retrospectively. The field is the
  // provider's `last_update`, recorded verbatim and labelled a PROVIDER timestamp
  // (SPEC-020 vocabulary): it may mean "when the crawler last saw this bookmaker",
  // which only bounds staleness from below — recorded as what it is, never renamed
  // into a claim it cannot support.
  const feed = [
    // Market-level timestamp is the more specific and wins over bookmaker-level.
    { key: "betfair_ex_uk", last_update: "2026-07-30T10:00:00Z", markets: [
      { key: "h2h", last_update: "2026-07-30T10:01:30Z", outcomes: [
        { name: "Home P.", price: 1.85 }, { name: "Away P.", price: 2.05 }] }] },
    // Bookmaker-level only: used as the fallback.
    { key: "smarkets", last_update: "2026-07-30T06:00:00Z", markets: [
      { key: "h2h", outcomes: [
        { name: "Home P.", price: 1.86 }, { name: "Away P.", price: 2.04 }] }] },
    // No timestamp anywhere: an explicit null, never a fabricated time.
    { key: "matchbook", markets: [{ key: "h2h", outcomes: [
      { name: "Home P.", price: 1.84 }, { name: "Away P.", price: 2.06 }] }] },
  ];
  const quotes = allVenueQuotes(feed, "Home P.", "Away P.");
  assertEquals(quotes.map((q) => q.lastUpdate), [
    "2026-07-30T10:01:30Z",
    "2026-07-30T06:00:00Z",
    null,
  ]);
});

Deno.test("the decision ladder holds only venues a UK resident can transact at", () => {
  // The Python side settled this in TE-0013: `venues.py` marks Pinnacle
  // `Access.CLOSED_TO_UK` — "It is NOT a place this account can bet and its return is
  // not money" — and `test_pinnacle_and_the_panel_maximum_are_never_settlement_venues`
  // makes a table led by Pinnacle impossible without deleting a test. The serving side
  // never got that guard, so the board could fall back to Pinnacle, compute an edge and
  // a break-even against it, and mint that into the append-only prediction ledger: a
  // number about a counterfactual, on the one path that feeds real decisions.
  //
  // Exchanges only, and only ones open to the UK. Bookmakers are excluded for a second,
  // independent reason: they restrict consistent winners, so an edge validated there has
  // an expiry date it does not control (TE-0037 rejected bookmaker line shopping on
  // exactly this ground).
  const CLOSED_TO_UK = ["pinnacle"];
  for (const venue of CLOSED_TO_UK) {
    assertEquals(
      (BOOK_PREFERENCE as readonly string[]).includes(venue),
      false,
      `${venue} is closed to UK customers and must never price a decision`,
    );
  }

  // A match only Pinnacle quotes is an ABSENCE, not a fallback. Minting no prediction
  // is the correct outcome: fewer predictions at takeable prices beats more at
  // untakeable ones.
  const pinnacleOnly = [
    { key: "pinnacle", markets: [{ key: "h2h", outcomes: [
      { name: "Home P.", price: 1.80 }, { name: "Away P.", price: 2.10 }] }] },
  ];
  assertEquals(pickPrices(pinnacleOnly, "Home P.", "Away P."), null);

  // But capture must be untouched. Pinnacle is a genuine sharpness benchmark — TE-0013
  // measured the model at +1.48% against it versus a -2.08% control — and dropping it
  // from `allVenueQuotes` would destroy evidence to fix a decision-path defect.
  const quotes = allVenueQuotes(pinnacleOnly, "Home P.", "Away P.");
  assertEquals(quotes.length, 1);
  assertEquals(quotes[0].venue, "pinnacle");
});
