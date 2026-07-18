# Stage 2B proposals — F3 June surface, identity corrections, alpha consumption

**Status:** PROPOSED 2026-07-18 (Stage 2B §7–§9). Founder decides; nothing here is
implemented or activated.

## 1. F3 June-surface feasibility (§7)

June F3 eligibility is zero because Betfair June metadata carries no surface. Two
candidate routes were assessed:

**Option 1 — field-level safe extractor over Tennis-Data June rows (RECOMMENDED).**
The 2026 Tennis-Data files contain June rows with Tournament/Location/Date/Surface
columns alongside the outcome columns. Proposal: a column-projection extractor with a
structural allowlist — it may read ONLY {Date, Tournament, Location, Surface} plus the
two player-name cells **projected as an UNORDERED pair** (`frozenset({cell_W, cell_L})`
— column identity is destroyed at read time, so the winner/loser semantics of those
columns is structurally unrecoverable). Winner identity, scores, sets, comment and all
odds columns are refused by the allowlist (outcome-fields guard pattern). June markets
are matched to rows by (mapped player pair, date within ±1 day); ambiguity (no row, >1
row with conflicting surfaces) refuses with a typed reason; every mapping carries
row-level provenance. The June lockbox stays intact: the projection cannot express who
won, and no settlement-adjacent field is readable.

**Option 2 — governed tournament→surface registry.** Rejected as primary: Betfair June
metadata rarely carries a usable competition/tournament name (mostly null in this
corpus), so registry keying would itself need a name heuristic — exactly what the
founder prohibits. Retained as a fallback for markets Option 1 cannot match.

Not implemented until (a) founder approves this policy and (b) F2's first evaluation is
complete (Stage 2B §7).

## 2. Identity-correction report (§8)

The **54** homonym/ambiguity refusals (25 HOMONYM_MULTIPLE_BETFAIR, 22
HOMONYM_MULTIPLE_SOURCE, 7 CROSS_NAMESPACE_AMBIGUOUS) remain unresolved and visible.
Proposed governed path: per-case investigation using OUTCOME-BLIND corroborating
evidence only — tour membership, tournament-week coincidence between the player's
Tennis-Data appearances and the Betfair event dates, and (where decisive) official
name spellings — each resolution entered as an append-only `IdentityCorrection`
(subject, action, evidence, authorised_by=founder, rationale) via the existing bridge
machinery. No fuzzy matching alone; no guessed corrections; an uninvestigable case
stays refused. The **760** source-unmatched lower-tier players remain excluded and
visible; the provider scope is NOT broadened before F2 is understood.

## 3. Alpha-consumption map (§9 — before any F3-vs-F2 confirmatory evaluation)

`alpha_total = 0.05` family-wise, rationed by `spent = (1−confidence)·(prior_trials+1)`.
F0 and F1 consume none (yardstick and harness-proof). F2 is the registered baseline —
it makes no superiority claim and consumes none. Proposed confirmatory plan
(exhausts the budget at exactly two trials; any third requires a new programme
registration):

| Trial | Comparison | Confidence | Spent (cumulative) | Power at δ=0.0007, σ_d=0.04075 |
|---|---|---|---|---|
| 1 | F3-vs-F2 (pre-June model-vs-model, Design B evaluation set 34,046) | 0.975 | 0.025 | N required 32,212 ≤ 34,046 → **adequately powered** |
| 2 | p_combined-vs-p_market (June M2, F2-eligible 1,218) | 0.975 | 0.050 (exhausted) | grossly underpowered → **CONTINUE/INCONCLUSIVE by design**; recorded, never inflated |

Consequence accepted in advance: F4+ families get NO confirmatory alpha under this
registration — they are exploratory unless a future founder decision re-registers the
programme (with the multiplicity cost that entails). The first objective remains a
clean F2 baseline; F3 earns its confirmatory slot only on F2's evidence.
