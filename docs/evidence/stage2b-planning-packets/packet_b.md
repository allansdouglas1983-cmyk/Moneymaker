# Packet B — Planning σ_d and derived sample sizes (outcome-blind)

Winners: synthetic Bernoulli(p_market) — NO real outcome used; replications per scenario: 100.
**σ_d is a PLANNING ASSUMPTION, not a measured fact** — it will be revised only by
governed pre-registration change, never silently.

Conservative planning value (predeclared p90 across all scenario×rep):
**σ_d = 0.04075** (per-match paired log-score difference, nats).

| shape | f | dp | σ_d mean | σ_d p90 | δ (nats) | N @ α=0.05 | N @ α=0.05/6 |
|---|--:|--:|--:|--:|--:|--:|--:|
| SYMMETRIC | 0.01 | 0.01 | 0.00216 | 0.00256 | 0.000002 | 8,937,260 | 13,788,749 |
| SYMMETRIC | 0.01 | 0.02 | 0.00443 | 0.00572 | 0.000010 | 2,729,332 | 4,210,918 |
| SYMMETRIC | 0.01 | 0.05 | 0.01047 | 0.01179 | 0.000057 | 335,690 | 517,916 |
| SYMMETRIC | 0.05 | 0.01 | 0.00563 | 0.00746 | 0.000018 | 1,411,646 | 2,177,941 |
| SYMMETRIC | 0.05 | 0.02 | 0.01092 | 0.01338 | 0.000062 | 371,732 | 573,522 |
| SYMMETRIC | 0.05 | 0.05 | 0.02710 | 0.03292 | 0.000346 | 70,953 | 109,469 |
| SYMMETRIC | 0.1 | 0.01 | 0.00760 | 0.00884 | 0.000030 | 663,990 | 1,024,430 |
| SYMMETRIC | 0.1 | 0.02 | 0.01509 | 0.01755 | 0.000113 | 189,054 | 291,680 |
| SYMMETRIC | 0.1 | 0.05 | 0.03681 | 0.04147 | 0.000708 | 26,921 | 41,535 |
| SYMMETRIC | 0.2 | 0.01 | 0.01062 | 0.01189 | 0.000060 | 305,167 | 470,823 |
| SYMMETRIC | 0.2 | 0.02 | 0.02193 | 0.02520 | 0.000237 | 88,861 | 137,098 |
| SYMMETRIC | 0.2 | 0.05 | 0.05313 | 0.05861 | 0.001347 | 14,852 | 22,913 |
| FAVOURITE | 0.01 | 0.01 | 0.00238 | 0.00304 | 0.000003 | 8,624,995 | 13,306,975 |
| FAVOURITE | 0.01 | 0.02 | 0.00460 | 0.00499 | 0.000010 | 1,804,762 | 2,784,456 |
| FAVOURITE | 0.01 | 0.05 | 0.01193 | 0.01561 | 0.000065 | 458,123 | 706,809 |
| FAVOURITE | 0.05 | 0.01 | 0.00539 | 0.00628 | 0.000014 | 1,532,705 | 2,364,716 |
| FAVOURITE | 0.05 | 0.02 | 0.01087 | 0.01323 | 0.000059 | 394,780 | 609,082 |
| FAVOURITE | 0.05 | 0.05 | 0.02879 | 0.03560 | 0.000346 | 83,135 | 128,264 |
| FAVOURITE | 0.1 | 0.01 | 0.00775 | 0.00936 | 0.000029 | 812,727 | 1,253,907 |
| FAVOURITE | 0.1 | 0.02 | 0.01502 | 0.01705 | 0.000108 | 194,628 | 300,279 |
| FAVOURITE | 0.1 | 0.05 | 0.03957 | 0.04460 | 0.000679 | 33,829 | 52,193 |
| FAVOURITE | 0.2 | 0.01 | 0.01121 | 0.01274 | 0.000060 | 353,704 | 545,708 |
| FAVOURITE | 0.2 | 0.02 | 0.02223 | 0.02551 | 0.000235 | 92,806 | 143,184 |
| FAVOURITE | 0.2 | 0.05 | 0.05854 | 0.06452 | 0.001408 | 16,486 | 25,435 |
| UNDERDOG | 0.01 | 0.01 | 0.00213 | 0.00247 | 0.000002 | 8,293,226 | 12,795,109 |
| UNDERDOG | 0.01 | 0.02 | 0.00421 | 0.00472 | 0.000011 | 1,371,156 | 2,115,472 |
| UNDERDOG | 0.01 | 0.05 | 0.01064 | 0.01262 | 0.000062 | 329,327 | 508,099 |
| UNDERDOG | 0.05 | 0.01 | 0.00527 | 0.00612 | 0.000016 | 1,149,091 | 1,772,862 |
| UNDERDOG | 0.05 | 0.02 | 0.01014 | 0.01141 | 0.000058 | 300,532 | 463,672 |
| UNDERDOG | 0.05 | 0.05 | 0.02497 | 0.02846 | 0.000330 | 58,489 | 90,239 |
| UNDERDOG | 0.1 | 0.01 | 0.00791 | 0.00920 | 0.000035 | 554,439 | 855,410 |
| UNDERDOG | 0.1 | 0.02 | 0.01427 | 0.01559 | 0.000111 | 156,335 | 241,199 |
| UNDERDOG | 0.1 | 0.05 | 0.03521 | 0.03920 | 0.000787 | 19,474 | 30,046 |
| UNDERDOG | 0.2 | 0.01 | 0.01119 | 0.01359 | 0.000068 | 317,968 | 490,574 |
| UNDERDOG | 0.2 | 0.02 | 0.02077 | 0.02265 | 0.000240 | 70,006 | 108,007 |
| UNDERDOG | 0.2 | 0.05 | 0.04982 | 0.05391 | 0.001458 | 10,725 | 16,547 |

Derivation: `l8_evidence.sample_size.derive_sample_size` (the platform's own SPEC-094
code), power = 0.80, two-sided (conservative), per-trial α from the family-wise
α_total = 0.05 rationed across 1 or 6 planned family comparisons by the existing
multiplicity rule. Each scenario's N pairs its OWN σ_d (p90) with its OWN δ.

Honest reading: at ~2.9k evaluable matches per month, scenarios below δ≈7e-4 are not
provable within any plausible programme budget. This is the quantified form of the
ADR 0018 §12 'power vs budget' design cost, known BEFORE any model exists.
