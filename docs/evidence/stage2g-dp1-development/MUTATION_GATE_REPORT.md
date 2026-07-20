# Stage 2G Slice 2 — DP1 mutation gate report (SPEC-105/106)

Three rounds on `sport_tennis/glicko2_family.py` + `sport_tennis/dp1_distribution.py`
(cosmic-ray 8.4.6, targeted suite `tests/{unit,properties}/sport_tennis`, 60s timeout).

| round | glicko2_family | dp1_distribution | action |
|---|---|---|---|
| 1 | 899/1043 (86.2%) | 861/1068 (80.6%) | kill batch 1 (commit 8062620) |
| 2 | 979/1043 (93.9%) | 907/1068 (84.9%) | kill batch 2 |
| 3 | 988/1043 (94.7%) | 948/1068 (88.8%) | classification packet below |

Every remaining survivor is classified below into a mechanically-proven equivalence
class. **NO classification is approved**: per the established per-ID protocol these
await explicit founder approval before any entry reaches `specs/mutation-survivors.yaml`.
The founder may instead direct further restructuring (notably class E, where the
prior programme refused blanket optimiser-path claims — the new independent
root-condition test is offered as the mechanical backstop).

## Class summary

### A_pep563_annotation (44 IDs)

mutation inside a parameter annotation; both modules use `from __future__ import annotations` (PEP 563): the expression is a never-evaluated string on every code path; typing.get_type_hints is never called on these functions anywhere in the repo

- `dp1_distribution.py L213 core/ReplaceBinaryOperator_BitOr_Add#0`
- `dp1_distribution.py L213 core/ReplaceBinaryOperator_BitOr_BitAnd#0`
- `dp1_distribution.py L213 core/ReplaceBinaryOperator_BitOr_BitXor#0`
- `dp1_distribution.py L213 core/ReplaceBinaryOperator_BitOr_Div#0`
- `dp1_distribution.py L213 core/ReplaceBinaryOperator_BitOr_FloorDiv#0`
- `dp1_distribution.py L213 core/ReplaceBinaryOperator_BitOr_LShift#0`
- `dp1_distribution.py L213 core/ReplaceBinaryOperator_BitOr_Mod#0`
- `dp1_distribution.py L213 core/ReplaceBinaryOperator_BitOr_Mul#0`
- `dp1_distribution.py L213 core/ReplaceBinaryOperator_BitOr_Pow#0`
- `dp1_distribution.py L213 core/ReplaceBinaryOperator_BitOr_RShift#0`
- `dp1_distribution.py L213 core/ReplaceBinaryOperator_BitOr_Sub#0`
- `dp1_distribution.py L214 core/ReplaceBinaryOperator_BitOr_Add#1`
- `dp1_distribution.py L214 core/ReplaceBinaryOperator_BitOr_BitAnd#1`
- `dp1_distribution.py L214 core/ReplaceBinaryOperator_BitOr_BitXor#1`
- `dp1_distribution.py L214 core/ReplaceBinaryOperator_BitOr_Div#1`
- `dp1_distribution.py L214 core/ReplaceBinaryOperator_BitOr_FloorDiv#1`
- `dp1_distribution.py L214 core/ReplaceBinaryOperator_BitOr_LShift#1`
- `dp1_distribution.py L214 core/ReplaceBinaryOperator_BitOr_Mod#1`
- `dp1_distribution.py L214 core/ReplaceBinaryOperator_BitOr_Mul#1`
- `dp1_distribution.py L214 core/ReplaceBinaryOperator_BitOr_Pow#1`
- `dp1_distribution.py L214 core/ReplaceBinaryOperator_BitOr_RShift#1`
- `dp1_distribution.py L214 core/ReplaceBinaryOperator_BitOr_Sub#1`
- `dp1_distribution.py L240 core/ReplaceBinaryOperator_BitOr_Add#2`
- `dp1_distribution.py L240 core/ReplaceBinaryOperator_BitOr_BitAnd#2`
- `dp1_distribution.py L240 core/ReplaceBinaryOperator_BitOr_BitXor#2`
- `dp1_distribution.py L240 core/ReplaceBinaryOperator_BitOr_Div#2`
- `dp1_distribution.py L240 core/ReplaceBinaryOperator_BitOr_FloorDiv#2`
- `dp1_distribution.py L240 core/ReplaceBinaryOperator_BitOr_LShift#2`
- `dp1_distribution.py L240 core/ReplaceBinaryOperator_BitOr_Mod#2`
- `dp1_distribution.py L240 core/ReplaceBinaryOperator_BitOr_Mul#2`
- `dp1_distribution.py L240 core/ReplaceBinaryOperator_BitOr_Pow#2`
- `dp1_distribution.py L240 core/ReplaceBinaryOperator_BitOr_RShift#2`
- `dp1_distribution.py L240 core/ReplaceBinaryOperator_BitOr_Sub#2`
- `dp1_distribution.py L241 core/ReplaceBinaryOperator_BitOr_Add#3`
- `dp1_distribution.py L241 core/ReplaceBinaryOperator_BitOr_BitAnd#3`
- `dp1_distribution.py L241 core/ReplaceBinaryOperator_BitOr_BitXor#3`
- `dp1_distribution.py L241 core/ReplaceBinaryOperator_BitOr_Div#3`
- `dp1_distribution.py L241 core/ReplaceBinaryOperator_BitOr_FloorDiv#3`
- `dp1_distribution.py L241 core/ReplaceBinaryOperator_BitOr_LShift#3`
- `dp1_distribution.py L241 core/ReplaceBinaryOperator_BitOr_Mod#3`
- `dp1_distribution.py L241 core/ReplaceBinaryOperator_BitOr_Mul#3`
- `dp1_distribution.py L241 core/ReplaceBinaryOperator_BitOr_Pow#3`
- `dp1_distribution.py L241 core/ReplaceBinaryOperator_BitOr_RShift#3`
- `dp1_distribution.py L241 core/ReplaceBinaryOperator_BitOr_Sub#3`

### B_symmetric_quadrature_reflection (1 IDs)

delta+scale*x -> delta-scale*x under an exactly symmetric node set (each x paired with -x sharing its weight, property-tested): the full sum is mathematically identical; output byte-identical (golden digest passes under the mutant)

- `dp1_distribution.py L127 core/ReplaceBinaryOperator_Add_Sub#6`

### C_dominated_comparison_sorted_invariant (1 IDs)

winner_id == a -> <= a where (a,b)=sorted(active), Race validation pins winner in {a,b}, a<b: True/True and False/False on every reachable input

- `glicko2_family.py L270 core/ReplaceComparisonOperator_Eq_LtE#0`

### D_unreachable_branch_race_invariant (2 IDs)

len(active) != 2 -> > 2: Race construction refuses <2 active runners, so the < side of != is unreachable; equivalent at every constructible input

- `glicko2_family.py L251 core/ReplaceComparisonOperator_NotEq_Gt#0`
- `glicko2_family.py L292 core/ReplaceComparisonOperator_NotEq_Gt#1`

### E_same_root_convergence_path (43 IDs)

Illinois bracket-initialisation / k-search / acceleration variants that still converge, within the 100-step cap and frozen 1e-6 tolerance, to the unique root of the TRUE f (any wrong-root limit now dies against the independent primary-source root-condition test); residual output difference bounded by the tolerance (~3e-8 in sigma-prime), below every behavioural contract; k-search iterations beyond k=1 numerically unreachable for sigma <= ~0.3 (probe attached in packet draft)

- `glicko2_family.py L126 core/ReplaceComparisonOperator_Gt_Eq#0`
- `glicko2_family.py L126 core/ReplaceComparisonOperator_Gt_GtE#0`
- `glicko2_family.py L126 core/ReplaceComparisonOperator_Gt_Is#0`
- `glicko2_family.py L127 core/ReplaceBinaryOperator_Sub_Add#7`
- `glicko2_family.py L127 core/ReplaceBinaryOperator_Sub_Add#6`
- `glicko2_family.py L127 core/ReplaceBinaryOperator_Sub_Div#7`
- `glicko2_family.py L127 core/ReplaceBinaryOperator_Sub_FloorDiv#7`
- `glicko2_family.py L127 core/ReplaceBinaryOperator_Sub_Mod#7`
- `glicko2_family.py L129 core/NumberReplacer#30`
- `glicko2_family.py L129 core/NumberReplacer#31`
- `glicko2_family.py L130 core/NumberReplacer#33`
- `glicko2_family.py L130 core/NumberReplacer#32`
- `glicko2_family.py L130 core/ReplaceBinaryOperator_Mul_Add#13`
- `glicko2_family.py L130 core/ReplaceBinaryOperator_Mul_Div#13`
- `glicko2_family.py L130 core/ReplaceBinaryOperator_Mul_FloorDiv#13`
- `glicko2_family.py L130 core/ReplaceBinaryOperator_Mul_Pow#13`
- `glicko2_family.py L130 core/ReplaceBinaryOperator_Mul_Sub#13`
- `glicko2_family.py L130 core/ReplaceBinaryOperator_Sub_Mul#8`
- `glicko2_family.py L130 core/ReplaceBinaryOperator_Sub_Pow#8`
- `glicko2_family.py L130 core/ReplaceComparisonOperator_Lt_Eq#1`
- `glicko2_family.py L130 core/ReplaceComparisonOperator_Lt_LtE#1`
- `glicko2_family.py L131 core/NumberReplacer#35`
- `glicko2_family.py L131 core/NumberReplacer#34`
- `glicko2_family.py L132 core/ReplaceBinaryOperator_Mul_Add#14`
- `glicko2_family.py L132 core/ReplaceBinaryOperator_Mul_Div#14`
- `glicko2_family.py L132 core/ReplaceBinaryOperator_Mul_FloorDiv#14`
- `glicko2_family.py L132 core/ReplaceBinaryOperator_Mul_Pow#14`
- `glicko2_family.py L132 core/ReplaceBinaryOperator_Mul_Sub#14`
- `glicko2_family.py L132 core/ReplaceBinaryOperator_Sub_Add#9`
- `glicko2_family.py L132 core/ReplaceBinaryOperator_Sub_Div#9`
- `glicko2_family.py L132 core/ReplaceBinaryOperator_Sub_FloorDiv#9`
- `glicko2_family.py L132 core/ReplaceBinaryOperator_Sub_Mod#9`
- `glicko2_family.py L132 core/ReplaceBinaryOperator_Sub_Mul#9`
- `glicko2_family.py L132 core/ReplaceBinaryOperator_Sub_Pow#9`
- `glicko2_family.py L136 core/NumberReplacer#37`
- `glicko2_family.py L136 core/NumberReplacer#36`
- `glicko2_family.py L137 core/ReplaceBinaryOperator_Sub_Mod#10`
- `glicko2_family.py L146 core/ReplaceBinaryOperator_Mul_Add#16`
- `glicko2_family.py L146 core/ReplaceBinaryOperator_Mul_Div#16`
- `glicko2_family.py L146 core/ReplaceBinaryOperator_Mul_FloorDiv#16`
- `glicko2_family.py L146 core/ReplaceComparisonOperator_LtE_Lt#1`
- `glicko2_family.py L149 core/NumberReplacer#40`
- `glicko2_family.py L151 core/NumberReplacer#42`

### F_byte_identical_rule_construction (64 IDs)

Newton initial-guess / polish-threshold / dead-store / cache-size variants whose constructed 20-node rule is BYTE-IDENTICAL to the golden sha256-pinned rule (test passes under the mutant); includes p2/x dead stores multiplied by zero on the first recurrence step, i-comparison variants unreachable off the loop range, and n|1 == n^1 == n+1 for the guard-enforced even n

- `dp1_distribution.py L48 core/NumberReplacer#6`
- `dp1_distribution.py L48 core/NumberReplacer#7`
- `dp1_distribution.py L70 core/NumberReplacer#21`
- `dp1_distribution.py L70 core/NumberReplacer#20`
- `dp1_distribution.py L71 core/ReplaceBinaryOperator_Add_BitOr#2`
- `dp1_distribution.py L71 core/ReplaceBinaryOperator_Add_BitXor#2`
- `dp1_distribution.py L78 core/NumberReplacer#31`
- `dp1_distribution.py L78 core/NumberReplacer#30`
- `dp1_distribution.py L78 core/RemoveDecorator#0`
- `dp1_distribution.py L82 core/NumberReplacer#33`
- `dp1_distribution.py L82 core/ReplaceComparisonOperator_NotEq_Gt#0`
- `dp1_distribution.py L86 core/NumberReplacer#41`
- `dp1_distribution.py L86 core/NumberReplacer#40`
- `dp1_distribution.py L89 core/ReplaceComparisonOperator_Eq_LtE#0`
- `dp1_distribution.py L90 core/NumberReplacer#54`
- `dp1_distribution.py L90 core/NumberReplacer#57`
- `dp1_distribution.py L90 core/NumberReplacer#50`
- `dp1_distribution.py L90 core/NumberReplacer#52`
- `dp1_distribution.py L90 core/NumberReplacer#44`
- `dp1_distribution.py L90 core/NumberReplacer#49`
- `dp1_distribution.py L90 core/NumberReplacer#51`
- `dp1_distribution.py L90 core/NumberReplacer#47`
- `dp1_distribution.py L90 core/NumberReplacer#46`
- `dp1_distribution.py L90 core/NumberReplacer#56`
- `dp1_distribution.py L90 core/NumberReplacer#53`
- `dp1_distribution.py L90 core/ReplaceBinaryOperator_Add_Div#3`
- `dp1_distribution.py L90 core/ReplaceBinaryOperator_Add_Div#4`
- `dp1_distribution.py L90 core/ReplaceBinaryOperator_Add_FloorDiv#4`
- `dp1_distribution.py L90 core/ReplaceBinaryOperator_Add_FloorDiv#3`
- `dp1_distribution.py L90 core/ReplaceBinaryOperator_Add_Mul#3`
- `dp1_distribution.py L90 core/ReplaceBinaryOperator_Add_Mul#4`
- `dp1_distribution.py L90 core/ReplaceBinaryOperator_Add_Pow#4`
- `dp1_distribution.py L90 core/ReplaceBinaryOperator_Add_Pow#3`
- `dp1_distribution.py L90 core/ReplaceBinaryOperator_Add_Sub#4`
- `dp1_distribution.py L90 core/ReplaceBinaryOperator_Add_Sub#3`
- `dp1_distribution.py L90 core/ReplaceBinaryOperator_Div_FloorDiv#4`
- `dp1_distribution.py L90 core/ReplaceBinaryOperator_Div_Mul#4`
- `dp1_distribution.py L90 core/ReplaceBinaryOperator_Div_Pow#4`
- `dp1_distribution.py L90 core/ReplaceBinaryOperator_Div_Sub#4`
- `dp1_distribution.py L90 core/ReplaceBinaryOperator_Mul_Add#5`
- `dp1_distribution.py L90 core/ReplaceBinaryOperator_Mul_FloorDiv#3`
- `dp1_distribution.py L90 core/ReplaceBinaryOperator_Mul_Mod#4`
- `dp1_distribution.py L90 core/ReplaceBinaryOperator_Mul_Pow#5`
- `dp1_distribution.py L90 core/ReplaceBinaryOperator_Pow_Mod#1`
- `dp1_distribution.py L90 core/ReplaceBinaryOperator_Pow_Mul#1`
- `dp1_distribution.py L90 core/ReplaceBinaryOperator_Sub_Add#3`
- `dp1_distribution.py L90 core/ReplaceBinaryOperator_Sub_Mul#3`
- `dp1_distribution.py L90 core/ReplaceBinaryOperator_Sub_Pow#3`
- `dp1_distribution.py L91 core/ReplaceComparisonOperator_Eq_LtE#1`
- `dp1_distribution.py L92 core/ReplaceBinaryOperator_Mul_Mod#6`
- `dp1_distribution.py L92 core/ReplaceBinaryOperator_Mul_Pow#6`
- `dp1_distribution.py L92 core/ReplaceBinaryOperator_Mul_Sub#6`
- `dp1_distribution.py L93 core/NumberReplacer#65`
- `dp1_distribution.py L93 core/ReplaceComparisonOperator_Eq_Lt#2`
- `dp1_distribution.py L93 core/ReplaceComparisonOperator_Eq_LtE#2`
- `dp1_distribution.py L95 core/NumberReplacer#75`
- `dp1_distribution.py L95 core/ReplaceComparisonOperator_Eq_Lt#3`
- `dp1_distribution.py L95 core/ReplaceComparisonOperator_Eq_LtE#3`
- `dp1_distribution.py L98 core/ReplaceBinaryOperator_Sub_Mod#6`
- `dp1_distribution.py L104 core/NumberReplacer#94`
- `dp1_distribution.py L104 core/NumberReplacer#95`
- `dp1_distribution.py L104 core/ReplaceBinaryOperator_Mul_Div#14`
- `dp1_distribution.py L104 core/ReplaceBinaryOperator_Mul_Mod#14`
- `dp1_distribution.py L104 core/ReplaceComparisonOperator_LtE_Lt#0`

### G_diagnostic_prose (14 IDs)

f-string internals of refusal messages whose exception type and pinned key content (match=) are already enforced; mirrors the ratified round-2 s2F class

- `glicko2_family.py L141 core/ReplaceBinaryOperator_Sub_Add#11`
- `glicko2_family.py L141 core/ReplaceBinaryOperator_Sub_Div#11`
- `glicko2_family.py L141 core/ReplaceBinaryOperator_Sub_FloorDiv#11`
- `glicko2_family.py L141 core/ReplaceBinaryOperator_Sub_Mod#11`
- `glicko2_family.py L141 core/ReplaceBinaryOperator_Sub_Mul#11`
- `glicko2_family.py L141 core/ReplaceBinaryOperator_Sub_Pow#11`
- `dp1_distribution.py L176 core/NumberReplacer#116`
- `dp1_distribution.py L176 core/NumberReplacer#117`
- `dp1_distribution.py L176 core/ReplaceBinaryOperator_Sub_Add#10`
- `dp1_distribution.py L176 core/ReplaceBinaryOperator_Sub_Div#10`
- `dp1_distribution.py L176 core/ReplaceBinaryOperator_Sub_FloorDiv#10`
- `dp1_distribution.py L176 core/ReplaceBinaryOperator_Sub_Mod#10`
- `dp1_distribution.py L176 core/ReplaceBinaryOperator_Sub_Mul#10`
- `dp1_distribution.py L176 core/ReplaceBinaryOperator_Sub_Pow#10`

### H_domain_bound_identity (5 IDs)

target%current == target-current for all real date ordinals (target < 2*current for any dates in the corpus era); max(-1,...) vs max(0,...) identical because range() treats -1 and 0 alike; sigmoid >= vs > at x=0 lands both branches on exactly 0.5; s==0 comparison variants shielded by the earlier s<0 refusal; str.strip() returns the identical object for already-trimmed text in CPython (environment-bound, per the ratified is-71 precedent)

- `glicko2_family.py L212 core/NumberReplacer#61`
- `glicko2_family.py L212 core/ReplaceBinaryOperator_Sub_Mod#16`
- `dp1_distribution.py L57 core/ReplaceComparisonOperator_GtE_Gt#0`
- `dp1_distribution.py L123 core/ReplaceComparisonOperator_Eq_LtE#5`
- `dp1_distribution.py L204 core/ReplaceComparisonOperator_NotEq_IsNot#0`

### I_type_checking_import (1 IDs)

if TYPE_CHECKING -> if not TYPE_CHECKING: imports become eager at runtime; no cycle exists on this path; behaviour unobservable

- `glicko2_family.py L31 core/AddNot#0`

