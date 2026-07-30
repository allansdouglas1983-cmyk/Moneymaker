// Tennis Edge — the API tier.
//
// This used to render HTML. It cannot: Supabase's gateway forces `content-type: text/plain`
// and a `default-src 'none'; sandbox` CSP onto every */functions/v1/* response, deliberately,
// so that nobody can host web pages on a supabase.co domain. An Edge Function is an API
// surface. The page lives in docs/index.html on GitHub Pages and calls this.
//
// It returns numbers. It never returns a recommendation. BET_CANDIDATE has no branch in
// scoring.ts that can produce it, and `recommendation` is pinned to NOT_EVALUATED by a
// database check constraint, so the store would refuse one even if something upstream
// invented it.
//
// Auth is a Supabase session bearer token, checked against the auth service on every
// request and then against an allowlist of one address. The browser holds a user token; the
// service-role key stays on this side and is what actually touches the tables.
import {
  bandSpread,
  COMMISSION,
  edgeBand,
  liveFeatures,
  type Model,
  type PlayerState,
  priceFixture,
  reasonsFor,
  statusFor,
} from "./scoring.ts";
import { budgetState, derivedBudgetPence, type PlacedBet, venueForBet } from "./trial.ts";
import {
  allVenueQuotes,
  entryTiming,
  minutesToStart,
  venueOf,
  bestOfFor,
  type FeedBookmaker,
  normalizeName,
  pickPrices,
  resolvePlayer,
  surfaceFor,
  surfaceIsKnown,
  tourOf,
} from "./board.ts";
import {
  login,
  marketBooks,
  SessionError,
  tennisMarkets,
} from "./betfair.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

/** The single account this service belongs to. Not a secret — an allowlist of one. */
const OWNER_EMAIL = "allansdouglas1983@gmail.com";

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "authorization, apikey, content-type",
  "access-control-allow-methods": "GET, POST, OPTIONS",
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...CORS, "content-type": "application/json" },
  });
}

async function db(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("apikey", SERVICE_KEY);
  headers.set("Authorization", "Bearer " + SERVICE_KEY);
  headers.set("Content-Type", "application/json");
  headers.set("Accept-Profile", "tennis");
  headers.set("Content-Profile", "tennis");
  return await fetch(SUPABASE_URL + "/rest/v1/" + path, { ...init, headers });
}

async function select<T>(path: string): Promise<T[]> {
  const response = await db(path);
  if (!response.ok) throw new Error(path + ": " + response.status + " " + await response.text());
  return await response.json() as T[];
}

/** The bearer must be a live Supabase session AND belong to the owner. Both, every request. */
async function owner(request: Request): Promise<boolean> {
  const header = request.headers.get("authorization") ?? "";
  if (!header.toLowerCase().startsWith("bearer ")) return false;
  const response = await fetch(SUPABASE_URL + "/auth/v1/user", {
    headers: { apikey: SERVICE_KEY, Authorization: header },
  });
  if (!response.ok) return false;
  const user = await response.json();
  return user?.email === OWNER_EMAIL;
}

interface StateRow extends PlayerState {
  tour: string;
  player: string;
  as_of: string;
}

interface MeetingRow {
  tour: string;
  player_a: string;
  player_b: string;
  wins_a: number;
  wins_b: number;
}

interface FixtureRow {
  match_key: string;
  match_date: string;
  tour: string;
  player_a: string;
  player_b: string;
  surface: string;
  best_of: number;
  odds_a: string;
  odds_b: string;
  source: string;
  /** Scheduled start. SCHEDULED, never actual — the live model may only know the
   *  scheduled time (SPEC-022). Absent on manual entries, which is a distinct state
   *  from actionable and is never defaulted. */
  commence_time?: string | null;
  /** When this price was captured. TE-0027 measured that acting on a stale price costs
   *  ~0.2% ROI, so the age is served and shown rather than left implicit. */
  updated_at?: string;
}

function matchKey(date: string, tour: string, a: string, b: string): string {
  const sorted = [a, b].map((n) => n.trim()).sort();
  return date + "|" + tour + "|" + sorted[0] + "|" + sorted[1];
}

/** Serve baseline by tour. Frozen defaults, used when the state carries no tour figure. */
const SERVE_BASELINE: Record<string, number> = { ATP: 0.6467, WTA: 0.5786 };

function assess(
  fixture: FixtureRow,
  states: Map<string, StateRow>,
  meetings: Map<string, [number, number]>,
  model: Model,
  stateAsOf: string,
  staleDays: number,
) {
  const oddsA = Number(fixture.odds_a);
  const oddsB = Number(fixture.odds_b);
  const impliedA = 1.0 / oddsA;
  const impliedB = 1.0 / oddsB;
  const a = states.get(fixture.tour + "|" + fixture.player_a) ?? null;
  const b = states.get(fixture.tour + "|" + fixture.player_b) ?? null;
  // Head-to-head is stored once under the sorted pair, so a fixture written either way
  // round resolves to the same record; the orientation is restored here.
  const sorted = [fixture.player_a, fixture.player_b].slice().sort();
  const record = meetings.get(fixture.tour + "|" + sorted[0] + "|" + sorted[1]) ?? null;
  const pair: [number, number] | null = record === null
    ? null
    : (fixture.player_a === sorted[0] ? record : [record[1], record[0]]);

  // A match dated before the state date cannot be priced from it: the state has already
  // absorbed the result. Reported as no features rather than a confident prediction.
  const features = fixture.match_date >= stateAsOf
    ? liveFeatures({
      a,
      b,
      meetings: pair,
      surface: fixture.surface,
      bestOf: fixture.best_of,
      marketProbability: impliedA / (impliedA + impliedB),
      matchDate: fixture.match_date,
      serveBaseline: SERVE_BASELINE[fixture.tour] ?? 0.62,
    })
    : {};
  const prediction = priceFixture(oddsA, oddsB, features, model);
  const bestEdge = Math.max(prediction.edgeA, prediction.edgeB);
  // Manual entries carry a price but not its age, so the stratum is unknown and the
  // band takes the pooled conservative fallback — never a claimed stratum (TE-0017 S6).
  const spread = bandSpread(null);
  const bandA = edgeBand(oddsA, spread);
  const bandB = edgeBand(oddsB, spread);
  return {
    fixture,
    prediction,
    status: statusFor(features, bestEdge),
    reasons: reasonsFor(features, prediction, staleDays),
    bestSide: prediction.edgeA >= prediction.edgeB ? "A" : "B",
    bestEdge,
    bestBand: prediction.edgeA >= prediction.edgeB ? bandA : bandB,
  };
}

/** Snake_case for the wire: the page reads it, and the database columns match. */
function wire(row: ReturnType<typeof assess>) {
  const p = row.prediction;
  const capturedAt = row.fixture.updated_at;
  return {
    fixture: row.fixture,
    price_age_minutes: capturedAt
      ? Math.max(0, Math.round((Date.now() - Date.parse(capturedAt)) / 60000))
      : null,
    // Advisory only. Changes no probability, no edge and no status, and authorises
    // nothing — every bet stays founder-manual under the ADR 0020 protocol.
    minutes_to_start: minutesToStart(row.fixture.commence_time),
    entry_timing: entryTiming(row.fixture.commence_time),
    status: row.status,
    reasons: row.reasons,
    best_side: row.bestSide,
    best_edge: row.bestEdge,
    best_band: row.bestBand,
    prediction: {
      market_probability_a: p.marketProbabilityA,
      market_probability_b: p.marketProbabilityB,
      probability_a: p.probabilityA,
      probability_b: p.probabilityB,
      fair_odds_a: p.fairOddsA,
      fair_odds_b: p.fairOddsB,
      break_even_a: p.breakEvenA,
      break_even_b: p.breakEvenB,
      edge_a: p.edgeA,
      edge_b: p.edgeB,
      features: p.features,
      contributions: p.contributions,
    },
  };
}

async function context() {
  const results = await Promise.all([
    select<Model & { is_current: boolean }>("model?is_current=eq.true&limit=1"),
    select<StateRow>("player_state?select=*"),
    select<MeetingRow>("head_to_head?select=*"),
  ]);
  const model = results[0][0] ?? null;
  const meetings = new Map<string, [number, number]>();
  for (const row of results[2]) {
    meetings.set(row.tour + "|" + row.player_a + "|" + row.player_b,
                 [row.wins_a, row.wins_b]);
  }
  const states = new Map<string, StateRow>();
  let asOf = "";
  for (const row of results[1]) {
    states.set(row.tour + "|" + row.player, row);
    if (row.as_of > asOf) asOf = row.as_of;
  }
  const today = new Date().toISOString().slice(0, 10);
  const staleDays = asOf
    ? Math.round((Date.parse(today + "T00:00:00Z") - Date.parse(asOf + "T00:00:00Z")) / 86400000)
    : 0;
  return { model, states, meetings, asOf, staleDays, today };
}

async function board(): Promise<Response> {
  const ctx = await context();
  if (!ctx.model) return json({ error: "no current model row — run the refresh job" }, 503);
  const fixtures = await select<FixtureRow>(
    "fixtures?match_date=gte." + ctx.today +
      "&select=match_key,match_date,tour,player_a,player_b,surface,best_of," +
      "odds_a,odds_b,source,commence_time,updated_at&order=match_date.asc",
  );
  const rows = fixtures
    .map((f) => assess(f, ctx.states, ctx.meetings, ctx.model!, ctx.asOf, ctx.staleDays))
    .sort((x, y) => {
      const rank = (r: typeof x) =>
        r.status === "BET_CANDIDATE_DISABLED" ? 0 : r.status === "LEAN" ? 1 : 2;
      return rank(x) - rank(y) || y.bestEdge - x.bestEdge;
    });
  // The live bank and its high-water mark ride along so the page's stake column and
  // every device share ONE bank (ADR 0020 Amendment 5) instead of per-phone copies.
  const [bankRaw, peakRaw] = await Promise.all([
    getConfig("bank_pence"), getConfig("bank_peak_pence"),
  ]);
  return json({
    model_digest: ctx.model.digest,
    model_trained_through: ctx.model.trained_through,
    state_as_of: ctx.asOf,
    state_players: ctx.states.size,
    state_stale_days: ctx.staleDays,
    bank_pence: bankRaw === null ? null : Number(bankRaw),
    bank_peak_pence: peakRaw === null ? null : Number(peakRaw),
    derived_budget_pence: derivedBudgetPence(bankRaw === null ? null : Number(bankRaw)),
    rows: rows.map(wire),
  });
}

async function price(request: Request): Promise<Response> {
  const body = await request.json().catch(() => ({}));
  const text = (name: string) => String(body[name] ?? "").trim();

  const playerA = text("player_a");
  const playerB = text("player_b");
  const oddsA = text("odds_a");
  const oddsB = text("odds_b");
  const date = text("match_date");
  const tour = text("tour") || "ATP";
  const bestOf = Number(body.best_of ?? 3);

  // Refuse rather than drop. A silently rejected fixture is one nobody notices is missing,
  // and the match you wanted a price on is the one most likely to be typed wrong.
  if (!playerA || !playerB) return json({ error: "Both players are required." }, 400);
  if (playerA === playerB) return json({ error: "The same player is on both sides." }, 400);
  for (const pair of [["A", oddsA], ["B", oddsB]] as Array<[string, string]>) {
    const value = Number(pair[1]);
    if (!Number.isFinite(value) || !(value > 1)) {
      return json({ error: "Price " + pair[0] + " must be a decimal above 1." }, 400);
    }
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return json({ error: "A match date is required." }, 400);
  if (bestOf !== 3 && bestOf !== 5) return json({ error: "Best of must be 3 or 5." }, 400);

  const key = matchKey(date, tour, playerA, playerB);
  const fixture: FixtureRow = {
    match_key: key,
    match_date: date,
    tour,
    player_a: playerA,
    player_b: playerB,
    surface: text("surface") || "Hard",
    best_of: bestOf,
    odds_a: oddsA,
    odds_b: oddsB,
    source: "MANUAL_BETFAIR_UI",
  };

  const stored = await db("fixtures?on_conflict=match_key", {
    method: "POST",
    headers: { Prefer: "resolution=merge-duplicates" },
    body: JSON.stringify([{ ...fixture, updated_at: new Date().toISOString() }]),
  });
  if (!stored.ok) return json({ error: await stored.text() }, 500);

  // A prediction is minted when the price is entered and never revised. A later view of the
  // same match is a new row, so the record shows what was believed when; there is no outcome
  // field here that could rewrite it afterwards.
  const ctx = await context();
  if (!ctx.model) return json({ error: "no current model row" }, 503);
  const row = await mintPrediction(fixture, ctx);
  return json({ ok: true, row: wire(row) });
}

/** Single-row config store; service-role only (RLS with no policies). */
async function getConfig(key: string): Promise<string | null> {
  const rows = await select<{ value: string }>(
    "config?key=eq." + encodeURIComponent(key) + "&select=value");
  return rows[0]?.value ?? null;
}

async function setConfig(key: string, value: string): Promise<void> {
  await db("config?on_conflict=key", {
    method: "POST",
    headers: { Prefer: "resolution=merge-duplicates" },
    body: JSON.stringify([{ key, value, updated_at: new Date().toISOString() }]),
  });
}

/** Mint the append-only prediction row for a fixture — the identical path for manual
 *  entries and the automated feed, so the ledger never contains two kinds of number. */
async function mintPrediction(
  fixture: FixtureRow,
  ctx: Awaited<ReturnType<typeof context>>,
): Promise<ReturnType<typeof assess>> {
  const row = assess(fixture, ctx.states, ctx.meetings, ctx.model!, ctx.asOf,
                     ctx.staleDays);
  const p = row.prediction;
  await db("predictions", {
    method: "POST",
    body: JSON.stringify([{
      match_key: fixture.match_key,
      match_date: fixture.match_date,
      tour: fixture.tour,
      player_a: fixture.player_a,
      player_b: fixture.player_b,
      surface: fixture.surface,
      best_of: fixture.best_of,
      odds_a: fixture.odds_a,
      odds_b: fixture.odds_b,
      market_probability_a: p.marketProbabilityA,
      probability_a: p.probabilityA,
      fair_odds_a: p.fairOddsA,
      fair_odds_b: p.fairOddsB,
      break_even_a: p.breakEvenA,
      break_even_b: p.breakEvenB,
      edge_a: p.edgeA,
      edge_b: p.edgeB,
      // The venue whose quote priced this decision, recorded HERE because `fixtures` is
      // UPDATE-in-place: after the next refresh overwrites the fixture, the prediction
      // would otherwise have no way to say which exchange it was priced at. Any
      // venue-relative measurement — CLV above all — must compare like with like.
      price_venue: venueOf(fixture.source),
      commission: COMMISSION,
      // 2% is the founder-confirmed Basic-package rate (TE-0044), but still an ASSUMPTION,
      // not a rate read off an account statement. SPEC-081 makes the statement truth; until
      // one is read this label keeps the assumption from being mistaken downstream for a
      // verified fact. A wrong rate moves break-even by roughly 0.5-0.9 probability points,
      // which mis-fires every bet whose edge sits in that strip.
      commission_source: "ASSUMPTION",
      features: p.features,
      contributions: p.contributions,
      reasons: row.reasons,
      status: row.status,
      recommendation: "NOT_EVALUATED",
      model_digest: ctx.model!.digest,
      state_as_of: ctx.asOf,
    }]),
  });
  return row;
}

const ODDS_HOST = "https://api.the-odds-api.com";
/** uk region carries the exchange (betfair_ex_uk) plus smarkets/matchbook, at one
 *  credit per tournament per refresh — the 500/month free tier holds even in slam
 *  weeks at three refreshes a day. */
const ODDS_REGIONS = "uk";
const REFRESH_MIN_HOURS = 6;

interface FeedEvent {
  commence_time: string;
  home_team: string;
  away_team: string;
  bookmakers: FeedBookmaker[];
}

/**
 * The board fills itself: active tennis tournaments -> exchange odds -> corpus-named
 * fixtures -> the identical mint path manual entries use. Public but throttled: a
 * caller cannot spend credits more than once per REFRESH_MIN_HOURS, and the response
 * carries counts, never data. Unmapped names become display-only fixtures (the site
 * already degrades them to INSUFFICIENT_DATA honestly); they never mint ledger rows.
 */
async function boardRefresh(): Promise<Response> {
  const apiKey = await getConfig("odds_api_key");
  if (!apiKey) return json({ error: "no odds_api_key configured" }, 503);

  const last = await getConfig("odds_last_refresh");
  const ageHours = last
    ? (Date.now() - Date.parse(last)) / 3600000
    : Number.POSITIVE_INFINITY;
  if (ageHours < REFRESH_MIN_HOURS) {
    return json({ skipped: true, last_refresh: last,
                  next_after_hours: REFRESH_MIN_HOURS - ageHours });
  }
  // Stamp before spending: a failing upstream must not be retried into credit drain.
  await setConfig("odds_last_refresh", new Date().toISOString());

  const sportsResponse = await fetch(ODDS_HOST + "/v4/sports/?apiKey=" + apiKey);
  if (!sportsResponse.ok) {
    return json({ error: "sports list: " + sportsResponse.status }, 502);
  }
  const sports = (await sportsResponse.json() as Array<{ key: string; active: boolean }>)
    .filter((s) => s.active && tourOf(s.key) !== null);

  const ctx = await context();
  if (!ctx.model) return json({ error: "no current model row" }, 503);
  const indexByTour = new Map<string, Map<string, string>>();
  for (const [key] of ctx.states) {
    const [tour, player] = [key.slice(0, key.indexOf("|")),
                            key.slice(key.indexOf("|") + 1)];
    let index = indexByTour.get(tour);
    if (!index) indexByTour.set(tour, index = new Map());
    index.set(normalizeName(player), player);
  }
  // Human corrections beat the spelling heuristic and are never re-guessed.
  const aliasByTour = new Map<string, Map<string, string>>();
  for (const row of await select<{ feed_name: string; tour: string; player: string }>(
    "player_aliases?select=feed_name,tour,player")) {
    let map = aliasByTour.get(row.tour);
    if (!map) aliasByTour.set(row.tour, map = new Map());
    map.set(row.feed_name, row.player);
  }

  let fixtures = 0, minted = 0, unmapped = 0, unpriced = 0, observations = 0;
  let creditsRemaining: string | null = null;
  const books: Record<string, number> = {};
  const today = new Date().toISOString().slice(0, 10);

  for (const sport of sports) {
    const response = await fetch(
      ODDS_HOST + "/v4/sports/" + sport.key + "/odds/?regions=" + ODDS_REGIONS +
        "&markets=h2h&apiKey=" + apiKey);
    if (!response.ok) continue;
    creditsRemaining = response.headers.get("x-requests-remaining") ?? creditsRemaining;
    const tour = tourOf(sport.key)!;
    const index = indexByTour.get(tour) ?? new Map<string, string>();
    const aliases = aliasByTour.get(tour);

    for (const event of await response.json() as FeedEvent[]) {
      const picked = pickPrices(event.bookmakers, event.home_team, event.away_team);
      if (picked === null) {
        unpriced += 1;
        continue;
      }
      books[picked.book] = (books[picked.book] ?? 0) + 1;
      const mappedHome = resolvePlayer(event.home_team, index, aliases);
      const mappedAwayEarly = resolvePlayer(event.away_team, index, aliases);
      // Capture EVERY venue's quote, whether or not the players map. An unmappable
      // match still carries a price series, and the market-side analyses (line
      // shopping, closing-line value) do not need the model to have an opinion.
      const observationKey = matchKey(
        event.commence_time.slice(0, 10), tour,
        mappedHome ?? event.home_team, mappedAwayEarly ?? event.away_team);
      const quotes = allVenueQuotes(event.bookmakers, event.home_team, event.away_team);
      if (quotes.length > 0) {
        const captured = new Date().toISOString();
        const written = await db("price_observations?on_conflict=match_key,venue,captured_at", {
          method: "POST",
          headers: { Prefer: "resolution=ignore-duplicates" },
          body: JSON.stringify(quotes.map((q) => ({
            match_key: observationKey,
            tour,
            venue: q.venue,
            odds_a: q.home,
            odds_b: q.away,
            commence_time: event.commence_time,
            captured_at: captured,
            venue_last_update: q.lastUpdate,
          }))),
        });
        if (written.ok) observations += quotes.length;
      }
      const mappedAway = mappedAwayEarly;
      const playerA = mappedHome ?? event.home_team;
      const playerB = mappedAway ?? event.away_team;
      // A tournament the derived table does not establish is served as Hard — a guess.
      // Record it so the gap closes from data rather than surfacing as a wrong
      // prediction in the clay swing months from now.
      if (!surfaceIsKnown(sport.key)) {
        await db("rpc/note_unmapped_tournament", {
          method: "POST",
          body: JSON.stringify({
            p_sport_key: sport.key,
            p_tour: tour,
            p_served_surface: surfaceFor(sport.key),
          }),
        });
      }
      const date = event.commence_time.slice(0, 10);
      const fixture: FixtureRow = {
        match_key: matchKey(date, tour, playerA, playerB),
        match_date: date,
        tour,
        player_a: playerA,
        player_b: playerB,
        surface: surfaceFor(sport.key),
        best_of: bestOfFor(sport.key),
        odds_a: String(picked.home),
        odds_b: String(picked.away),
        source: "ODDS_API_" + picked.book.toUpperCase(),
        commence_time: event.commence_time,
      };
      const stored = await db("fixtures?on_conflict=match_key", {
        method: "POST",
        headers: { Prefer: "resolution=merge-duplicates" },
        body: JSON.stringify([{ ...fixture, updated_at: new Date().toISOString() }]),
      });
      if (!stored.ok) continue;
      fixtures += 1;

      if (mappedHome === null || mappedAway === null) {
        unmapped += 1;
        // Record WHICH name failed. An uncounted gap is a gap nobody can close, and
        // each one is a match the board shows with no opinion — evidence not collected.
        for (const [feedName, mapped] of
             [[event.home_team, mappedHome], [event.away_team, mappedAway]] as
               Array<[string, string | null]>) {
          if (mapped !== null) continue;
          await db("rpc/note_unmapped", {
            method: "POST",
            body: JSON.stringify({ p_feed_name: normalizeName(feedName), p_tour: tour }),
          });
        }
        continue;
      }
      // One auto-minted ledger row per match per UTC day: odds drift within a day
      // updates the board but never spams the append-only record.
      const existing = await select<{ created_at: string }>(
        "predictions?match_key=eq." + encodeURIComponent(fixture.match_key) +
          "&select=created_at&order=created_at.desc&limit=1");
      if (existing[0]?.created_at?.slice(0, 10) === today) continue;
      await mintPrediction(fixture, ctx);
      minted += 1;
    }
  }
  return json({
    refreshed: true,
    tournaments: sports.map((s) => s.key),
    fixtures_upserted: fixtures,
    predictions_minted: minted,
    unmapped_names: unmapped,
    price_observations_written: observations,
    unmapped_queue: (await select<{ feed_name: string; tour: string; seen_count: number }>(
      "unmapped_names?select=feed_name,tour,seen_count&order=seen_count.desc&limit=20")),
    unpriced_matches: unpriced,
    books_used: books,
    credits_remaining: creditsRemaining,
  });
}

const CAPTURE_MIN_MINUTES = 20;

/** A session is hours-lived; cache it and re-login only on auth-shaped failure. */
async function betfairSession(appKey: string): Promise<string> {
  const cached = await getConfig("betfair_session_token");
  const at = await getConfig("betfair_session_at");
  if (cached && at && Date.now() - Date.parse(at) < 6 * 3600000) return cached;
  const username = await getConfig("betfair_username");
  const password = await getConfig("betfair_password");
  const cert = await getConfig("betfair_client_cert");
  const key = await getConfig("betfair_client_key");
  if (!username || !password) throw new Error("betfair credentials not configured");
  if (!cert || !key) throw new Error("betfair client certificate not configured");
  const token = await login(username, password, appKey, cert, key);
  await setConfig("betfair_session_token", token);
  await setConfig("betfair_session_at", new Date().toISOString());
  return token;
}

/**
 * Order-book capture on the DELAYED key (ADR 0020 / SPEC-112): every pre-off tennis
 * Match Odds singles market in the next 36 hours, best three levels each side plus
 * traded volume, stored whole. Public but throttled; responds with counts only.
 */
async function bookCapture(): Promise<Response> {
  const appKey = await getConfig("betfair_delayed_app_key");
  if (!appKey) return json({ error: "no betfair_delayed_app_key configured" }, 503);

  const last = await getConfig("betfair_last_capture");
  const ageMinutes = last
    ? (Date.now() - Date.parse(last)) / 60000
    : Number.POSITIVE_INFINITY;
  if (ageMinutes < CAPTURE_MIN_MINUTES) {
    return json({ skipped: true, next_after_minutes: CAPTURE_MIN_MINUTES - ageMinutes });
  }
  await setConfig("betfair_last_capture", new Date().toISOString());

  let token = await betfairSession(appKey);
  let markets;
  try {
    markets = await tennisMarkets(appKey, token);
  } catch (error) {
    if (!(error instanceof SessionError)) throw error;
    // Session died — one fresh login, one retry, never a loop.
    await setConfig("betfair_session_at", "1970-01-01T00:00:00Z");
    token = await betfairSession(appKey);
    markets = await tennisMarkets(appKey, token);
  }
  if (markets.length === 0) {
    return json({ refreshed: true, markets: 0, snapshots: 0 });
  }

  const byId = new Map(markets.map((m) => [m.marketId, m]));
  const books = await marketBooks([...byId.keys()], appKey, token);
  const rows = books.map((book) => {
    const catalogue = byId.get(book.marketId);
    return {
      market_id: book.marketId,
      event_name: catalogue?.event?.name ?? null,
      market_start: catalogue?.marketStartTime ?? null,
      market_status: book.status,
      inplay: book.inplay,
      total_matched: book.totalMatched ?? null,
      book: {
        runners: (book.runners ?? []).map((r) => ({
          selection_id: r.selectionId,
          name: catalogue?.runners?.find((c) => c.selectionId === r.selectionId)
            ?.runnerName ?? null,
          status: r.status,
          last_price_traded: r.lastPriceTraded ?? null,
          total_matched: r.totalMatched ?? null,
          available_to_back: r.ex?.availableToBack ?? [],
          available_to_lay: r.ex?.availableToLay ?? [],
        })),
      },
    };
  });
  const stored = await db("book_snapshots", {
    method: "POST",
    body: JSON.stringify(rows),
  });
  if (!stored.ok) return json({ error: await stored.text() }, 500);
  return json({ refreshed: true, markets: markets.length, snapshots: rows.length });
}

// budgetState and the founder-verified venue registry live in trial.ts (TE-0041 #6),
// where their governance properties are pinned by tests: the budget is venue-blind
// (SPEC-103) and an unregistered venue is a refusal, never a default commission.

/**
 * Record a bet the founder has ALREADY placed by hand on their own account. This
 * flow places nothing — it is the trial's append-only memory (ADR 0020), and it is
 * the only writer that can refuse: no budget set, or budget exhausted, means no row.
 */
async function recordBet(request: Request): Promise<Response> {
  const body = await request.json().catch(() => ({}));
  const matchKeyValue = String(body.match_key ?? "").trim();
  const side = String(body.side ?? "").trim().toUpperCase();
  const stake = Number(body.stake);
  const matchedOdds = Number(body.matched_odds);

  if (!matchKeyValue) return json({ error: "match_key is required." }, 400);
  if (side !== "A" && side !== "B") return json({ error: "side must be A or B." }, 400);
  if (!Number.isFinite(stake) || !(stake > 0)) {
    return json({ error: "stake must be a positive number." }, 400);
  }
  if (!Number.isFinite(matchedOdds) || !(matchedOdds > 1)) {
    return json({ error: "matched_odds must be a decimal above 1." }, 400);
  }
  // TE-0041 #6: venue provenance. Only founder-verified venues are recordable — an
  // unregistered venue has no verified commission, so recording it would fabricate a
  // cost. Refusal writes no row. This records venues; it never recommends one.
  const venueEntry = venueForBet(body.venue == null ? undefined : String(body.venue));
  if (venueEntry === null) {
    return json({ error: "Venue is not in the founder-verified registry — its " +
      "commission is unverified, so the bet cannot be costed. Register the venue " +
      "(a founder act) before recording bets at it." }, 409);
  }

  // The budget DERIVES from the live bank — 30% of it, the registered cap, so this
  // guard and the staking policy agree about the worst case by construction (ADR 0020
  // Amendment 5). Editing the bank in the app is the deliberate act that re-derives it.
  const bankRaw = await getConfig("bank_pence");
  const budgetPence = derivedBudgetPence(bankRaw === null ? null : Number(bankRaw));
  if (budgetPence === null) {
    return json({ error: "No bank is set. Enter your bank in the app first — the loss " +
      "budget derives from it (30% of bank, the registered cap; ADR 0020)." }, 409);
  }
  const bets = await select<PlacedBet>("placed_bets?select=stake,status,pnl");
  const state = budgetState(String(budgetPence / 100), bets);
  if (state.exhausted) {
    return json({ error: "The derived loss budget (30% of the bank) is spent by settled " +
      "losses. Recording is refused; updating the bank in the app is the deliberate act " +
      "that re-derives it (ADR 0020).", ...state }, 409);
  }

  const fixtures = await select<FixtureRow>(
    "fixtures?match_key=eq." + encodeURIComponent(matchKeyValue));
  const fixture = fixtures[0];
  if (!fixture) return json({ error: "Unknown match_key — price the match first." }, 404);

  const stored = await db("placed_bets", {
    method: "POST",
    body: JSON.stringify([{
      match_key: fixture.match_key,
      match_date: fixture.match_date,
      tour: fixture.tour,
      player_a: fixture.player_a,
      player_b: fixture.player_b,
      side,
      stake,
      matched_odds: matchedOdds,
      // The venue's founder-verified rate — valid per bet only because v1 enforces one
      // selection per market (SPEC-080: commission is on the net market result).
      commission: venueEntry.commission,
      venue: venueEntry.venue,
      // The board's quoted price for this side at recording time: each real fill's
      // quoted-vs-matched gap is a direct observation of the execution-cost band
      // (TE-0020) that no historical archive can provide. Null when absent — never 0.
      quoted_odds_at_decision:
        (side === "A" ? fixture.odds_a : fixture.odds_b) ?? null,
    }]),
  });
  if (!stored.ok) return json({ error: await stored.text() }, 500);
  return json({ ok: true, ...budgetState(String(budgetPence / 100), bets) });
}

/**
 * Set or edit the live bank (founder directive 2026-07-30; ADR 0020 Amendment 5).
 * The loss budget is never set directly any more — it DERIVES as 30% of this bank
 * (the registered cap), so it moves whenever the bank does. The high-water mark
 * ratchets up with the bank; `reset_peak: true` is the explicit founder act that
 * re-bases it (a fresh bankroll), never a default.
 */
async function setBank(request: Request): Promise<Response> {
  const body = await request.json().catch(() => ({}));
  const bank = Number(body.bank);
  if (!Number.isFinite(bank) || !(bank > 0)) {
    return json({ error: "bank must be a positive number of pounds." }, 400);
  }
  const pence = Math.round(bank * 100);
  const prevPeakRaw = await getConfig("bank_peak_pence");
  const prevPeak = prevPeakRaw === null ? 0 : Number(prevPeakRaw);
  const peak = body.reset_peak === true ? pence : Math.max(prevPeak, pence);
  await setConfig("bank_pence", String(pence));
  await setConfig("bank_peak_pence", String(peak));
  return json({
    ok: true,
    bank_pence: pence,
    bank_peak_pence: peak,
    derived_budget_pence: derivedBudgetPence(pence),
  });
}

async function ledger(): Promise<Response> {
  const [predictions, settled, placed, bankRaw] = await Promise.all([
    select<Record<string, unknown>>(
      "predictions?select=match_key,match_date,player_a,player_b,status,edge_a,edge_b" +
        "&order=created_at.desc&limit=100"),
    select<Record<string, unknown>>(
      "ledger?select=*&order=match_date.desc&limit=200"),
    select<PlacedBet & Record<string, unknown>>(
      "placed_bets?select=*&order=placed_at.desc&limit=200"),
    getConfig("bank_pence"),
  ]);
  const bankPence = bankRaw === null ? null : Number(bankRaw);
  const budgetPence = derivedBudgetPence(bankPence);
  return json({
    predictions,
    settled,
    placed_bets: placed,
    real: {
      bank: bankPence === null ? null : bankPence / 100,
      budget_rule: "30% of the current bank — the registered cap (TE-0047); derives " +
        "automatically whenever the bank changes (ADR 0020 Amendment 5)",
      ...budgetState(budgetPence === null ? null : String(budgetPence / 100), placed),
      realised_pnl: Math.round(placed.reduce(
        (a, b) => a + (typeof b.pnl === "number" ? b.pnl : 0), 0) * 100) / 100,
    },
  });
}

/**
 * The site grades its own served predictions (TE-0017 S6). Monitoring with intervals,
 * EXPLICITLY NON-GATING: nothing here feeds anything served — not MIN_EDGE, not the
 * staleness thresholds, not the model. Single-user volume can gate nothing, and this
 * number is never comparable to the 63,676-match research intervals.
 */
// Day-clustered percentile interval, deterministically seeded so two loads of the page
// show the same numbers. Null below five distinct days — no interval rather than a
// misleading one.
function interval95(days: number[][], seedStart: number): [number, number] | null {
  if (days.length < 5) return null;
  let seed = seedStart;
  const random = () => {
    // Park-Miller: deterministic across loads; statistical polish is irrelevant here.
    seed = (seed * 48271) % 2147483647;
    return seed / 2147483647;
  };
  const draws: number[] = [];
  for (let d = 0; d < 2000; d++) {
    const sample: number[] = [];
    for (let i = 0; i < days.length; i++) {
      sample.push(...days[Math.floor(random() * days.length)]);
    }
    draws.push(sample.reduce((a, b) => a + b, 0) / sample.length);
  }
  draws.sort((a, b) => a - b);
  return [draws[Math.floor(0.025 * draws.length)],
          draws[Math.floor(0.975 * draws.length)]];
}

async function scorecard(): Promise<Response> {
  const [predictions, ledger, resultDays, forecasts] = await Promise.all([
    select<{ match_key: string; match_date: string; tour: string; created_at: string }>(
      "predictions?select=match_key,match_date,tour,created_at"),
    select<{ match_key: string; match_date: string; a_won: boolean; completion: string;
             model_log_loss: number | null; market_log_loss: number | null }>(
      "ledger?select=match_key,match_date,a_won,completion,model_log_loss,market_log_loss"),
    select<{ match_date: string; tour: string }>("results?select=match_date,tour"),
    select<{ match_date: string; p_model: number; p_market: number; won_a: boolean;
             state_as_of: string }>(
      "forecasts?select=match_date,p_model,p_market,won_a,state_as_of"),
  ]);

  // The declared vintage policy: one row per match, the last created on or before the
  // match date. Post-match rows are excluded from the denominator entirely.
  const byMatch = new Map<string, { match_date: string; tour: string; created_at: string }>();
  let postMatchOnly = 0;
  const seenKeys = new Set<string>();
  for (const p of predictions) seenKeys.add(p.match_key);
  for (const p of predictions) {
    if (p.created_at.slice(0, 10) > p.match_date) continue;
    const current = byMatch.get(p.match_key);
    if (!current || p.created_at > current.created_at) byMatch.set(p.match_key, p);
  }
  for (const key of seenKeys) if (!byMatch.has(key)) postMatchOnly += 1;

  const graded = new Set(ledger.map((l) => l.match_key));
  const covered = new Set(resultDays.map((r) => r.match_date + "|" + r.tour));
  let pending = 0;
  let unmatched = 0;
  for (const [key, p] of byMatch) {
    if (graded.has(key)) continue;
    if (covered.has(p.match_date + "|" + p.tour)) unmatched += 1;
    else pending += 1;
  }

  // Paired model-vs-market log-loss over graded rows, day-clustered. Deterministic
  // seeded bootstrap so two loads of the page show the same interval.
  const scored = ledger.filter((l) =>
    l.model_log_loss != null && l.market_log_loss != null);
  const byDay = new Map<string, number[]>();
  for (const l of scored) {
    const diff = (l.market_log_loss as number) - (l.model_log_loss as number);
    const day = byDay.get(l.match_date) ?? [];
    day.push(diff);
    byDay.set(l.match_date, day);
  }
  const days = [...byDay.values()];
  const all = days.flat();
  const mean = all.length ? all.reduce((a, b) => a + b, 0) / all.length : null;
  const interval = interval95(days, 20260728);

  // The automatic ledger: the served state graded weekly against Bet365 on every
  // completed corpus match — no manual entry involved, so it accumulates regardless.
  const logLoss = (p: number, won: boolean) =>
    -Math.log(Math.min(Math.max(won ? p : 1 - p, 1e-6), 1 - 1e-6));
  const autoByDay = new Map<string, number[]>();
  for (const f of forecasts) {
    const diff = logLoss(f.p_market, f.won_a) - logLoss(f.p_model, f.won_a);
    const day = autoByDay.get(f.match_date) ?? [];
    day.push(diff);
    autoByDay.set(f.match_date, day);
  }
  const autoDays = [...autoByDay.values()];
  const autoAll = autoDays.flat();
  const autoMean = autoAll.length
    ? autoAll.reduce((a, b) => a + b, 0) / autoAll.length : null;
  const autoInterval = interval95(autoDays, 20260729);

  return json({
    automatic: {
      graded: forecasts.length,
      distinct_days: autoDays.length,
      state_vintages: new Set(forecasts.map((f) => f.state_as_of)).size,
      paired_log_loss_gain: autoMean,
      interval_95: autoInterval,
      note: "The committed weekly state graded against the Bet365 book on every " +
        "completed corpus match — knowledge-time enforced by git history, no manual " +
        "entry involved. Bet365 baseline, not Betfair: never comparable to the manual " +
        "ledger's exchange prices, and it feeds nothing served.",
    },
    denominator: {
      matches_predicted: byMatch.size,
      graded: graded.size,
      pending_result: pending,
      unmatched_name: unmatched,
      post_match_rows_excluded: postMatchOnly,
    },
    model_wins: scored.filter((l) =>
      (l.model_log_loss as number) < (l.market_log_loss as number)).length,
    paired_log_loss_gain: mean,
    interval_95: interval,
    interval_note: interval === null
      ? "Fewer than five distinct match days graded; no interval is shown rather than a misleading one."
      : "Day-clustered bootstrap. Monitoring only.",
    non_gating: "This scorecard feeds nothing served and gates nothing. A single user's " +
      "volume cannot resolve model quality, and this number is never comparable to the " +
      "research intervals measured on 63,676 matches.",
  });
}

/**
 * Closing-line value: did the market move TOWARD the side we picked?
 *
 * This is the fastest honest read on whether a live edge exists. Settled P&L on a ~2%
 * edge needs tens of thousands of bets to clear noise (TE-0012); CLV is a continuous
 * per-bet measurement of the same underlying claim and converges far sooner. TE-0027
 * already found the exchange price drifts toward this model's picks on historical data
 * — this endpoint asks whether that keeps happening LIVE, on predictions minted before
 * the move.
 *
 * Measured in de-vigged probability points on the picked side: decision-time probability
 * versus the last observation before the off. Positive means the market came to us.
 *
 * DIAGNOSTIC. CLV is evidence about edge, not profit, and SPEC-095 forbids it as a
 * training target. It gates nothing and feeds nothing served.
 */
async function clv(): Promise<Response> {
  const [predictions, observations] = await Promise.all([
    select<{ match_key: string; match_date: string; odds_a: string; odds_b: string;
             edge_a: number; edge_b: number; created_at: string;
             price_venue: string | null }>(
      "predictions?select=match_key,match_date,odds_a,odds_b,edge_a,edge_b,created_at," +
        "price_venue&order=created_at.desc&limit=2000"),
    select<{ match_key: string; venue: string; odds_a: string; odds_b: string;
             commence_time: string; captured_at: string }>(
      "price_observations?select=match_key,venue,odds_a,odds_b,commence_time,captured_at" +
        "&venue=eq.betfair_ex_uk&order=captured_at.asc&limit=20000"),
  ]);

  // Last observation strictly BEFORE the off is the closing line. An observation after
  // commence is in-play data and must never enter (hard prohibition).
  const closing = new Map<string, { odds_a: string; odds_b: string }>();
  for (const o of observations) {
    if (o.commence_time && o.captured_at >= o.commence_time) continue;
    closing.set(o.match_key, { odds_a: o.odds_a, odds_b: o.odds_b });
  }

  const devig = (a: number, b: number): [number, number] => {
    const ia = 1 / a, ib = 1 / b;
    return [ia / (ia + ib), ib / (ia + ib)];
  };

  const byDay = new Map<string, number[]>();
  let positive = 0, scored = 0;
  // One row per match: the LAST prediction created on or before the match date, matching
  // the scorecard's declared vintage policy so the two denominators agree.
  const latest = new Map<string, typeof predictions[number]>();
  for (const p of predictions) {
    if (p.created_at.slice(0, 10) > p.match_date) continue;
    const held = latest.get(p.match_key);
    if (!held || p.created_at > held.created_at) latest.set(p.match_key, p);
  }
  // The closing line above is Betfair-only. A decision price from a different exchange
  // measured against a Betfair close is not closing-line value — it is the sum of a
  // genuine market move and a fixed cross-venue quote difference, and the two cannot be
  // separated after the fact. The venue gap is of order 0.1-0.9 de-vigged probability
  // points against a CLV signal of order 0.05, so mixing does not add noise, it swamps
  // the measurement. Mismatched rows are EXCLUDED and COUNTED, never silently dropped.
  let venueMismatched = 0, venueUnknown = 0;
  for (const [key, p] of latest) {
    const close = closing.get(key);
    if (!close) continue;
    if (p.price_venue === null) { venueUnknown += 1; continue; }
    if (p.price_venue !== "betfair_ex_uk") { venueMismatched += 1; continue; }
    const [openA, openB] = devig(Number(p.odds_a), Number(p.odds_b));
    const [closeA, closeB] = devig(Number(close.odds_a), Number(close.odds_b));
    // The side the rule would have backed is the side with the larger edge.
    const pickedA = p.edge_a >= p.edge_b;
    const move = pickedA ? closeA - openA : closeB - openB;
    const day = byDay.get(p.match_date) ?? [];
    day.push(move);
    byDay.set(p.match_date, day);
    scored += 1;
    if (move > 0) positive += 1;
  }

  const days = [...byDay.values()];
  const all = days.flat();
  const mean = all.length ? all.reduce((a, b) => a + b, 0) / all.length : null;
  return json({
    matches_with_closing_line: scored,
    distinct_days: days.length,
    positive_clv_share: scored ? positive / scored : null,
    mean_clv_probability_points: mean,
    interval_95: interval95(days, 20260730),
    // Both sides of this comparison are betfair_ex_uk, by construction. These two counters
    // are the denominator's missing pieces and stay visible even at zero.
    venue: "betfair_ex_uk",
    excluded_venue_mismatch: venueMismatched,
    excluded_venue_unrecorded: venueUnknown,
    note: "De-vigged probability points gained on the picked side between the decision " +
      "price and the last exchange quote before the off. Positive means the market " +
      "moved toward the pick. CLV converges far faster than settled P&L, so it is the " +
      "earliest honest signal that a live edge exists — but it is evidence about edge, " +
      "NOT profit, it is never a training target (SPEC-095), and it gates nothing.",
    coverage_note: scored === 0
      ? "No closing lines yet. Price observations began 2026-07-30; this fills as " +
        "matches are captured before their start and then settle."
      : null,
  });
}

async function health(): Promise<Response> {
  const ctx = await context();
  return json({
    ok: true,
    model_digest: ctx.model?.digest ?? null,
    model_trained_through: ctx.model?.trained_through ?? null,
    state_as_of: ctx.asOf || null,
    state_players: ctx.states.size,
    head_to_head_pairs: ctx.meetings.size,
    model_features: ctx.model?.feature_names?.length ?? 0,
    state_stale_days: ctx.staleDays,
    recommendation: "NOT_EVALUATED",
    bet_candidate_reachable: false,
  });
}

Deno.serve(async (request: Request) => {
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
  const path = new URL(request.url).pathname.replace(/^.*\/tips/, "") || "/";

  try {
    // Open on purpose: it carries no prediction and no personal data, and it is how both a
    // person and a monitor can tell whether the model and state actually loaded.
    if (path === "/health") return await health();
    // Public but self-throttled: it can spend at most one refresh per six hours no
    // matter who calls it, and answers with counts, never data. The cron poke uses it.
    if (path === "/board-refresh") return await boardRefresh();
    if (path === "/book-capture") return await bookCapture();

    if (!await owner(request)) return json({ error: "not authorised" }, 401);

    if (path === "/ledger") return await ledger();
    if (path === "/scorecard") return await scorecard();
    if (path === "/clv") return await clv();
    if (request.method === "POST" && path === "/price") return await price(request);
    if (request.method === "POST" && path === "/bet") return await recordBet(request);
    if (request.method === "POST" && path === "/bank") return await setBank(request);
    return await board();
  } catch (error) {
    // Fail loudly rather than returning something that looks right and is not.
    return json({ error: String(error) }, 500);
  }
});
