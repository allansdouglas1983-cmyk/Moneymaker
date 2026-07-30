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

/** The four slams, by name. Their sport keys carry no city, so nothing else can resolve
 *  them. `french_open` is Roland Garros in Paris and `wimbledon` is in London — both
 *  cities are omitted from the city table below as ambiguous, which is why these come
 *  first and settle it. */
const SLAM_SURFACE: Record<string, string> = {
  australian_open: "Hard",
  us_open: "Hard",
  french_open: "Clay",
  wimbledon: "Grass",
};

// Derived by tools/derive_surface_map.py from vintage-2026-07-26:
// 34,786 matches since 2019-01-01, 171 cities asserted, 16 omitted as ambiguous.
const CITY_SURFACE: Record<string, string> = {
  "ATP|acapulco": "Hard",  // 233 matches
  "ATP|adelaide": "Hard",  // 213 matches
  "ATP|almaty": "Hard",  // 53 matches
  "ATP|antwerp": "Hard",  // 161 matches
  "ATP|athens": "Hard",  // 27 matches
  "ATP|atlanta": "Hard",  // 132 matches
  "ATP|auckland": "Hard",  // 155 matches
  "ATP|banja_luka": "Clay",  // 26 matches
  "ATP|barcelona": "Clay",  // 285 matches
  "ATP|basel": "Hard",  // 148 matches
  "ATP|bastad": "Clay",  // 184 matches
  "ATP|beijing": "Hard",  // 119 matches
  "ATP|brisbane": "Hard",  // 109 matches
  "ATP|brussels": "Hard",  // 25 matches
  "ATP|bucharest": "Clay",  // 79 matches
  "ATP|budapest": "Clay",  // 27 matches
  "ATP|buenos_aires": "Clay",  // 212 matches
  "ATP|cagliari": "Hard",  // 27 matches
  "ATP|chengdu": "Hard",  // 105 matches
  "ATP|cincinnati": "Hard",  // 351 matches
  "ATP|cologne": "Hard",  // 54 matches
  "ATP|cordoba": "Clay",  // 156 matches
  "ATP|dallas": "Hard",  // 139 matches
  "ATP|delray_beach": "Hard",  // 220 matches
  "ATP|doha": "Hard",  // 214 matches
  "ATP|dubai": "Hard",  // 251 matches
  "ATP|eastbourne": "Grass",  // 186 matches
  "ATP|estoril": "Clay",  // 131 matches
  "ATP|florence": "Hard",  // 26 matches
  "ATP|geneva": "Clay",  // 181 matches
  "ATP|gijon": "Hard",  // 25 matches
  "ATP|gstaad": "Clay",  // 185 matches
  "ATP|halle": "Grass",  // 211 matches
  "ATP|hamburg": "Clay",  // 236 matches
  "ATP|hangzhou": "Hard",  // 51 matches
  "ATP|hong_kong": "Hard",  // 79 matches
  "ATP|houston": "Clay",  // 157 matches
  "ATP|indian_wells": "Hard",  // 644 matches
  "ATP|kitzbuhel": "Clay",  // 187 matches
  "ATP|los_cabos": "Hard",  // 160 matches
  "ATP|lyon": "Clay",  // 126 matches
  "ATP|madrid": "Clay",  // 521 matches
  "ATP|mallorca": "Grass",  // 158 matches
  "ATP|marbella": "Hard",  // 27 matches
  "ATP|marrakech": "Clay",  // 163 matches
  "ATP|marseille": "Hard",  // 183 matches
  "ATP|metz": "Hard",  // 155 matches
  "ATP|miami": "Hard",  // 644 matches
  "ATP|monte_carlo": "Clay",  // 370 matches
  "ATP|montpellier": "Hard",  // 206 matches
  "ATP|montreal": "Hard",  // 159 matches
  "ATP|moscow": "Hard",  // 53 matches
  "ATP|munich": "Clay",  // 190 matches
  "ATP|napoli": "Hard",  // 26 matches
  "ATP|newport": "Grass",  // 133 matches
  "ATP|nur_sultan": "Hard",  // 109 matches
  "ATP|parma": "Clay",  // 26 matches
  "ATP|pune": "Hard",  // 101 matches
  "ATP|queens_club": "Grass",  // 211 matches
  "ATP|rio_de_janeiro": "Clay",  // 207 matches
  "ATP|rome": "Clay",  // 584 matches
  "ATP|rotterdam": "Hard",  // 243 matches
  "ATP|s_hertogenbosch": "Grass",  // 160 matches
  "ATP|san_diego": "Hard",  // 53 matches
  "ATP|santiago": "Clay",  // 185 matches
  "ATP|sao_paulo": "Clay",  // 27 matches
  "ATP|sardinia": "Clay",  // 25 matches
  "ATP|seoul": "Hard",  // 24 matches
  "ATP|shanghai": "Hard",  // 327 matches
  "ATP|singapore": "Hard",  // 27 matches
  "ATP|sofia": "Hard",  // 131 matches
  "ATP|st_petersburg": "Hard",  // 83 matches
  "ATP|stockholm": "Hard",  // 158 matches
  "ATP|stuttgart": "Grass",  // 180 matches
  "ATP|sydney": "Hard",  // 52 matches
  "ATP|tel_aviv": "Hard",  // 26 matches
  "ATP|tokyo": "Hard",  // 152 matches
  "ATP|toronto": "Hard",  // 190 matches
  "ATP|turin": "Hard",  // 73 matches
  "ATP|umag": "Clay",  // 183 matches
  "ATP|vienna": "Hard",  // 207 matches
  "ATP|washington": "Hard",  // 272 matches
  "ATP|winston_salem": "Hard",  // 267 matches
  "ATP|zhuhai": "Hard",  // 51 matches
  "WTA|abu_dhabi": "Hard",  // 166 matches
  "WTA|acapulco": "Clay",  // 58 matches
  "WTA|adelaide": "Hard",  // 242 matches
  "WTA|athens": "Hard",  // 31 matches
  "WTA|auckland": "Hard",  // 173 matches
  "WTA|austin": "Hard",  // 121 matches
  "WTA|bad_homburg": "Grass",  // 169 matches
  "WTA|beijing": "Hard",  // 297 matches
  "WTA|belgrade": "Clay",  // 29 matches
  "WTA|berlin": "Grass",  // 157 matches
  "WTA|birmingham": "Grass",  // 151 matches
  "WTA|bogota": "Clay",  // 213 matches
  "WTA|brisbane": "Hard",  // 187 matches
  "WTA|bucharest": "Clay",  // 29 matches
  "WTA|charleston": "Clay",  // 380 matches
  "WTA|chennai": "Hard",  // 57 matches
  "WTA|chicago": "Hard",  // 75 matches
  "WTA|cincinnati": "Hard",  // 350 matches
  "WTA|cleveland": "Hard",  // 147 matches
  "WTA|cluj_napoca": "Hard",  // 183 matches
  "WTA|courmayeur": "Hard",  // 30 matches
  "WTA|doha": "Hard",  // 341 matches
  "WTA|dubai": "Hard",  // 370 matches
  "WTA|eastbourne": "Grass",  // 229 matches
  "WTA|gdynia": "Clay",  // 31 matches
  "WTA|granby": "Hard",  // 30 matches
  "WTA|guadalajara": "Hard",  // 232 matches
  "WTA|guangzhou": "Hard",  // 118 matches
  "WTA|hamburg": "Clay",  // 117 matches
  "WTA|hiroshima": "Hard",  // 30 matches
  "WTA|hobart": "Hard",  // 181 matches
  "WTA|hong_kong": "Hard",  // 87 matches
  "WTA|hua_hin": "Hard",  // 149 matches
  "WTA|iasi": "Clay",  // 87 matches
  "WTA|indian_wells": "Hard",  // 641 matches
  "WTA|istanbul": "Clay",  // 113 matches
  "WTA|jiujiang": "Hard",  // 58 matches
  "WTA|jurmala": "Clay",  // 29 matches
  "WTA|lausanne": "Clay",  // 120 matches
  "WTA|lexington": "Hard",  // 30 matches
  "WTA|lugano": "Clay",  // 31 matches
  "WTA|luxembourg": "Hard",  // 57 matches
  "WTA|lyon": "Hard",  // 118 matches
  "WTA|madrid": "Clay",  // 556 matches
  "WTA|mallorca": "Grass",  // 29 matches
  "WTA|merida": "Hard",  // 105 matches
  "WTA|miami": "Hard",  // 630 matches
  "WTA|monastir": "Hard",  // 90 matches
  "WTA|monterrey": "Hard",  // 202 matches
  "WTA|montreal": "Hard",  // 195 matches
  "WTA|moscow": "Hard",  // 50 matches
  "WTA|n_rnberg": "Clay",  // 29 matches
  "WTA|nanchang": "Hard",  // 57 matches
  "WTA|ningbo": "Hard",  // 79 matches
  "WTA|nottingham": "Grass",  // 226 matches
  "WTA|nur_sultan": "Hard",  // 29 matches
  "WTA|osaka": "Hard",  // 117 matches
  "WTA|palermo": "Clay",  // 180 matches
  "WTA|parma": "Clay",  // 60 matches
  "WTA|portoroz": "Hard",  // 58 matches
  "WTA|queens_club": "Grass",  // 53 matches
  "WTA|rabat": "Clay",  // 176 matches
  "WTA|riyadh": "Hard",  // 30 matches
  "WTA|rome": "Clay",  // 567 matches
  "WTA|rouen": "Clay",  // 90 matches
  "WTA|s_hertogenbosch": "Grass",  // 181 matches
  "WTA|san_diego": "Hard",  // 78 matches
  "WTA|san_jose": "Hard",  // 81 matches
  "WTA|sao_paulo": "Hard",  // 30 matches
  "WTA|seoul": "Hard",  // 140 matches
  "WTA|shenzhen": "Hard",  // 56 matches
  "WTA|singapore": "Hard",  // 30 matches
  "WTA|st_petersburg": "Hard",  // 107 matches
  "WTA|strasbourg": "Clay",  // 223 matches
  "WTA|stuttgart": "Clay",  // 178 matches
  "WTA|sydney": "Hard",  // 55 matches
  "WTA|tallinn": "Hard",  // 31 matches
  "WTA|tashkent": "Hard",  // 30 matches
  "WTA|tenerife": "Hard",  // 30 matches
  "WTA|tianjin": "Hard",  // 28 matches
  "WTA|tokyo": "Hard",  // 100 matches
  "WTA|toronto": "Hard",  // 152 matches
  "WTA|warsaw": "Clay",  // 61 matches
  "WTA|washington": "Hard",  // 139 matches
  "WTA|wuhan": "Hard",  // 152 matches
  "WTA|zhengzhou": "Hard",  // 52 matches
  "WTA|zhuhai": "Hard",  // 30 matches
};

// Omitted — genuinely ambiguous, so served as the Hard default and flagged:
//   ATP antalya: {'Grass': 26, 'Hard': 27} (purity=0.51 n=53)
//   ATP belgrade: {'Clay': 79, 'Hard': 27} (purity=0.75 n=106)
//   ATP london: {'Grass': 860, 'Hard': 30} (slam city, resolved by name)
//   ATP melbourne: {'Hard': 1109} (slam city, resolved by name)
//   ATP new_york: {'Hard': 952} (slam city, resolved by name)
//   ATP paris: {'Clay': 981, 'Hard': 365} (slam city, resolved by name)
//   WTA budapest: {'Hard': 31, 'Clay': 117} (purity=0.79 n=148)
//   WTA cancun: {'Hard': 15} (purity=1.00 n=15)
//   WTA fort_worth: {'Hard': 15} (purity=1.00 n=15)
//   WTA linz: {'Hard': 137, 'Clay': 25} (purity=0.85 n=162)
//   WTA london: {'Grass': 872} (slam city, resolved by name)
//   WTA melbourne: {'Hard': 1237} (slam city, resolved by name)
//   WTA new_york: {'Hard': 955} (slam city, resolved by name)
//   WTA ostrava: {'Clay': 54, 'Hard': 53} (purity=0.50 n=107)
//   WTA paris: {'Clay': 985} (slam city, resolved by name)
//   WTA prague: {'Clay': 88, 'Hard': 118} (purity=0.57 n=206)

export function tourOf(sportKey: string): "ATP" | "WTA" | null {
  if (sportKey.startsWith("tennis_atp")) return "ATP";
  if (sportKey.startsWith("tennis_wta")) return "WTA";
  return null;
}

export function bestOfFor(sportKey: string): number {
  if (tourOf(sportKey) === "ATP" && SLAMS.some((s) => sportKey.includes(s))) return 5;
  return 3;
}

/** The city tokens of a sport key: everything after the `tennis_<tour>_` prefix. */
function keyTokens(sportKey: string): string[] {
  return sportKey.split("_").slice(2);
}

/** The surface this tournament is actually played on, or null if nothing establishes it.
 *
 *  Slams by name first, then the corpus-derived (tour, city) table. A city is matched as
 *  a contiguous run of tokens so that `monte_carlo` resolves and a stray substring does
 *  not. */
function lookupSurface(sportKey: string): string | null {
  for (const name of Object.keys(SLAM_SURFACE)) {
    if (sportKey.includes(name)) return SLAM_SURFACE[name];
  }
  const tour = tourOf(sportKey);
  if (tour === null) return null;
  const tokens = keyTokens(sportKey);
  // Longest city first, so `monte_carlo` wins over a hypothetical `monte`.
  for (let span = Math.min(3, tokens.length); span >= 1; span--) {
    for (let i = 0; i + span <= tokens.length; i++) {
      const city = tokens.slice(i, i + span).join("_");
      const hit = CITY_SURFACE[tour + "|" + city];
      if (hit !== undefined) return hit;
    }
  }
  return null;
}

/** Whether the served surface is established or is the fallback guess.
 *
 *  A false here is the signal to record the tournament: the gap should be closed from
 *  data, not discovered by a wrong prediction months later. */
export function surfaceIsKnown(sportKey: string): boolean {
  return lookupSurface(sportKey) !== null;
}

/**
 * The surface served for a tournament.
 *
 * Hard remains the fallback. Not because it is right — on a clay event it is a confident
 * false claim fed into two of the model's features — but because every alternative needs
 * a scoring change: `surfaceRating` maps an empty surface to "Hard" anyway, so an
 * "unknown" surface cannot be expressed without changing the served numbers and the
 * Python/TypeScript golden vectors together. That is its own measured slice.
 *
 * What changes here is how often the fallback fires. Four tournaments were mapped; 171
 * (tour, city) pairs now are, derived from the corpus rather than recalled — including
 * the Stuttgart split that recall gets wrong. Where the fallback still fires,
 * `surfaceIsKnown` says so out loud.
 */
export function surfaceFor(sportKey: string): string {
  return lookupSurface(sportKey) ?? "Hard";
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
  last_update?: string;
  markets: Array<{ key: string; last_update?: string; outcomes: FeedOutcome[] }>;
}

export interface VenueQuote {
  venue: string;
  home: number;
  away: number;
  /** The provider's own `last_update` for this quote, verbatim, or null. PROVIDER
   * timestamp semantics (SPEC-020): it may mean "when the crawler last saw this
   * bookmaker", which bounds staleness only from below — recorded as what it is. */
  lastUpdate: string | null;
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
    // Market-level timestamp is the more specific; bookmaker-level is the fallback;
    // absence is an explicit null, never a fabricated time (TE-0041 #1).
    out.push({ venue: book.key, home: h, away: a,
               lastUpdate: market.last_update ?? book.last_update ?? null });
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
