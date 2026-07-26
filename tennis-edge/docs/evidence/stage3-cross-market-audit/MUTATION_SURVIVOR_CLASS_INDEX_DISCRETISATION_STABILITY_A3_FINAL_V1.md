# A3 survivor class index — discretisation-stability amendment (FINAL)

Directive: STAGE3-0006C-D-A3-FINALIZE §5. Commit `37bac01`. Exactly **16** classified exact
residual equivalents — the survivors remaining after the two round-2 tests-first kills (ds L170,
solver L269, which are **KILLED**, not listed here). Every entry: **`approved_by: null`**.
Approval is NOT inferred from any return prose.

Machine-readable detail: `MUTATION_SURVIVOR_PACKET_DISCRETISATION_STABILITY_A3_FINAL_V1.json`.
Reproducible proof: `A3_SURVIVOR_EQUIVALENCE_PROOF_V1.json` (all 16 → 0 reachable diffs).
Environment: CPython, version recorded in the packet/proof (`environment`).

## ENUM_IDENTITY — count 5

- **Survivor IDs:** A3-SV-01, A3-SV-02, A3-SV-03 (`ScanVariant`), A3-DS-05 (`ScanVariant`),
  A3-DS-13 (`MirrorRelation`).
- **Modules:** scan_variants.py (3), discretisation_stability.py (2).
- **Representative:** `variant is ScanVariant.G0_BASELINE` → `variant == ScanVariant.G0_BASELINE`.
- **Common proof:** the operand is guaranteed to be a member of the named enum class; enum
  members are process-unique singletons; `Enum.__eq__` is identity; raw strings, `None` and
  foreign types are refused (via `ValueError`/type structure) before the branch, so no
  attacker-controlled foreign `__eq__` is reachable; no serialization/digest change.
- **Per-ID exceptions:** two distinct enum classes are proven **separately** — A3-SV-01/02/03 and
  A3-DS-05 concern `ScanVariant`; A3-DS-13 concerns `MirrorRelation`. Not batched.
- **Environment dependence:** none (singleton identity of enum members holds in every Python
  implementation).
- **Proposed disposition:** EXACT_EQUIVALENT (language-guaranteed).

## INTEGER_IDENTITY — count 4

- **Survivor IDs:** A3-DS-01, A3-DS-03, A3-DS-04, A3-DS-08.
- **Module:** discretisation_stability.py.
- **Representative:** `len(left) != len(right)` → `len(left) is not len(right)`.
- **Common proof:** the branch depends only on integer equality; every reachable operand is a
  small integer (root counts 0–4, snapshot count 3, recursion index ≤ 4), all within CPython's
  small-int cache `[-5, 256]`, so object identity tracks value equality.
- **Per-ID exceptions:** A3-DS-03 is the recursion index `i is n`; the other three are `len()`
  comparisons. All within the cache range.
- **Environment dependence:** **YES — explicitly environment-bound.** Recorded in the packet:
  CPython implementation + full version + small-int cache range + why every reachable value is
  cached. This is NOT claimed as language-level equivalence.
- **Reclassification trigger:** Python implementation/version change, or a reachable length/index
  exceeding 256.
- **Proposed disposition:** EXACT_EQUIVALENT (environment-bound; reclassify on runtime change).

## GUARD_DOMINATED — count 3

- **Survivor IDs:** A3-DS-02 (`i == n` → `i >= n`), A3-DS-06 (`!= 1` → `> 1`),
  A3-DS-09 (`> 1` → `!= 1`).
- **Module:** discretisation_stability.py.
- **Common proof:** a preceding guard/invariant excludes the input on which the operators would
  differ — A3-DS-02: recursion invariant `0 ≤ i ≤ n`; A3-DS-06: a set of three booleans has
  cardinality ∈ {1,2}; A3-DS-09: `matchings` is non-empty here (the empty case already
  `continue`d). Each carries a complete truth table over the reachable branch domain (packet) and
  the malformed-input path (each refused earlier). Exception timing/type and diagnostics are
  unchanged.
- **Per-ID exceptions:** the guard differs per ID (recursion bound / boolean-set cardinality /
  non-empty matchings) — proven individually, not merged.
- **Environment dependence:** none.
- **Reclassification trigger:** weakening the relevant preceding guard.
- **Proposed disposition:** EXACT_EQUIVALENT (guard-dominated).

## IDEMPOTENT_SELF_COMPARISON — count 2

- **Survivor IDs:** A3-DS-07 (status loop), A3-DS-12 (mirror loop).
- **Module:** discretisation_stability.py.
- **Representative:** `for snap in snapshots[1:]` → `snapshots[0:]`.
- **Common proof:** `base = snapshots[0]`; extending the loop to index 0 adds a comparison of the
  base against itself, which is always equal, so the conditional append never fires. The loop
  body performs **no** setter, callback, counter, timestamp, logging event, provenance mutation,
  digest mutation, state transition, or exception-timing change — only a pure conditional
  `list.append` that the self-comparison does not trigger. `classify_mirror_relation` (A3-DS-12)
  is a pure function.
- **Per-ID exceptions:** A3-DS-07 compares `status` strings; A3-DS-12 compares
  `MirrorRelation` values — different operands, same idempotent structure.
- **Environment dependence:** none.
- **Reclassification trigger:** the loop body gaining any side effect.
- **Proposed disposition:** EXACT_EQUIVALENT (idempotent self-comparison).

## BOOLEAN_IDENTITY — count 1

- **Survivor ID:** A3-DS-11.
- **Module:** discretisation_stability.py.
- **Expression:** `on_boundary != on_boundary` → `is not`.
- **Proof:** `Root.on_boundary` is produced by `within_boundary_tolerance(...) = min(...) <
  tolerance`, a closed internal function returning a genuine built-in `bool`; `True`/`False` are
  unique singletons, so `is not` tracks `!=`. No production path yields a `0/1` int, numpy-like
  bool, foreign truthy object, or `None` for `on_boundary` (a `Root` is only ever built from
  `within_boundary_tolerance`).
- **Environment dependence:** none (bool singletons are universal).
- **Reclassification trigger:** a caller able to supply a non-bool `on_boundary`.
- **Proposed disposition:** EXACT_EQUIVALENT (bool singleton).

## SINGLE_ELEMENT_INDEX — count 1

- **Survivor ID:** A3-DS-10.
- **Module:** discretisation_stability.py.
- **Expression:** `enumerate(matchings[0])` → `enumerate(matchings[-1])`.
- **Proof:** reached only when `len(matchings) == 1` — `if not matchings: continue` (line 182)
  refuses empty; `if len(matchings) > 1: continue` (line 186) refuses multi-element. With exactly
  one element, `matchings[0] is matchings[-1]`. No index value enters provenance or diagnostics;
  no exception behavior changes.
- **Environment dependence:** none.
- **Reclassification trigger:** weakening the `len == 1` cardinality guard.
- **Proposed disposition:** EXACT_EQUIVALENT (single-element index).

---

**Totals:** 5 + 4 + 3 + 2 + 1 + 1 = **16**. All `approved_by: null`. No class hides a materially
different mechanism; the two environment-bound / two enum-class distinctions are called out above.
This directive does not approve any survivor.
