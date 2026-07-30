/**
 * The self-filling board: pure helpers for The Odds API feed.
 *
 * The feed's job is to deliver what the manual entry box delivered — a real, current,
 * transactable price and two player names — without anyone typing. The price preference
 * is therefore the exchange itself: `betfair_ex_uk` is the venue a bet would actually go
 * to, and its quote is the exact number the manual flow assumed. Smarkets and Matchbook
 * are the fallbacks, both UK-open exchanges; a match none of the three quotes is a typed
 * absence, never a default.
 *
 * Everything here is pure and deno-tested. Nothing in scoring.ts changes: the feed
 * produces fixtures, and fixtures flow through the identical assess/mint path the
 * manual box uses.
 */

/** Venue order for the DECISION price: exchanges only, and only ones a UK resident can
 *  transact at. FROZEN — never reordered to flatter a number.
 *
 *  Pinnacle is deliberately absent. It closed to UK customers on 1 November 2014 and
 *  abandoned its 2016 licence application, so an edge computed against its quote is a
 *  number about a counterfactual — `venues.py` records exactly that, and TE-0013
 *  corrected a money table that had been led by it. Bookmakers are excluded for a
 *  second, independent reason: they restrict consistent winners, so an edge validated
 *  at one has an expiry date it does not control.
 *
 *  Pinnacle is still CAPTURED by `allVenueQuotes` below — as a sharpness benchmark, not
 *  as a price anyone can take. Capture is not a decision. */
export const BOOK_PREFERENCE = [
  "betfair_ex_uk",
  "smarkets",
  "matchbook",
] as const;

/** ATP slams are best of five; everything else (and all WTA) is best of three. */
const SLAMS = ["australian_open", "french_open", "wimbledon", "us_open"];

/** Surface by tournament key fragment. Hard is the honest default: it is the most
 *  common tour surface and the same default the manual entry box applies. */
const SURFACES: Record<string, string> = {
  australian_open: "Hard",
  us_open: "Hard",
  french_open: "Clay",
  wimbledon: "Grass",
};

export function tourOf(sportKey: string): "ATP" | "WTA" | null {
  if (sportKey.startsWith("tennis_atp")) return "ATP";
  if (sportKey.startsWith("tennis_wta")) return "WTA";
  return null;
}

export function bestOfFor(sportKey: string): number {
  if (tourOf(sportKey) === "ATP" && SLAMS.some((s) => sportKey.includes(s))) return 5;
  return 3;
}

export function surfaceFor(sportKey: string): string {
  for (const fragment of Object.keys(SURFACES)) {
    if (sportKey.includes(fragment)) return SURFACES[fragment];
  }
  return "Hard";
}

/** Case/diacritic/punctuation-insensitive form used ONLY for matching, never stored. */
export function normalizeName(name: string): string {
  return name
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[-'.]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Candidate corpus spellings for a feed name.
 *
 * The corpus writes "Surname I." while the feed writes "First [Middle] Surname" — and
 * neither convention is reliable for particles ("Alex de Minaur" -> "De Minaur A.") or
 * for names in family-name-last transcription ("Xinyu Wang" -> "Wang X."). Two
 * candidates cover both: everything-after-the-first-token as the surname, and
 * last-token-only. Matching is against the live state's actual keys, so a candidate
 * that hits is by construction a player the model can price.
 */
export function corpusCandidates(feedName: string): string[] {
  const tokens = feedName.trim().split(/\s+/);
  if (tokens.length < 2) return [];
  const initial = tokens[0][0];
  const wide = tokens.slice(1).join(" ") + " " + initial;
  const narrow = tokens[tokens.length - 1] + " " + initial;
  return wide === narrow ? [wide] : [wide, narrow];
}

/**
 * Resolve a feed name against the state's player keys for one tour, or null.
 *
 * Aliases are consulted FIRST and are authoritative: the heuristic below is a guess
 * about spelling conventions, and a human correction must never be re-guessed. An
 * unresolved name stays null — the board shows the fixture with no model opinion
 * rather than pricing the wrong player, which is the only failure here that would
 * put a fabricated number in the ledger.
 */
export function resolvePlayer(
  feedName: string,
  normalizedIndex: Map<string, string>,
  aliases?: Map<string, string>,
): string | null {
  const alias = aliases?.get(normalizeName(feedName));
  if (alias !== undefined) return alias;
  for (const candidate of corpusCandidates(feedName)) {
    const hit = normalizedIndex.get(normalizeName(candidate));
    if (hit !== undefined) return hit;
  }
  return null;
}

export interface FeedOutcome {
  name: string;
  price: number;
}

export interface FeedBookmaker {
  key: string;
  markets: Array<{ key: string; outcomes: FeedOutcome[] }>;
}

export interface VenueQuote {
  venue: string;
  home: number;
  away: number;
}

/**
 * Every venue's two-sided h2h quote, in feed order.
 *
 * The feed carries ~35 venues per response at no extra credit cost and the board bets
 * at one. The other 34 are the raw material for the two most reliable known sources of
 * realised edge — line shopping (cross-venue at an instant) and closing-line value
 * (one venue across time, decision to off) — so they are captured rather than dropped.
 *
 * Capture only. This function makes NO claim about which price is better: that depends
 * on each venue's commission, which must be verified before any policy uses it.
 */
export function allVenueQuotes(
  bookmakers: FeedBookmaker[],
  home: string,
  away: string,
): VenueQuote[] {
  const out: VenueQuote[] = [];
  for (const book of bookmakers) {
    const market = book.markets.find((m) => m.key === "h2h");
    if (!market) continue;
    const h = market.outcomes.find((o) => o.name === home)?.price;
    const a = market.outcomes.find((o) => o.name === away)?.price;
    // A one-sided book cannot be de-vigged into a probability, so it is an absence.
    if (h === undefined || a === undefined || !(h > 1) || !(a > 1)) continue;
    out.push({ venue: book.key, home: h, away: a });
  }
  return out;
}

/**
 * The preferred book's two prices for (home, away), or null if no preferred venue
 * quotes both sides above 1. A one-sided or absent book is an absence, not a default.
 */
export function pickPrices(
  bookmakers: FeedBookmaker[],
  home: string,
  away: string,
): { book: string; home: number; away: number } | null {
  const byKey = new Map(bookmakers.map((b) => [b.key, b]));
  for (const key of BOOK_PREFERENCE) {
    const book = byKey.get(key);
    if (!book) continue;
    const market = book.markets.find((m) => m.key === "h2h");
    if (!market) continue;
    const h = market.outcomes.find((o) => o.name === home)?.price;
    const a = market.outcomes.find((o) => o.name === away)?.price;
    if (h !== undefined && a !== undefined && h > 1 && a > 1) {
      return { book: key, home: h, away: a };
    }
  }
  return null;
}

/**
 * The exchange a fixture's price came from, from its governed source label.
 *
 * Recorded on every prediction because `fixtures` is UPDATE-in-place: once the next
 * refresh overwrites a fixture, the prediction row is the only place that still knows
 * which exchange priced the decision. Any venue-relative measurement needs it — CLV above
 * all, where a decision price from one exchange measured against another's closing quote
 * is not closing-line value but the sum of a market move and a fixed cross-venue gap.
 *
 * Only the three decision-ladder exchanges can appear. An unrecognised source THROWS:
 * defaulting it to Betfair would manufacture precisely the mixing this exists to prevent.
 */
export function venueOf(source: string): string {
  switch (source) {
    case "MANUAL_BETFAIR_UI":
    case "DELAYED_KEY":
    case "ODDS_API_BETFAIR_EX_UK":
      return "betfair_ex_uk";
    case "ODDS_API_SMARKETS":
      return "smarkets";
    case "ODDS_API_MATCHBOOK":
      return "matchbook";
    default:
      throw new Error("unmapped price source, refusing to guess a venue: " + source);
  }
}

/** Minutes from `now` until a scheduled start, or null if no start time is recorded.
 *
 *  Negative when the scheduled start has passed, and deliberately NOT clamped: a
 *  negative number is the single most important state to see, because it means the
 *  match may already be in play. */
export function minutesToStart(
  commenceTime: string | null | undefined,
  now: number = Date.now(),
): number | null {
  if (!commenceTime) return null;
  const start = Date.parse(commenceTime);
  if (Number.isNaN(start)) return null;
  return Math.round((start - now) / 60000);
}

/** Opens the entry window at T-90m. Earlier than this the price is no better as a
 *  forecast — TE-0006 found log loss flat across horizons — while the relative spread
 *  is measurably wider (5.75% at T-24h, 3.17% at T-6h against 2.61% at T-1h) and
 *  top-of-book depth is roughly halved. Acting early pays a real cost for no
 *  information. */
const WINDOW_OPENS_MINUTES = 90;

/** Closes the entry window at T-30m. This is a SAFETY bound, not a cost bound: the book
 *  is flat from here to the off (2.43% at T-30m against 2.47% at T-10m), so the margin
 *  is almost free. It exists because tennis matches can START EARLY, so a scheduled
 *  start is not a safe live boundary — SPEC-022 says so explicitly and conceptual audit
 *  F-01 records it as a defect to key a live rule to. Inside this margin the founder
 *  could be looking at a market that has already gone in-play. */
const WINDOW_CLOSES_MINUTES = 30;

export type EntryTiming = "TOO_EARLY" | "ACT" | "TOO_LATE" | "UNKNOWN";

/**
 * Where a fixture sits relative to the entry window.
 *
 * Advisory and display-only. It changes no probability, no edge and no status, and it
 * authorises nothing — every bet remains founder-manual under the ADR 0020 protocol.
 */
export function entryTiming(
  commenceTime: string | null | undefined,
  now: number = Date.now(),
): EntryTiming {
  const minutes = minutesToStart(commenceTime, now);
  if (minutes === null) return "UNKNOWN";
  if (minutes > WINDOW_OPENS_MINUTES) return "TOO_EARLY";
  if (minutes < WINDOW_CLOSES_MINUTES) return "TOO_LATE";
  return "ACT";
}
