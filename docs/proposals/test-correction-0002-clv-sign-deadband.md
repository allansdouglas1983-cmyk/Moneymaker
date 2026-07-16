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

---

## Governed review packet (2026-07-16, per founder request — 13 points)

Isolated on branch **`correction/0002-clv-sign-deadband`** (pushed, commit a0a3b68,
NOT merged). Full diff: 3 files, +188/−10. Nothing lands until approval.

**1. Identity.** SPEC-095; `tests/properties/l8/test_clv_props.py`;
`test_clv_bps_sign_matches_taken_vs_close`.

**2. Current property, mathematically.** For odds t, c ∈ [1.01, 1000] (Decimal, 2dp):
let B(t,c) = Q₀.₀₁((1/c − 1/t)·10⁴) where Q₀.₀₁ is 2dp HALF_EVEN quantization. The
committed property asserts: t > c ⇒ B > 0; t < c ⇒ B < 0; t = c ⇒ B = 0.00.

**3. Smallest concrete failing example.** odds_taken = Decimal('141.43'),
odds_close = Decimal('141.42') (both exact 2dp Decimals; BSP benchmark). Raw CLV
= (1/141.42 − 1/141.43)·10⁴ = **0.004999742363276020386669470000 bps** (Decimal,
28-digit context). Expected sign: positive (taken > close). Observed: B = Q₀.₀₁(raw)
= **Decimal('0.00')**; assertion `0.00 > 0` fails. (Hypothesis also produced the
mirrored case → Decimal('-0.00'), which equals 0, failing `< 0`.)

**4. Root cause.** Decimal quantization — specifically the DOCUMENTED 2dp reporting
quantization of `clv_bps`. Not binary floating point (no float anywhere), not a log
approximation (no logs), not formula ambiguity (formula fixed and fixture-pinned),
not inconsistent tolerance, and **not an implementation defect**: the code does
exactly what its docstring and the hand fixture (666.67) specify. The property
asserted strict sign preservation through a representation that structurally cannot
express magnitudes below its half-quantum.

**5. The deadband.** Value: **0.005**, units: implied-probability basis points,
**absolute**. Derivation: exactly `_BPS_QUANTUM / 2` = 0.01/2 — the rounding
half-quantum of the documented representation. Minimum defensible: any |raw| ≥ 0.005
survives 2dp quantization with correct sign in every case (the single tie point
±0.005 is handled by classifying off the RAW value, so classification never depends
on the tie rule); any smaller band would readmit the counterexample class, any larger
band would suppress representable signs. It is exported as `CLV_SIGN_DEADBAND_BPS`
with its derivation asserted by a test (`deadband × 2 == quantum`).

**6. What changes.** The TEST, plus ADDITIVE production API only: new
`clv_bps_raw` / `sign_classification` properties, `CLVSign` enum,
`classify_clv_bps()`. Production CLV **classification did not previously exist** —
it is introduced (explicitly, per points 10–11), not altered. `clv_bps` reporting
values: byte-identical to before. Stored values: none exist (all CLV values are
computed properties; `content_digest()` covers dataclass fields only, which are
untouched — digests unchanged). Gate calculations: none consume CLV (verified by
grep over `l8_evidence/gates/` and `specs/gates/*.yaml` — zero references; SPEC-095
also forbids CLV as anything but a diagnostic). Reports: none exist yet (pre-data).
Historical compatibility: no persisted artifacts exist; nothing to migrate.

**7. Why not "fix production" by removing quantization.** (a) Any finite
representation has a sub-representable band — removing 2dp just moves the boundary
to context precision and replaces a documented economic representation with 28-digit
division artifacts; (b) it would break the committed hand-fixture tests (also a test
change, but one that degrades the contract); (c) the genuine production gap — "what
is the sign inside the band?" — is answered properly by the new explicit
classification, which this correction ADDS. So production IS improved, additively,
while the reporting contract stays intact.

**8. Exact diffs.** Branch `correction/0002-clv-sign-deadband`, commit a0a3b68 —
`git diff claude/project-files-followup-dif8al..correction/0002-clv-sign-deadband`.
Summary: `l8_evidence/clv.py` +98 (raw helper, deadband constant, enum,
classifier, 3×2 properties; `_clv_bps` body now delegates to the raw helper then
quantizes — same output, fixture-proven); property test: exact-contract assertion
(`clv_bps == raw.quantize(0.01, HALF_EVEN)` — STRONGER than the old assertion
everywhere) + strict sign at |raw| ≥ 0.005 + explicit NEUTRAL inside;
`tests/unit/l8/test_clv.py` +70 (boundary class below).

**9. Boundary tests** (all on the branch, all passing): −0.0051 → NEGATIVE;
−0.005 exactly → NEGATIVE; 0 → ZERO; +0.005 exactly → POSITIVE; +0.0051 → POSITIVE;
plus inside-band ±0.0049 and 1E-20 → NEUTRAL_SUB_QUANTUM.

**10. NEUTRAL confirmation.** Inside-deadband values classify as
`CLVSign.NEUTRAL_SUB_QUANTUM` — a distinct enum member, never coerced to POSITIVE,
NEGATIVE, or ZERO (ZERO is reserved for exactly-equal odds and tested separately).

**11. Raw unchanged.** `clv_bps_raw` is the unquantized computation, full precision,
true sign, unaffected by the deadband (tested on the falsifying example itself:
raw ≈ 0.0049997 > 0 while report = 0.00 and classification = NEUTRAL_SUB_QUANTUM).
The deadband affects ONLY the separately named `sign_classification` /
`classify_clv_bps` operation.

**12. Mutation results** (manual mutants, applied → suite run → reverted):
sign inversion in `classify_clv_bps` → **killed, 5 tests fail**; deadband enlarged
×10 (0.005→0.05) → **killed, 5 tests fail**; boundary comparison flipped `<`→`<=`
→ **killed, 2 tests fail**. Original restored → 61/61 pass. (Full cosmic-ray over
`l8_evidence/clv.py` can be run on request; it is not currently an enforced mutation
target.)

**13. No gate can consume the deadband.** Zero references to CLV or the constant in
the gate evaluator or either gate spec; the constant's docstring states it is a
representation fact and cites SPEC-094's ban on module-constant boundaries; the
no-numeric-leaves pin tests keep every gate spec free of numeric thresholds; and
SPEC-095 already prohibits CLV from being anything but a diagnostic.

**Branch state note:** on the correction branch, all CLV/l8 suites pass (61/61 in
the affected files); repo-wide `make verify` on ANY current branch is red only from
the deliberate Phase 3A red-phase (committed failing l6 tests awaiting their
implementation), which is unrelated and expected.
