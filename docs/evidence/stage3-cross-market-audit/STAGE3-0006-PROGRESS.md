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

## Remaining before the coherence gate is closed
- Full mutation + packets for the other six coherence modules: `formats.py`,
  `format_evidence.py`, `pmf.py`, `match.py`, `solver.py`, `holdout.py` (§4/§7).
- Consolidated `MUTATION_SURVIVOR_PACKET_COHERENCE_V1_FINAL` across all seven modules (§10).

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
