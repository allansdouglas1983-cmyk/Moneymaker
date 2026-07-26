# STAGE3-0006C-D-REV2 — Milestone D stop record

**Verdict: `STOP_REFERENCE_DISAGREEMENT`** (mandated by §17/§22; stopped immediately on the
first production/reference disagreement; production was NOT changed to match the reference).

## What completed before the stop

- **§4 freeze**: `SOLVER_MILESTONE_D_V2_PRECHANGE.json` (`sha256:22235f47…`, commit `492bf95`).
- **§5 red tests**: commit `49aedc0` (confirmed red).
- **§6–§16 extraction + wiring**: commit `f2791dd` — `rootset.py` (RootCandidate helpers bound to
  the governing fingerprint; direct-nearness bound to `root_dedup.have_edge`; mirror
  coordinate/relationship diagnostics, internal-only; the frozen boundary seam; exhaustive
  per-solve and identify-level status decision tables; immutable `RootSet` wrapping the
  amendment result verbatim) and `solver.py` wired through the boundary seam and both
  classifiers. **V2 golden 3/3 byte-identical post-wiring** (§18 differential
  `SOLVER_MILESTONE_D_V2_DIFFERENTIAL.json`: expected changes 0, observed 0). 165 fast/dedup/
  contract tests green; ruff / mypy (`--strict` on the new module) / pylint clean.
  `root_dedup.py` untouched.
- **§17 architecture boundary**: the independent reference solver imports only the scoring
  generator and format contract (AST-enforced); dedup-level agreement suites pass.
- **§17 end-to-end comparisons run before the stop** (`SOLVER_MILESTONE_D_REFERENCE_REPORT.json`,
  `sha256:b8ab478e…`): `unique_interior_root` AGREE (IDENTIFIED, locations within 1e-3);
  `no_root` AGREE; `mirror_pair_multiple_roots` AGREE (IDENTIFIED). All candidate-level
  comparisons (unrelated roots, close cluster, chain, both-first-server, permutations) AGREE
  including exact diameters and membership.

## The disagreement (§17 fixture 4: `mirror_fixed_point`)

Targets generated from the symmetric pair (0.5, 0.5) — `tw = 0.5`, `to ≈ 0.5519` — on domain
(0.35, 0.90):

| solver | status | roots |
|--------|--------|-------|
| production (amended V2) | `MULTIPLE_ROOTS` | (0.496260, 0.496260) · (0.499674, 0.499674) · (0.504340, 0.504340) |
| independent reference | `NON_IDENTIFIABLE` | (0.500000, 0.500000) |

Production's own per-root evidence: residuals 4.3e-5 / 3.3e-7 / 5.8e-5 (all inside the 1e-4
acceptance) and Jacobian determinants **−0.1239 / −0.0108 / +0.1438 — the determinant changes
sign across the valley**, i.e. a true Jacobian singularity sits near the centre root. The
sub-tolerance acceptance region is an elongated diagonal segment; production's seed layout
samples it at three points pairwise ≥ 1e-3 apart, and the frozen per-solve precedence
(multiplicity is decided BEFORE the singularity check) yields `MULTIPLE_ROOTS`. The reference's
refinement collapses the same valley to its deepest point and its literal singularity rule
classifies `NON_IDENTIFIABLE`.

**The structural finding:** on near-singular systems whose sub-tolerance region is an extended
valley rather than a point, the amended solver's public root COUNT (and therefore its status:
`MULTIPLE_ROOTS` vs `NON_IDENTIFIABLE`) is **discretization-defined** — an artifact of the seed
layout and refinement depth, not a set-defined property of the mathematical system. This is the
same class of contract gap as the dedup sequence-dependence corrected by amendment A1, now one
level up: the CANDIDATE SET itself is discretization-defined on degenerate systems. Neither
output is "wrong" under its own rules; they disagree because the underlying quantity is not
well-defined at this tolerance.

Per §17 ("Any disagreement is STOP_REFERENCE_DISAGREEMENT. Do not change production to match a
newly written reference without founder review") and §22 ("Stop immediately on: reference
disagreement"), Milestone D halts here. No correction was improvised; no fixture was dropped to
make the comparison pass; production and V2 remain exactly as committed.

## Not reached (stopped)

§17 fixtures 5–9 (singular_flat, nearly_singular, saturated, boundary_edge_root,
b_first_generated_targets — parts 0–3 preserved in `scratch_d_ref_parts/`); §19 mutation
micro-gates; §20 mutation consolidation/class-index/reconciliation; §21 full targeted
verification sweep beyond what is recorded above.

## Decision required from the founder

How the root-multiplicity-versus-degeneracy question should be adjudicated on extended
sub-tolerance valleys, e.g. (options, none executed):
(a) accept the frozen production semantics as the registered contract and re-scope the reference
comparison to non-degenerate fixtures with the degenerate class documented as known
discretization-defined behaviour;
(b) a governed amendment making valley-degeneracy detection explicit (e.g. Jacobian sign-change
or collinearity evidence across the accepted candidates escalating to NON_IDENTIFIABLE before
the multiplicity count) — a public-behaviour change requiring the full amendment protocol;
(c) another rule you specify.
Milestone D resumes only after that adjudication.

## Constraint confirmations

Working tree clean; nothing running; `root_dedup.py`, `rank_seed_nodes`, Milestones A–C
unchanged except the governed V2 wiring; all survivors remain `approved_by: null`; xmarket
unchanged; no June run; no outcome read; `p_market_info`/V0 unchanged; no tip/EV/stake/order;
£0 spend.
