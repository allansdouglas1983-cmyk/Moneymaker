# TE-0027 — S2: the picks get steamed toward, the placebo sits at zero, and delay costs money

Harness `tennis_edge/experiments/s2_delay.py`, committed with the three-branch verdict and
the selection-on-bounce null declared before the run. Intended-order CLV under SPEC-095
discipline: no realised-fill CLV exists for any row; later prices never enter features or
training. Coverage is honest — a horizon counts only where the picked side actually
printed after T-600s (typed exclusions: 12.0k of 38.3k at T-300, 7.3k at T-120); drift on
covered rows is drift conditional on continued trading, the same class the SUPPORTED
money reading lives in.

## The primary readings (mean signed logit drift of the picked side; 98.75% CIs)

| picks | T-600→T-300 | T-600→T-120 |
|---|---|---|
| **model** | **+0.002197** [+0.001591, +0.002751] | **+0.002564** [+0.001964, +0.003162] |
| control | +0.003086 [+0.002503, +0.003619] | +0.004082 [+0.003490, +0.004722] |
| always-back-A placebo | +0.000027 [−0.000473, +0.000543] | +0.000006 [−0.000607, +0.000552] |

Positive drift means the picked side's price **shortened after the pick** — the market
moved toward the selection. The placebo spans zero at both horizons: no mechanical
artifact manufactures this. The median drift is exactly zero everywhere (most markets
simply do not print a move inside five to eight minutes at BASIC's cadence); the mean is
carried by the markets that do move, and they move toward the picks.

## The three-branch verdict, read as declared

- **Branch (i) — adverse drift in excess of the band — does not fire.** The mean drift is
  favourable, not adverse, and the per-market share of adverse-beyond-half-Roll moves
  (24.6% / 26.5%) is indistinguishable from the placebo's own share (26.4% / 28.2%) —
  exactly the bounce-null's prediction. **The P1 headline interval is not widened.**
- Branch (ii) is moot for the same reason.
- **Branch (iii) fires, and then some: the SUPPORTED class gains force.** The registered
  worry was that the +4.56% UNSUPPORTED cohort was steam running away from unfillable
  bets. The intended-order CLV now shows the model's picks carry genuine anticipatory
  content — the market agrees with them minutes later — which is the mechanism that makes
  the SUPPORTED reading's fills plausible rather than lucky.

## The delay cost, paired on identical bets

Settling the same bet list at the later LTP instead of the T-600 price costs
**+0.18% ROI by T-300 and +0.21% by T-120** (both clear at 95%): the price available at
the decision moment is measurably better than the price five or eight minutes later.
Operationally: when a price is entered, it is entered now — hesitation has a measured
price of roughly a fifth of a percent, small beside the +2.63% headline but real, and now
on the record instead of assumed away. (The control's even larger favourable drift is the
same mechanism seen from the market's own disagreement with Bet365; it earns nothing at
settlement — TE-0019's control loses — because its "picks" are already fully priced.)

All rows hypothetical trade-through returns; TE-0020's band applies throughout.
