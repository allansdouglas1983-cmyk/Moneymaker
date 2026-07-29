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
  edgeBand,
  liveFeatures,
  type Model,
  type PlayerState,
  priceFixture,
  reasonsFor,
  statusFor,
} from "./scoring.ts";
import {
  bestOfFor,
  type FeedBookmaker,
  normalizeName,
  pickPrices,
  resolvePlayer,
  surfaceFor,
  tourOf,
} from "./board.ts";

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
  return {
    fixture: row.fixture,
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
    "fixtures?match_date=gte." + ctx.today + "&order=match_date.asc",
  );
  const rows = fixtures
    .map((f) => assess(f, ctx.states, ctx.meetings, ctx.model!, ctx.asOf, ctx.staleDays))
    .sort((x, y) => {
      const rank = (r: typeof x) =>
        r.status === "BET_CANDIDATE_DISABLED" ? 0 : r.status === "LEAN" ? 1 : 2;
      return rank(x) - rank(y) || y.bestEdge - x.bestEdge;
    });
  return json({
    model_digest: ctx.model.digest,
    model_trained_through: ctx.model.trained_through,
    state_as_of: ctx.asOf,
    state_players: ctx.states.size,
    state_stale_days: ctx.staleDays,
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
      commission: 0.02,
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

  let fixtures = 0, minted = 0, unmapped = 0, unpriced = 0;
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

    for (const event of await response.json() as FeedEvent[]) {
      const picked = pickPrices(event.bookmakers, event.home_team, event.away_team);
      if (picked === null) {
        unpriced += 1;
        continue;
      }
      books[picked.book] = (books[picked.book] ?? 0) + 1;
      const mappedHome = resolvePlayer(event.home_team, index);
      const mappedAway = resolvePlayer(event.away_team, index);
      const playerA = mappedHome ?? event.home_team;
      const playerB = mappedAway ?? event.away_team;
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
    unpriced_matches: unpriced,
    books_used: books,
    credits_remaining: creditsRemaining,
  });
}

async function ledger(): Promise<Response> {
  const predictions = await select<Record<string, unknown>>(
    "predictions?select=match_key,match_date,player_a,player_b,status,edge_a,edge_b" +
      "&order=created_at.desc&limit=100",
  );
  const settled = await select<Record<string, unknown>>(
    "ledger?select=*&order=match_date.desc&limit=200",
  );
  return json({ predictions, settled });
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

    if (!await owner(request)) return json({ error: "not authorised" }, 401);

    if (path === "/ledger") return await ledger();
    if (path === "/scorecard") return await scorecard();
    if (request.method === "POST" && path === "/price") return await price(request);
    return await board();
  } catch (error) {
    // Fail loudly rather than returning something that looks right and is not.
    return json({ error: String(error) }, 500);
  }
});
