# Discretisation-stability amendment — survivor class index (STAGE3-0006C-D-A3 §16)

Amendment: `CROSS_MARKET_COHERENCE_DISCRETISATION_STABILITY_AMENDMENT_V1`.
Every residual survivor below is a **proven exact equivalent**; `approved_by` is `null` for all.
The two behavioural survivors were **killed tests-first** (round 2, commit `2d788f2`) and are
listed separately. Machine-readable detail:
`DISCRETISATION_STABILITY_AMENDMENT_MUTATION_CONSOLIDATION.json`.

Executed mutants: **367** (scan_variants 148 + discretisation_stability 178 + solver-wiring 41
git-filtered; 294 non-A3 solver lines correctly SKIPPED). Killed by session test-sets: 349.
Session survivors: 18 → 2 killed round 2 + 16 classified exact equivalents. Behavioural
remaining: **0**.

## Proof method

- **scan_variants enum survivors** — CPython language guarantee: `enum.Enum` members are
  singletons and `Enum.__eq__` is identity, so `is`/`==`/`!=`/`is not` are indistinguishable for
  every input. No sweep can distinguish them.
- **discretisation_stability survivors** — a temp-module differential against production over
  **4000 reachable trios per survivor** (seed `20260724+i`), comparing `(stable, reason,
  disagreements)`: **0 observable differences** for every classified survivor. The one mutant
  that showed a difference (L170) was reclassified behavioural and killed.

## Classified exact-equivalent classes (16)

### ENUM_IDENTITY_EQUIVALENT (5)
Enum member `is`/`==`/`!=`/`is not` — identical by the Enum-singleton guarantee.
- `scan_variants.variant_axis` L85/L87/L89 — `variant is ScanVariant.Gk -> ==` (×3).
- `discretisation_stability.compare_registered_variants` L150 — `snap.variant is not variant -> !=`.
- `discretisation_stability.compare_registered_variants` L199 — `mirror is not base_mirror -> !=`
  (`MirrorRelation` enum).

### INTEGER_IDENTITY_EQUIVALENT (4)
`len(...)` / index comparisons where the branch depends only on integer equality and CPython
small-int identity tracks it.
- `_complete_matchings` L106 — `len(left) != len(right) -> is not`.
- `recurse` L117 — `i == n -> i is n`.
- `compare_registered_variants` L145 — `len(snapshots) != len(REGISTERED_VARIANT_ORDER) -> is not`.
- `compare_registered_variants` L176 — `len(left.roots) != len(right.roots) -> is not`.

### GUARD_DOMINATED_EQUIVALENT (3)
A preceding guard/invariant excludes the input on which the mutated operator would differ.
- `recurse` L117 — `i == n -> i >= n`: recursion invariant `0 <= i <= n`.
- `compare_registered_variants` L154 — `len({bool…}) != 1 -> > 1`: a set of three booleans has
  size 1 or 2, never 0.
- `compare_registered_variants` L186 — `len(matchings) > 1 -> != 1`: reached only when
  `matchings` is non-empty (line 182 continues otherwise), so `> 1 <=> != 1`.

### IDEMPOTENT_SELF_COMPARISON_EQUIVALENT (2)
Extending a `snapshots[1:]` loop to `[0:]` adds only a self-comparison against `base =
snapshots[0]`, which never fires.
- `compare_registered_variants` L160 — status loop.
- `compare_registered_variants` L197 — mirror loop.

### BOOLEAN_IDENTITY_EQUIVALENT (1)
- `compare_registered_variants` L191 — `on_boundary != on_boundary -> is not`: `bool` singletons.

### SINGLE_ELEMENT_INDEX_EQUIVALENT (1)
- `compare_registered_variants` L190 — `matchings[0] -> matchings[-1]`: reached only when
  `len(matchings) == 1` (the `> 1` case continues at line 189), so `[0] is [-1]`.

## Killed tests-first — round 2 (2, NOT classified as equivalents)

- **`discretisation_stability.compare_registered_variants` L170** — `all(s.status == NON_
  IDENTIFIABLE.value) -> >=`. Behavioural over the function's type domain: `"NO_ROOT"` sorts
  above `"NON_IDENTIFIABLE"`, so `>=` shortcuts a unanimous-`NO_ROOT` trio to stable. Equivalent
  only over reachable inputs (the `NO_ROOT ⟹ empty roots` invariant of `classify_per_solve`);
  killed conservatively rather than lean on that soft invariant. Kill test:
  `test_all_refusal_shortcut_keys_on_exact_non_identifiable_not_ordering`.
- **`solver._solve_one_on_axis` L269** — `(hi - lo) / (len(axis) - 1) -> ^ 1`. Behavioural:
  `len ^ 1 == len - 1` only for odd axis lengths (the registered 13/25/13), so the registered
  variants leave it inert; an even equally-spaced axis distinguishes them. Kill test:
  `test_solve_on_axis_coarse_step_uses_cardinality_decrement_not_xor` (length-6 axis → one
  `IDENTIFIED` root under `len-1`, spurious second root under `len^1`).

Both kills verified by manual mutant application (test fails under the exact mutant) with
byte-identical source restore; no second mutation session was started.
