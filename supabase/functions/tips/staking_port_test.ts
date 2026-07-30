/**
 * The staking-policy port test: docs/staking.js must reproduce the registered Python
 * policy EXACTLY — integer-pence equality on every stake and string equality on every
 * reservation reason, across all 300 golden vectors emitted by
 * tennis-edge/tools/emit_staking_vectors.py from the registered rule composition:
 * TE-0047's D7 conservative-bound allocator (Kelly at the conservative bound,
 * delta_e = 0.0249, /k correlation charge, multi-bet HB-CAP day budget d_max = 0.30)
 * followed by reserve_day + the GBP 1 minimum skip.
 *
 * Exact, not 1e-12: the policy is integer-pence arithmetic end to end, so any
 * divergence at all means the page is showing a number the study never measured.
 * CLAMP_RESERVE/SKIP_RESERVE are structurally unreachable for this policy (the HB day
 * budget is always below the bank), so the vectors exercise STAKED / NO_STAKE /
 * SKIP_MIN — the reachable set.
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
  const reasons = new Set<string>();
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
      reasons.add(want.reason);
      bets++;
    }
  }
  if (bets < 1000) throw new Error(`only ${bets} bets exercised`);
  for (const needed of ["STAKED", "NO_STAKE", "SKIP_MIN"]) {
    if (!reasons.has(needed)) throw new Error(`reason ${needed} never exercised`);
  }
});
