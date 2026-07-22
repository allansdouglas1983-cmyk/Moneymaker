# DR-TENNIS-XMARKET-MATH-001 — findings (accepted as implementation-specification input)

**Status:** ACCEPTED AS IMPLEMENTATION-SPECIFICATION INPUT, subject to the binding
corrections in STAGE3-0005 §2. Findings inform the implementation; they never prove a gate
(Amendment A §4). **Research date accepted:** 2026-07-22.

**Blocker:** `EXT-XMARKET-003` → `SPECIFICATION_ACCEPTED_IMPLEMENTATION_VALIDATION`
(`specs/programme/xmarket-blockers.yaml`).

## Source hierarchy

External founder-run Deep Research on point→game→set→match tennis scoring mathematics
(Newton/O'Malley/Barnett-style recursions). Standard, well-established scoring probability
theory; not a novel claim. Used only to structure a synthetic, independently-verified engine.

## Accepted mathematical conclusions (used only synthetically)

- A game/tiebreak/set/match probability surface can be computed from two per-player
  serve-point-win probabilities `p_A`, `p_B` plus an explicit match format.
- Total-games and game-margin distributions follow deterministically from the set/match model.
- Match Odds + one Total Games line give two observations for the two latent serve
  parameters — an **identification** problem, not a coherence proof (see §2.2 correction).

## Assumptions (recorded, not asserted as true of any real match)

- i.i.d. serve-point model per player within the format (standard simplification).
- Format is KNOWN independently of the priced markets (§2.1 correction).

## Binding corrections applied (STAGE3-0005 §2)

1. **§2.1 Format independently known** — format is NEVER inferred from Total Games/Handicap
   prices, fitted parameters, realized games, score, or result. It comes from independently
   lawful pre-match evidence (format-evidence policy tiers A/B/C).
2. **§2.2 Identification ≠ coherence** — MO + one selected Total Games line is used for
   identification; every other Total Games line and every Game Handicap line is reserved as
   an OUT-OF-FIT holdout coherence observation.
3. **§2.3 One fitting definition** — V1 identification target: frozen `p_market_info` +
   normalized-midpoint probability of ONE deterministically selected Total Games Over line;
   a deterministic bounded 2-D root solve; back/lay intervals + one-tick perturbations used
   only for the identification envelope/sensitivity, never mixed into the fit objective.
4. **§2.4 First server is a nuisance parameter** — no 50/50 prior; compute A-serves-first
   and B-serves-first separately, carry the union; a materially different result →
   `FIRST_SERVER_SENSITIVE_PENDING_THRESHOLD` (numeric threshold pending founder).
5. **§2.5 Independent verification mandatory** — a production generator (deterministic
   DP/state-machine) AND a differently-structured test-only reference generator must AGREE
   over a governed grid; any discrepancy is `STOP_MATH_INTEGRITY`.

## Unsupported claims (rejected)

- No claim that derivative prices are independent information (EXT-XMARKET-002 stands).
- No claim of a model edge, price discovery, or a coherence-based tip/EV.
- No default-to-best-of-three; unknown/unsupported formats refuse.

## Unresolved facts

- Numeric first-server materiality threshold — pending founder.
- Final parameter domain — synthetic candidate domains tested; not frozen.
- Coherence categorical thresholds (COHERENT/INCOHERENT) — not frozen; only structural
  statuses + raw metrics permitted in this slice.
- Match-tiebreak settlement-counting for total-games — verified synthetically before use.

## Implementation consequences

- Synthetic-only engine authorised (`sport_tennis/coherence/`), quarantined from real market
  ingestion, V0, pricing and tipping; no outcomes; no threshold selection.
- Registration: `specs/programme/cross-market-coherence-v1.yaml`.
- No real June run until the promoted-plumbing mutation packet is founder-adjudicated.

## Evidence role

Implementation-specification input only. It authorises a synthetic build + validation; it
does not prove EXT-XMARKET-003 resolved, does not authorise a real-data run, and never
proves a gate.
