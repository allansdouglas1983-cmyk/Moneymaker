# The standing evidence state — read this before claiming anything about the edge

**Purpose.** 34+ TE findings exist and a session that has not read them will misstate the
evidence — it has already happened once (2026-07-30: a session summarised the edge as
"unproven, sign not established", erasing TE-0019/0026/0032/0034 from its briefs). This
page is the current position in one place. It is UPDATED in the same commit as any TE
finding that changes it. The TE documents remain the authority; this is the index, not
the source.

**Last updated:** 2026-07-30 (through TE-0046).

## The forecast edge: REAL IN THE RECORD, execution is the open question

| evidence | what it showed | doc |
|---|---|---|
| Eleven-year strict money reading | +2.63% [+0.94, +4.29] on 24,886 supported-fill bets, **clears zero**; identical rule on the market's own probability loses −1.33% | TE-0019 |
| Monotonicity | returns rise nearly monotonically in predicted edge by decile (+2.4% → +4.9%); above-the-cost-floor cohort +3.33% [+1.47, +5.32] **with** cost logic | TE-0026 |
| Untouched ten weeks (rules provably predate all prices) | sign and size reproduced (+1.18% supported, +2.01% all fills); control lost ~6% again; calibration slope 0.959 | TE-0032, TE-0034 |
| At the account's ACTUAL 2% rate | supported reading clears zero across the whole threshold range (+3.86% [+1.37, +6.29] at min_edge 0.02); control significantly negative on 35k bets | TE-0043, TE-0044 |

**Summary sentence, use this one:** the forecast edge is positive, replicated
out-of-window, control-rejected, monotone in predicted edge, and calibrated; the residual
uncertainty is EXECUTION (no fill is proven from a trace, no realised returns exist), not
sign.

## The standing caveats — these are the true open items

- **TE-0020**: at the half-Roll execution haircut the supported reading is +1.25%
  [−0.41, +2.86] — spans zero. This is the strongest remaining objection. TE-0026 answers
  it in structure (the bets that fail the cost are identifiable ex ante), but the pooled
  costed reading has not itself cleared.
- **No realised returns.** Everything is hypothetical trade-through settlement on a
  last-trade trace. The ADR 0020 trial's purpose is FILL EVIDENCE, not income (TE-0036).
- **CLV is the evidence route**, not settled P&L: at any single-person budget, ruin
  through pure variance is ~29% even with the edge exactly as measured, so P&L cannot
  resolve the question on a human timescale (TE-0036). The live CLV monitor is the
  fastest honest signal.
- **Commission** is 2% by founder-confirmed package choice (TE-0044); still ASSUMPTION
  under SPEC-081 until the first settled statement shows the deduction.

## Structure worth remembering before designing anything

- Where the money was: **outsiders** (odds > 2.0) carry ~5× the favourite half's point
  ROI (+4.26% vs +0.83%), though every slice alone spans zero (TE-0035). The 1.50–2.00
  band is dead weight in four independent configurations; 6.00+ is bad everywhere
  (TE-0043).
- The ride: 11 years of the frozen rule earned +315 units through a **128-unit max
  drawdown**; 17 consecutive losers is NORMAL; the historical path was lucky — the
  bootstrap median re-ordering goes 5× deeper underwater (TE-0036).
- Selection moves per-bet expectation ~7×; no staking rule moves it at all — staking
  chooses the weights in sum(S_i·ev_i), never the ev_i (TE-0043).
- The deployment gate: the site serves the Bet365-anchored model; the exchange re-anchor
  FAILED its pre-registered deployment bar and does not ship (TE-0019 verdict 2).
- **The staking head-to-head ran and returned the pre-declared null** (TE-0046): no arm
  passed the frozen admissibility gates — every growing rule breaches the £70 floor
  under the zero-edge scenario over the eleven-year horizon (flat £1: 86.7%), and every
  floor-protecting rule switches itself off on a £100 bank (TIPP silent in 100% of
  draws). Flat £1 retained, now on 48,000 replayed histories. The floor-rule
  almost-sure guarantee was demonstrated exactly (P(breach)=0.000 in all scenarios,
  including sign-reversed). Registered follow-up: horizon-sliced re-run for the
  bank-sizing arithmetic. sqrt-profit (escalates only from banked profit) is the
  leading shape for that re-run — highest median at flat-like floor risk.
- **A staking head-to-head cannot outrun the edge test** (DR-TENNIS-STAKING-006): for
  non-compounding rules on one settled sequence, every pairwise comparison is the edge
  test rescaled downward (|t_pair| ≤ t_edge, n_eff as low as 27 bets). Until the costed
  reading resolves, only the risk-shape columns (drawdown, floor-breach, participation)
  are estimable between rules — reward rankings are noise. Protocol and matrix:
  `docs/research/findings/DR-TENNIS-STAKING-006-*`.
- **DR-003's adopt-nothing condition is discharged on the supported reading**
  (DR-TENNIS-STAKING-007): the completed deep research's chain, re-derived at the
  founder-attested 2%, reproduces DR-005's @5% table exactly and then shows (a) the
  day-clustered CI95 lower bound positive at every threshold 0.00–0.04 (min_edge 0.02:
  +3.86% [+1.37, +6.29], 9,793 bets), market control significantly negative; (b)
  DR-004's "no rule expressible below ~£400" reversed — an artefact of the 5% error.
  NOT discharged: realised fills, SPEC-081 statement verification, design-level
  selection. Consequence: the matrix's D7 K-LCB (Kelly at the conservative bound) was
  registered (TE-0047, frozen constants Δe=0.0249, d_max=0.30, ÷k card charge) and
  adopted for the trial by founder directive (ADR 0020 Amendment 4) — the mis-derived
  shrink allocator of Amendment 2 stays WITHDRAWN (Amendment 3). The served stakes are
  golden-vectored (300 vectors, exact pence) against the registered Python rules.
- **Stationary training stands** (TE-0045, pre-registered): recency-weighted refits never
  beat the equal-weighted fit — pooled null at every half-life, monotone HARM as the
  half-life shortens (h=1y: −0.000230 [−0.000439, −0.000003]), and no help post-2024
  where the regime hypothesis predicted it. The post-2023 anomaly is now localised to
  the ANCHOR relationship (TE-0033 Q2, directional), resolvable only by live-data
  accumulation. TE-0041 item 18 CLOSED.

## Discipline

A summary of this page is not a substitute for the TE documents it cites. Any claim that
contradicts a TE document is wrong until the document is amended. When a new finding
changes this picture, update this page in the same commit.
