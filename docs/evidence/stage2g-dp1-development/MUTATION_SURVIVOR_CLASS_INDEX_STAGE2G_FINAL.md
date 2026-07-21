# Stage 2G mutation survivor class index (FINAL) — founder adjudication

Total surviving mutants: **215** across glicko2_family / dp1_calibration / dp1_distribution. Every entry `approved_by: null`; no prior founder approval exists.
Merged manifest: MUTATION_SURVIVOR_PACKET_STAGE2G_FINAL_ALL_V1.json (entries digest sha256:e4725acec4237d27...).

| class | count | modules |
|---|---|---|
| B_byte_identical_rule_construction | 62 | dp1_distribution |
| A_pep563_annotation | 44 | dp1_distribution |
| J_dead_except_sign_unreachable | 34 | glicko2_family |
| L_layered_unreachable_boundary | 15 | dp1_calibration, dp1_distribution |
| G_diagnostic_prose | 14 | dp1_distribution, glicko2_family |
| E_unreachable_ksearch_structure | 13 | glicko2_family |
| F_defensive_counter | 7 | dp1_calibration, glicko2_family |
| F_defensive_cap | 4 | dp1_calibration, dp1_distribution |
| C_min_invariant_equivalent | 4 | dp1_calibration |
| N_slope_guard_masked_by_temperature | 3 | dp1_calibration |
| E_same_root_convergence_path | 2 | glicko2_family |
| H_domain_bound_identity | 2 | glicko2_family |
| D_unreachable_branch_race_invariant | 2 | glicko2_family |
| K_sigmoid_branch_x0_identity | 2 | dp1_calibration, dp1_distribution |
| H_environment_bound_identity | 2 | dp1_calibration, dp1_distribution |
| I_type_checking_import | 1 | glicko2_family |
| C2_dominated_comparison_sorted_invariant | 1 | glicko2_family |
| F_defensive_epsilon | 1 | dp1_calibration |
| M_defensive_finite_guard_masked | 1 | dp1_calibration |
| C_symmetric_quadrature_reflection | 1 | dp1_distribution |

## B_byte_identical_rule_construction (62)

- **modules:** dp1_distribution
- **mechanism:** Gauss-Hermite rule construction (Newton root-finder internals / dead stores / cache)
- **representative:** `p2 = 0.0` -> `p2 = 1.0`
- **disposition:** bit-identical throughout the registered domain (golden SHA-256 pinned)
- **structural proof:** The frozen 20-node rule is built by an orthonormal-Hermite Newton root finder. Initial-guess formulae, pre-loop dead stores, the memoization cache size, and the polish-threshold constant only affect HOW each root is reached; Newton converges to the same root, and the constructed (node, weight) arrays are BYTE-IDENTICAL — pinned by TestNumericalEdges::test_golden_rule_digest_pinned (sha256 of repr(rule)) plus the quadrature exactness/symmetry/weight-sum tests. central_win_probability is additionally cross-checked against an independent Simpson integral.
- **survivor IDs:**

  - `dp1_distribution.py::core/NumberReplacer::20` (L70, core/NumberReplacer)
  - `dp1_distribution.py::core/NumberReplacer::21` (L70, core/NumberReplacer)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Add_BitOr::2` (L71, core/ReplaceBinaryOperator_Add_BitOr)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Add_BitXor::2` (L71, core/ReplaceBinaryOperator_Add_BitXor)
  - `dp1_distribution.py::core/NumberReplacer::30` (L78, core/NumberReplacer)
  - `dp1_distribution.py::core/NumberReplacer::31` (L78, core/NumberReplacer)
  - `dp1_distribution.py::core/RemoveDecorator::0` (L78, core/RemoveDecorator)
  - `dp1_distribution.py::core/NumberReplacer::33` (L82, core/NumberReplacer)
  - `dp1_distribution.py::core/ReplaceComparisonOperator_NotEq_Gt::0` (L82, core/ReplaceComparisonOperator_NotEq_Gt)
  - `dp1_distribution.py::core/NumberReplacer::40` (L86, core/NumberReplacer)
  - `dp1_distribution.py::core/NumberReplacer::41` (L86, core/NumberReplacer)
  - `dp1_distribution.py::core/ReplaceComparisonOperator_Eq_LtE::0` (L89, core/ReplaceComparisonOperator_Eq_LtE)
  - `dp1_distribution.py::core/NumberReplacer::44` (L90, core/NumberReplacer)
  - `dp1_distribution.py::core/NumberReplacer::46` (L90, core/NumberReplacer)
  - `dp1_distribution.py::core/NumberReplacer::47` (L90, core/NumberReplacer)
  - `dp1_distribution.py::core/NumberReplacer::49` (L90, core/NumberReplacer)
  - `dp1_distribution.py::core/NumberReplacer::50` (L90, core/NumberReplacer)
  - `dp1_distribution.py::core/NumberReplacer::51` (L90, core/NumberReplacer)
  - `dp1_distribution.py::core/NumberReplacer::52` (L90, core/NumberReplacer)
  - `dp1_distribution.py::core/NumberReplacer::53` (L90, core/NumberReplacer)
  - `dp1_distribution.py::core/NumberReplacer::54` (L90, core/NumberReplacer)
  - `dp1_distribution.py::core/NumberReplacer::56` (L90, core/NumberReplacer)
  - `dp1_distribution.py::core/NumberReplacer::57` (L90, core/NumberReplacer)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Add_Div::3` (L90, core/ReplaceBinaryOperator_Add_Div)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Add_Div::4` (L90, core/ReplaceBinaryOperator_Add_Div)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Add_FloorDiv::3` (L90, core/ReplaceBinaryOperator_Add_FloorDiv)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Add_FloorDiv::4` (L90, core/ReplaceBinaryOperator_Add_FloorDiv)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Add_Mul::3` (L90, core/ReplaceBinaryOperator_Add_Mul)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Add_Mul::4` (L90, core/ReplaceBinaryOperator_Add_Mul)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Add_Pow::3` (L90, core/ReplaceBinaryOperator_Add_Pow)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Add_Pow::4` (L90, core/ReplaceBinaryOperator_Add_Pow)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Add_Sub::3` (L90, core/ReplaceBinaryOperator_Add_Sub)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Add_Sub::4` (L90, core/ReplaceBinaryOperator_Add_Sub)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Div_FloorDiv::4` (L90, core/ReplaceBinaryOperator_Div_FloorDiv)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Div_Mul::4` (L90, core/ReplaceBinaryOperator_Div_Mul)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Div_Pow::4` (L90, core/ReplaceBinaryOperator_Div_Pow)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Div_Sub::4` (L90, core/ReplaceBinaryOperator_Div_Sub)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Mul_Add::5` (L90, core/ReplaceBinaryOperator_Mul_Add)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Mul_FloorDiv::3` (L90, core/ReplaceBinaryOperator_Mul_FloorDiv)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Mul_Mod::4` (L90, core/ReplaceBinaryOperator_Mul_Mod)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Mul_Pow::5` (L90, core/ReplaceBinaryOperator_Mul_Pow)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Pow_Mod::1` (L90, core/ReplaceBinaryOperator_Pow_Mod)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Pow_Mul::1` (L90, core/ReplaceBinaryOperator_Pow_Mul)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Sub_Add::3` (L90, core/ReplaceBinaryOperator_Sub_Add)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Sub_Mul::3` (L90, core/ReplaceBinaryOperator_Sub_Mul)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Sub_Pow::3` (L90, core/ReplaceBinaryOperator_Sub_Pow)
  - `dp1_distribution.py::core/ReplaceComparisonOperator_Eq_LtE::1` (L91, core/ReplaceComparisonOperator_Eq_LtE)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Mul_Mod::6` (L92, core/ReplaceBinaryOperator_Mul_Mod)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Mul_Pow::6` (L92, core/ReplaceBinaryOperator_Mul_Pow)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Mul_Sub::6` (L92, core/ReplaceBinaryOperator_Mul_Sub)
  - `dp1_distribution.py::core/NumberReplacer::65` (L93, core/NumberReplacer)
  - `dp1_distribution.py::core/ReplaceComparisonOperator_Eq_Lt::2` (L93, core/ReplaceComparisonOperator_Eq_Lt)
  - `dp1_distribution.py::core/ReplaceComparisonOperator_Eq_LtE::2` (L93, core/ReplaceComparisonOperator_Eq_LtE)
  - `dp1_distribution.py::core/NumberReplacer::75` (L95, core/NumberReplacer)
  - `dp1_distribution.py::core/ReplaceComparisonOperator_Eq_Lt::3` (L95, core/ReplaceComparisonOperator_Eq_Lt)
  - `dp1_distribution.py::core/ReplaceComparisonOperator_Eq_LtE::3` (L95, core/ReplaceComparisonOperator_Eq_LtE)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Sub_Mod::6` (L98, core/ReplaceBinaryOperator_Sub_Mod)
  - `dp1_distribution.py::core/NumberReplacer::94` (L104, core/NumberReplacer)
  - `dp1_distribution.py::core/NumberReplacer::95` (L104, core/NumberReplacer)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Mul_Div::14` (L104, core/ReplaceBinaryOperator_Mul_Div)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Mul_Mod::14` (L104, core/ReplaceBinaryOperator_Mul_Mod)
  - `dp1_distribution.py::core/ReplaceComparisonOperator_LtE_Lt::0` (L104, core/ReplaceComparisonOperator_LtE_Lt)

## A_pep563_annotation (44)

- **modules:** dp1_distribution
- **mechanism:** PEP-563 postponed annotation mutation
- **representative:** `last_active_date_a: date | None,` -> `last_active_date_a: date + None,`
- **disposition:** bit-identical (never evaluated at runtime)
- **structural proof:** Mutation inside a parameter annotation. All three modules begin with `from __future__ import annotations`, so every annotation is a never-evaluated string. No production module calls typing.get_type_hints / inspect.get_annotations / .__annotations__ (TestClassAPep563ArchitecturePin::test_no_runtime_annotation_consumer_in_repo), and the DP1 modules define no pydantic models (test_dp1_modules_define_no_pydantic_models). The mutated expression is dead text on every code path.
- **survivor IDs:**

  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_Add::0` (L213, core/ReplaceBinaryOperator_BitOr_Add)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_BitAnd::0` (L213, core/ReplaceBinaryOperator_BitOr_BitAnd)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_BitXor::0` (L213, core/ReplaceBinaryOperator_BitOr_BitXor)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_Div::0` (L213, core/ReplaceBinaryOperator_BitOr_Div)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_FloorDiv::0` (L213, core/ReplaceBinaryOperator_BitOr_FloorDiv)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_LShift::0` (L213, core/ReplaceBinaryOperator_BitOr_LShift)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_Mod::0` (L213, core/ReplaceBinaryOperator_BitOr_Mod)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_Mul::0` (L213, core/ReplaceBinaryOperator_BitOr_Mul)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_Pow::0` (L213, core/ReplaceBinaryOperator_BitOr_Pow)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_RShift::0` (L213, core/ReplaceBinaryOperator_BitOr_RShift)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_Sub::0` (L213, core/ReplaceBinaryOperator_BitOr_Sub)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_Add::1` (L214, core/ReplaceBinaryOperator_BitOr_Add)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_BitAnd::1` (L214, core/ReplaceBinaryOperator_BitOr_BitAnd)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_BitXor::1` (L214, core/ReplaceBinaryOperator_BitOr_BitXor)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_Div::1` (L214, core/ReplaceBinaryOperator_BitOr_Div)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_FloorDiv::1` (L214, core/ReplaceBinaryOperator_BitOr_FloorDiv)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_LShift::1` (L214, core/ReplaceBinaryOperator_BitOr_LShift)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_Mod::1` (L214, core/ReplaceBinaryOperator_BitOr_Mod)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_Mul::1` (L214, core/ReplaceBinaryOperator_BitOr_Mul)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_Pow::1` (L214, core/ReplaceBinaryOperator_BitOr_Pow)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_RShift::1` (L214, core/ReplaceBinaryOperator_BitOr_RShift)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_Sub::1` (L214, core/ReplaceBinaryOperator_BitOr_Sub)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_Add::2` (L240, core/ReplaceBinaryOperator_BitOr_Add)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_BitAnd::2` (L240, core/ReplaceBinaryOperator_BitOr_BitAnd)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_BitXor::2` (L240, core/ReplaceBinaryOperator_BitOr_BitXor)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_Div::2` (L240, core/ReplaceBinaryOperator_BitOr_Div)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_FloorDiv::2` (L240, core/ReplaceBinaryOperator_BitOr_FloorDiv)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_LShift::2` (L240, core/ReplaceBinaryOperator_BitOr_LShift)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_Mod::2` (L240, core/ReplaceBinaryOperator_BitOr_Mod)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_Mul::2` (L240, core/ReplaceBinaryOperator_BitOr_Mul)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_Pow::2` (L240, core/ReplaceBinaryOperator_BitOr_Pow)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_RShift::2` (L240, core/ReplaceBinaryOperator_BitOr_RShift)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_Sub::2` (L240, core/ReplaceBinaryOperator_BitOr_Sub)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_Add::3` (L241, core/ReplaceBinaryOperator_BitOr_Add)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_BitAnd::3` (L241, core/ReplaceBinaryOperator_BitOr_BitAnd)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_BitXor::3` (L241, core/ReplaceBinaryOperator_BitOr_BitXor)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_Div::3` (L241, core/ReplaceBinaryOperator_BitOr_Div)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_FloorDiv::3` (L241, core/ReplaceBinaryOperator_BitOr_FloorDiv)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_LShift::3` (L241, core/ReplaceBinaryOperator_BitOr_LShift)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_Mod::3` (L241, core/ReplaceBinaryOperator_BitOr_Mod)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_Mul::3` (L241, core/ReplaceBinaryOperator_BitOr_Mul)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_Pow::3` (L241, core/ReplaceBinaryOperator_BitOr_Pow)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_RShift::3` (L241, core/ReplaceBinaryOperator_BitOr_RShift)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_BitOr_Sub::3` (L241, core/ReplaceBinaryOperator_BitOr_Sub)

## J_dead_except_sign_unreachable (34)

- **modules:** glicko2_family
- **mechanism:** (see proof)
- **representative:** `num = ex * (delta_sq - phi_sq - v - ex)` -> `num = ex ** (delta_sq - phi_sq - v - ex)`
- **disposition:** bit-identical throughout the registered pure-seam domain
- **structural proof:** initial_bracket's LOCAL f(x) is evaluated exactly ONCE, at x=a-tau, only to test the k-search while-condition. On the k-branch D=delta^2-phi^2-v<=0, so f(a-tau)>3/2>0 (analytic; TestInitialBracketSeam::test_k_search_body_is_structurally_unreachable pins f(a-tau)>0 across a wide domain grid). A mutation of f's arithmetic that preserves that strictly-positive sign leaves the returned bracket (a, a-tau) unchanged; the sign margin >3/2 is not crossable by these operand mutations. f is otherwise dead code.
- **survivor IDs:**

  - `glicko2_family.py::core/ReplaceBinaryOperator_Mul_Pow::10` (L137, core/ReplaceBinaryOperator_Mul_Pow)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Mul_Sub::10` (L137, core/ReplaceBinaryOperator_Mul_Sub)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Sub_Add::1` (L137, core/ReplaceBinaryOperator_Sub_Add)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Sub_Add::2` (L137, core/ReplaceBinaryOperator_Sub_Add)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Sub_Add::3` (L137, core/ReplaceBinaryOperator_Sub_Add)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Sub_Div::1` (L137, core/ReplaceBinaryOperator_Sub_Div)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Sub_Div::2` (L137, core/ReplaceBinaryOperator_Sub_Div)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Sub_FloorDiv::1` (L137, core/ReplaceBinaryOperator_Sub_FloorDiv)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Sub_FloorDiv::2` (L137, core/ReplaceBinaryOperator_Sub_FloorDiv)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Sub_Mod::1` (L137, core/ReplaceBinaryOperator_Sub_Mod)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Sub_Mod::2` (L137, core/ReplaceBinaryOperator_Sub_Mod)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Sub_Mod::3` (L137, core/ReplaceBinaryOperator_Sub_Mod)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Sub_Mul::1` (L137, core/ReplaceBinaryOperator_Sub_Mul)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Sub_Mul::2` (L137, core/ReplaceBinaryOperator_Sub_Mul)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Sub_Pow::1` (L137, core/ReplaceBinaryOperator_Sub_Pow)
  - `glicko2_family.py::core/NumberReplacer::26` (L138, core/NumberReplacer)
  - `glicko2_family.py::core/NumberReplacer::27` (L138, core/NumberReplacer)
  - `glicko2_family.py::core/NumberReplacer::28` (L138, core/NumberReplacer)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Add_Mul::4` (L138, core/ReplaceBinaryOperator_Add_Mul)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Add_Sub::4` (L138, core/ReplaceBinaryOperator_Add_Sub)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Mul_Add::11` (L138, core/ReplaceBinaryOperator_Mul_Add)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Mul_Sub::11` (L138, core/ReplaceBinaryOperator_Mul_Sub)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Div_Add::4` (L139, core/ReplaceBinaryOperator_Div_Add)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Div_Add::5` (L139, core/ReplaceBinaryOperator_Div_Add)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Div_FloorDiv::4` (L139, core/ReplaceBinaryOperator_Div_FloorDiv)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Div_FloorDiv::5` (L139, core/ReplaceBinaryOperator_Div_FloorDiv)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Div_Mod::4` (L139, core/ReplaceBinaryOperator_Div_Mod)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Mul_Add::12` (L139, core/ReplaceBinaryOperator_Mul_Add)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Mul_Div::12` (L139, core/ReplaceBinaryOperator_Mul_Div)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Mul_FloorDiv::12` (L139, core/ReplaceBinaryOperator_Mul_FloorDiv)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Mul_Pow::12` (L139, core/ReplaceBinaryOperator_Mul_Pow)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Sub_Div::4` (L139, core/ReplaceBinaryOperator_Sub_Div)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Sub_FloorDiv::4` (L139, core/ReplaceBinaryOperator_Sub_FloorDiv)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Sub_Mul::4` (L139, core/ReplaceBinaryOperator_Sub_Mul)

## L_layered_unreachable_boundary (15)

- **modules:** dp1_calibration, dp1_distribution
- **mechanism:** domain-guard boundary (open-interval / layered guard)
- **representative:** `if not (0.0 < p < 1.0):` -> `if not ( -1.0 < p < 1.0):`
- **disposition:** unreachable boundary / masked by a paired guard
- **structural proof:** Boundary/widening mutations of `0.0 < p < 1.0` domain guards. In the fit and pair paths the guarded value is always a validated OPEN-interval probability (OOFFundamental / WinProbabilityDistribution constructors), so the {0,1} boundary is unreachable. In the public apply/logit path the two guards are layered so a mutation of either boundary is masked by the other (apply(0.0)/apply(1.0)/apply(1.5) still raise). The s==0 shortcut boundary is likewise shielded by the earlier s<0 refusal. No returned value changes.
- **survivor IDs:**

  - `dp1_calibration.py::core/NumberReplacer::15` (L74, core/NumberReplacer)
  - `dp1_calibration.py::core/NumberReplacer::16` (L74, core/NumberReplacer)
  - `dp1_calibration.py::core/ReplaceComparisonOperator_Lt_IsNot::1` (L74, core/ReplaceComparisonOperator_Lt_IsNot)
  - `dp1_calibration.py::core/ReplaceComparisonOperator_Lt_LtE::1` (L74, core/ReplaceComparisonOperator_Lt_LtE)
  - `dp1_calibration.py::core/ReplaceComparisonOperator_Lt_LtE::2` (L74, core/ReplaceComparisonOperator_Lt_LtE)
  - `dp1_calibration.py::core/ReplaceComparisonOperator_Lt_NotEq::1` (L74, core/ReplaceComparisonOperator_Lt_NotEq)
  - `dp1_calibration.py::core/ReplaceComparisonOperator_Lt_NotEq::2` (L74, core/ReplaceComparisonOperator_Lt_NotEq)
  - `dp1_calibration.py::core/NumberReplacer::25` (L103, core/NumberReplacer)
  - `dp1_calibration.py::core/NumberReplacer::26` (L103, core/NumberReplacer)
  - `dp1_calibration.py::core/ReplaceComparisonOperator_Lt_IsNot::2` (L103, core/ReplaceComparisonOperator_Lt_IsNot)
  - `dp1_calibration.py::core/ReplaceComparisonOperator_Lt_LtE::4` (L103, core/ReplaceComparisonOperator_Lt_LtE)
  - `dp1_calibration.py::core/ReplaceComparisonOperator_Lt_LtE::5` (L103, core/ReplaceComparisonOperator_Lt_LtE)
  - `dp1_calibration.py::core/ReplaceComparisonOperator_Lt_NotEq::4` (L103, core/ReplaceComparisonOperator_Lt_NotEq)
  - `dp1_calibration.py::core/ReplaceComparisonOperator_Lt_NotEq::5` (L103, core/ReplaceComparisonOperator_Lt_NotEq)
  - `dp1_distribution.py::core/ReplaceComparisonOperator_Eq_LtE::5` (L123, core/ReplaceComparisonOperator_Eq_LtE)

## G_diagnostic_prose (14)

- **modules:** dp1_distribution, glicko2_family
- **mechanism:** diagnostic message f-string internals
- **representative:** `f"(|b-a|={abs(big_b - big_a)!r}, tolerance={tolerance!r}) — refusing, "` -> `f"(|b-a|={abs(big_b + big_a)!r}, tolerance={tolerance!r}) — refusing, "`
- **disposition:** bit-identical (message text only)
- **structural proof:** Mutation inside a refusal-message f-string; the exception TYPE and trigger are pinned by tests and no control flow or returned value depends on the message text. Ratified round-2 s2F class.
- **survivor IDs:**

  - `glicko2_family.py::core/ReplaceBinaryOperator_Sub_Add::16` (L172, core/ReplaceBinaryOperator_Sub_Add)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Sub_Div::16` (L172, core/ReplaceBinaryOperator_Sub_Div)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Sub_FloorDiv::16` (L172, core/ReplaceBinaryOperator_Sub_FloorDiv)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Sub_Mod::16` (L172, core/ReplaceBinaryOperator_Sub_Mod)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Sub_Mul::16` (L172, core/ReplaceBinaryOperator_Sub_Mul)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Sub_Pow::16` (L172, core/ReplaceBinaryOperator_Sub_Pow)
  - `dp1_distribution.py::core/NumberReplacer::116` (L176, core/NumberReplacer)
  - `dp1_distribution.py::core/NumberReplacer::117` (L176, core/NumberReplacer)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Sub_Add::10` (L176, core/ReplaceBinaryOperator_Sub_Add)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Sub_Div::10` (L176, core/ReplaceBinaryOperator_Sub_Div)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Sub_FloorDiv::10` (L176, core/ReplaceBinaryOperator_Sub_FloorDiv)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Sub_Mod::10` (L176, core/ReplaceBinaryOperator_Sub_Mod)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Sub_Mul::10` (L176, core/ReplaceBinaryOperator_Sub_Mul)
  - `dp1_distribution.py::core/ReplaceBinaryOperator_Sub_Pow::10` (L176, core/ReplaceBinaryOperator_Sub_Pow)

## E_unreachable_ksearch_structure (13)

- **modules:** glicko2_family
- **mechanism:** (see proof)
- **representative:** `k = 1` -> `k = 0`
- **disposition:** structurally unreachable throughout the registered public-model domain
- **structural proof:** The k-search loop body (k+=1) never executes: f(a-k*tau)>0 for all k>=1 in the domain (same analytic bound as J). Mutations of the loop init/condition/increment/return that assume >=1 iterations therefore cannot change the returned bracket, which is invariantly (a, a-tau) on the k-branch. TestInitialBracketSeam::test_k_branch_exact and test_exact_equality_takes_the_k_branch pin the exact return; the golden grid pins the downstream new_volatility output.
- **survivor IDs:**

  - `glicko2_family.py::core/NumberReplacer::31` (L143, core/NumberReplacer)
  - `glicko2_family.py::core/NumberReplacer::32` (L144, core/NumberReplacer)
  - `glicko2_family.py::core/NumberReplacer::33` (L144, core/NumberReplacer)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Mul_Add::13` (L144, core/ReplaceBinaryOperator_Mul_Add)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Mul_Div::13` (L144, core/ReplaceBinaryOperator_Mul_Div)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Mul_FloorDiv::13` (L144, core/ReplaceBinaryOperator_Mul_FloorDiv)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Mul_Pow::13` (L144, core/ReplaceBinaryOperator_Mul_Pow)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Mul_Sub::13` (L144, core/ReplaceBinaryOperator_Mul_Sub)
  - `glicko2_family.py::core/ReplaceComparisonOperator_Lt_Eq::1` (L144, core/ReplaceComparisonOperator_Lt_Eq)
  - `glicko2_family.py::core/ReplaceComparisonOperator_Lt_LtE::1` (L144, core/ReplaceComparisonOperator_Lt_LtE)
  - `glicko2_family.py::core/NumberReplacer::34` (L145, core/NumberReplacer)
  - `glicko2_family.py::core/NumberReplacer::35` (L145, core/NumberReplacer)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Mul_Add::14` (L146, core/ReplaceBinaryOperator_Mul_Add)

## F_defensive_counter (7)

- **modules:** dp1_calibration, glicko2_family
- **mechanism:** (see proof)
- **representative:** `iterations = 0` -> `iterations = 1`
- **disposition:** bit-identical throughout the registered pure-seam domain
- **structural proof:** Perturbs an iteration counter that feeds ONLY the never-binding max-iteration cap. On every convergent input the loop exits on the convergence predicate long before the cap; the counter's exact value is never read into any returned/persisted quantity. Output bit-identical (golden grids pass under the mutant).
- **survivor IDs:**

  - `glicko2_family.py::core/NumberReplacer::40` (L167, core/NumberReplacer)
  - `glicko2_family.py::core/NumberReplacer::41` (L167, core/NumberReplacer)
  - `glicko2_family.py::core/NumberReplacer::46` (L182, core/NumberReplacer)
  - `dp1_calibration.py::core/NumberReplacer::48` (L170, core/NumberReplacer)
  - `dp1_calibration.py::core/NumberReplacer::49` (L170, core/NumberReplacer)
  - `dp1_calibration.py::core/NumberReplacer::52` (L204, core/NumberReplacer)
  - `dp1_calibration.py::core/NumberReplacer::53` (L204, core/NumberReplacer)

## F_defensive_cap (4)

- **modules:** dp1_calibration, dp1_distribution
- **mechanism:** never-binding defensive iteration cap
- **representative:** `MAX_NEWTON_ITERATIONS = 100` -> `MAX_NEWTON_ITERATIONS = 101`
- **disposition:** bit-identical (cap never reached)
- **structural proof:** Perturbs a fixed polish/iteration budget that is never reached on convergent inputs; the golden digest / golden-fit pins land bit-identical under the mutant.
- **survivor IDs:**

  - `dp1_calibration.py::core/NumberReplacer::0` (L42, core/NumberReplacer)
  - `dp1_calibration.py::core/NumberReplacer::1` (L42, core/NumberReplacer)
  - `dp1_distribution.py::core/NumberReplacer::6` (L48, core/NumberReplacer)
  - `dp1_distribution.py::core/NumberReplacer::7` (L48, core/NumberReplacer)

## C_min_invariant_equivalent (4)

- **modules:** dp1_calibration
- **mechanism:** (see proof)
- **representative:** `if row.runner_id == low:` -> `if row.runner_id is low:`
- **disposition:** bit-identical throughout the registered domain (equivalent by the canonical invariant)
- **structural proof:** `row.runner_id == low` and `race.winner_id == row.runner_id`, where low=min(active ids). (a) `<=`: nothing is strictly less than the min, so `id <= low` <=> `id == low`; and winner in {a,b} with low=a gives `winner <= a` <=> `winner == a`. Identical labels. (b) `is`: min() returns one of its argument objects by reference, and the OOF row's runner_id is the SAME int object as the RunnerRow's, so `is` coincides with `==` on the production data flow. The golden corpora use large non-interned ids (base 1000/20000/50000) and land bit-identical fits.
- **survivor IDs:**

  - `dp1_calibration.py::core/ReplaceComparisonOperator_Eq_Is::0` (L150, core/ReplaceComparisonOperator_Eq_Is)
  - `dp1_calibration.py::core/ReplaceComparisonOperator_Eq_LtE::2` (L150, core/ReplaceComparisonOperator_Eq_LtE)
  - `dp1_calibration.py::core/ReplaceComparisonOperator_Eq_Is::1` (L164, core/ReplaceComparisonOperator_Eq_Is)
  - `dp1_calibration.py::core/ReplaceComparisonOperator_Eq_LtE::3` (L164, core/ReplaceComparisonOperator_Eq_LtE)

## N_slope_guard_masked_by_temperature (3)

- **modules:** dp1_calibration
- **mechanism:** (see proof)
- **representative:** `if b <= 0.0:` -> `if b <= -1.0:`
- **disposition:** masked by the constructor temperature guard (defense in depth)
- **structural proof:** `if b <= 0.0: raise` -> `== 0.0` / `<= -1.0` / `< 0.0`. Any non-positive slope b that the mutated guard admits produces temperature = 1/b that is negative, zero-divide (inf), or non-finite, all of which AffineLogitCalibration.__post_init__ refuses (temperature must be finite and > 0). So an anti-informative fit is refused either way with CalibrationFitError. No returned value differs.
- **survivor IDs:**

  - `dp1_calibration.py::core/NumberReplacer::55` (L211, core/NumberReplacer)
  - `dp1_calibration.py::core/ReplaceComparisonOperator_LtE_Eq::2` (L211, core/ReplaceComparisonOperator_LtE_Eq)
  - `dp1_calibration.py::core/ReplaceComparisonOperator_LtE_Lt::2` (L211, core/ReplaceComparisonOperator_LtE_Lt)

## E_same_root_convergence_path (2)

- **modules:** glicko2_family
- **mechanism:** (see proof)
- **representative:** `if f_c * f_b <= 0.0:` -> `if f_c / f_b <= 0.0:`
- **disposition:** bit-identical throughout the registered pure-seam domain (exact-output pinned)
- **structural proof:** Illinois acceleration-branch survivor in new_volatility. The Illinois method converges to the UNIQUE root of the paper's strictly-monotone f regardless of the halving detail; TestVolatilityGoldenGrid pins new_volatility to exact float repr across a 12-point extreme grid (tiny/large sigma, phi/RD extremes, surprising and near-expected outcomes, both bracket branches, near-boundary inputs). The mutant produces BIT-IDENTICAL output on every grid point (the golden test passes under it); TestVolatilityRootCondition independently confirms the returned sigma' zeroes the true f.
- **survivor IDs:**

  - `glicko2_family.py::core/ReplaceBinaryOperator_Mul_Div::23` (L177, core/ReplaceBinaryOperator_Mul_Div)
  - `glicko2_family.py::core/ReplaceComparisonOperator_LtE_Lt::1` (L177, core/ReplaceComparisonOperator_LtE_Lt)

## H_domain_bound_identity (2)

- **modules:** glicko2_family
- **mechanism:** (see proof)
- **representative:** `for _ in range(max(0, target_day - current_through - 1)):` -> `for _ in range(max( -1, target_day - current_through - 1)):`
- **disposition:** bit-identical throughout the registered public-model domain
- **structural proof:** `max(0, target_day - current_through - 1)` inactivity-advance survivors. For real UTC-day ordinals target>=current, and range() treats max(0,..) and max(-1,..) identically; the mod/other-operator variants coincide with subtraction on the ordinal domain (target < 2*current always). TestExactPredictionReconstruction pins predict() exactly across gaps 1,2,3,11,40.
- **survivor IDs:**

  - `glicko2_family.py::core/NumberReplacer::65` (L243, core/NumberReplacer)
  - `glicko2_family.py::core/ReplaceBinaryOperator_Sub_Mod::21` (L243, core/ReplaceBinaryOperator_Sub_Mod)

## D_unreachable_branch_race_invariant (2)

- **modules:** glicko2_family
- **mechanism:** (see proof)
- **representative:** `if len(active) != 2:` -> `if len(active) > 2:`
- **disposition:** unreachable branch under the Race constructor invariant
- **structural proof:** `len(active) != 2` -> `> 2`. The Race constructor refuses fewer than two active runners, so len(active) < 2 is unreachable; on the reachable domain {2, >=3}, `!= 2` and `> 2` agree. TestClassDRaceInvariantPin pins the constructor refusals; TestStructuralContracts pins the 3-active refusal message.
- **survivor IDs:**

  - `glicko2_family.py::core/ReplaceComparisonOperator_NotEq_Gt::0` (L282, core/ReplaceComparisonOperator_NotEq_Gt)
  - `glicko2_family.py::core/ReplaceComparisonOperator_NotEq_Gt::1` (L323, core/ReplaceComparisonOperator_NotEq_Gt)

## K_sigmoid_branch_x0_identity (2)

- **modules:** dp1_calibration, dp1_distribution
- **mechanism:** stable-sigmoid branch dispatch at x==0
- **representative:** `if x >= 0.0:` -> `if x > 0.0:`
- **disposition:** bit-identical (both branches equal 0.5 at x=0)
- **structural proof:** `if x >= 0.0` -> `> 0.0`. The two branches implement the SAME function (1/(1+e^-x) == e^x/(1+e^x)); they differ only in dispatch at x==0.0, where both yield exactly 0.5. Off-zero both branches are pinned bit-exact by TestGuardKills::test_sigmoid_branch_split_is_bit_exact.
- **survivor IDs:**

  - `dp1_calibration.py::core/ReplaceComparisonOperator_GtE_Gt::0` (L67, core/ReplaceComparisonOperator_GtE_Gt)
  - `dp1_distribution.py::core/ReplaceComparisonOperator_GtE_Gt::0` (L57, core/ReplaceComparisonOperator_GtE_Gt)

## H_environment_bound_identity (2)

- **modules:** dp1_calibration, dp1_distribution
- **mechanism:** str identity (`!=` -> `is not` on an already-trimmed string)
- **representative:** `if not self.tour or self.tour != self.tour.strip():` -> `if not self.tour or self.tour is not self.tour.strip():`
- **disposition:** environment-bound equivalent (documented; NOT a language-level equivalence)
- **structural proof:** `text != text.strip()` -> `is not`. CPython str.strip() returns the SAME object for an already-trimmed string, so `is not` is False exactly where `!=` is False; untrimmed input is rejected by both. Ratified is-71 precedent (environment-bound CPython identity).
- **survivor IDs:**

  - `dp1_calibration.py::core/ReplaceComparisonOperator_NotEq_IsNot::0` (L96, core/ReplaceComparisonOperator_NotEq_IsNot)
  - `dp1_distribution.py::core/ReplaceComparisonOperator_NotEq_IsNot::0` (L204, core/ReplaceComparisonOperator_NotEq_IsNot)

## I_type_checking_import (1)

- **modules:** glicko2_family
- **mechanism:** (see proof)
- **representative:** `if TYPE_CHECKING:` -> `if not TYPE_CHECKING:`
- **disposition:** bit-identical throughout the registered public-model domain
- **structural proof:** `if TYPE_CHECKING` -> `if not TYPE_CHECKING`. TYPE_CHECKING is False at runtime, so the guarded block (type-only imports) never executes in either form; no import cycle exists on this path (make verify import graph). No runtime observable.
- **survivor IDs:**

  - `glicko2_family.py::core/AddNot::0` (L31, core/AddNot)

## C2_dominated_comparison_sorted_invariant (1)

- **modules:** glicko2_family
- **mechanism:** (see proof)
- **representative:** `score_a = 1.0 if race.winner_id == a else 0.0` -> `score_a = 1.0 if race.winner_id <= a else 0.0`
- **disposition:** bit-identical under the sorted-pair + Race winner invariant
- **structural proof:** `race.winner_id == a` -> `<=` / `is`, where (a,b)=sorted(active) and Race validation pins winner in {a,b}, a<b. `winner <= a` <=> `winner == a`; `is` coincides via non-interned kill test. TestExactPredictionReconstruction::test_winner_identity_not_used_for_score kills the `is` variant with ids>256; the `<=` variant is equivalent by the a<b invariant.
- **survivor IDs:**

  - `glicko2_family.py::core/ReplaceComparisonOperator_Eq_LtE::0` (L301, core/ReplaceComparisonOperator_Eq_LtE)

## F_defensive_epsilon (1)

- **modules:** dp1_calibration
- **mechanism:** (see proof)
- **representative:** `DET_EPSILON = 1e-12` -> `DET_EPSILON = 1.000000000001`
- **disposition:** bit-identical throughout the registered domain
- **structural proof:** Perturbs DET_EPSILON, the singular-Hessian floor. On well-conditioned corpora abs(det) is orders of magnitude above the floor; the guard never fires, so the floor value is immaterial. Golden pins bit-identical.
- **survivor IDs:**

  - `dp1_calibration.py::core/NumberReplacer::2` (L43, core/NumberReplacer)

## M_defensive_finite_guard_masked (1)

- **modules:** dp1_calibration
- **mechanism:** (see proof)
- **representative:** `if not (math.isfinite(a) and math.isfinite(b)):` -> `if not (math.isfinite(a) or math.isfinite(b)):`
- **disposition:** masked by a downstream guard (defense in depth)
- **structural proof:** `not (isfinite(a) and isfinite(b))` -> `or`. A one-sided non-finite parameter that the `or` form misses is caught one iteration later by the singular-Hessian guard (det degenerates) or the max-iteration cap (nan step never converges), both raising the SAME CalibrationFitError. Non-finite parameters arise only on separable/degenerate corpora, which are refused regardless. No returned value differs.
- **survivor IDs:**

  - `dp1_calibration.py::core/ReplaceAndWithOr::2` (L200, core/ReplaceAndWithOr)

## C_symmetric_quadrature_reflection (1)

- **modules:** dp1_distribution
- **mechanism:** quadrature node reflection (delta + scale*x -> delta - scale*x)
- **representative:** `integral = math.fsum(w * _sigmoid(delta + scale * x) for x, w in rule)` -> `integral = math.fsum(w * _sigmoid(delta - scale * x) for x, w in rule)`
- **disposition:** bit-identical (rule symmetry)
- **structural proof:** The frozen rule is exactly symmetric: each node x is paired with -x sharing its weight (TestGaussHermiteRule::test_node_count_and_symmetry). Reflecting x->-x permutes the fsum terms onto themselves, so the sum is byte-identical; the golden digest test passes under the mutant.
- **survivor IDs:**

  - `dp1_distribution.py::core/ReplaceBinaryOperator_Add_Sub::6` (L127, core/ReplaceBinaryOperator_Add_Sub)



# §5/§6 EXACT PROOF BOUNDARIES (founder-required)

## §5.A  E_unreachable_ksearch_structure (13) — glicko2_family.initial_bracket, L143-146
1. **Reachable via public DP1 model?** NO. The k-search loop body never executes for any
   input rate_player produces.
2. **Reachable via the registered pure seam?** The function is called, but the loop BODY
   (k+=1; k>1 return) is unreachable: no domain input makes f(a−τ)<0.
3. **Invariant establishing unreachability:** on the k-branch D=Δ²−φ²−v≤0, so
   f(a−τ)=[first term with |·|<½] − (−τ)/τ² = [<½] + 1/τ = [<½]+2 > 3/2 > 0 (τ=0.5).
   Analytic; pinned over a wide grid by test_k_search_body_is_structurally_unreachable.
4. **Malformed inputs refused before?** Yes: rate_player validates score∈{0,1}, non-empty
   results; φ,v,δ,σ are its own finite computed values.
5. **Changes to volatility/rating/RD/probability/uncertainty/convergence/iteration-
   diagnostics/serialized-state/replay-digest:** NONE. The returned bracket is invariantly
   (a, a−τ); sigma' is bit-identical (golden grid); every downstream quantity and digest is
   bit-identical; the OUTER Illinois loop's iteration count is unchanged (same bracket).

## §5.B  J_dead_except_sign_unreachable (34) — glicko2_family.initial_bracket local f, L137-139
1. **Public model?** The f value is computed but ONLY its sign at the single k=1 evaluation
   is consumed, and that sign is invariantly positive (>3/2).
2. **Pure seam?** f is evaluated once; any operand mutation preserving sign>0 leaves the
   returned bracket unchanged. f is otherwise dead code.
3. **Invariant:** same f(a−τ)>3/2 bound; the >3/2 margin is not crossable by these operand
   mutations (verified over the domain grid).
4. **Malformed refused before?** Yes (as §5.A).
5. **Changes:** NONE — bracket unchanged ⇒ sigma' and all downstream bit-identical.

## §5.C  L_layered_unreachable_boundary (15) — calib L74/L103, dist L123
1. **Public model?** The boundary (p∈{0,1} at apply(); s<0 at central/interval) is reachable
   at the PUBLIC entry, but masked by a paired guard.
2. **Pure seam?** _logit/_sigmoid receive only validated OPEN-interval values in the fit/pair
   path; the boundary is never presented there.
3. **Invariant:** OOFFundamental validates p∈(0,1) OPEN; apply's guard and _logit's guard are
   layered (either masks the other); the s<0 refusal precedes the s==0 shortcut.
4. **Malformed refused before?** YES — that IS the mechanism.
5. **Changes:** NONE — same exception type raised, or unreachable boundary; no returned value
   differs.

## §6  Same-root Illinois convergence variants (2) — glicko2_family.new_volatility, L177
- **Exact mutant IDs:** `glicko2_family.py::core/ReplaceBinaryOperator_Mul_Div::23`, `glicko2_family.py::core/ReplaceComparisonOperator_LtE_Lt::1`
- **Changed control flow:** the Illinois bracket-update branch selection (which endpoint the
  next iterate replaces) / the acceleration test.
- **Iteration count changes?** MAY differ (different bracket-shrink path).
- **Diagnostic changes?** None observable: the iteration count is neither returned nor
  persisted nor hashed; no diagnostic field exposes it.
- **Max ULP over the registered generated domain:** 0 — bit-identical on every point of the
  12-point extreme grid (TestVolatilityGoldenGrid exact-repr pins pass under the mutant).
- **State/replay digest comparison:** identical (deterministic; make replay unaffected).
- **Analytic reason the finite result must be bit-identical:** the paper's f is strictly
  monotone decreasing (f'(x)<0 everywhere), so it has a UNIQUE root; Illinois from any valid
  bracket converges to that unique root; the convergence tolerance |b−a|≤1e-6 in x yields
  sigma'=exp(A/2) accurate far below float epsilon, so every convergent path rounds to the
  same float. The grid is CONFIRMATION; uniqueness+tolerance is the analytic basis.
- **Generated-domain definition + seed:** the 12-point extreme grid (tiny/large sigma,
  phi/RD extremes, surprising and near-expected outcomes, both bracket branches, near-boundary
  inputs); fully deterministic, no RNG seed.
- **Public vs pure-seam distinction:** new_volatility IS the pure seam and is reachable via
  rate_player (public path); its domain is exactly rate_player's produced (φ,v,δ,σ). The founder
  is correct that the grid alone is not a universal proof — these two entries carry the
  uniqueness argument as their primary basis and remain approved_by: null for adjudication
  (kill via a broader generated-domain sweep, approve as bit-identical, or refactor).
