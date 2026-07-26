/**
 * The scoring maths, ported from Python so it can run in the request path.
 *
 * This is the only place in the deployment where the same calculation exists twice, and a
 * silent divergence between the two copies is the single most dangerous failure this system
 * can have: the site would show numbers that no measurement ever validated, and they would
 * look exactly like the validated ones. So the port is not trusted — `scoring.test.ts`
 * replays 500 cases emitted by the Python and fails on any disagreement beyond 1e-12.
 *
 * Every function below is a direct transcription. Where the Python used `math.fsum` for a
 * compensated sum, so does this. Where it clamped, this clamps at the same bound. The
 * temptation to "clean up" an expression while porting is exactly how the two copies drift,
 * so the shapes are kept even where TypeScript would prefer something else.
 *
 * Ported from:
 *   tennis_edge/devig.py          power()
 *   tennis_edge/point_model.py    game/tiebreak/set/match probability
 *   tennis_edge/ratings.py        eloExpected()
 *   tennis_edge/live_state.py     liveFeatures()
 *   tennis_edge/residual_model.py probability()
 *   tennis_edge/upcoming.py       breakEven(), priceFixture()
 *   tennis_edge/today.py          reasons(), status
 */

const EPS = 1e-12;
const DEVIG_TOL = 1e-12;
const DEVIG_MAX_ITER = 200;

/** Betfair Rewards flat rate. Applied even to a bookmaker quote — the exchange is where a
 *  bet would actually go, and pricing it cheaper flatters the rule. */
export const COMMISSION = 0.02;
/** Frozen in the policy digest. Roughly the per-match edge the measured +0.000862 nats
 *  corresponds to at typical prices. Never tuned to produce a pleasing number of tips. */
export const MIN_EDGE = 0.02;
export const WATCH_EDGE = 0.01;

/** Below these the state cannot support a feature and absence is reported, never a zero. */
const MIN_MAIN_TOUR_MATCHES = 5;
const MIN_SERVE_COVERAGE = 300.0;
const MIN_PYRAMID_MATCHES = 5;

function clamp(p: number): number {
  return Math.min(Math.max(p, EPS), 1.0 - EPS);
}

export function logit(p: number): number {
  const q = Math.min(Math.max(p, 1e-12), 1 - 1e-12);
  return Math.log(q / (1 - q));
}

function sigmoid(z: number): number {
  return 1.0 / (1.0 + Math.exp(-Math.max(Math.min(z, 30.0), -30.0)));
}

/**
 * Neumaier compensated summation — the same value `math.fsum` produces.
 *
 * Ten coefficient products summed naively differ from fsum in the last bits, and the golden
 * vectors assert to 1e-12, so plain `+=` would fail them. It would also mean the site's
 * arithmetic was not the arithmetic that was measured.
 */
export function fsum(values: number[]): number {
  let sum = 0.0;
  let compensation = 0.0;
  for (const value of values) {
    const t = sum + value;
    compensation += Math.abs(sum) >= Math.abs(value)
      ? (sum - t) + value
      : (value - t) + sum;
    sum = t;
  }
  return sum + compensation;
}

// ---------------------------------------------------------------------------------------
// De-vig: power (logarithmic) removal
// ---------------------------------------------------------------------------------------

/**
 * Find k with sum((1/o_i)^k) == 1, then normalise.
 *
 * Each raw implied probability is below 1, so k > 1 shrinks the smaller one proportionally
 * more — which takes margin off the longshot rather than the favourite. That is the
 * empirically correct direction and the method under which tennis closing prices come out
 * almost perfectly calibrated. Using raw 1/O instead would shift every prediction by the
 * book's whole margin.
 */
export function devigPower(odds: number[]): number[] {
  for (const price of odds) {
    if (!(price > 1.0)) throw new Error(`decimal odds must exceed 1, got ${price}`);
  }
  const raw = odds.map((o) => 1.0 / o);
  const book = raw.reduce((a, b) => a + b, 0.0);
  if (Math.abs(book - 1.0) < DEVIG_TOL) return raw;

  const total = (k: number) => raw.reduce((acc, r) => acc + Math.pow(r, k), 0.0);

  // total(k) is strictly decreasing in k, so bracket by which side of 1 the book sits.
  let low = 1e-6;
  let high = 1.0;
  if (total(1.0) > 1.0) {
    low = 1.0;
    high = 2.0;
    while (total(high) > 1.0 && high < 1e6) high *= 2.0;
  }
  for (let i = 0; i < DEVIG_MAX_ITER; i++) {
    const mid = (low + high) / 2.0;
    const value = total(mid);
    if (Math.abs(value - 1.0) < DEVIG_TOL) break;
    if (value > 1.0) low = mid;
    else high = mid;
  }
  const k = (low + high) / 2.0;
  const probabilities = raw.map((r) => Math.pow(r, k));
  const scale = probabilities.reduce((a, b) => a + b, 0.0);
  return probabilities.map((p) => p / scale);
}

// ---------------------------------------------------------------------------------------
// Barnett–Clarke point model
// ---------------------------------------------------------------------------------------

/** P(server holds) given p = P(server wins a point on serve). */
export function gameProbability(p: number): number {
  const pc = clamp(p);
  const q = 1.0 - pc;
  const memo = new Map<number, number>();
  const state = (server: number, receiver: number): number => {
    if (server >= 4 && server - receiver >= 2) return 1.0;
    if (receiver >= 4 && receiver - server >= 2) return 0.0;
    if (server >= 3 && receiver >= 3) {
      // Deuce: the classic two-clear geometric sum.
      return (pc * pc) / (pc * pc + q * q);
    }
    const key = server * 16 + receiver;
    const seen = memo.get(key);
    if (seen !== undefined) return seen;
    const value = pc * state(server + 1, receiver) + q * state(server, receiver + 1);
    memo.set(key, value);
    return value;
  };
  return state(0, 0);
}

/** P(A wins the tiebreak) with A serving first; serving alternates 1-2-2-2. */
export function tiebreakProbability(pServe: number, pReturn: number, target = 7): number {
  const s = clamp(pServe);
  const r = clamp(pReturn);
  const memo = new Map<number, number>();
  const state = (a: number, b: number): number => {
    if (a >= target && a - b >= 2) return 1.0;
    if (b >= target && b - a >= 2) return 0.0;
    if (a >= target && b >= target) {
      // From parity, A must win a serve-and-return pair; otherwise back to parity.
      const winPair = s * r;
      const losePair = (1.0 - s) * (1.0 - r);
      const denominator = winPair + losePair;
      if (denominator <= EPS) return 0.5;
      return winPair / denominator;
    }
    const key = a * 64 + b;
    const seen = memo.get(key);
    if (seen !== undefined) return seen;
    // A serves points 0, 3, 4, 7, 8, ... under the 1-2-2-2 alternation.
    const mod = (a + b + 3) % 4;
    const aServing = mod >= 2 && mod <= 3;
    const p = aServing ? s : r;
    const value = p * state(a + 1, b) + (1.0 - p) * state(a, b + 1);
    memo.set(key, value);
    return value;
  };
  return state(0, 0);
}

/** P(A wins the set) with A serving the first game. */
export function setProbability(pServe: number, pReturn: number): number {
  const hold = gameProbability(pServe);
  const broken = gameProbability(1.0 - pReturn);
  const winReturnGame = 1.0 - broken;
  const memo = new Map<number, number>();
  const state = (a: number, b: number): number => {
    if (a >= 6 && a - b >= 2) return 1.0;
    if (b >= 6 && b - a >= 2) return 0.0;
    if (a === 6 && b === 6) return tiebreakProbability(pServe, pReturn);
    const key = a * 32 + b;
    const seen = memo.get(key);
    if (seen !== undefined) return seen;
    const aServing = (a + b) % 2 === 0;
    const p = aServing ? hold : winReturnGame;
    const value = p * state(a + 1, b) + (1.0 - p) * state(a, b + 1);
    memo.set(key, value);
    return value;
  };
  return state(0, 0);
}

/**
 * P(A wins the match). Sets are independent draws from setProbability — the standard
 * simplification, since who serves first alternates by set and modelling that explicitly
 * moves the answer far less than the error in estimating p_serve itself.
 */
export function matchProbability(pServe: number, pReturn: number, bestOf: number): number {
  if (bestOf !== 3 && bestOf !== 5) {
    throw new Error(`tennis matches are best of 3 or 5, got ${bestOf}`);
  }
  const perSet = setProbability(pServe, pReturn);
  const needed = bestOf === 3 ? 2 : 3;
  const memo = new Map<number, number>();
  const state = (a: number, b: number): number => {
    if (a === needed) return 1.0;
    if (b === needed) return 0.0;
    const key = a * 8 + b;
    const seen = memo.get(key);
    if (seen !== undefined) return seen;
    const value = perSet * state(a + 1, b) + (1.0 - perSet) * state(a, b + 1);
    memo.set(key, value);
    return value;
  };
  return state(0, 0);
}

// ---------------------------------------------------------------------------------------
// Ratings and features
// ---------------------------------------------------------------------------------------

export function eloExpected(ratingA: number, ratingB: number): number {
  if (ratingA === ratingB) return 0.5;
  return 1.0 / (1.0 + Math.pow(10.0, (ratingB - ratingA) / 400.0));
}

export interface PlayerState {
  elo: number;
  weighted_elo: number;
  surface_elo: Record<string, number>;
  matches: number;
  last_played: string | null;
  serve_rate: number;
  return_rate: number;
  serve_points: number;
  serve_matches: number;
  pyramid_elo: number;
  pyramid_surface_elo: Record<string, number>;
  pyramid_matches: number;
  pyramid_tour_share: number;
  pyramid_last_played: string | null;
  pyramid_recent_14d: number;
}

function surfaceRating(state: PlayerState, surface: string): number {
  const value = state.surface_elo[surface || "Hard"];
  // Postgres returns JSON null where Python had an absent key; both mean "no rating on
  // this surface", and both must fall back to the overall one rather than to NaN.
  return value === undefined || value === null ? state.elo : value;
}

function pyramidSurfaceRating(state: PlayerState, surface: string): number {
  const value = state.pyramid_surface_elo[surface || "Hard"];
  return value === undefined || value === null ? state.pyramid_elo : value;
}

function daysSince(stamp: string | null, when: string): number | null {
  if (stamp === null) return null;
  const a = Date.parse(`${when}T00:00:00Z`);
  const b = Date.parse(`${stamp}T00:00:00Z`);
  return Math.round((a - b) / 86400000);
}

export interface FeatureInputs {
  a: PlayerState | null;
  b: PlayerState | null;
  surface: string;
  bestOf: number;
  marketProbability: number;
  matchDate: string;
  serveBaseline: number;
  rankA?: number | null;
  rankB?: number | null;
}

/**
 * Residual features for an upcoming match, or `{}` when the state cannot support them.
 *
 * Returning nothing rather than zeros is deliberate and it matters: a zero gap claims the
 * two players are equal, and absence claims nothing. A debutant priced with zeros would sit
 * at the exact centre of every distribution, which is both false and systematically so.
 */
export function liveFeatures(input: FeatureInputs): Record<string, number> {
  const { a, b, surface, bestOf, marketProbability, matchDate, serveBaseline } = input;
  if (a === null || b === null) return {};
  if (a.matches < MIN_MAIN_TOUR_MATCHES || b.matches < MIN_MAIN_TOUR_MATCHES) return {};

  const marketLogit = logit(marketProbability);
  const blendedA = 0.5 * (a.elo + surfaceRating(a, surface));
  const blendedB = 0.5 * (b.elo + surfaceRating(b, surface));
  const features: Record<string, number> = {
    elo_residual: logit(eloExpected(blendedA, blendedB)) - marketLogit,
    surface_elo_gap: (surfaceRating(a, surface) - surfaceRating(b, surface)) / 400.0,
    weighted_elo_gap: (a.weighted_elo - b.weighted_elo) / 400.0,
  };
  if (input.rankA != null && input.rankB != null) {
    features.rank_gap = Math.log1p(input.rankB) - Math.log1p(input.rankA);
  }

  if (Math.min(a.serve_points, b.serve_points) >= MIN_SERVE_COVERAGE) {
    // f_ij = f_t + (f_i - f_av) - (g_j - g_av), as in serve_stats.estimate.
    const returnAverage = 1.0 - serveBaseline;
    const pA = Math.min(
      Math.max(serveBaseline + (a.serve_rate - serveBaseline) - (b.return_rate - returnAverage), 0.30),
      0.90,
    );
    const pB = Math.min(
      Math.max(serveBaseline + (b.serve_rate - serveBaseline) - (a.return_rate - returnAverage), 0.30),
      0.90,
    );
    const point = matchProbability(pA, 1.0 - pB, bestOf);
    features.point_model_residual = logit(point) - marketLogit;
  }

  if (a.pyramid_matches >= MIN_PYRAMID_MATCHES && b.pyramid_matches >= MIN_PYRAMID_MATCHES) {
    const restA = daysSince(a.pyramid_last_played, matchDate);
    const restB = daysSince(b.pyramid_last_played, matchDate);
    if (restA !== null && restB !== null) {
      features.pyramid_elo_gap = (a.pyramid_elo - b.pyramid_elo) / 400.0;
      features.pyramid_surface_gap =
        (pyramidSurfaceRating(a, surface) - pyramidSurfaceRating(b, surface)) / 400.0;
      features.pyramid_workload_gap = a.pyramid_recent_14d - b.pyramid_recent_14d;
      features.pyramid_rest_gap = (Math.min(restA, 180) - Math.min(restB, 180)) / 30.0;
      features.pyramid_tier_gap = a.pyramid_tour_share - b.pyramid_tour_share;
    }
  }
  return features;
}

// ---------------------------------------------------------------------------------------
// The model
// ---------------------------------------------------------------------------------------

export interface Model {
  digest: string;
  coefficients: Record<string, number>;
  feature_names: string[];
  trained_through: string;
}

/**
 * P(player A wins), as the market's view corrected by what it missed.
 *
 * A feature the model does not know throws. Dropping it silently would price a match with a
 * different feature set than the one trained on, and the result would be indistinguishable
 * from a valid prediction.
 */
export function modelProbability(
  model: Model,
  marketLogit: number,
  features: Record<string, number>,
): number {
  const known = new Set(model.feature_names);
  const unknown = Object.keys(features).filter((name) => !known.has(name));
  if (unknown.length > 0) {
    throw new Error(
      `unknown feature(s) ${unknown.sort().join(", ")} — this model was trained on ` +
        `${model.feature_names.join(", ")} and cannot price a different set`,
    );
  }
  // Python iterates the feature dict in insertion order; fsum is order-sensitive in its
  // last bits, so the golden vectors carry the order and it is preserved here.
  const terms = Object.keys(features).map((name) =>
    (model.coefficients[name] ?? 0.0) * features[name]
  );
  return sigmoid(marketLogit + fsum(terms));
}

/** Per-feature signed contribution to the logit. Display only — the sum is the model. */
export function contributions(
  model: Model,
  features: Record<string, number>,
): Record<string, number> {
  const out: Record<string, number> = {};
  for (const name of Object.keys(features)) {
    out[name] = (model.coefficients[name] ?? 0.0) * features[name];
  }
  return out;
}

// ---------------------------------------------------------------------------------------
// Prices
// ---------------------------------------------------------------------------------------

/**
 * 1 / (1 + (O-1)(1-c)) — the probability at which a back bet breaks even.
 *
 * Not 1/O. Commission is charged on net winnings, so it raises the bar twice over: the bet
 * needs a higher true probability to be worth taking, and settlement pays less than the
 * quote implies. Conflating the two credits a strategy with money the exchange keeps, and
 * the error is invisible in a backtest that makes it consistently.
 */
export function breakEvenProbability(odds: number, commission = COMMISSION): number {
  if (!(odds > 1)) throw new Error(`decimal odds must be above 1, got ${odds}`);
  return 1.0 / (1.0 + (odds - 1.0) * (1.0 - commission));
}

export interface Prediction {
  marketProbabilityA: number;
  marketProbabilityB: number;
  probabilityA: number;
  probabilityB: number;
  fairOddsA: number;
  fairOddsB: number;
  breakEvenA: number;
  breakEvenB: number;
  edgeA: number;
  edgeB: number;
  features: Record<string, number>;
  contributions: Record<string, number>;
  modelDigest: string;
}

export function priceFixture(
  oddsA: number,
  oddsB: number,
  features: Record<string, number>,
  model: Model,
  commission = COMMISSION,
): Prediction {
  const devigged = devigPower([oddsA, oddsB]);
  const marketA = devigged[0];
  const marketB = devigged[1];
  const marketLogit = logit(marketA);
  const probabilityA = modelProbability(model, marketLogit, features);
  const probabilityB = 1.0 - probabilityA;
  const breakEvenA = breakEvenProbability(oddsA, commission);
  const breakEvenB = breakEvenProbability(oddsB, commission);
  return {
    marketProbabilityA: marketA,
    marketProbabilityB: marketB,
    probabilityA,
    probabilityB,
    // Python quantises fair odds to three decimals with Decimal; round-half-even at 1e-3.
    fairOddsA: roundHalfEven(1.0 / probabilityA, 3),
    fairOddsB: roundHalfEven(1.0 / probabilityB, 3),
    breakEvenA,
    breakEvenB,
    edgeA: probabilityA - breakEvenA,
    edgeB: probabilityB - breakEvenB,
    features,
    contributions: contributions(model, features),
    modelDigest: model.digest,
  };
}

/** Decimal.quantize uses banker's rounding; matching it keeps fair odds identical. */
export function roundHalfEven(value: number, places: number): number {
  const factor = Math.pow(10, places);
  const scaled = value * factor;
  const floor = Math.floor(scaled);
  const diff = scaled - floor;
  let rounded: number;
  if (Math.abs(diff - 0.5) < 1e-9) rounded = floor % 2 === 0 ? floor : floor + 1;
  else rounded = Math.round(scaled);
  return rounded / factor;
}

// ---------------------------------------------------------------------------------------
// Status and reasons
// ---------------------------------------------------------------------------------------

/**
 * The governed status vocabulary. `BET_CANDIDATE` is deliberately absent: there is no branch
 * anywhere in this file that can produce it, which is what "structurally unreachable" means.
 * Adding it would be a governance decision, not a code change.
 */
export const Status = {
  INSUFFICIENT_DATA: "INSUFFICIENT_DATA",
  MODEL_VIEW_ONLY: "MODEL_VIEW_ONLY",
  LEAN: "LEAN",
  NO_BET: "NO_BET",
  BET_CANDIDATE_DISABLED: "BET_CANDIDATE_DISABLED",
} as const;

export function statusFor(features: Record<string, number>, bestEdge: number): string {
  if (Object.keys(features).length === 0) return Status.INSUFFICIENT_DATA;
  if (bestEdge >= MIN_EDGE) return Status.BET_CANDIDATE_DISABLED;
  if (bestEdge >= WATCH_EDGE) return Status.LEAN;
  return Status.NO_BET;
}

/**
 * Deterministic reason codes from the numeric core. No causal language, no invention.
 *
 * Every code is a sign or threshold statement about a number already computed. Nothing here
 * explains *why* a player is better; it says only which input pushed the price.
 */
export function reasonsFor(
  features: Record<string, number>,
  prediction: Prediction,
  staleDays: number,
): string[] {
  const found: string[] = [];
  if (Object.keys(features).length === 0) found.push("INSUFFICIENT_DATA");
  if (staleDays > 14) found.push("STALE_STATE");
  const pyramid = features.pyramid_elo_gap;
  if (pyramid !== undefined && Math.abs(pyramid) > 0.25) {
    found.push(pyramid > 0 ? "RATING_ADVANTAGE" : "RATING_DISADVANTAGE");
  }
  const point = features.point_model_residual;
  if (point !== undefined && Math.abs(point) > 0.35) found.push("SERVE_MODEL_DISAGREES");
  if ((features.pyramid_workload_gap ?? 0.0) >= 2.0) found.push("HEAVY_RECENT_WORKLOAD");
  const gap = prediction.probabilityA - prediction.marketProbabilityA;
  found.push(Math.abs(gap) > 0.03 ? "MARKET_DISAGREEMENT" : "MARKET_AGREEMENT");
  if (Math.max(prediction.edgeA, prediction.edgeB) >= MIN_EDGE) {
    found.push("PRICE_ABOVE_CONSERVATIVE_FAIR");
  }
  found.push("TIPPING_GATE_DISABLED");
  return found;
}
