# Test-correction proposal 0003 — SPEC-032 α-variation property guard (float-degenerate inputs)

**Status:** PROPOSED 2026-07-18, awaiting founder approval. Per the three rules, the
implementing agent does not edit a test in-slice: this correction is its own
human-approved change, citing the SPEC-ID and the error.

## The failure

`tests/properties/l4/test_stage_two_props.py::test_output_varies_with_alpha` now fails
deterministically. Hypothesis discovered (2026-07-18, during an unrelated Stage-2
governance slice — no l4 code or test was touched) the counterexample:

```
p_fundamental = {1: 0.05, 2: 0.05000000000000001}   # distinct by ~1e-17
p_market      = {1: 0.05, 2: 0.05}
alpha 0.0 vs 1.0, beta 0.0  →  both outputs {1: 0.5, 2: 0.5}
```

The falsifying example is cached in `.hypothesis/examples`, so `make verify` is RED on
every run until corrected. Bisect note: the test is unchanged since the original L4
slice (commit 90da71d); this is a latent guard weakness surfacing, not a regression.

## Why the test (not the implementation) is wrong

SPEC-032's metamorphic property is "output must vary with both alpha and beta" — in the
**specified region** of informative inputs (the manifest's guard-dominance doctrine:
properties are asserted where their causal inputs are live). The test approximates
"informative" as `len(set(p_fundamental.values())) > 1`, i.e. ANY float inequality.
With values distinct by 1e-17, `alpha·log(p)` differences vanish below double-precision
softmax resolution — mathematically the outputs differ by ~1e-17, which is not
representable in the result. The implementation is correct; the guard admits inputs
outside the property's meaningful region.

## Proposed correction (founder chooses/edits)

Strengthen the informativeness guard to material distinctness, e.g.:

```python
spread = max(p_fundamental.values()) / min(p_fundamental.values())
assume(spread > 1 + 1e-6)   # materially informative fundamental input
```

(Alternative considered: assert in log-space with an epsilon tolerance — rejected as it
weakens the assertion rather than tightening the region.) No implementation change; no
other test touched.

## Impact while pending

`make verify` is red at HEAD on this single pre-existing property test; all Stage-2A/2B
slice tests pass. No money-module behaviour is affected. Approving this correction (or
an amended guard) restores green; nothing in the Stage-2 programme depends on the
outcome either way.
