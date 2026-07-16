# Test-correction proposal 0002 — CLV sign property vs documented quantization (SPEC-095)

**Status:** PROPOSED — awaiting explicit founder approval. Blocking: `make verify` is
currently RED on this property (Hypothesis found the counterexample on 2026-07-16 and
its example database will replay it deterministically), which blocks landing any
further implementation slice until resolved.

## The defect

`tests/properties/l8/test_clv_props.py::test_clv_bps_sign_matches_taken_vs_close`
asserts strict sign: `odds_taken > odds_close ⇒ clv_bps > 0` (and symmetrically).
But `clv_bps` is DOCUMENTED (module docstring + unit fixture `666.67`) as quantized to
2 decimal places of basis points, ROUND_HALF_EVEN. For near-equal odds the true CLV is
smaller than the half-quantum: e.g. taken 141.43 vs close 141.42 → raw ≈ 0.005 bps →
quantizes to `0.00`, and the strict assertion fails.

The implementation does exactly what its specification says; the committed property is
STRONGER than the documented behaviour. Economically, a CLV below 0.005 bps is noise —
the quantization choice is sound. The property test is the defective side.

## Proposed correction (test-only, no implementation change)

Replace the strict-sign assertions with the deadband-aware property that the
documented behaviour actually guarantees:

- compute `raw = (1/odds_close - 1/odds_taken) * 10000` exactly in the test;
- assert `clv_bps == raw.quantize(Decimal("0.01"), ROUND_HALF_EVEN)` (the exact
  documented contract — strictly STRONGER than the old test everywhere except inside
  the deadband);
- retain strict sign assertions whenever `abs(raw) >= Decimal("0.005")`;
- equal odds still assert exactly `0.00`.

No other test changes. The negation-symmetry property is unaffected (it already holds
under quantization since HALF_EVEN is symmetric about zero).

## Why not change the implementation instead

Removing quantization would preserve strict sign but (a) break the committed
hand-fixture unit tests (also a test change), and (b) replace a documented, bounded
representation with context-precision division artifacts. Keeping the documented 2dp
economic representation and correcting the over-strong property is the smaller, more
honest change.

## Approval

Approve by replying "test-correction 0002 approved". The correction lands as its own
commit citing SPEC-095 and this proposal.
