/* The served staking policy: TE-0047's D7 conservative-bound allocator, ported
 * operation-for-operation from the registered Python rules
 * (tennis_edge/staking/rules.py::d7_conservative_bound + harness.py::reserve_day)
 * and held to them by 300 golden vectors at EXACT integer-pence equality
 * (supabase/functions/tips/staking_port_test.ts).
 *
 * The formula (registration: docs/TE-0047-d7-registration.md):
 *   b   = (O - 1)(1 - c)            commission-adjusted net odds, c = 0.02
 *   e_c = p(b + 1) - 1 - delta_e    conservative edge; delta_e = 0.0249, the TE-0043
 *                                   day-clustered interval displacement (3.86 - 1.37)
 *   f   = e_c / b  if e_c > 0, else REFUSE (the D7 "not yet" branch)
 *   want = floor(bank * f / k)      k = FULL selected card size (correlation charge)
 *   then the multi-bet HB-CAP day budget, granted in order:
 *   cap = max(floor(bank - 0.70 * peak), 0); stake = min(want, capRemaining)
 *   then reservation + the GBP 1 minimum: below 100p is SKIPPED, never rounded up.
 *
 * All arithmetic is BigInt — no float ever touches money. Probabilities are quantised
 * once to integer nanoprobability, identically to the vector emitter.
 *
 * DISPLAY ONLY. Nothing here places, cancels or amends an order; the founder decides
 * at the point of placement, every time (ADR 0020).
 */

const NANO = 1_000_000_000n;
const MIN_STAKE_PENCE = 100n;
// delta_e = 0.0249 and the "-1" share the 10^13 denominator below:
// 10^13 + 0.0249 * 10^13 = 10_249 * 10^9.
const BREAK_EVEN_NUM = 10_249n * 1_000_000_000n;
const COMMISSION_COMPLEMENT = 98n; // (1 - c) in hundredths, c = 0.02

export function quantiseProbability(p) {
  return BigInt(Math.round(p * 1e9));
}

export function quantiseOdds(odds) {
  return BigInt(Math.round(Number(odds) * 100));
}

// The operative firing rule, mirrored from tennis_edge.staking.selection: a bet is
// selected when p - break_even(O, c) is STRICTLY greater than 0.02 (probability
// scale). Integer form: (pNano - 0.02*1e9) * b1 > 1e13, b1 = (oddsC-100)*98 + 10000.
// The selected card defines k; a below-bar row is not on the card at all.
const MIN_EDGE_NANO = 20_000_000n;
const TEN_13 = 10_000_000_000_000n;

export function isFired(pNano, oddsC) {
  const p = BigInt(pNano);
  const o = BigInt(oddsC);
  if (o <= 100n) return false;
  const b1 = (o - 100n) * COMMISSION_COMPLEMENT + 10_000n;
  return (p - MIN_EDGE_NANO) * b1 > TEN_13;
}

/**
 * The registered plan for one day's selected card.
 * @param {number|bigint} bankPence  morning bank, integer pence
 * @param {number|bigint} peakPence  high-water mark, integer pence (>= bank)
 * @param {{pNano: number|bigint, oddsC: number|bigint}[]} card selected bets in
 *        canonical order (scheduled start, then market id)
 * @returns {{requestedPence: number, stakePence: number, reason: string}[]}
 */
export function stakePlan(bankPence, peakPence, card) {
  const bank = BigInt(bankPence);
  const peak = BigInt(peakPence);
  const k = BigInt(card.length);
  if (k === 0n) return [];

  // Multi-bet HB-CAP day budget: floor(bank - 0.70*peak) = floor((10*bank - 7*peak)/10).
  const capNum = 10n * bank - 7n * peak;
  let capRemaining = capNum > 0n ? capNum / 10n : 0n;

  // The rule's own pass: conservative-bound fraction, /k, capped pathwise.
  const requested = [];
  for (const bet of card) {
    const pNano = BigInt(bet.pNano);
    const oddsC = BigInt(bet.oddsC);
    if (oddsC <= 100n) {
      requested.push(0n);
      continue;
    }
    // e_c numerator over 10^13: p*(b+1) - 1 - delta_e
    // with b+1 = ((oddsC-100)*98 + 10000)/10000.
    const b1 = (oddsC - 100n) * COMMISSION_COMPLEMENT + 10_000n;
    const num = pNano * b1 - BREAK_EVEN_NUM;
    if (num <= 0n) {
      requested.push(0n);
      continue;
    }
    // want = floor(bank * (e_c / b) / k); b = (oddsC-100)*98/10000, so the 10^13
    // denominator becomes 10^9 * (oddsC-100) * 98. All terms positive: / is floor.
    const want = (bank * num) / (NANO * (oddsC - 100n) * COMMISSION_COMPLEMENT * k);
    const grant = want < capRemaining ? want : capRemaining;
    capRemaining -= grant;
    requested.push(grant);
  }

  // Engine semantics downstream: sequential reservation against the bank, and a grant
  // below the exchange minimum is SKIPPED, never rounded up (reserve_day, verbatim).
  let remaining = bank;
  const out = [];
  for (const want of requested) {
    const grant = want < remaining ? want : remaining;
    let size, reason;
    if (want <= 0n) {
      size = 0n;
      reason = "NO_STAKE";
    } else if (grant < MIN_STAKE_PENCE) {
      size = 0n;
      reason = want >= MIN_STAKE_PENCE ? "SKIP_RESERVE" : "SKIP_MIN";
    } else if (grant < want) {
      size = grant;
      reason = "CLAMP_RESERVE";
    } else {
      size = grant;
      reason = "STAKED";
    }
    remaining -= size;
    out.push({
      requestedPence: Number(want),
      stakePence: Number(size),
      reason,
    });
  }
  return out;
}
