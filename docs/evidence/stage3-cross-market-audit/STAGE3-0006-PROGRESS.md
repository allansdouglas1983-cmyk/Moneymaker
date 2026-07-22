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

### §4/§7 per-module packets — coherence engine (EXACT, committed)
| module | mutants | killed | survivors | rate | residual classes (all equivalents unless noted) |
|--------|--------:|-------:|----------:|-----:|--------------------------------------------------|
| scoring.py         | 1020 | 987 | 33 | 96.76% | 10 classes (float-tol, serve/parity, tail-n0, eps, small-int[env], guards, accumulator, no-tie) |
| formats.py         |  ~73 |  ~70 |  3 | ~95.9% | enum-singleton identity, guard or/and fall-through |
| format_evidence.py |   52 |   49 |  3 | 94.2%  | bounded-total-order-max, interned-singleton identity |
| pmf.py             |  139 |  139 |  0 | 100%   | — (fully closed) |
| match.py           |  302 |  292 | 10 | 96.69% | bounded-max ==/>=, small-int is[env], serve-flip, no-tie, mod-2 |
| holdout.py         |  232 |  222 | 10 | 95.69% | model-prob routing, interned identity, dead init, interval order-boundary no-ops |
| solver.py          | 1113 |  —  | —  | (mutation running — direct-unit harness makes it feasible) |

Each committed module packet reconciles missing=extra=duplicate=stale=unclassified=0. The
behavioural survivors flagged this pass were **killed**, not classified: pmf `_validate_line`
(round-down line), match keyword-only signature, the entire holdout diagnostic-metric surface
(82→10), and the three holdout refinements (interval Sub→Mod, two chained-comparison guards).

- Consolidated `MUTATION_SURVIVOR_PACKET_COHERENCE_V1_FINAL` across all seven modules (§10):
  pending solver only; merger `tools/consolidate_coherence_packet.py` delivered and used for the
  xmarket final.

## Workstream A — promoted xmarket contracts/plumbing (§8/§9/§11 — DONE this pass)
186 STAGE3-0004 survivors → **85** after the behavioural kills (69 worker-drafted + the lead
integrity kill + 5 lead synchronizer kills), reconciled EXACTLY:

| module | mutants | killed | survivors | annotation | non-annotation equiv |
|--------|--------:|-------:|----------:|-----------:|---------------------:|
| parsers.py      | 200 | 184 | 16 | 11 | 5 |
| linkage.py      | 104 |  89 | 15 | 11 | 4 |
| synchronizer.py | 254 | 200 | 54 | 44 | 10 |
| observation.py  |  30 |  30 |  0 |  0 | 0 |
| **total**       | 588 | 503 | **85** | **66** | 19 |

- **Integrity-critical kill (lead-verified):** `parse_game_handicap` L138 — the set-vs-game
  boundary was tested only at 3.0/3.5, so `<=`→`==` admitted a genuine set handicap (max 2.5).
  Added strictly-interior refusals. The prior YAML's "pinned and killed" claim was inaccurate.
- The **66 PEP-563 annotation-operator** mutants reconcile exactly (parsers 11, linkage 11,
  synchronizer 44) — ONE class with a per-module future-import architecture proof.
- 19 non-annotation equivalents: set A&B==A|B on equal sets; redundant len==2 guard; hc≥0⟺>0
  post zero-check; sorted-pair min ≤ == ==; self-sibling inert identity; _sole unreachable-at-1;
  dead _Slot default / inert dataclass; out-of-range negative sentinel; max-track no-op-at-=.
- `MUTATION_SURVIVOR_PACKET_XMARKET_CONTRACTS_V1_FINAL` (85 entries) + class index +
  reconciliation: missing=extra=duplicate=stale=unclassified=0; per-module reconciliations zero.

## Tooling delivered
- `tools/build_mutation_packet.py` (21-field packet + class index + reconciliation).
- `tools/consolidate_coherence_packet.py` (per-module → final packet merge with reconciliation).
- Fast mutation harness: `test_match_ref_bo3_fast.py`, `test_solver_mutation_fast.py`,
  `test_solver_units_fast.py`, `test_holdout_metrics.py`.

## Honest status
Workstream A (xmarket) is **closed to an exact one-to-one packet** — every behavioural survivor
killed, the 66 annotation mutants reconciled, 19 equivalents proved. Workstream B (coherence) is
closed for six of seven modules with exact packets (pmf fully at 100%); solver.py mutation is
running under the direct-unit harness (feasible in minutes) and its packet + the seven-module
`COHERENCE_V1_FINAL` are the only remaining build steps. No mutation survivor is approved
(`approved_by: null` throughout); both gates remain OPEN and held for founder adjudication; no
June diagnostic runs until the founder ratifies and authorises.
