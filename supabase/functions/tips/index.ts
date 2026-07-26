/**
 * Tennis Edge — the website.
 *
 * A private, single-user page that shows what the model thinks about today's matches
 * against what the market is charging for them. It runs on Supabase's edge runtime, reads
 * its state from Postgres, and depends on nothing else being alive.
 *
 * **It states probabilities. It never says "bet".** `BET_CANDIDATE` has no branch anywhere
 * in `scoring.ts` that can produce it, and `recommendation` is pinned to `NOT_EVALUATED` by
 * a database check constraint. That is not caution for its own sake: the model's measured
 * performance on Betfair — the only venue that matters, because it is the one that cannot
 * limit a winning account — is +6.94% with a confidence interval that spans zero. Printing
 * an instruction off an undecided measurement would convert a statistical non-result into a
 * financial one.
 *
 * **Auth is Supabase's own, restricted to one address.** No password, no registration form,
 * no secret in this repository. A code is emailed, exchanged for a session, and stored in
 * an HttpOnly cookie. Any other address is refused before an email is ever sent.
 *
 * **Writes use the injected service role and never leave the server.** The browser is sent
 * HTML, never a key. There is no order-placement route here and no code path from which one
 * could be built — the function has no Betfair credential to place one with.
 */
import {
  breakEvenProbability,
  liveFeatures,
  MIN_EDGE,
  type Model,
  type PlayerState,
  priceFixture,
  reasonsFor,
  statusFor,
  WATCH_EDGE,
} from "./scoring.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY")!;

/** The single account this service belongs to. Not a secret — an allowlist of one. */
const OWNER_EMAIL = "allansdouglas1983@gmail.com";

const COOKIE = "te_session";
const BASE = "/tips";

// ---------------------------------------------------------------------------------------
// Postgres over PostgREST
// ---------------------------------------------------------------------------------------

async function db(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("apikey", SERVICE_KEY);
  headers.set("Authorization", `Bearer ${SERVICE_KEY}`);
  headers.set("Content-Type", "application/json");
  headers.set("Accept-Profile", "tennis");
  headers.set("Content-Profile", "tennis");
  return await fetch(`${SUPABASE_URL}/rest/v1/${path}`, { ...init, headers });
}

async function select<T>(path: string): Promise<T[]> {
  const response = await db(path);
  if (!response.ok) throw new Error(`${path}: ${response.status} ${await response.text()}`);
  return await response.json() as T[];
}

// ---------------------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------------------

async function sessionEmail(request: Request): Promise<string | null> {
  const cookies = request.headers.get("cookie") ?? "";
  const match = cookies.match(new RegExp(`${COOKIE}=([^;]+)`));
  if (!match) return null;
  const response = await fetch(`${SUPABASE_URL}/auth/v1/user`, {
    headers: { apikey: ANON_KEY, Authorization: `Bearer ${decodeURIComponent(match[1])}` },
  });
  if (!response.ok) return null;
  const user = await response.json();
  // Belt and braces: a session for any other address is treated as no session at all.
  return user?.email === OWNER_EMAIL ? user.email : null;
}

async function requestCode(email: string): Promise<string | null> {
  if (email.trim().toLowerCase() !== OWNER_EMAIL) {
    return "That address is not the owner of this service.";
  }
  const response = await fetch(`${SUPABASE_URL}/auth/v1/otp`, {
    method: "POST",
    headers: { apikey: ANON_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ email: OWNER_EMAIL, create_user: true }),
  });
  if (!response.ok) return `Could not send a code: ${(await response.text()).slice(0, 200)}`;
  return null;
}

async function exchangeCode(token: string): Promise<string | null> {
  const response = await fetch(`${SUPABASE_URL}/auth/v1/verify`, {
    method: "POST",
    headers: { apikey: ANON_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ type: "email", email: OWNER_EMAIL, token: token.trim() }),
  });
  if (!response.ok) return null;
  const payload = await response.json();
  return payload?.access_token ?? null;
}

// ---------------------------------------------------------------------------------------
// Domain
// ---------------------------------------------------------------------------------------

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
  const [first, second] = [a, b].map((n) => n.trim()).sort();
  return `${date}|${tour}|${first}|${second}`;
}

/** Serve baseline by tour. Frozen defaults, used when the state carries no tour figure. */
const SERVE_BASELINE: Record<string, number> = { ATP: 0.6467, WTA: 0.5786 };

interface Assessed {
  fixture: FixtureRow;
  prediction: ReturnType<typeof priceFixture>;
  status: string;
  reasons: string[];
  bestSide: "A" | "B";
  bestEdge: number;
  featureCount: number;
}

function assess(
  fixture: FixtureRow,
  states: Map<string, StateRow>,
  model: Model,
  stateAsOf: string,
  staleDays: number,
): Assessed {
  const oddsA = Number(fixture.odds_a);
  const oddsB = Number(fixture.odds_b);
  const impliedA = 1.0 / oddsA;
  const impliedB = 1.0 / oddsB;
  const a = states.get(`${fixture.tour}|${fixture.player_a}`) ?? null;
  const b = states.get(`${fixture.tour}|${fixture.player_b}`) ?? null;
  // A match dated before the state date cannot be priced from it — the state has already
  // absorbed the result. Reported as no features rather than as a confident prediction.
  const priceable = fixture.match_date >= stateAsOf;
  const features = priceable
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
    featureCount: Object.keys(features).length,
  };
}

function rank(row: Assessed): number {
  if (row.status === "BET_CANDIDATE_DISABLED") return 0;
  if (row.status === "LEAN") return 1;
  return 2;
}

// ---------------------------------------------------------------------------------------
// HTML
// ---------------------------------------------------------------------------------------

function esc(value: unknown): string {
  return String(value).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));
}

const CSS = `
:root{--bg:#0e1116;--card:#161b22;--line:#262c36;--fg:#e6edf3;--dim:#8b949e;
--good:#3fb950;--warn:#d29922;--bad:#f85149;--accent:#58a6ff}
@media (prefers-color-scheme: light){:root{--bg:#f6f8fa;--card:#fff;--line:#d0d7de;
--fg:#1f2328;--dim:#636c76;--accent:#0969da}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,
BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;-webkit-text-size-adjust:100%}
.wrap{max-width:920px;margin:0 auto;padding:16px}
.banner{background:#7d3b00;color:#ffd9a0;padding:10px 14px;border-radius:8px;
font-weight:600;font-size:13px;margin-bottom:14px}
@media (prefers-color-scheme: light){.banner{background:#fff3cd;color:#7d4e00}}
h1{font-size:19px;margin:0 0 2px}
.meta{color:var(--dim);font-size:12px;margin-bottom:16px;font-variant-numeric:tabular-nums}
nav{display:flex;gap:14px;margin-bottom:16px;font-size:14px}
nav a{color:var(--accent);text-decoration:none}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:14px;margin-bottom:10px}
.head{display:flex;justify-content:space-between;align-items:baseline;gap:10px;
flex-wrap:wrap}
.players{font-weight:600;font-size:16px}
.chip{font-size:11px;font-weight:700;letter-spacing:.4px;padding:3px 8px;border-radius:99px;
white-space:nowrap}
.c-BET_CANDIDATE_DISABLED{background:#1f6feb33;color:var(--accent);border:1px solid #1f6feb}
.c-LEAN{background:#d2992233;color:var(--warn);border:1px solid #d29922}
.c-NO_BET{background:#8b949e22;color:var(--dim);border:1px solid var(--line)}
.c-INSUFFICIENT_DATA{background:#f8514922;color:var(--bad);border:1px solid #f85149}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;
margin-top:12px}
.cell{background:var(--bg);border-radius:8px;padding:8px 10px}
.cell .k{font-size:10px;color:var(--dim);text-transform:uppercase;letter-spacing:.5px}
.cell .v{font-size:15px;font-variant-numeric:tabular-nums;margin-top:2px}
.pos{color:var(--good)}.neg{color:var(--dim)}
.why{margin-top:10px;font-size:11px;color:var(--dim);word-break:break-word}
table{width:100%;border-collapse:collapse;font-size:13px;
font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:7px 6px;border-bottom:1px solid var(--line)}
th{color:var(--dim);font-weight:600;font-size:11px;text-transform:uppercase}
form.entry{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:14px;margin-bottom:16px}
form.entry .row{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));
gap:8px;margin-bottom:8px}
input,select,button{font:inherit;padding:9px 10px;border-radius:7px;
border:1px solid var(--line);background:var(--bg);color:var(--fg);width:100%}
button{background:var(--accent);color:#fff;border:0;font-weight:600;cursor:pointer}
.err{background:#f8514922;border:1px solid var(--bad);color:var(--bad);padding:10px;
border-radius:8px;margin-bottom:12px;font-size:13px}
.empty{color:var(--dim);text-align:center;padding:28px 0}
a.match{color:inherit;text-decoration:none}
`;

function page(title: string, body: string): Response {
  return new Response(
    `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>${esc(title)}</title><style>${CSS}</style></head><body><div class="wrap">
<div class="banner">RESEARCH / SHADOW ONLY — no stake is authorised by anything on this page</div>
${body}</div></body></html>`,
    { headers: { "content-type": "text/html; charset=utf-8" } },
  );
}

function loginPage(message?: string, codeSent = false): Response {
  return page(
    "Tennis Edge",
    `<h1>Tennis Edge</h1>
<div class="meta">Private single-user service</div>
${message ? `<div class="err">${esc(message)}</div>` : ""}
${
      codeSent
        ? `<form class="entry" method="post" action="${BASE}/auth/verify">
<p style="margin-top:0;font-size:13px">A sign-in code has been emailed. Enter it below.</p>
<div class="row"><input name="code" placeholder="6-digit code" autocomplete="one-time-code"
inputmode="numeric" required></div><button type="submit">Sign in</button></form>`
        : `<form class="entry" method="post" action="${BASE}/auth/start">
<div class="row"><input name="email" type="email" placeholder="your email"
autocomplete="email" required></div><button type="submit">Email me a code</button></form>`
    }`,
  );
}

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function signed(value: number): string {
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(2)}%`;
}

function boardPage(
  rows: Assessed[],
  model: Model,
  stateAsOf: string,
  staleDays: number,
  error?: string,
): Response {
  const counts: Record<string, number> = {};
  for (const row of rows) counts[row.status] = (counts[row.status] ?? 0) + 1;

  const cards = rows.map((row) => {
    const f = row.fixture;
    const p = row.prediction;
    const side = row.bestSide === "A" ? f.player_a : f.player_b;
    const odds = row.bestSide === "A" ? f.odds_a : f.odds_b;
    const edgeClass = row.bestEdge >= WATCH_EDGE ? "pos" : "neg";
    return `<div class="card"><a class="match" href="${BASE}/match/${
      encodeURIComponent(f.match_key)
    }">
<div class="head"><span class="players">${esc(f.player_a)} v ${esc(f.player_b)}</span>
<span class="chip c-${esc(row.status)}">${esc(row.status.replace(/_/g, " "))}</span></div>
<div class="meta">${esc(f.match_date)} · ${esc(f.tour)} · ${esc(f.surface)} · best of ${
      esc(f.best_of)
    }</div>
<div class="grid">
<div class="cell"><div class="k">Market</div><div class="v">${
      pct(p.marketProbabilityA)
    } / ${pct(p.marketProbabilityB)}</div></div>
<div class="cell"><div class="k">Model</div><div class="v">${pct(p.probabilityA)} / ${
      pct(p.probabilityB)
    }</div></div>
<div class="cell"><div class="k">Quoted</div><div class="v">${esc(f.odds_a)} / ${
      esc(f.odds_b)
    }</div></div>
<div class="cell"><div class="k">Fair</div><div class="v">${p.fairOddsA.toFixed(2)} / ${
      p.fairOddsB.toFixed(2)
    }</div></div>
<div class="cell"><div class="k">Best edge</div><div class="v ${edgeClass}">${
      signed(row.bestEdge)
    }</div></div>
<div class="cell"><div class="k">On</div><div class="v">${esc(side)} @ ${
      esc(odds)
    }</div></div>
</div>
<div class="why">${esc(row.reasons.join(" · "))}</div></a></div>`;
  }).join("");

  return page(
    "Tennis Edge",
    `<h1>Today</h1>
<div class="meta">model ${esc(model.digest.slice(7, 19))}… trained through ${
      esc(model.trained_through)
    } · state ${esc(stateAsOf)} (${staleDays}d old)${
      staleDays > 14 ? " · <span style='color:var(--bad)'>STALE</span>" : ""
    }</div>
<nav><a href="${BASE}/">Board</a><a href="${BASE}/ledger">Ledger</a><a href="${BASE}/health">Health</a></nav>
${error ? `<div class="err">${esc(error)}</div>` : ""}
<form class="entry" method="post" action="${BASE}/price">
<div class="row">
<input name="player_a" placeholder="Player A" required>
<input name="player_b" placeholder="Player B" required>
</div>
<div class="row">
<input name="odds_a" placeholder="Betfair back price A" inputmode="decimal" required>
<input name="odds_b" placeholder="Betfair back price B" inputmode="decimal" required>
</div>
<div class="row">
<select name="tour"><option>ATP</option><option>WTA</option></select>
<select name="surface"><option>Hard</option><option>Clay</option><option>Grass</option></select>
<select name="best_of"><option value="3">Best of 3</option><option value="5">Best of 5</option></select>
<input name="match_date" type="date" value="${esc(new Date().toISOString().slice(0, 10))}" required>
</div>
<button type="submit">Price it</button></form>
${
      rows.length
        ? cards
        : `<div class="empty">No fixtures yet. Enter a match and its Betfair prices above.</div>`
    }
<div class="meta" style="margin-top:16px">${
      Object.entries(counts).map(([k, v]) => `${esc(k)} ${v}`).join(" · ")
    }</div>
<div class="meta">BET_CANDIDATE is structurally unreachable — no branch in the scoring code
can produce it. The model's measured Betfair return is +6.94% with an interval that spans
zero: undecided, not proven.</div>`,
  );
}

function matchPage(row: Assessed, model: Model): Response {
  const p = row.prediction;
  const f = row.fixture;
  const names = Object.keys(p.features).sort();
  const rowsHtml = names.length
    ? names.map((name) =>
      `<tr><td>${esc(name)}</td><td>${p.features[name].toFixed(6)}</td>
<td>${(model.coefficients[name] ?? 0).toFixed(6)}</td>
<td class="${p.contributions[name] >= 0 ? "pos" : "neg"}">${
        p.contributions[name] >= 0 ? "+" : ""
      }${p.contributions[name].toFixed(6)}</td></tr>`
    ).join("")
    : `<tr><td colspan="4" class="empty">No features — the state does not cover both
players, so this match is priced at the market and the model has no opinion on it.</td></tr>`;

  return page(
    `${f.player_a} v ${f.player_b}`,
    `<h1>${esc(f.player_a)} v ${esc(f.player_b)}</h1>
<div class="meta">${esc(f.match_date)} · ${esc(f.tour)} · ${esc(f.surface)} · best of ${
      esc(f.best_of)
    } · price from ${esc(f.source)}</div>
<nav><a href="${BASE}/">&larr; Board</a></nav>
<div class="card"><div class="head"><span class="players">Assessment</span>
<span class="chip c-${esc(row.status)}">${esc(row.status.replace(/_/g, " "))}</span></div>
<div class="grid">
<div class="cell"><div class="k">Market A</div><div class="v">${
      pct(p.marketProbabilityA)
    }</div></div>
<div class="cell"><div class="k">Model A</div><div class="v">${
      pct(p.probabilityA)
    }</div></div>
<div class="cell"><div class="k">Break-even A</div><div class="v">${
      pct(p.breakEvenA)
    }</div></div>
<div class="cell"><div class="k">Edge A</div><div class="v ${
      p.edgeA >= MIN_EDGE ? "pos" : "neg"
    }">${signed(p.edgeA)}</div></div>
<div class="cell"><div class="k">Market B</div><div class="v">${
      pct(p.marketProbabilityB)
    }</div></div>
<div class="cell"><div class="k">Model B</div><div class="v">${
      pct(p.probabilityB)
    }</div></div>
<div class="cell"><div class="k">Break-even B</div><div class="v">${
      pct(p.breakEvenB)
    }</div></div>
<div class="cell"><div class="k">Edge B</div><div class="v ${
      p.edgeB >= MIN_EDGE ? "pos" : "neg"
    }">${signed(p.edgeB)}</div></div>
</div>
<div class="why">Break-even is 1/(1+(O-1)(1-c)) with commission c=2%, not 1/O. Commission is
charged on net winnings, so it raises the bar twice: the bet needs a higher true probability
to be worth taking, and settlement pays less than the quote implies.</div></div>

<div class="card"><div class="players">What moved the price</div>
<div class="meta">Each contribution is a coefficient times a feature, added to the market's
own logit. The market is the starting point; these are corrections to it.</div>
<table><thead><tr><th>Feature</th><th>Value</th><th>Coefficient</th><th>Contribution</th></tr>
</thead><tbody>${rowsHtml}</tbody></table></div>

<div class="card"><div class="players">Reasons</div>
<div class="why">${esc(row.reasons.join(" · "))}</div>
<div class="meta" style="margin-top:8px">Reason codes are sign and threshold statements about
numbers already computed. They describe which input pushed the price, never why a player is
better, and no language model writes them.</div></div>

<div class="meta">model ${esc(model.digest)}</div>`,
  );
}

// ---------------------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------------------

async function loadContext() {
  const [models, states] = await Promise.all([
    select<Model & { is_current: boolean }>("model?is_current=eq.true&limit=1"),
    select<StateRow>("player_state?select=*"),
  ]);
  const model = models[0] ?? null;
  const byKey = new Map<string, StateRow>();
  let asOf = "";
  for (const row of states) {
    byKey.set(`${row.tour}|${row.player}`, row);
    if (row.as_of > asOf) asOf = row.as_of;
  }
  const today = new Date().toISOString().slice(0, 10);
  const staleDays = asOf
    ? Math.round((Date.parse(`${today}T00:00:00Z`) - Date.parse(`${asOf}T00:00:00Z`)) / 86400000)
    : 0;
  return { model, states: byKey, asOf, staleDays };
}

async function handleBoard(error?: string): Promise<Response> {
  const { model, states, asOf, staleDays } = await loadContext();
  if (!model) {
    return page(
      "Tennis Edge",
      `<h1>Not seeded yet</h1><div class="err">No current model row. Run the refresh job
(<code>tools/push_state.py</code>) to load the model and player state.</div>`,
    );
  }
  const today = new Date().toISOString().slice(0, 10);
  const fixtures = await select<FixtureRow>(
    `fixtures?match_date=gte.${today}&order=match_date.asc`,
  );
  const rows = fixtures.map((f) => assess(f, states, model, asOf, staleDays));
  rows.sort((x, y) => rank(x) - rank(y) || y.bestEdge - x.bestEdge);
  return boardPage(rows, model, asOf, staleDays, error);
}

async function handlePrice(request: Request): Promise<Response> {
  const form = await request.formData();
  const get = (name: string) => String(form.get(name) ?? "").trim();

  const playerA = get("player_a");
  const playerB = get("player_b");
  const oddsA = get("odds_a");
  const oddsB = get("odds_b");
  const date = get("match_date");
  const tour = get("tour") || "ATP";
  const bestOf = Number(get("best_of") || "3");

  // Refuse rather than drop. A silently rejected fixture is one nobody notices is missing,
  // and the match you wanted a price on is the one most likely to be typed wrong.
  if (!playerA || !playerB) return await handleBoard("Both players are required.");
  if (playerA === playerB) return await handleBoard("The same player is on both sides.");
  for (const [label, value] of [["A", oddsA], ["B", oddsB]] as const) {
    const price = Number(value);
    if (!Number.isFinite(price) || !(price > 1)) {
      return await handleBoard(`Price ${label} must be a decimal above 1, got "${value}".`);
    }
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return await handleBoard("A match date is required.");
  if (bestOf !== 3 && bestOf !== 5) return await handleBoard("Best of must be 3 or 5.");

  const key = matchKey(date, tour, playerA, playerB);
  const fixture: FixtureRow = {
    match_key: key,
    match_date: date,
    tour,
    player_a: playerA,
    player_b: playerB,
    surface: get("surface") || "Hard",
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
  if (!stored.ok) return await handleBoard(`Could not save: ${await stored.text()}`);

  // A prediction is minted at the moment the price is entered, and never revised. A later
  // view of the same match is a new row, so the record shows what was believed when, and
  // no outcome field exists here that could rewrite it afterwards.
  const { model, states, asOf, staleDays } = await loadContext();
  if (model) {
    const row = assess(fixture, states, model, asOf, staleDays);
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
        model_digest: model.digest,
        state_as_of: asOf,
      }]),
    });
  }
  return Response.redirect(new URL(`${BASE}/`, Deno.env.get("SITE_ORIGIN") ?? request.url), 303);
}

async function handleLedger(): Promise<Response> {
  const settled = await select<Record<string, unknown>>(
    "ledger?select=*,predictions(status,edge_a,edge_b,odds_a,odds_b,probability_a)" +
      "&order=match_date.desc&limit=200",
  );
  const pending = await select<Record<string, unknown>>(
    "predictions?select=match_key,match_date,player_a,player_b,status,edge_a,edge_b" +
      "&order=created_at.desc&limit=50",
  );
  const settledRows = settled.map((r) =>
    `<tr><td>${esc(r.match_date)}</td><td>${esc(r.winner)}</td>
<td>${r.a_won ? "A" : "B"}</td></tr>`
  ).join("");
  const pendingRows = pending.map((r) =>
    `<tr><td>${esc(r.match_date)}</td><td>${esc(r.player_a)} v ${esc(r.player_b)}</td>
<td>${esc(r.status)}</td><td>${
      signed(Math.max(Number(r.edge_a), Number(r.edge_b)))
    }</td></tr>`
  ).join("");

  return page(
    "Ledger",
    `<h1>Shadow ledger</h1>
<div class="meta">Every prediction is recorded before the match and never rewritten.
Results join after settlement, through a separate table.</div>
<nav><a href="${BASE}/">&larr; Board</a></nav>
<div class="card"><div class="players">Recorded predictions</div>
<table><thead><tr><th>Date</th><th>Match</th><th>Status</th><th>Best edge</th></tr></thead>
<tbody>${
      pendingRows || `<tr><td colspan="4" class="empty">Nothing recorded yet.</td></tr>`
    }</tbody></table></div>
<div class="card"><div class="players">Settled</div>
<table><thead><tr><th>Date</th><th>Winner</th><th>Side</th></tr></thead>
<tbody>${
      settledRows ||
      `<tr><td colspan="3" class="empty">Nothing settled yet. Results are joined by the
weekly job, never entered by hand alongside a prediction.</td></tr>`
    }</tbody></table></div>`,
  );
}

async function handleHealth(): Promise<Response> {
  const { model, states, asOf, staleDays } = await loadContext();
  return new Response(
    JSON.stringify({
      ok: true,
      model_digest: model?.digest ?? null,
      model_trained_through: model?.trained_through ?? null,
      state_as_of: asOf || null,
      state_players: states.size,
      state_stale_days: staleDays,
      recommendation: "NOT_EVALUATED",
      bet_candidate_reachable: false,
    }, null, 1),
    { headers: { "content-type": "application/json" } },
  );
}

// ---------------------------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------------------------

Deno.serve(async (request: Request) => {
  const url = new URL(request.url);
  // Supabase serves the function under /functions/v1/tips; strip whatever prefix arrives.
  const path = url.pathname.replace(/^.*\/tips/, "") || "/";

  try {
    if (request.method === "POST" && path === "/auth/start") {
      const form = await request.formData();
      const problem = await requestCode(String(form.get("email") ?? ""));
      return loginPage(problem ?? undefined, problem === null);
    }
    if (request.method === "POST" && path === "/auth/verify") {
      const form = await request.formData();
      const token = await exchangeCode(String(form.get("code") ?? ""));
      if (!token) return loginPage("That code was not accepted. Request a new one.", false);
      const response = await handleBoard();
      response.headers.append(
        "set-cookie",
        `${COOKIE}=${encodeURIComponent(token)}; Path=/; HttpOnly; Secure; ` +
          `SameSite=Lax; Max-Age=604800`,
      );
      return response;
    }

    const email = await sessionEmail(request);
    if (!email) return loginPage();

    if (path === "/health") return await handleHealth();
    if (path === "/ledger") return await handleLedger();
    if (request.method === "POST" && path === "/price") return await handlePrice(request);
    if (path.startsWith("/match/")) {
      const key = decodeURIComponent(path.slice("/match/".length));
      const { model, states, asOf, staleDays } = await loadContext();
      const found = await select<FixtureRow>(
        `fixtures?match_key=eq.${encodeURIComponent(key)}&limit=1`,
      );
      if (!found.length || !model) return await handleBoard("That match is not on the board.");
      return matchPage(assess(found[0], states, model, asOf, staleDays), model);
    }
    return await handleBoard();
  } catch (error) {
    // Fail loudly rather than serving a page that looks right and is not.
    return page(
      "Tennis Edge",
      `<h1>Something failed</h1><div class="err">${esc(String(error))}</div>
<nav><a href="${BASE}/">Back</a></nav>`,
    );
  }
});
