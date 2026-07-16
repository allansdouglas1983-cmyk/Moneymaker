# 0012 — L4 pricing framework: two-stage model, cross-fit harness, edge distribution (SPEC-030–035)

**Status: design accepted 2026-07-16; implemented in this slice.** Built and tested on
synthetic fixtures with closed-form-verifiable optima — real fitting and Gate-1/2 evaluation
are data-gated (licensed historical data is not in-repo), not code-gated.

## Context

SPEC-030–035 (`planned`, criticality `money`). Governing text: §6.4 (stage one conditional
logit — the v1 BASELINE; the regularised/interaction/hierarchical/boosted variants are a
progression where "each step must earn its place on held-out race-level score"; stage two
`score_i = α·log(p_fundamental_i) + β·log(p_market_info_i)`, `c = softmax(score)` within
race, α/β by MLE on the winner; the five-step cross-fitting procedure; horizon-specific
models; "produce a *distribution* over edge, not a point estimate"), §6.12 (model lineage
manifest), §8 (objective separation: fundamental model targets outcome log likelihood /
proper score), §9.1 (race-level log score), §9.4 (calibration renormalised across each
race), §6.11 (every retraining is a new immutable version). The race is the unit of
analysis; runner-level independence is forbidden (`.claude/rules/evidence.md`).

## Decisions

1. **Pure-Python deterministic numerics; no numpy/scipy.** Runtime deps stay
   `pydantic + pyyaml`. Rationale: races are small (fields ≲ 40, feature dim small), so
   O(K³) Newton steps are trivial; BLAS thread-dependent summation would make fits
   non-bit-reproducible across runs/environments, breaking the manifest-digest discipline
   the platform is built on. All likelihood/gradient/Hessian accumulations use
   `math.fsum` (exactly rounded, argument-order independent), making **fit determinism and
   runner-permutation invariance exact bit-level properties**, not tolerance assertions.
2. **Float scope.** Statistical internals (utilities, probabilities, coefficients) are
   binary floats BY DESIGN — this is the modelling layer, and §6.9's never-float rule
   scopes to stake/liability/tick/odds representations. Every boundary is explicit:
   features ARRIVE as l3's Decimals (`Mapping[str, Decimal]`) and are converted once
   inside the fitter; probabilities LEAVE only as `Decimal` via shortest-repr conversion
   (`Decimal(repr(x))`) inside guarded types. No float ever represents money.
3. **Stage one (SPEC-030), `conditional_logit.py`.** `fit_conditional_logit(races, schema,
   horizon)` — race-grouped MLE on the winner: `LL = Σ_r [u_{w_r} − logsumexp(u_r)]`,
   analytic gradient and Hessian, Newton with Cholesky solve, `grad_tol = 1e-10`,
   `max_iter = 100`. Non-convergence raises `FitDidNotConverge`; coefficient blow-up
   (‖β‖∞ > 1e6, perfect separation) raises `SeparationError` — **never silent
   regularisation** (the spec's step-1 progression "regularised conditional logit" is a
   future, separately-earned variant). Non-runners are dropped before fitting and
   prediction renormalises over active runners; a race with fewer than two active runners
   is refused at construction (an explicit upstream exclusion, never a silent disappearance).
4. **Cross-fitting (SPEC-031), `crossfit.py`.** Meeting-day blocks in chronological order;
   expanding window (block k's stage-one model trains on blocks strictly before k). Every
   out-of-fold fundamental is a typed `OOFFundamental` carrying provenance
   (`trained_through_day`, the training race-id set and its digest). The assembler
   re-verifies every row (`race.meeting_day > trained_through_day` and
   `race_id ∉ training_race_ids`) and raises `CrossFitViolation` otherwise — the SPEC-031
   property test constructs contaminated assignments and MUST see the violation. Earliest
   block(s) have no OOF model; they are returned as explicit exclusions with reasons and
   `len(oof_races) + len(excluded) == len(input)` is asserted (universe accounting). The
   plan also returns the **deployment model** (§6.4 step 4: stage one retrained on the full
   window) — distinct from the OOF models by construction and never a source of stage-two
   training rows.
5. **Stage two (SPEC-032), `stage_two.py`.** Accepts only `OOFFundamental` values — a bare
   float/Decimal fundamental cannot type into training (the SPEC-031→032 coupling), and the
   market input is `l5_decision.prices.MarketInfoPrice`, extending SPEC-051's three-price
   type separation upstream (a `p_close` cannot reach the combiner). Two-parameter Newton
   MLE for (α, β) on the winner; collinear inputs (p_fundamental ≡ p_market across the
   data ⇒ singular Hessian) raise `CollinearInputsError` rather than returning an arbitrary
   point on the ridge. `combine(alpha, beta, p_fundamental, p_market)` is a pure function:
   softmax within race, sums to 1, and satisfies the manifest's metamorphic set (varies
   with α and with β; increasing `p_fundamental_i` at fixed market and α>0 never decreases
   `c_i`).
6. **Horizon (SPEC-033).** `HorizonLabel` — validated non-empty label (nominal-time bands
   like `T-2m` or market-state-based labels, per §6.4's preference) — is pinned immutably
   on every fitted model; every scoring entry point calls `require_horizon_match` and
   raises `HorizonMismatch` on any difference. That is the "deployment MUST refuse"
   mechanism: scoring is deployment's only door.
7. **Edge distribution (SPEC-034), `distribution.py`.** v1 uses the §6.4-sanctioned
   time-fold ensemble: the cross-fit fold models each price the target runner, giving
   `WinProbabilityDistribution` (frozen; ≥ 2 samples; samples sorted). Its ONLY route into
   the decision layer is `conservative_lower_bound(quantile)` → the existing
   `l5_decision.ev.WinProbabilityLowerBound`; the quantile is the **lower order statistic**
   (floor index — conservative and exactly deterministic; no interpolation). The type
   defines `__float__` and `__bool__` to raise `TypeError`, so it cannot be coerced into a
   point estimate; it deliberately has no mean/median accessor. Samples remain readable for
   l8 calibration diagnostics — the prohibition is on the DECISION layer, whose typed entry
   (`WinProbabilityLowerBound`) is the enforcement point.
8. **No LambdaRank (SPEC-035), `objectives.py`.** The package's only training objective is
   grouped-softmax MLE (= conditional logit; Plackett-Luce reduces to it for winner-only
   data, which is all v1 trains on). A frozen objective registry names it; there is no
   pairwise/ranking loss anywhere, and a guard test asserts the API surface stays free of
   ranking objectives. Validation helpers are race-level proper scores only: `race_log_score`
   (§9.1's `L_r = −log p_{r,w_r}`) and race-level multiclass Brier; the model-selection
   helper consumes those types alone.
9. **Model lineage (§6.12), `manifest.py`.** `ModelManifest` carries exactly the §6.12
   fields (`model_id`, `training_data_manifest`, `source_ids`, `license_check_status`,
   `feature_schema_hash`, `code_commit`, `container_digest`, `random_seeds`,
   `gate_results`, `approved_scope`). `container_digest` reuses
   `l1_reduce.reducer.environment_digest()` (one environment-fingerprint definition
   platform-wide). Fits are deterministic, so `random_seeds` is the empty tuple recorded
   explicitly. The digest is canonical JSON → `sha256:<hex>`, the exact format the gate
   evaluator's `--model-manifest` binding validates. The §6.12 live-build lineage rejection
   is a Phase-3 hook; the field structure and digest exist now.
10. **Immutability (§6.11).** Fitted models and manifests are frozen; refitting returns new
    objects with new digests. No update-in-place API exists.
11. **Synthetic fixtures with exact optima.** Recovery tests avoid sampling noise entirely:
    replicated-frequency constructions make the MLE closed-form (a 3:1 replicated
    two-runner design recovers β̂ = ln 3 exactly; two interleaved race types — fundamental
    informative/market flat and the reverse — identify α and β separately with
    logit-closed-form optima), asserted to 1e-8. Test doubles live inside `tests/` only,
    marked TEST_ONLY where they mimic manifests, and are never importable from the package.
12. **Activation.** SPEC-030–035 flip `planned → active` in this slice's activation commit
    once implemented and covered (enforcement-increasing only, per the standing progression
    plan). SPEC-030/031/032/034 gain manifest causal declarations mirroring their tested
    properties; SPEC-033/035 are structural guard IDs (both-absent per the ADR 0001
    convention).

## Consequences

Gate-1 experiments can now be pre-registered against a real pricing pipeline: cross-fitted
OOF fundamentals → stage-two combination → race-level paired log scores (`d_r`) → the
SPEC-093 evaluator's `Evidence` bounds, with `--model-manifest` binding the exact lineage
digest. The IIA limitation of the baseline is documented and accepted for v1 (§6.4); every
progression step beyond the baseline must earn its place on held-out race-level score and
produces a new immutable version. l4_pricing joins the money-lint surface (already in
`MONEY`) and becomes a mutation-report target; escalation to enforced kill follows the
ADR 0010 pattern once survivors are triaged.
