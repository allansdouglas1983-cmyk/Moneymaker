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
  liveFeatures,
  type Model,
  type PlayerState,
  priceFixture,
  reasonsFor,
  statusFor,
} from "./scoring.ts";

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
  // A match dated before the state date cannot be priced from it: the state has already
  // absorbed the result. Reported as no features rather than a confident prediction.
  const features = fixture.match_date >= stateAsOf
    ? liveFeatures({
      a,
      b,
      surface: fixture.surface,
      bestOf: fixture.best_of,
      marketProbability: impliedA / (impliedA + impliedB),
      matchDate: fixture.match_date,
      serveBaseline: SERVE_BASELINE[fixture.tour] ?? 0.62,
    })
    : {};
  const prediction = priceFixture(oddsA, oddsB, features, model);
  const bestEdge = Math.max(prediction.edgeA, prediction.edgeB);
  return {
    fixture,
    prediction,
    status: statusFor(features, bestEdge),
    reasons: reasonsFor(features, prediction, staleDays),
    bestSide: prediction.edgeA >= prediction.edgeB ? "A" : "B",
    bestEdge,
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
  ]);
  const model = results[0][0] ?? null;
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
  return { model, states, asOf, staleDays, today };
}

async function board(): Promise<Response> {
  const ctx = await context();
  if (!ctx.model) return json({ error: "no current model row — run the refresh job" }, 503);
  const fixtures = await select<FixtureRow>(
    "fixtures?match_date=gte." + ctx.today + "&order=match_date.asc",
  );
  const rows = fixtures
    .map((f) => assess(f, ctx.states, ctx.model!, ctx.asOf, ctx.staleDays))
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
  const row = assess(fixture, ctx.states, ctx.model, ctx.asOf, ctx.staleDays);
  const p = row.prediction;
  await db("predictions", {
    method: "POST",
    body: JSON.stringify([{
      match_key: key,
      match_date: date,
      tour,
      player_a: playerA,
      player_b: playerB,
      surface: fixture.surface,
      best_of: bestOf,
      odds_a: oddsA,
      odds_b: oddsB,
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
      model_digest: ctx.model.digest,
      state_as_of: ctx.asOf,
    }]),
  });
  return json({ ok: true, row: wire(row) });
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

async function health(): Promise<Response> {
  const ctx = await context();
  return json({
    ok: true,
    model_digest: ctx.model?.digest ?? null,
    model_trained_through: ctx.model?.trained_through ?? null,
    state_as_of: ctx.asOf || null,
    state_players: ctx.states.size,
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

    if (!await owner(request)) return json({ error: "not authorised" }, 401);

    if (path === "/ledger") return await ledger();
    if (request.method === "POST" && path === "/price") return await price(request);
    return await board();
  } catch (error) {
    // Fail loudly rather than returning something that looks right and is not.
    return json({ error: String(error) }, 500);
  }
});
