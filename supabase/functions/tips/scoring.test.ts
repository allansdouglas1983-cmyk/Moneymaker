/**
 * The differential test: 500 cases the Python computed, replayed against the TypeScript.
 *
 * This exists because the scoring maths is written twice and only one copy was ever
 * measured. A drift between them would not throw — it would serve numbers that no evidence
 * supports, indistinguishable on screen from numbers that plenty of evidence supports.
 *
 * Tolerance is 1e-12, which is tight enough that a genuine formula difference cannot hide
 * inside it and loose enough that IEEE-754 ordering in a compensated sum does not trip it.
 * A failure here is not flakiness: regenerate the vectors with
 * `python tools/emit_golden_vectors.py` only after the Python itself has changed, never to
 * make a failing port pass.
 *
 * Run: deno test --allow-read supabase/functions/tips/
 */
import { assertEquals } from "jsr:@std/assert@1";
import {
  liveFeatures,
  type Model,
  type PlayerState,
  priceFixture,
  reasonsFor,
  statusFor,
} from "./scoring.ts";

const TOLERANCE = 1e-12;

interface Vector {
  case: number;
  input: {
    tour: string;
    surface: string;
    best_of: number;
    match_date: string;
    state_as_of: string;
    serve_baseline: number;
    odds_a: string;
    odds_b: string;
    rank_a: number | null;
    rank_b: number | null;
    stale_days: number;
    a: PlayerState;
    b: PlayerState;
  };
  expected: {
    feature_order: string[];
    features: Record<string, number>;
    market_probability_a: number;
    market_probability_b: number;
    probability_a: number;
    probability_b: number;
    fair_odds_a: string;
    fair_odds_b: string;
    break_even_a: number;
    break_even_b: number;
    edge_a: number;
    edge_b: number;
    status: string;
    reasons: string[];
  };
}

const vectors: Vector[] = JSON.parse(
  await Deno.readTextFile(new URL("./golden.json", import.meta.url)),
);

const model: Model = JSON.parse(
  await Deno.readTextFile(new URL("../../../artifacts/residual-model.json", import.meta.url)),
);

function close(actual: number, expected: number, what: string, index: number) {
  const delta = Math.abs(actual - expected);
  if (!(delta <= TOLERANCE)) {
    throw new Error(
      `case ${index}: ${what} diverged — TypeScript ${actual}, Python ${expected}, ` +
        `difference ${delta.toExponential(3)}`,
    );
  }
}

Deno.test("the vector file is the one that was generated, and covers the branches", () => {
  assertEquals(vectors.length, 500);
  const statuses = new Set(vectors.map((v) => v.expected.status));
  // If a status stops appearing, the vectors have drifted away from testing that branch.
  assertEquals(statuses.has("INSUFFICIENT_DATA"), true);
  assertEquals(statuses.has("BET_CANDIDATE_DISABLED"), true);
  assertEquals(statuses.has("LEAN"), true);
  assertEquals(statuses.has("NO_BET"), true);
  // Absent layers must be exercised: a port can be right on the full feature set and wrong
  // on a debutant, which is the fixture a person is most likely to be looking at.
  assertEquals(vectors.some((v) => Object.keys(v.expected.features).length === 0), true);
  assertEquals(
    vectors.some((v) =>
      Object.keys(v.expected.features).length > 0 &&
      v.expected.features.point_model_residual === undefined
    ),
    true,
  );
  assertEquals(
    vectors.some((v) =>
      Object.keys(v.expected.features).length > 0 &&
      v.expected.features.pyramid_elo_gap === undefined
    ),
    true,
  );
});

Deno.test("the model artefact is the one the vectors were generated against", () => {
  assertEquals(
    model.digest,
    "sha256:78b95237a216b4763d26ef9717474af4ca270844dd033d2363d5c1f2a3f6c258",
  );
});

Deno.test("every feature matches the Python, including which features exist", () => {
  for (const vector of vectors) {
    const { input, expected } = vector;
    const implied_a = 1.0 / Number(input.odds_a);
    const implied_b = 1.0 / Number(input.odds_b);
    const features = liveFeatures({
      a: input.a,
      b: input.b,
      surface: input.surface,
      bestOf: input.best_of,
      marketProbability: implied_a / (implied_a + implied_b),
      matchDate: input.match_date,
      serveBaseline: input.serve_baseline,
      rankA: input.rank_a,
      rankB: input.rank_b,
    });
    // Presence is a claim about what is known. A port that invents a zero where the Python
    // reported absence would price a debutant at the centre of every distribution.
    assertEquals(
      Object.keys(features).sort(),
      Object.keys(expected.features).sort(),
      `case ${vector.case}: feature set differs`,
    );
    for (const name of Object.keys(expected.features)) {
      close(features[name], expected.features[name], `feature ${name}`, vector.case);
    }
  }
});

Deno.test("every price, probability, edge, status and reason matches the Python", () => {
  for (const vector of vectors) {
    const { input, expected } = vector;
    // Rebuild the feature dict in the order the Python built it: fsum is order-sensitive
    // in its last bits and the compensated sum reproduces that exactly.
    const ordered: Record<string, number> = {};
    for (const name of expected.feature_order) ordered[name] = expected.features[name];

    const prediction = priceFixture(
      Number(input.odds_a),
      Number(input.odds_b),
      ordered,
      model,
    );
    close(prediction.marketProbabilityA, expected.market_probability_a, "market A", vector.case);
    close(prediction.marketProbabilityB, expected.market_probability_b, "market B", vector.case);
    close(prediction.probabilityA, expected.probability_a, "probability A", vector.case);
    close(prediction.probabilityB, expected.probability_b, "probability B", vector.case);
    close(prediction.breakEvenA, expected.break_even_a, "break-even A", vector.case);
    close(prediction.breakEvenB, expected.break_even_b, "break-even B", vector.case);
    close(prediction.edgeA, expected.edge_a, "edge A", vector.case);
    close(prediction.edgeB, expected.edge_b, "edge B", vector.case);
    assertEquals(
      prediction.fairOddsA.toFixed(3),
      Number(expected.fair_odds_a).toFixed(3),
      `case ${vector.case}: fair odds A`,
    );
    assertEquals(
      prediction.fairOddsB.toFixed(3),
      Number(expected.fair_odds_b).toFixed(3),
      `case ${vector.case}: fair odds B`,
    );

    const bestEdge = Math.max(prediction.edgeA, prediction.edgeB);
    assertEquals(
      statusFor(ordered, bestEdge),
      expected.status,
      `case ${vector.case}: status`,
    );
    assertEquals(
      reasonsFor(ordered, prediction, input.stale_days),
      expected.reasons,
      `case ${vector.case}: reason codes`,
    );
  }
});

Deno.test("BET_CANDIDATE cannot be produced by any input", () => {
  // Not a policy promise — there is no branch in scoring.ts that returns it. This asserts
  // the property over every vector plus the extremes, so a future edit that adds one fails.
  for (const vector of vectors) {
    assertEquals(vector.expected.status === "BET_CANDIDATE", false);
  }
  for (const edge of [-1, 0, 0.019, 0.02, 0.5, 1, 1e9]) {
    assertEquals(statusFor({ elo_residual: 0.1 }, edge) === "BET_CANDIDATE", false);
  }
});
