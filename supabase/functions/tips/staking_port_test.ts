/**
 * The staking-policy port test: docs/staking.js must reproduce the registered Python
 * policy EXACTLY — integer-pence equality on every stake and string equality on every
 * reservation reason, across all 300 golden vectors (1,450 bets) emitted by
 * tennis-edge/tools/emit_staking_vectors.py from the registered rule composition
 * hb_cap(conservative_kelly(shrink=1.37/3.86, commission=0.02), 0.50) plus
 * STK-HARNESS-V1 §1.6 reservation (ADR 0020 Amendment 2).
 *
 * Exact, not 1e-12: the policy is integer-pence arithmetic end to end, so any
 * divergence at all means the page is showing a number the study never measured.
 */
import { assertEquals } from "jsr:@std/assert@1";
import { stakePlan } from "../../../docs/staking.js";

interface VectorBet {
  p_nano: number;
  odds_c: number;
}
interface VectorExpectation {
  requested_pence: number;
  stake_pence: number;
  reason: string;
}
interface Vector {
  bank_pence: number;
  peak_pence: number;
  candidates: VectorBet[];
  expected: VectorExpectation[];
}

const golden = JSON.parse(
  await Deno.readTextFile(new URL("./staking_golden.json", import.meta.url)),
) as { meta: { count: number }; vectors: Vector[] };

Deno.test("staking policy port matches the registered Python policy exactly", () => {
  assertEquals(golden.vectors.length, golden.meta.count);
  let bets = 0;
  for (const vector of golden.vectors) {
    const plan = stakePlan(
      vector.bank_pence,
      vector.peak_pence,
      vector.candidates.map((c) => ({ pNano: c.p_nano, oddsC: c.odds_c })),
    );
    assertEquals(plan.length, vector.expected.length);
    for (let i = 0; i < plan.length; i++) {
      const got = plan[i];
      const want = vector.expected[i];
      const at = `bank=${vector.bank_pence} peak=${vector.peak_pence} bet#${i} ` +
        `p_nano=${vector.candidates[i].p_nano} odds_c=${vector.candidates[i].odds_c}`;
      assertEquals(got.requestedPence, want.requested_pence, `requested @ ${at}`);
      assertEquals(got.stakePence, want.stake_pence, `stake @ ${at}`);
      assertEquals(got.reason, want.reason, `reason @ ${at}`);
      bets++;
    }
  }
  // The emitter reported 1,450 bets across the five reservation reasons; a shrunk
  // vector file must not quietly pass.
  if (bets < 1000) throw new Error(`only ${bets} bets exercised`);
});
