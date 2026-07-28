"""Does cross-book dispersion around the close add forecast value? (DR-TENNIS-FORECAST-LIT-001)

The literature review returned one clearly actionable, literature-backed feature family we
do not use: the **shape of the market around the close** — specifically the spread between
the best and the average quote across the bookmaker panel, which Wilkens (2021) found among
the highest-importance inputs in bookmaker-augmented models. We already parse ``Max`` and
``Avg`` (2010-04 onward, ~74% of the corpus), so the test costs nothing but compute.

The feature: ``odds_dispersion_gap = ln(max_a/avg_a) − ln(max_b/avg_b)`` — antisymmetric by
construction, positive when the panel disagrees more about player A than about player B.

**Governance note.** ``tennis_edge/features.py`` bans odds-derived names from model features
as a leakage guard. This experiment computes the candidate ad hoc, for measurement only —
the ban stops *accidental* market leakage; the offset is already deliberate market
information at the same knowledge time (the close), and dispersion at the close is the same
knowledge time again. If the layer survives, admitting it to the registry is a governed,
documented exception — never a workaround. Deployment caveat regardless of result:
dispersion is not observable live without a multi-book feed, so a positive result is
measurement-only until that is solved.

**Multiplicity.** This is one of up to three feature families screened from the same
research round (dispersion, intransitivity, buzz). Per the review's own standard, final
acceptance requires the effect to survive a Bonferroni-adjusted bar across however many of
those are actually tested — a result that only just clears zero at 95% dies.
"""
import math

from tennis_edge.experiments.residual_edge import (
    BOOTSTRAP_DRAWS,
    _day_of,
    _mean_gain,
    _sigmoid,
    walk_forward,
)
from tennis_edge.metrics import clustered_bootstrap
from tennis_edge.residual_features import build_residual_features

FEATURE = "odds_dispersion_gap"


def main() -> None:
    from dataclasses import replace

    rows = build_residual_features()
    names = sorted({n for r in rows for n in r.features})

    covered = 0
    augmented = []
    for row in rows:
        max_a, avg_a = row.odds_a.get("max"), row.odds_a.get("avg")
        max_b, avg_b = row.odds_b.get("max"), row.odds_b.get("avg")
        if all(v is not None and v > 1.0 for v in (max_a, avg_a, max_b, avg_b)):
            value = math.log(max_a / avg_a) - math.log(max_b / avg_b)
            augmented.append(replace(row, features={**row.features, FEATURE: value}))
            covered += 1
        else:
            augmented.append(row)
    print(f"rows {len(rows):,}  dispersion computable on {covered:,} "
          f"({100 * covered / len(rows):.1f}%)")

    print("\nbaseline walk-forward:")
    base = walk_forward(rows, names)
    print("\n+dispersion walk-forward:")
    disp = walk_forward(augmented, names + [FEATURE])

    # Paired on identical rows in identical order; one feature-set difference.
    diffs = []
    for (row_b, p_b), (_row_d, p_d) in zip(base, disp):
        won = row_b.won == 1
        gain = (math.log(p_d if won else 1 - p_d)
                - math.log(p_b if won else 1 - p_b))
        diffs.append((row_b.date, gain))
    mean = math.fsum(g for _d, g in diffs) / len(diffs)
    lo, hi = clustered_bootstrap(diffs, statistic=_mean_gain, cluster_of=_day_of,
                                 draws=BOOTSTRAP_DRAWS)
    print(f"\nDISPERSION LAYER, paired over {len(diffs):,} matches")
    print(f"  gain {mean:+.6f} nats  CI95=[{lo:+.6f},{hi:+.6f}]  "
          f"-> {'clears zero' if lo > 0 else 'does NOT clear zero'}")

    market = [(r.date,
               math.log(p if r.won else 1 - p)
               - math.log(_sigmoid(r.market_logit) if r.won
                          else 1 - _sigmoid(r.market_logit)))
              for r, p in disp]
    m_mean = math.fsum(g for _d, g in market) / len(market)
    m_lo, m_hi = clustered_bootstrap(market, statistic=_mean_gain, cluster_of=_day_of,
                                     draws=BOOTSTRAP_DRAWS)
    print(f"  +dispersion over the market  {m_mean:+.6f}  CI95=[{m_lo:+.6f},{m_hi:+.6f}]")
    print("\n  Read with the multiplicity note in the module docstring: borderline-at-95%")
    print("  is a death, not a pass, while sibling families from the same round are open.")


if __name__ == "__main__":
    main()
