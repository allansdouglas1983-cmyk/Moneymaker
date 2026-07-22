# FOUNDER DIRECTIVE — STAGE3-0006 (durable copy)
# CLOSE BOTH CROSS-MARKET MUTATION GATES BEFORE ANY REAL JUNE RUN

Status: ACTIVE
Authority: Founder
Recorded: 2026-07-22
Branch: claude/project-files-followup-dif8al

STAGE3-0005 is accepted as a successful **quarantined engineering slice**, NOT as a closed
mutation gate. **No mutation survivor is founder-approved.** `approved_by` remains null through
all of STAGE3-0006.

## Standing constraints (unchanged, in force)
- coherence engine is synthetic-only; import-quarantined;
- NO real June coherence run; NO outcome read; `p_market_info` authoritative;
- PERSONAL_TENNIS_ASSISTANT_V0 unchanged; no tip/edge/EV/ROI/P&L/CLV/stake/order/execution;
- £0 budget freeze.

## Two required workstreams (both must be founder-adjudicated before June)
- **A.** close the promoted xmarket-contract/plumbing mutation gate (STAGED_NOT_APPROVED);
- **B.** close the full synthetic coherence-engine mutation gate (SYNTHETIC_QUARANTINED_GATE_OPEN).

## No blanket equivalence approval (§2)
An equivalence proposal must tie to an EXACT mutation and one of:
1. complete reachable-state proof;
2. algebraic identity over the registered domain;
3. exact byte-identical contract behaviour;
4. environment-bound identity with explicit environment reclassification;
5. runtime-inert postponed annotation with architecture proof.
NOT acceptable as justification: normal tests pass; finite-grid agreement; believed-unreachable;
small operands; unchanged scalar summary; synthetic-only.

## Priority order (§3)
1. red-test + refactor the clearly behavioural coherence survivors (§5.1–§5.10);
2. full advice-critical mutation scope over EVERY coherence module (§4/§7);
3. complete + harden the xmarket contracts gate (§8/§9);
4. generate exact reconciled packets for both gates (§10/§11);
5. STOP for founder adjudication. Do not run June because one gate finished first.

## Coherence full scope (§4)
formats.py, format_evidence.py, scoring.py, match.py, pmf.py, solver.py, holdout.py — separate
focused mutation configs per module where needed; each config runs all tests that can
distinguish that module. Do not call a scoring-only fast subset the full gate.

## Required coherence refactors/kills (§5) — tests-first
- 5.1 immutable result contracts: frozen=True→False is behavioural; test FrozenInstanceError,
  alias-can't-mutate-PMF, digest/serialization stable; KILL.
- 5.2 normalization guards: pure predicate/validator; pin nextafter(tol,±inf), exact tol,
  normalized, non-normalized, NaN, ±inf; typed refusal before returning a PMF; don't weaken tol.
- 5.3 final-set rule identity: replace string with governed enum; pin members/foreign/raw/None/
  unsupported refusal; KILL identity/lexicographic/foreign-accept mutants.
- 5.4 tiebreak service sequence: pure seam; pin server for points 1..≥40, both first servers,
  7- and 10-point, the two points after each deuce-tail entry; refuse index≤0/non-int; KILL
  point-1 branch, pair/parity arithmetic, inversion, n0, n0+1, recursion counter.
- 5.5 remove artificial tiebreak-tail mutation sites: explicit pure helper returning the tail
  server pair; pin target 7/10 × both first servers; eliminate redundant arithmetic.
- 5.6 bounded reachable-state DPs: explicit bounded pre-tail state spaces (game/tiebreak/set);
  independent reachability enumerator; report reachable/terminal/unreachable per format.
- 5.7 terminal predicates: pure predicates + exhaustive truth tables over the bounded domain;
  KILL operator substitutions.
- 5.8 continue-vs-break + map accumulation: fixture with 6-6 AND another live state at the same
  DP level; prove all contribute; pin every terminal cell.
- 5.9 game-number/service parity: exhaustive reachable-score truth table; KILL a+b+1 / +→- / XOR
  / parity / orientation mutants.
- 5.10 epsilon fallback: (A) prove denominator strictly positive over open domain, remove branch,
  pin proof boundaries; OR (B) keep and kill negative-eps/altered-comparison/denominator/value.

## Production/reference independence (§6)
Audit shared deps; reference must not import production helpers for server order, terminal
detection, line interpretation, push semantics, PMF normalization, format branching. Architecture
test proving independence. For every production mutation the reference path stays unchanged.

## Full coherence mutation test matrix (§7)
full set-PMF, match-PMF, total-games PMF, margin PMF agreement; Over/Under integer+half; push
mass; handicap cover; player swap; both first servers; every format; asymmetric + near-boundary
serve p; solver no-root/multi-root/mirror fixtures; holdout non-fitting; format-evidence
refusals; immutable output contracts. Targeted per-module tests to bound runtime.

## xmarket hardening (§8/§9)
Kill every non-annotation survivor changing governed behaviour (marketType preservation;
Total/Handicap/Set classification; line sign/orientation; runner identity; linkage; dup/relist;
F0 cutoff inclusion/exclusion; quote age; suspension; in-play; one-sided; crossed; refusal
reason; provenance; immutable field; serialization; digest; unsupported cohort; outcome-field
prohibition; probability/tip-field prohibition). Simplify source to remove ambiguous dead
branches. The 66 annotation mutants: one exact class ONLY with the architecture proof per module;
return exact 66 IDs; signature (kw-only/positional-only) changes are behavioural — KILL/prove.

## Packets (§10/§11)
COHERENCE: MUTATION_SURVIVOR_PACKET_COHERENCE_V1_FINAL.json (one entry/mutant, 21 fields incl.
approved_by:null), MUTATION_SURVIVOR_CLASS_INDEX_COHERENCE_V1_FINAL.md,
MUTATION_RECONCILIATION_COHERENCE_V1_FINAL.json (missing=extra=duplicate=stale=0).
XMARKET: MUTATION_SURVIVOR_PACKET_XMARKET_CONTRACTS_FINAL_V1.json, ..._CLASS_INDEX_..._FINAL_V1.md,
..._RECONCILIATION_..._FINAL_V1.json. Same reconciliation rules. No blanket approval; approved_by null.

## Target end state (§12)
Both gates: all behavioural survivors killed; remaining survivors exact proposed equivalents;
unexplained=0; exact one-to-one packet. No broad unproven arithmetic class. Prefer fewer
survivors with stronger evidence over a higher cosmetic %.

## Verification (§13)
full unit/property/stateful/agreement/replay/failure-injection; every import quarantine; ruff;
pylint; mypy --strict; full make verify. Record exact runtime env; env-bound survivors need
implementation+version+env-digest+reclassification rule.

## Still prohibited (§14)
No real June run; no outcome read; no domain/coherence thresholds from June; no xmarket exposure;
no V0 integration; no p_market_info change; no tip/EV/ROI/P&L/CLV/stake/order; £0.

## Required return (§15): 25 items — closure record; xmarket totals/count/packet+index+recon
digests; coherence totals/count/packet+index+recon digests; killed/refactored count of the
previous 80 unproven; remaining proposed-equivalent classes; prod/ref independence audit;
reachable-state proof artifacts; annotation proof; unexplained per gate; behavioural per gate;
full verification; clean tree; six founder-visible files; no-June; no-outcome; p_market_info/V0
unchanged; no tip/EV/stake/order/paid. STOP for adjudication.
