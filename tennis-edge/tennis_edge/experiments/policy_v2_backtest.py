"""What does the v2 policy actually do, before it is allowed near a ledger?

``residual_edge`` measures the model with a **parameter-free** staking rule: bet whenever the
probability clears the quoted break-even, no buffer. That is the right rule for measuring a
*model*, because it has no knob to tune.

A policy is not a model. v2 adds ``MIN_EDGE`` — a threshold, and therefore a parameter — and
the honest order of operations is to declare it first (which
:mod:`tennis_edge.policy_v2` does, frozen into its digest) and only then find out what it
does. This file is that second step. It must not become the first: if a threshold is chosen
after seeing this output, it stops being a prior and becomes a fitted parameter, and every
interval below becomes a lie about a search nobody recorded.

So the output is deliberately reported at **several thresholds including the frozen one**.
Seeing the whole curve makes the tuning temptation explicit rather than hiding it, and makes
it obvious when a good-looking cell is just the best of six.

The control is the same one ``residual_edge`` uses and for the same reason: the identical
rule driven by the market's own probability. At the best-of-market quote a threshold rule
fires wherever some book disagrees with the pricing book, which earns money regardless of
whether a model is involved.
"""
from tennis_edge.experiments.residual_edge import (
    BOOTSTRAP_DRAWS,
    COMMISSIONS,
    _sigmoid,
    walk_forward,
)
from tennis_edge.feature_cache import FeatureRow as Row
from tennis_edge.metrics import BetResult, summarise_bets
from tennis_edge.policy_v2 import MIN_EDGE, WATCH_EDGE
from tennis_edge.residual_features import SETTLE_BOOKS, build_residual_features

#: Reported alongside the frozen threshold so the whole curve is visible. These are NOT
#: candidates to choose from — MIN_EDGE is already frozen in the policy digest.
THRESHOLDS = (0.0, WATCH_EDGE, MIN_EDGE, 0.03, 0.05, 0.10)


def _break_even(odds: float, commission: float) -> float:
    return 1.0 / (1.0 + (odds - 1.0) * (1.0 - commission))


def _settle(scored: list[tuple[Row, float]], book: str, threshold: float,
            use_model: bool) -> list[BetResult]:
    commission = COMMISSIONS[book]
    results: list[BetResult] = []
    for row, p in scored:
        probability = p if use_model else _sigmoid(row.market_logit)
        for side, odds, won in (
            (probability, row.odds_a.get(book), bool(row.won)),
            (1.0 - probability, row.odds_b.get(book), not row.won),
        ):
            if odds is None or odds <= 1.0:
                continue
            if side - _break_even(odds, commission) < threshold:
                continue
            results.append(BetResult(cluster=row.date, odds=odds, stake=1.0,
                                     won=won, commission=commission))
    return results


def main() -> None:
    rows = build_residual_features()
    names = sorted({n for r in rows for n in r.features})
    print("\nwalk-forward:")
    scored = walk_forward(rows, names)
    print(f"\nscored {len(scored):,} out-of-sample matches "
          f"({min(r.date for r, _p in scored)} .. {max(r.date for r, _p in scored)})")
    print(f"\nfrozen policy threshold MIN_EDGE = {MIN_EDGE:.3f}  "
          f"(declared before this was run, and inside the policy digest)")

    for book in SETTLE_BOOKS:
        print(f"\n{book.upper()}  (commission {COMMISSIONS[book]:.0%})")
        print(f"  {'threshold':>10}{'bets':>9}{'ROI':>10}{'95% CI':>22}"
              f"{'control ROI':>14}")
        for threshold in THRESHOLDS:
            model = _settle(scored, book, threshold, use_model=True)
            control = _settle(scored, book, threshold, use_model=False)
            if len(model) < 100:
                print(f"  {threshold:>10.3f}{len(model):>9,}   (too few to score)")
                continue
            summary = summarise_bets(model, bootstrap=BOOTSTRAP_DRAWS)
            control_roi = (f"{100 * summarise_bets(control, bootstrap=BOOTSTRAP_DRAWS).roi:+.2f}%"
                           if len(control) >= 100 else "n/a")
            marker = "  <- frozen" if abs(threshold - MIN_EDGE) < 1e-9 else ""
            print(f"  {threshold:>10.3f}{summary.bets:>9,}{100 * summary.roi:>+9.2f}%"
                  f"   [{100 * summary.roi_ci95[0]:+.2f}%,{100 * summary.roi_ci95[1]:+.2f}%]"
                  f"{control_roi:>14}{marker}")

    print("\nThe curve is printed in full so that picking a threshold off it would be")
    print("visibly a search rather than a prior. MIN_EDGE is already frozen; if a different")
    print("value is ever wanted it is a new policy vintage with its own digest and its own")
    print("out-of-sample record, not a better reading of this table.")


if __name__ == "__main__":
    main()
