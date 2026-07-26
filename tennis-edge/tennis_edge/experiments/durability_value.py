"""Do head-to-head, retirement risk and workload earn their place?

An Elo rating is a scalar summary of who a player beats, and it is blind to three things a
market prices: that two players with identical ratings can have a lopsided record against
each other, that a player who retires often hands the market a settled loss without being
beaten, and that minutes on court accumulate while a rating does not decay them.

That is a reason to *measure* them, not a reason to keep them. A feature that restates
information already in the rating will fit a coefficient, look plausible, and add nothing
out of sample — and every extra coefficient is another way to overfit a market that is very
close to efficient. Head-to-head in particular is the classic trap: it looks like the most
obvious signal in tennis and most of it is the rating difference wearing a different hat.

**The comparison is paired and everything but the feature set is held fixed.** Same rows,
same walk-forward, same ridge penalty, same day-clustered interval. The two models are
scored on identical matches, so the difference is per-match and the bootstrap resamples
whole days of *differences* rather than two independent means. An unpaired comparison of
two noisy quantities would need far more data to see the same effect.

**The null result is the expected one.** Four architectures have already come out flat
against this market. If the seven features add nothing, they get deleted, and the deletion
is the finding.
"""
from __future__ import annotations

import collections
import datetime as dt
import math
from dataclasses import dataclass
from typing import Sequence

from tennis_edge.experiments.residual_edge import FIRST_SCORED_YEAR, fit, predict
from tennis_edge.feature_cache import FeatureRow as Row
from tennis_edge.metrics import clustered_bootstrap
from tennis_edge.residual_features import build_residual_features

#: The layer under test. Everything else in the feature set is the incumbent baseline,
#: which by now includes the serve-detail layer measured in the sibling experiment.
DURABILITY = (
    "h2h_gap",
    "retirement_risk_gap",
    "workload_minutes_gap",
    "workload_long_gap",
    "surface_switch_gap",
)


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(min(z, 30.0), -30.0)))


def _log_score(probability: float, won: int) -> float:
    """Negative log likelihood of the actual winner. Lower is better."""
    p = min(max(probability, 1e-12), 1 - 1e-12)
    return -math.log(p if won else 1 - p)


@dataclass(frozen=True)
class Paired:
    """One match scored by both models, plus the market it is being corrected from."""

    date: dt.date
    market: float
    baseline: float
    extended: float
    won: int

    @property
    def gain_over_market(self) -> float:
        """How much the extended model beat the price by, in nats."""
        return _log_score(self.market, self.won) - _log_score(self.extended, self.won)

    @property
    def layer_gain(self) -> float:
        """How much the seven features added, in nats. This is the quantity under test."""
        return _log_score(self.baseline, self.won) - _log_score(self.extended, self.won)


def walk_forward_paired(rows: list[Row], baseline: list[str],
                        extended: list[str]) -> list[Paired]:
    """Fit both feature sets on every prior year and score the next with each.

    The two fits see byte-identical training rows. Only the columns differ, so any
    difference downstream is the layer and not the split, the sample, or the year.
    """
    by_year: dict[int, list[Row]] = collections.defaultdict(list)
    for row in rows:
        by_year[row.date.year].append(row)
    ordered = sorted(by_year)
    years = [y for y in ordered if y >= FIRST_SCORED_YEAR]
    out: list[Paired] = []
    train: list[Row] = [r for y in ordered if y < years[0] for r in by_year[y]]
    for year in years:
        if len(train) >= 5000:
            beta_base = fit(train, baseline)
            beta_ext = fit(train, extended)
            for row in by_year[year]:
                out.append(Paired(
                    date=row.date,
                    market=_sigmoid(row.market_logit),
                    baseline=predict(row, beta_base),
                    extended=predict(row, beta_ext),
                    won=row.won,
                ))
            print(f"  {year}: trained on {len(train):,}, scored {len(by_year[year]):,}",
                  flush=True)
        train.extend(by_year[year])
    return out


def _mean_layer_gain(items: Sequence[object]) -> float:
    pairs = [i for i in items if isinstance(i, Paired)]
    return sum(p.layer_gain for p in pairs) / len(pairs) if pairs else 0.0


def _mean_market_gain(items: Sequence[object]) -> float:
    pairs = [i for i in items if isinstance(i, Paired)]
    return sum(p.gain_over_market for p in pairs) / len(pairs) if pairs else 0.0


def _day_of(item: object) -> dt.date:
    assert isinstance(item, Paired)
    return item.date


def report(scored: list[Paired]) -> bool:
    """Print both effects with day-clustered intervals. Returns whether the layer earned it."""
    covered = [p for p in scored if p.baseline != p.extended]
    print(f"\nscored {len(scored):,} out-of-sample matches, "
          f"{len(covered):,} where the layer changed the price")

    layer = _mean_layer_gain(scored)
    lo, hi = clustered_bootstrap(scored, statistic=_mean_layer_gain, cluster_of=_day_of)
    print(f"\nDURABILITY LAYER over the baseline model")
    print(f"  mean gain      {layer:+.6f} nats   95% CI [{lo:+.6f}, {hi:+.6f}]")

    market = _mean_market_gain(scored)
    mlo, mhi = clustered_bootstrap(scored, statistic=_mean_market_gain, cluster_of=_day_of)
    print(f"\nEXTENDED MODEL over the closing price")
    print(f"  mean gain      {market:+.6f} nats   95% CI [{mlo:+.6f}, {mhi:+.6f}]")

    # The interval has to clear zero on the side that helps. A point estimate above zero
    # with an interval straddling it is a coin landing heads, not a layer earning a place.
    earned = lo > 0.0
    print(f"\nVERDICT: {'KEEP' if earned else 'DELETE'} — the interval "
          f"{'excludes' if earned else 'includes'} zero")
    return earned


def main() -> None:
    rows = build_residual_features()
    present = {n for r in rows for n in r.features}
    extended = sorted(present)
    baseline = sorted(present - set(DURABILITY))
    coverage = {n: sum(1 for r in rows if n in r.features) for n in DURABILITY}

    print(f"priceable matches: {len(rows):,}")
    print(f"baseline features: {len(baseline)}   extended: {len(extended)}")
    print("durability coverage: "
          + ", ".join(f"{n.replace('_gap', '')} {coverage[n]:,}" for n in DURABILITY))
    if not set(DURABILITY) <= present:
        missing = sorted(set(DURABILITY) - present)
        raise SystemExit(f"the cache has no durability columns ({missing}); rebuild it")

    print("\nwalk-forward, both models on identical training rows:")
    scored = walk_forward_paired(rows, baseline, extended)
    if not scored:
        raise SystemExit("no out-of-sample years")
    report(scored)


if __name__ == "__main__":
    main()
