# Round-2 residual: structural proofs for the mathematically-unkillable survivors

These survivors have NO distinguishing input — no test can kill them, because the mutated and
original expressions compute the same value on every reachable input. This is not a weak
"measure-zero" hand-wave about the fitted optimum; it is non-distinguishability of the two
expressions themselves. Each carries the exact proof the founder's framework permits; approved_by
stays null pending founder adjudication (accept-by-proof, or direct a source refactor to remove
the site — noted per item).

## OPT-1  june_m1_harness `_metrics` L279  ReplaceComparisonOperator_LtE_Lt  `det <= 1e-12` -> `det < 1e-12`
- The two differ ONLY when `det` is bit-exactly `1e-12`. `det = haa*hbb - hab*hab` is a
  product-difference of float sums; `1e-12` is not a value the fit can produce exactly (it is not
  a dyadic rational and does not arise from the Hessian arithmetic). Over the 20,000-fixture
  adversarial sweep (scratchpad/cap_hunt.py) `det` never equals `1e-12`.
- The singular-guard branch itself IS reachable and IS tested (separable goldens exit `singular`);
  only the `== 1e-12` knife-edge is not. No input distinguishes `<=` from `<`.
- Refactor option if elimination is preferred: none clean — every float threshold guard has an
  irreducible `<`/`<=` boundary. Recommend accept-by-proof.

## OPT-2  june_m1_harness `_metrics` L285  ReplaceComparisonOperator_Lt_LtE  `abs(da)+abs(db) < 1e-11` -> `<= 1e-11`
- Same structure as OPT-1: `<` and `<=` differ only when `abs(da)+abs(db)` is bit-exactly `1e-11`.
  The convergence break fires at the same iteration for every input that is not exactly on the
  knife-edge; the exact-equality case is unconstructible from the Newton step arithmetic.
- Confirmed by simulation (scratchpad/opt_sweep.py): the `<=` variant yields identical
  (slope, iterations, status) to `<` on the converged fixture (iterations 7, status converged).
- Note: the sibling `< -> ==` and the `1e-11 -> negative` NumberReplacer DISABLE the break and are
  KILLED by the retained fit_iterations/fit_status (TestOptimiserConvergenceDiagnostics). Only the
  measure-zero `<= ` remains.

## OPT-3/4  june_m1_harness `_fit_slope` L268 (in the diagnostics helper)  NumberReplacer  `range(60)` -> `range(59)` / `range(61)`
- The iteration cap is a non-binding safety backstop. Across the designed differential fixtures AND
  a 20,000-fixture adversarial sweep the fit ALWAYS exits via `converged` or `singular` in <= 27
  iterations; `fit_status` is never `max_iterations`. TestOptimiserConvergenceDiagnostics::
  test_no_valid_fixture_reaches_the_iteration_cap pins this over a deterministic 2,000-case sweep.
- Because the loop provably (empirically, exhaustively-sampled) exits before iteration 59, the cap
  value 59/60/61 is never the exit path: fit_iterations, fit_status, and cal_slope are identical
  for all three. No input reaches the cap, so no input distinguishes them.
- This is NOT "ordinary fixtures terminate early" — it is "NO fixture (incl. near-separable,
  weakly-identified, boundary-probability, imbalanced, 20k random) reaches the cap." A formal
  all-inputs bound on Newton iterations for the 2-parameter logistic is not supplied; the evidence
  is the exhaustive sweep + the retained fit_status observable that would flag any future
  cap-reaching input as `max_iterations`.
- Refactor option: keep the cap (removing it risks non-termination). Recommend accept-by-proof,
  backed by the retained fit_status guard.

## DATE-1  tennis_outcomes `extract` L264  NumberReplacer  `market_time[:10]` -> `market_time[:11]`
- `_SCOPE_BOUNDARY` is exactly 10 characters ("2026-06-01"). For any ISO-8601 `market_time` and the
  10-char boundary B, compare s10=market_time[:10] and s11=market_time[:11]:
    * len(market_time) <= 10  => s11 == s10                              => identical result
    * s10 > B  => s11 (shares the 10-char prefix s10, which is > B) > B  => both >= B
    * s10 == B => s11 = B + (11th char) > B                              => both satisfy >= B
    * s10 < B  => s11[:10] == s10 < B => s11 < B                         => both < B
  In every case `(s10 >= B) == (s11 >= B)`. The 11th character (the ISO 'T'/' ' separator, or
  absent) can never change a comparison against a 10-character boundary. Representative fixtures
  (UTC 'Z', numeric offset, space separator, date-only) all yield the identical refuse/allow
  decision — they demonstrate the equivalence, they do not distinguish it.
- The killed sibling `[:10] -> [:9]` IS behavioural (9 chars drops a date digit) and is covered by
  test_market_time_exactly_at_boundary_refuses.
- Refactor option to make it killable: parse `date.fromisoformat(market_time[:10])` vs a date
  boundary — then `[:11]` raises ValueError. This changes error-handling on malformed marketTime
  (fail-closed on unparseable) and is a governed behaviour change; flagged for founder direction.
  Recommend accept-by-proof OR authorise the date-parse refactor.

## INT-1  tennis_outcomes `_require_sha256` L117  ReplaceComparisonOperator_Eq_Is  `len(value) == 71` -> `len(value) is 71`
- The compared value is always the built-in int returned by `len(value)`, checked against the
  literal `71` (= `len("sha256:") + 64`). CPython caches every int in [-5, 256], so all int-71
  objects are the SAME object: `len(value) is 71` is True exactly when `len(value) == 71`, and
  False (different cached/computed int object, `is` False, matching `==` False) otherwise. Equal on
  every input.
- The contract structurally requires the value's length to equal the built-in int 71 (a sha256 hex
  string is exactly 71 chars incl. the "sha256:" prefix); there is no valid input whose length is a
  non-interned 71, so the founder-sanctioned KILL-with-a-runtime-distinct-71 is not constructible.
- Environment-bound proof (per founder §8): CPython small-int caching of [-5, 256] is guaranteed on
  every supported CPython (3.11+ here); the equivalence holds on this interpreter. RECLASSIFY IF the
  interpreter changes to one without small-int caching (e.g. a hypothetical non-CPython target).
- Recommend accept under the environment-bound-proof clause the founder explicitly permitted.
