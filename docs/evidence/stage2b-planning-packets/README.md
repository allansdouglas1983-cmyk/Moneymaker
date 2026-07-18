# Stage-2B planning packets (outcome-blind) — FROZEN 2026-07-18

Founder-commissioned evidence packets supporting the three still-pending declarations
(δ, σ_d, dwell W). Everything here is OUTCOME-BLIND: inputs are the frozen Stage-1
reconstruction (first-instance T-5m two-sided books), Stage-1 schedule/timing metadata,
declared commission scenarios, and SEEDED synthetic winners drawn from the market
probability. **No real outcome, winner, settlement or June-lockbox field was read.**
Scripts are archival records (excluded from lint/type-check like all docs/evidence).

| Artefact | sha256 |
|---|---|
| packet_a.json | 3f425c33f8033834fef727b029838c2d59bf02176fc50d2e95dcae270267be54 |
| packet_b.json | 89b32475817b89adf996d0df439cf4488418d99b6bc393560deb117652682e3f |
| packet_c.json | 7fce303e97f9f8f0461b1feb6a296ca367256abfba7afcb13c56f785a7619e72 |
| packet_a.md | 10b9da30a2d180367896e37ed7f3f6f07a44965828ee487c6cf6e23a399c1bd4 |
| packet_b.md | 4f79d10951e571d782bfbac612bafc76ca59a587050cfce04374ad062cfc24bb |
| packet_c.md | d04369059e114711ad1eac548a3ab58ed1561d2e4a9975a11fe3518148d8a8e9 |

Regeneration: `python3 scripts/packet_ab.py && python3 scripts/packet_c.py &&
python3 scripts/render_summaries.py` from the repo root with the Stage-1 scratchpad
data present (paths in the scripts; deterministic seeds `stage2b-packets:20260718`).

Headline findings (details in the packets):
- **A:** diffuse 1-point mispricing is both statistically invisible and mostly unable to
  clear 5% commission even best-case; candidate δ ∈ {1e-4, 2.5e-4, 7e-4, 1.3e-3} nats
  with explicit interpretations; only concentrated ≥2-point signal on ≥10% of matches is
  simultaneously actionable and provable.
- **B:** conservative planning σ_d (predeclared p90) = 0.04075; per-scenario N table at
  power 0.80, family-wise α=0.05 (K=1 and K=6): N ranges ~15k (large-common signal) to
  millions (small-rare). σ_d is a planning ASSUMPTION.
- **C:** dwell W∈{15..120}s is operationally indistinguishable; L dominates availability
  (89→95%); ~82–88% of committed decisions see a LATER marketTime revision at every
  (W,L) — post-decision revision is structural, so the real open policy question is the
  governed response to it (re-decide vs hold), decided outcome-blind by the founder.
