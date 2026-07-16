# Betfair Racing Research Platform

Research and measurement platform. **Not a betting bot.** It may become one only if
the evidence supports it. Full spec: `docs/SPECIFICATION.md`. Authoritative requirement
list: @docs/spec-manifest.yaml

## The three rules

1. **Never stub, placeholder, or simplify anything in `l4b_fill/`, `l5_decision/`,
   `l5b_risk/`, `l6_broker/`, `l7_settle/`, `l8_evidence/gates/`.** If you cannot
   implement a SPEC-ID fully, STOP and report which one is blocked and why. Do not
   ship a lesser version. A missing feature is recoverable; a silently degraded one
   corrupts every conclusion drawn after it.

2. **Never weaken, delete, or alter a test to make an implementation pass.** If a test
   looks wrong, STOP. A test correction is a separate, human-approved PR that cites the
   SPEC-ID and explains the error. Never in the same change as the implementation.

3. **An LLM never estimates a probability, prices a bet, or sizes a stake.** Not as a
   fallback, not temporarily. All numerical decisions come from deterministic tested code.

## Expected outcome

Most likely there is **no exploitable edge**. The platform's job is to establish that
cheaply and honestly. The first several models are expected to fail their gates — that
is the system working. **Treat every surprisingly good backtest as a suspected bug.**

## Hard prohibitions

- No in-play. Pre-off only. `marketVersion` guard on every order.
- No lay betting, no hedging, no green-up. Back only, hold to settlement.
- One runner per market. Commission is charged on the **net market result**.
- No Kelly staking in v1. Fixed minimum stake + absolute loss budget.
- No passive/maker execution until Gate 4. **`taker-v1` only: FILL_OR_KILL with
  minFillSize = full stake.** A plain marketable limit can leave a resting remainder —
  that is a passive order and it contaminates Gates 2/3.
- **No automatic live learning.** No deployed model, threshold, calibration, feature,
  execution policy or risk parameter updates from live outcomes. Retraining produces a new
  immutable version + new gate evaluation + human approval.
- No reconciled BSP in pre-off features. No post-race data. No actual-off time (races
  are delayed; live only knows *scheduled* start).
- No import path from `research/scraping/` into anything that can place a bet.
- No MCP connection to Betfair, account state, order state, or secrets.

## Analytics consumer (ADR 0013)

The probability platform may support both trading and future analytics consumers. Analytics
code is **read-only** with respect to models and must never import live execution, account,
stake, risk, or settlement-command state. Predictor publication is forbidden until Gate P1
(SPEC-046) is activated and passed; recommendation status is `NOT_EVALUATED`. Detail:
`.claude/rules/analytics.md`.

## Structural facts you must not "simplify" away

- **Queue position is a latent variable.** Historical data cannot distinguish a
  cancellation from a match. Build a fill *probability* model, not a queue simulator.
- **Shadow mode cannot produce actual fills.** flumine paper trading routes to
  simulated execution, not Betfair's matching engine. Any "simulated vs actual"
  comparison needs real orders.
- **The race is the unit of analysis, not the runner.** Runners in a race are one
  mutually exclusive choice set. Cluster by meeting-day.
- **Prove EV at crossable prices before crediting any passive fill.** If it only wins
  on simulated maker fills, you are modelling the simulator. Note: historical displayed
  prices are **not** actual executions — Gate 2 is latency-adjusted, size-aware scenarios.
- **The universe is frozen before outcomes are known.** Missing data produces an explicit
  exclusion with a knowledge-time, never a disappearance.
- **Three prices, never conflated:** `p_market_info` (model input), `odds_exec`
  (what you can transact at now), `p_close` (diagnostic only).

## Types

- Tick index: **integer** into the canonical ladder. Never float.
- Stake/liability: integer minor units or exact Decimal. Never float.
- Timestamps: UTC **and** monotonic clock.

## Properties: declare causal inputs, do not assert universal variance

"Every output varies with every input" is **wrong** — exhausted budget must always REJECT
regardless of edge; a duplicate command must add no exposure regardless of differing
fields. Guard branches legitimately dominate.

Each money SPEC-ID declares `relevant_inputs` and `metamorphic_properties`. Test those.

## Verify before claiming done

```
make verify    # pytest + active-SPEC-ID coverage + hypothesis + ruff ARG + pylint W0613
make mutants   # cosmic-ray on money modules — 100% of NON-EQUIVALENT gate mutants killed;
               # every survivor classified + human-approved
make replay    # canonical replay regression (same env digest -> same canonical hash)
```

Only `enforcement_state: active` IDs gate CI. `planned` IDs are documented, not enforced —
activating a phase is a human-controlled specification change.

Status comes from CI, never from your own prose claim. The `spec-verifier` subagent is
**advisory evidence only** — useful fresh eyes, never a gate.

## Model orchestration

The lead model (Opus 4.8 or Fable) is the **brain**: it plans the slice, chooses the design,
writes the ADR, reasons about spec fidelity and money-critical invariants, and decides what
is correct. It **orchestrates**; it does not personally spend tokens on work a cheaper model
does just as well.

Delegate to **Sonnet subagents** (via the Agent tool) the high-volume, low-judgement work —
bulk file reads and codebase sweeps, mechanical edits across many files, running the test/lint
suite and collecting output, drafting boilerplate, searching for usages. Spawn them in parallel
when the work is independent. The lead keeps the conclusion, not the file dumps.

This division **never lowers the bar**:

- **The three rules bind every worker.** A subagent may not stub a money module, weaken a test,
  or let an LLM price/size/estimate — the lead is accountable for the whole slice regardless of
  who typed it.
- **Money-critical design and review stay with the lead.** Authoring `l4b_fill/`, `l5_decision/`,
  `l5b_risk/`, `l6_broker/`, `l7_settle/`, `l8_evidence/gates/`, deciding metamorphic properties,
  and judging correctness are brain work, not worker work. A worker may draft; the lead verifies
  line by line before it counts.
- **CI is still the only status.** Worker output is trusted exactly as far as `make verify` /
  `make mutants` / `make replay` confirm it — same as anything the lead writes. Delegation changes
  who drafts, never what gates.

**The lead owns spec fidelity, top to bottom.** Fable/Opus is accountable that every slice meets
the supplied spec at the **absolute highest standard** — `docs/SPECIFICATION.md` and
`docs/spec-manifest.yaml` to the letter, no minimising, no reduction in scope or effort. That
standard is not the lead's to keep and the worker's to guess at: the lead **drills it down into
every delegation** — each subagent brief must carry the exact SPEC-IDs in play, the relevant
`relevant_inputs` / `metamorphic_properties`, the money-module and no-float constraints, and the
verification the output must satisfy. A worker is never handed a vague task; it is handed the
spec obligation. When a worker returns, the lead checks the result **against the spec, not against
the worker's own summary** — the bar is the specification, and the lead is the one holding the
line at the top.

Match the model to the task: reserve the lead's judgement for the thinking, push the token-heavy
grind down to Sonnet — but the spec standard travels with the work, never diluted on the way down.

## Session discipline

One spec slice per session. Write failing tests first, **commit them separately**, then
implement without editing them. Durable state lives in files, not in this conversation.

## Rules loaded by path

See `.claude/rules/` — money-critical invariants load automatically when you touch
those directories.
