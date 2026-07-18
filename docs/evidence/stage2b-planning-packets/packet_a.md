# Packet A — Candidate minimum meaningful effect δ (outcome-blind)

Basis: 2,336 primary singles matches with complete two-sided books at the
first T-5m horizon instance (frozen Stage-1 reconstruction). Predeclared residual-
information scenarios; log scores in NATS; NO real outcome read. δ here is the mean
per-match log-score improvement over ALL matches (the SPEC-090 endpoint unit).

| shape | f | dp | δ (all, nats) | per-affected (nats) | clear c=2% (of affected) | clear c=5% |
|---|--:|--:|--:|--:|--:|--:|
| SYMMETRIC | 0.01 | 0.01 | 0.000002 | 0.00024 | 56.5% | 4.3% |
| SYMMETRIC | 0.01 | 0.02 | 0.000010 | 0.00098 | 91.3% | 78.3% |
| SYMMETRIC | 0.01 | 0.05 | 0.000057 | 0.00579 | 100.0% | 95.7% |
| SYMMETRIC | 0.05 | 0.01 | 0.000018 | 0.00035 | 47.0% | 12.0% |
| SYMMETRIC | 0.05 | 0.02 | 0.000062 | 0.00123 | 83.8% | 70.1% |
| SYMMETRIC | 0.05 | 0.05 | 0.000346 | 0.00691 | 97.4% | 97.4% |
| SYMMETRIC | 0.1 | 0.01 | 0.000030 | 0.00030 | 55.1% | 10.3% |
| SYMMETRIC | 0.1 | 0.02 | 0.000113 | 0.00113 | 80.8% | 69.7% |
| SYMMETRIC | 0.1 | 0.05 | 0.000708 | 0.00707 | 95.7% | 94.4% |
| SYMMETRIC | 0.2 | 0.01 | 0.000060 | 0.00030 | 49.9% | 9.2% |
| SYMMETRIC | 0.2 | 0.02 | 0.000237 | 0.00119 | 79.2% | 65.1% |
| SYMMETRIC | 0.2 | 0.05 | 0.001347 | 0.00674 | 94.9% | 93.6% |
| FAVOURITE | 0.01 | 0.01 | 0.000003 | 0.00029 | 52.2% | 13.0% |
| FAVOURITE | 0.01 | 0.02 | 0.000010 | 0.00105 | 87.0% | 87.0% |
| FAVOURITE | 0.01 | 0.05 | 0.000065 | 0.00656 | 91.3% | 91.3% |
| FAVOURITE | 0.05 | 0.01 | 0.000014 | 0.00028 | 54.7% | 13.7% |
| FAVOURITE | 0.05 | 0.02 | 0.000059 | 0.00118 | 86.3% | 74.4% |
| FAVOURITE | 0.05 | 0.05 | 0.000346 | 0.00690 | 95.7% | 95.7% |
| FAVOURITE | 0.1 | 0.01 | 0.000029 | 0.00029 | 65.8% | 15.0% |
| FAVOURITE | 0.1 | 0.02 | 0.000108 | 0.00108 | 86.8% | 73.1% |
| FAVOURITE | 0.1 | 0.05 | 0.000679 | 0.00678 | 97.0% | 97.0% |
| FAVOURITE | 0.2 | 0.01 | 0.000060 | 0.00030 | 62.1% | 15.4% |
| FAVOURITE | 0.2 | 0.02 | 0.000235 | 0.00117 | 88.2% | 77.9% |
| FAVOURITE | 0.2 | 0.05 | 0.001408 | 0.00704 | 96.4% | 96.1% |
| UNDERDOG | 0.01 | 0.01 | 0.000002 | 0.00024 | 30.4% | 4.3% |
| UNDERDOG | 0.01 | 0.02 | 0.000011 | 0.00115 | 69.6% | 65.2% |
| UNDERDOG | 0.01 | 0.05 | 0.000062 | 0.00625 | 100.0% | 100.0% |
| UNDERDOG | 0.05 | 0.01 | 0.000016 | 0.00032 | 34.2% | 2.6% |
| UNDERDOG | 0.05 | 0.02 | 0.000058 | 0.00116 | 77.8% | 61.5% |
| UNDERDOG | 0.05 | 0.05 | 0.000330 | 0.00658 | 92.3% | 91.5% |
| UNDERDOG | 0.1 | 0.01 | 0.000035 | 0.00034 | 40.6% | 4.7% |
| UNDERDOG | 0.1 | 0.02 | 0.000111 | 0.00110 | 73.9% | 61.1% |
| UNDERDOG | 0.1 | 0.05 | 0.000787 | 0.00786 | 94.9% | 93.2% |
| UNDERDOG | 0.2 | 0.01 | 0.000068 | 0.00034 | 42.8% | 5.1% |
| UNDERDOG | 0.2 | 0.02 | 0.000240 | 0.00120 | 78.8% | 63.8% |
| UNDERDOG | 0.2 | 0.05 | 0.001458 | 0.00730 | 95.9% | 95.1% |

## Favourite-band sensitivity (SYMMETRIC, f=0.10, dp=0.02)

| p_fav band | n affected | mean KL (nats) | clear c=2% |
|---|--:|--:|--:|
| [0.5,0.6) | 76 | 0.000814 | 82.9% |
| [0.6,0.75) | 95 | 0.000922 | 85.3% |
| [0.75,0.9) | 51 | 0.001471 | 78.4% |
| [0.9,1.0) | 12 | 0.003308 | 41.7% |

## Candidate δ values (units: mean per-match log-score improvement, nats)

Drawn directly from the scenario grid — the founder chooses; none is recommended
because of any real result (none exists):

- **δ = 1e-4** ≈ 'a 2-point probability error on ~10% of matches' — plausible-shaped,
  mostly cost-clearing where it occurs (~81% at c=2%), but requires N ≈ 190k–290k
  matches (Packet B) — beyond any affordable horizon at ~2.9k matches/month.
- **δ = 2.5e-4** ≈ '2-point error on ~20%' — N ≈ 89k–137k. Still years of data.
- **δ = 7e-4** ≈ '5-point error on ~10%' — N ≈ 27k–42k; ~1–1.5 years of comparable
  months. The smallest δ with a describable programme horizon.
- **δ = 1.3e-3** ≈ '5-point error on ~20%' — N ≈ 15k–23k; ~6–9 months. Large,
  detectable, and (best-case) 94%+ cost-clearing where it occurs.

Interpretation: a DIFFUSE small edge (1-point shifts) is statistically invisible at
any affordable N and mostly cannot clear 5% commission even best-case; only
CONCENTRATED (≥2-point) and reasonably COMMON (≥10%) residual information is both
actionable and provable. Choosing δ is therefore choosing the smallest edge the
programme considers worth being able to detect — smaller real edges will be
declared futile by design, honestly.
