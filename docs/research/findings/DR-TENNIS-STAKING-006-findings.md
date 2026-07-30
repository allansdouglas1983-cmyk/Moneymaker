# DR-TENNIS-STAKING-006 — the complete staking-systems study: 12 families surveyed, every formula adversarially verified, the matrix and the head-to-head protocol delivered

**Status:** ASSESSED. **Date:** 2026-07-30. **Run:** 28 agents (2 objective studies, 12
family surveys, 12 adversarial verifications, 2 syntheses), ~2.1M tokens, all agents
completed with results. **Deliverables archived verbatim alongside this file:**
`DR-TENNIS-STAKING-006-MATRIX.md` (the ranked candidate set and objective-by-rule
matrix) and `DR-TENNIS-STAKING-006-PROTOCOL.md` (STK-HARNESS-V1, the pre-registered
implementation spec for the empirical head-to-head).

Supersedes nothing; extends DR-TENNIS-STAKING-001–005 from "is Kelly right?" to the full
space the founder demanded: *"There are probably better ways to calculate stakes
depending on the goal instead of just looking at one… Trade results of each system and
results then allocation based on that."*

## Framing correction, recorded first

The research briefs stated "the edge is unproven, its sign is not established." Per
`docs/EVIDENCE-STATE.md` that framing was too strong: the forecast edge is positive,
replicated out-of-window, control-rejected and monotone; the genuinely open items are
the costed reading (TE-0020) and realised fills. The study's design absorbs the error —
its stress scenarios span as-measured/half/zero/negative regardless of what anyone
believes, and its admissibility gates bind on the adverse scenarios — but rankings in
the matrix that lean on "sign unknown" should be read with EVIDENCE-STATE alongside.

## The one result that governs everything else

For non-compounding rules replayed on one settled sequence, **every pairwise staking
comparison is the edge test rescaled downward**: t(A beats B) = t(edge≠0) × (mean
ΔS / rms ΔS) ≤ t(edge≠0), with effective sample sizes as low as 27 of the 4,153 bets for
genuinely different rules. While the costed edge reading is unresolved, **no
reward-metric ranking between staking rules is establishable at any confidence the edge
test itself fails.** What IS estimable now — because it depends on second-moment and
path structure, not the mean's sign — is the risk-shape matrix: drawdown, floor-breach,
silent-death and participation behaviour per rule per scenario. That is precisely "the
whole matrix" the founder asked for, and it stays valid whenever the edge question
resolves.

## The candidate set, after deduplication and adversarial verification

254 surveyed rules → 74 verified family entries → **45 canonical candidates + 7 retained
controls + 5 exclusions**. Kelly appeared under three names (it is the γ=1 CRRA member);
flat staking appeared in five disguises; a dozen risk-parity aliases collapsed to one
exponent. Every surviving formula was re-derived by an independent verifier; nine
verification corrections are load-bearing and written into the protocol (§8.4), and
four truncated entries are barred from implementation until re-emitted.

Highlights the head-to-head inherits:

- **The strongest guarantee in the whole set is edge-free**: B5 (Hsieh–Barmish drawdown
  cap) gives a probability-ONE maximum-drawdown bound needing no distribution, no
  i.i.d., no edge — stake ≤ W − (1−d_max)·HWM.
- **28 arms are operable right now** with no edge estimate: flat/shape rules, the CPPI/
  TIPP floor family, risk-statistic targeting, CVaR scale rules. Every one verified for
  edge-smuggled-through-constants.
- **Every Kelly/CRRA rule needs a signed edge**, and the measured cost of running one
  with the wrong sign is 100% ruin (0.6% with the right sign — the same rule). The one
  honestly-operable Kelly variant is D7 (Kelly at the conservative lower bound), which
  outputs f=0 today by construction — the formalisation of "not yet".
- **Two rules are dangerous impostors** and stay caged as controls: Bayes-CRRA and the
  squared-error Bayes estimator both emit positive stakes from a zero-spanning interval.
- **Five dominated rules were dropped before the study** (Merton diffusion vs the exact
  binary form; QRCK vs RCK; trigger-band CPPI; per-bet CVaR ≡ flat; the bank-divisor
  trap configuration), shrinking the multiplicity burden honestly.
- **Same-day cards**: per-bet Kelly-type rules silently overstake a correlated card;
  floor rules keep their guarantee only under day-level cushion reservation — coded as a
  constraint in the harness, not assumed.

## The protocol (STK-HARNESS-V1), in brief

Integer-pence, Decimal-only, deterministic (ledger hash + config hash → byte-identical
outputs). Morning-bank sizing with day-end settlement (the only knowledge-time-honest
choice); round-down-then-SKIP at the £1 floor (round-up would silently convert
probability-one floors into probability-<1 floors, hardest when the bank is low);
commission on net market winnings, rounded against the bettor. Stress scenarios shift
the mean by a win-payout haircut — never by inventing or flipping outcomes — at
as-measured/half/zero/sign-reversed, plus a one-adverse-tick physical variant.
Resampling: stationary bootstrap over whole UTC days, 10,000 draws, with the SAME
resampled path replayed through every rule so all comparisons are paired. Ruin has three
recorded definitions with fixed roles; the primary is the SPEC-060-shaped founder floor.

**Selection is pre-registered and Bonferroni-corrected by the true trial count**: a rule
is adoptable only if it (G1–G4) survives the zero- and negative-edge scenarios, doesn't
silently switch itself off, isn't clamp-distorted — and then beats flat £1 in the paired
sense at α/N. **The expected outcome is the null**, declared in advance: flat £1 retained
as the estimator-optimal incumbent, with the risk-shape matrix as the durable deliverable
and the staking decision deferred behind the edge-sign decision. A winner that only wins
when the edge is real is recorded as "an edge amplifier, not a staking improvement" and
not adopted.

## What the research could not establish

Ten items, recorded in the matrix §6 — chiefly: the edge question itself (untouched by
construction); the Baker–McHale shrinkage closed form (paper not obtained; fallback
declared); odds-mix-dependent constants that the harness must recompute from the
platform's actual price population; two ambiguous metric definitions frozen path-minimum
before use; and the pervasive finding that **a £100 bank with a £1 floor cannot express
most defensibly-conservative rules** — defensible CRRA γ, conservative E[MDD] targets
and attenuation schemes all land below the minimum stake. The comparison lattice is
coarse at short odds and every result must be stratified by odds band.

## Ledger

No SPEC-ID changes. No staking rule adopted, changed, or activated. SPEC-060/061 stand.
The head-to-head implementation (task #88) follows this protocol under the repo's
tests-first discipline; its config hash is committed before any replay output is seen.
