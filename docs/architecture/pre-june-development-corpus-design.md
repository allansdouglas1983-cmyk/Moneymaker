# Pre-June development-corpus design (PROPOSAL — founder ratifies at F2 registration)

**Basis:** the governed acceptance audit (vintage-2026-07-18; 117,276 pre-June singles
matches: ATP 70,631 / WTA 46,645). Outcome-aware and time-respecting; every boundary
ends before **2026-06-01**. June 2026 remains the fully sealed lockbox (2,876 primary /
2,287 strict; no June outcome access, training, calibration, or feature selection).
Proposed numeric choices below are PROPOSALS: they bind only when copied into the F2
trial registration and ratified.

| Element | Proposal | Rationale (audit-grounded, outcome-blind) |
|---|---|---|
| Elo warm-up | ATP 2000-01→2020-12; WTA 2007-01→2020-12 (ratings evolve, nothing scored) | deep convergence; absorbs era drift without scoring it |
| Development (fit/tune via crossfit) | 2021-01→2025-08 (~12.2k ATP + 11.4k WTA matches) | recent regime; large enough for UTC-day-clustered folds |
| Validation (held-in, pre-registered checks) | 2025-09→2026-05-31 (~2.9k+2.7k matches) | strictly after development; ends at the boundary |
| Chronological blocks | UTC-day clusters (the declared tennis correlation-cluster key), strictly ordered folds (SPEC-031) | matches platform crossfit machinery |
| Tour policy | SEPARATE ratings per tour (td-atp / td-wta); no pooling in v1 | identity namespaces are distinct; pooling is a governed change with its own evidence |
| Surface policy | F2 ignores surface; F3 conditions on the validated Surface field (zero missingness) | field registry v1 |
| Label policy | valid outcomes = COMPLETED, RETIRED, AWARDED, DISQUALIFIED (winner declared); EXCLUDED with reasons = WALKOVER (691), ABANDONED, SCHEDULED (1), AMBIGUOUS (3) | walkovers contain no play signal; retirements are contested play with a declared winner — kept, and flagged for an F2 sensitivity split |
| Duplicates/conflicts | exact dupes: keep-first (0 found); pair-day-tournament dupes with agreeing winners: dedupe to one (2 keys); CONFLICTING winners: exclude both rows (1 record — 2000 Masters Cup RR artefact) | audit policy, frozen |
| Minimum prior-match rule | a player enters scored evaluation only with ≥ 10 prior corpus matches; otherwise the match is an explicit abstention | cold-start honesty; threshold ratified at registration |
| New-player initialisation | namespace-mean initial rating; provisional until the prior-match minimum is met | standard, deterministic |
| Identity coverage | F2 fits on Tennis-Data-internal identities (no Betfair join needed for training); at any future June evaluation, only both-players-mapped markets are evaluable (currently 1,218/2,876 = 42.4%; strict 50.5%) and unmapped markets stay in the denominator as explicit abstentions (SPEC-038) | bridge report; coverage threshold for gate evaluation is a founder call at registration |

Registered via the existing `weighted-elo` template with `PreRegisteredEndpoints` once
δ / σ_d are declared; the crossfit orchestrator (A5 seam) owns folds and OOF
production; the same chronology, identity universe, scoring, calibration and exclusion
accounting then serve F3 unchanged.
