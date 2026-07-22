# STAGE3-0006 — Progress record (both mutation gates)

Authority: founder directive STAGE3-0006 (durable copy: `specs/programme/stage3-0006-directive.md`).
Branch: `claude/project-files-followup-dif8al`. **Neither gate is closed; nothing is exposed; no
June run; no outcomes; `p_market_info`/V0 unchanged; £0; `approved_by: null` throughout.**

## Workstream B — synthetic coherence engine

### §5 behavioural hardening (tests-first, committed)
| § | Change | Kills |
|---|--------|-------|
| 5.1 | immutability contract guards | `frozen=True→False` (all result types) |
| 5.2 | `check_normalized` (math.isfinite + exact tol) | NaN-accepting / tolerance-weakening |
| 5.3 | `FinalSetRule` enum + resolver seams | identity / lexicographic / foreign-string |
| 5.4/5.5/5.10 | tiebreak service seams + guarded deuce-tail resolver | serve / parity / n0 / eps |
| 5.7 | pure terminal predicates + exhaustive truth tables | operator substitutions |
| 5.8/5.9 | set-level completeness seam + parity seam | `continue→break`, parity flips |
| 5.6 | independent reachable-state enumerator + boundedness proof | backs unreachable-domain class |
| 6 | production/reference independence architecture test | keeps 1e-9 agreement independent |
| 8/9 | dead-code simplification, point-win seam, signature tests | 13 dead `7-5` + serve-flip + `*`→`/` |

### §10 scoring.py packet (EXACT, committed)
- `scoring.py`: **1020 mutants, 987 killed, 33 survived — 96.76%** (from 136 survivors / 86.9%
  at STAGE3-0005; the 80 previously-"unproven" DP-arithmetic survivors are eliminated).
- Packet: `MUTATION_SURVIVOR_PACKET_COHERENCE_SCORING_V1.json` (33 entries, 21 fields, approved_by
  null), `..._CLASS_INDEX_..._V1.md`, `..._RECONCILIATION_..._V1.json`
  (**missing=extra=duplicate=stale=unclassified=0**).
- 10 exact proof classes: float-tolerance-boundary (1), serve-order-redundant/parity (6),
  tail-n0-period4 (6), float-eps-boundary (1), CPython-small-int-identity **[ENV-BOUND, reclassify
  off CPython]** (3), redundant-guard (2), parity-identity (3), serve-schedule-flip-win-prob-
  invariant (2), accumulator-fresh-get-key (8), no-tie-in-terminal-scores (1).
- Two classes (serve-schedule-flip, accumulator-fresh-get-key; 10 mutants) are win-prob-invariant
  path mutants that are additionally KILLABLE by a pinned point-number seam / direct assignment —
  offered to the founder; classified as proven-equivalent for now.

### §4/§7 formats.py packet (EXACT, committed)
- `formats.py`: **3 survivors** — all genuine equivalents. Classes: `ENUM_MEMBER_IDENTITY_EQUIVALENT`
  (`is`↔`==` on FinalSetRule singletons; 2), `GUARD_OR_AND_FALLTHROUGH_EQUIVALENT`
  (classify_format_token guard `or`→`and` with identical FORMAT_UNRESOLVED fall-through; 1).
- Packet/index/reconciliation `..._COHERENCE_FORMATS_V1.*` (missing=extra=duplicate=stale=unclassified=0).

### §4/§7/§12 format_evidence.py packet (EXACT, committed) — kill-refactor
- Applied the §12 preference (**kill, don't hand-wave**): source-simplified to a length-status
  dict lookup, replaced the ordered/`!=` status branch with positive `in _SUPPORTED_FORMAT_VALUES`
  membership, and replaced `len(...)==1` with truthiness; added 4 adversarial tests
  (unsupported-alongside-real-format, tier-A unknown token, length-token-on-non-tier-C,
  non-interned tier string). **13 survivors → 3.**
- The 3 residuals have complete proofs (not interplay): `BOUNDED_TOTAL_ORDER_MAX_EQUIVALENT`
  (`>=` vs `==` where the RHS constant is the lexicographic maximum of the exact reachable set —
  `{UNSUPPORTED_FORMAT, FORMAT_UNRESOLVED}` at L108, `{A,B,C}` at L121; 2) and
  `INTERNED_SINGLETON_IDENTITY_EQUIVALENT` (`is` vs `==` on the interned `UNSUPPORTED_FORMAT`
  constant returned by identity; 1).
- Packet/index/reconciliation `..._COHERENCE_FORMAT_EVIDENCE_V1.*` (all-zero).

## Remaining before the coherence gate is closed
- Full mutation + packets for the last four coherence modules: `pmf.py`, `match.py`, `solver.py`,
  `holdout.py` (§4/§7) — mutation IN PROGRESS this pass (fast BO3 exact-reference + property/
  refusal test subsets built so each mutant runs in seconds rather than the un-memoised BO5
  reference's minutes).
- Consolidated `MUTATION_SURVIVOR_PACKET_COHERENCE_V1_FINAL` across all seven modules (§10) —
  merger tool `tools/consolidate_coherence_packet.py` delivered.

## Workstream A — promoted xmarket contracts/plumbing
- NOT STARTED this pass. State unchanged from STAGE3-0004
  (`specs/mutation-survivors-xmarket-contracts.yaml`: 588 mutants, 66 PEP-563-equivalent,
  120 non-annotation pending). §8 behavioural kills, §9 66-annotation exact IDs, and the §11
  final xmarket packet remain.

## Tooling delivered
- `tools/build_mutation_packet.py` (21-field packet + class index + reconciliation).
- `tools/extract_mutation_survivors.py`, `tests/unit/coherence/reachability.py`.

## Honest status
The behavioural-kill work (the hard part) and the reachability/independence proofs are done for
the coherence engine, and the worst module (scoring.py) is near-closed with an exact one-to-one
packet. The remaining work is per-module mutation packaging (6 coherence modules) and the entire
xmarket workstream. This is a multi-session effort at the exactness bar set by STAGE3-0006. Both
gates remain OPEN and held for founder adjudication; no June diagnostic will run until both are
closed and the founder authorises.
