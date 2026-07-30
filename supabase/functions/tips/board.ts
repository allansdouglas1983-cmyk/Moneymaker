/**
 * The self-filling board: pure helpers for The Odds API feed.
 *
 * The feed's job is to deliver what the manual entry box delivered — a real, current,
 * transactable price and two player names — without anyone typing. The price preference
 * is therefore the exchange itself: `betfair_ex_uk` is the venue a bet would actually go
 * to, and its quote is the exact number the manual flow assumed. Pinnacle and the other
 * exchanges are fallbacks; a match with none of them is a typed absence, never a default.
 *
 * Everything here is pure and deno-tested. Nothing in scoring.ts changes: the feed
 * produces fixtures, and fixtures flow through the identical assess/mint path the
 * manual box uses.
 */

/** Venue order: the exchange first (where a bet would go), the sharpest book second,
 *  the other exchanges after. FROZEN — never reordered to flatter a number. */
export const BOOK_PREFERENCE = [
  "betfair_ex_uk",
  "pinnacle",
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
