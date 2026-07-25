"""Scoring, calibration and betting metrics.

Selection is on **log loss and calibration**, never accuracy. Accuracy is close to useless
here: "the higher-ranked player wins" scores ~68% on ATP, matching a properly specified
point-based model, while being far worse priced. And a Kelly-staked system is destroyed by
miscalibration long before it is troubled by a point of accuracy — a calibration slope of
0.89 (the published figure for the common-opponent model) means systematically under-betting
real edges and over-betting marginal ones.

Brier is reported under the Murphy decomposition, ``Brier = reliability - resolution +
uncertainty``, because reliability and resolution fail in different ways and the sum hides
which one moved. Resolution is where sharp markets beat rating models.

Uncertainty is day-clustered throughout. Matches on the same day share tournament
conditions, a common opponent pool and correlated model error, so treating them as
independent overstates significance — for a season of tennis, by a lot.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable, Hashable, Sequence

__all__ = [
    "EPS",
    "log_loss",
    "brier",
    "BrierDecomposition",
    "brier_decomposition",
    "Calibration",
    "calibration_fit",
    "ScoreCard",
    "score",
    "clv_beat",
    "BetResult",
    "BettingSummary",
    "summarise_bets",
    "clustered_bootstrap",
    "bootstrap_ratio_by_cluster",
]

EPS = 1e-15


def _clip(p: float) -> float:
    return min(max(p, EPS), 1.0 - EPS)


def log_loss(probabilities: Sequence[float], outcomes: Sequence[int]) -> float:
    """Mean negative log likelihood. The primary selection metric."""
    if len(probabilities) != len(outcomes):
        raise ValueError("probabilities and outcomes must be the same length")
    if not probabilities:
        raise ValueError("cannot score an empty sample")
    total = 0.0
    for p, y in zip(probabilities, outcomes):
        q = _clip(float(p))
        total += -math.log(q if y else 1.0 - q)
    return total / len(probabilities)


def brier(probabilities: Sequence[float], outcomes: Sequence[int]) -> float:
    """Mean squared error of the probability forecast."""
    if len(probabilities) != len(outcomes):
        raise ValueError("probabilities and outcomes must be the same length")
    if not probabilities:
        raise ValueError("cannot score an empty sample")
    return sum((float(p) - y) ** 2 for p, y in zip(probabilities, outcomes)) / len(probabilities)


@dataclass(frozen=True)
class BrierDecomposition:
    """Murphy (1973) reliability/resolution/uncertainty split.

    The exact identity ``reliability - resolution + uncertainty`` reconstructs the Brier
    score of the **binned** forecast — the one where every prediction is replaced by its
    bin's mean. It does not reconstruct the raw Brier score, because binning discards the
    spread of forecasts inside each bin. Reporting the raw score as if the identity held
    would be quietly wrong, so both are kept and :attr:`binning_loss` names the difference.
    """

    brier: float
    brier_binned: float
    reliability: float
    resolution: float
    uncertainty: float
    bins: int

    @property
    def binning_loss(self) -> float:
        """How much of the raw Brier score the binning hides. Small bins, small number."""
        return self.brier - self.brier_binned

    def check(self, tolerance: float = 1e-9) -> bool:
        """The decomposition identity, verified against the binned score it describes."""
        reconstructed = self.reliability - self.resolution + self.uncertainty
        return abs(self.brier_binned - reconstructed) < tolerance


def brier_decomposition(
    probabilities: Sequence[float], outcomes: Sequence[int], *, bins: int = 20
) -> BrierDecomposition:
    """Split Brier into reliability (calibration error) and resolution (discrimination).

    Reliability: how far each bin's realised rate sits from its forecast — lower is better.
    Resolution: how far each bin's realised rate sits from the base rate — higher is better.
    """
    if bins < 2:
        raise ValueError(f"need at least two bins, got {bins}")
    n = len(probabilities)
    if n == 0:
        raise ValueError("cannot decompose an empty sample")
    base = sum(outcomes) / n
    buckets: dict[int, list[tuple[float, int]]] = {}
    for p, y in zip(probabilities, outcomes):
        index = min(int(float(p) * bins), bins - 1)
        buckets.setdefault(index, []).append((float(p), int(y)))
    reliability = 0.0
    resolution = 0.0
    binned = 0.0
    for members in buckets.values():
        weight = len(members) / n
        mean_p = sum(p for p, _ in members) / len(members)
        mean_y = sum(y for _, y in members) / len(members)
        reliability += weight * (mean_p - mean_y) ** 2
        resolution += weight * (mean_y - base) ** 2
        binned += sum((mean_p - y) ** 2 for _, y in members) / n
    return BrierDecomposition(
        brier=brier(probabilities, outcomes),
        brier_binned=binned,
        reliability=reliability,
        resolution=resolution,
        uncertainty=base * (1.0 - base),
        bins=len(buckets),
    )


@dataclass(frozen=True)
class Calibration:
    """Logistic recalibration fit: ``logit(y) ~ intercept + slope * logit(p)``.

    A perfectly calibrated forecast gives intercept 0, slope 1. Slope below 1 means
    over-confidence (predictions too extreme); above 1 means under-confidence.
    """

    intercept: float
    slope: float
    iterations: int
    converged: bool

    def apply(self, probability: float) -> float:
        z = math.log(_clip(probability) / (1.0 - _clip(probability)))
        return 1.0 / (1.0 + math.exp(-(self.intercept + self.slope * z)))


def calibration_fit(
    probabilities: Sequence[float], outcomes: Sequence[int], *, max_iter: int = 100
) -> Calibration:
    """Newton-Raphson logistic fit of outcomes on the forecast logit."""
    xs = [math.log(_clip(float(p)) / (1.0 - _clip(float(p)))) for p in probabilities]
    ys = [float(y) for y in outcomes]
    if not xs:
        raise ValueError("cannot fit calibration on an empty sample")
    intercept, slope = 0.0, 1.0
    converged = False
    used = 0
    for used in range(1, max_iter + 1):
        g0 = g1 = h00 = h01 = h11 = 0.0
        for x, y in zip(xs, ys):
            mu = 1.0 / (1.0 + math.exp(-(intercept + slope * x)))
            w = max(mu * (1.0 - mu), 1e-12)
            residual = y - mu
            g0 += residual
            g1 += residual * x
            h00 += w
            h01 += w * x
            h11 += w * x * x
        det = h00 * h11 - h01 * h01
        if abs(det) < 1e-14:
            break
        step0 = (h11 * g0 - h01 * g1) / det
        step1 = (h00 * g1 - h01 * g0) / det
        intercept += step0
        slope += step1
        if abs(step0) < 1e-10 and abs(step1) < 1e-10:
            converged = True
            break
    return Calibration(intercept=intercept, slope=slope, iterations=used, converged=converged)


@dataclass(frozen=True)
class ScoreCard:
    """Everything we judge a probability model on, in one object."""

    n: int
    log_loss: float
    brier: float
    decomposition: BrierDecomposition
    calibration: Calibration
    accuracy: float
    base_rate: float

    def better_than(self, other: "ScoreCard") -> bool:
        """Strictly lower log loss. The only comparison that decides promotion."""
        return self.log_loss < other.log_loss

    def report(self, label: str = "") -> str:
        head = f"{label:<28}" if label else ""
        return (
            f"{head}n={self.n:>7,}  logloss={self.log_loss:.5f}  brier={self.brier:.5f}  "
            f"rel={self.decomposition.reliability:.5f} res={self.decomposition.resolution:.5f}  "
            f"cal_slope={self.calibration.slope:.4f} cal_int={self.calibration.intercept:+.4f}  "
            f"acc={100 * self.accuracy:.2f}%"
        )


def score(probabilities: Sequence[float], outcomes: Sequence[int], *, bins: int = 20) -> ScoreCard:
    """Full scorecard for one set of forecasts."""
    n = len(probabilities)
    correct = sum(1 for p, y in zip(probabilities, outcomes)
                  if (float(p) >= 0.5) == bool(y))
    return ScoreCard(
        n=n,
        log_loss=log_loss(probabilities, outcomes),
        brier=brier(probabilities, outcomes),
        decomposition=brier_decomposition(probabilities, outcomes, bins=bins),
        calibration=calibration_fit(probabilities, outcomes),
        accuracy=correct / n,
        base_rate=sum(outcomes) / n,
    )


def clv_beat(taken_odds: float, closing_fair_probability: float) -> float:
    """Expected value implied by the closing line: ``p_close * o_taken - 1``.

    If the closing no-vig price is an unbiased estimate of the truth, this *is* the expected
    return on the bet. It is the primary KPI because it converges far faster than realised
    P&L — a consistent 5% beat can be significant in tens of bets, where ROI needs thousands.
    """
    if not taken_odds > 1.0:
        raise ValueError(f"taken odds must exceed 1, got {taken_odds}")
    if not 0.0 < closing_fair_probability < 1.0:
        raise ValueError(f"closing probability must be in (0,1), got {closing_fair_probability}")
    return closing_fair_probability * taken_odds - 1.0


@dataclass(frozen=True)
class BetResult:
    """One settled notional bet. ``stake`` is in units; no real money exists."""

    cluster: Hashable
    odds: float
    stake: float
    won: bool
    commission: float
    clv: float | None = None

    @property
    def profit(self) -> float:
        if not self.won:
            return -self.stake
        return self.stake * (self.odds - 1.0) * (1.0 - self.commission)


@dataclass(frozen=True)
class BettingSummary:
    """Realised performance of a set of notional bets, with honest uncertainty."""

    bets: int
    staked: float
    profit: float
    roi: float
    mean_clv: float | None
    max_drawdown: float
    t_stat: float
    roi_ci95: tuple[float, float]
    bets_for_significance: int | None

    def report(self, label: str = "") -> str:
        head = f"{label:<28}" if label else ""
        clv = "n/a" if self.mean_clv is None else f"{100 * self.mean_clv:+.2f}%"
        need = "n/a" if self.bets_for_significance is None else f"{self.bets_for_significance:,}"
        return (
            f"{head}bets={self.bets:>6,}  ROI={100 * self.roi:+6.2f}%  "
            f"CI95=[{100 * self.roi_ci95[0]:+.2f}%,{100 * self.roi_ci95[1]:+.2f}%]  "
            f"CLV={clv}  t={self.t_stat:+.2f}  maxDD={self.max_drawdown:.1f}u  n*={need}"
        )


def summarise_bets(
    results: Sequence[BetResult], *, bootstrap: int = 2000, seed: int = 20260725
) -> BettingSummary:
    """Aggregate settled bets with a day-clustered bootstrap confidence interval.

    Also reports how many bets would be needed for the observed ROI to be distinguishable
    from zero at 95% — usually a sobering number, and the point of including it.
    """
    if not results:
        raise ValueError("cannot summarise an empty bet list")
    staked = sum(r.stake for r in results)
    profit = sum(r.profit for r in results)
    roi = profit / staked if staked else 0.0

    equity = 0.0
    peak = 0.0
    drawdown = 0.0
    for r in results:
        equity += r.profit
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)

    returns = [r.profit / r.stake for r in results if r.stake]
    mean = sum(returns) / len(returns)
    variance = sum((x - mean) ** 2 for x in returns) / max(len(returns) - 1, 1)
    sd = math.sqrt(variance)
    t_stat = mean / (sd / math.sqrt(len(returns))) if sd > 0 else 0.0
    needed = int(math.ceil((1.96 * sd / mean) ** 2)) if mean != 0 and sd > 0 else None

    clvs = [r.clv for r in results if r.clv is not None]
    mean_clv = sum(clvs) / len(clvs) if clvs else None

    lo, hi = bootstrap_ratio_by_cluster(
        [(r.cluster, r.profit, r.stake) for r in results], draws=bootstrap, seed=seed
    )
    return BettingSummary(
        bets=len(results), staked=staked, profit=profit, roi=roi, mean_clv=mean_clv,
        max_drawdown=drawdown, t_stat=t_stat, roi_ci95=(lo, hi),
        bets_for_significance=needed,
    )


def bootstrap_ratio_by_cluster(
    rows: Sequence[tuple[Hashable, float, float]],
    *,
    draws: int = 2000,
    seed: int = 20260725,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Cluster bootstrap of a ratio (profit/stake), aggregating each cluster once.

    Resampling whole bet lists is O(bets x draws) and becomes unusable at corpus scale. For
    a ratio statistic the cluster totals are sufficient: summing a cluster's profit and
    stake up front gives an identical answer in a fraction of the time.
    """
    totals: dict[Hashable, list[float]] = {}
    for cluster, profit, stake in rows:
        entry = totals.setdefault(cluster, [0.0, 0.0])
        entry[0] += profit
        entry[1] += stake
    aggregates = list(totals.values())
    if not aggregates:
        raise ValueError("cannot bootstrap without clusters")
    rng = random.Random(seed)
    count = len(aggregates)
    values: list[float] = []
    for _ in range(draws):
        profit = 0.0
        stake = 0.0
        for _ in range(count):
            chosen = aggregates[rng.randrange(count)]
            profit += chosen[0]
            stake += chosen[1]
        values.append(profit / stake if stake else 0.0)
    values.sort()
    lo_index = max(0, int(alpha / 2 * len(values)) - 1)
    hi_index = min(len(values) - 1, int((1 - alpha / 2) * len(values)))
    return values[lo_index], values[hi_index]


def clustered_bootstrap(
    items: Sequence[object],
    *,
    statistic: Callable[[Sequence[object]], float],
    cluster_of: Callable[[object], Hashable],
    draws: int = 2000,
    seed: int = 20260725,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Percentile CI resampling whole clusters, not individual observations.

    Resampling matches independently would treat two matches on the same day as independent
    evidence. They are not, and pretending otherwise is how a noise strategy acquires a
    significant-looking t-statistic.
    """
    groups: dict[Hashable, list[object]] = {}
    for item in items:
        groups.setdefault(cluster_of(item), []).append(item)
    keys = list(groups)
    if not keys:
        raise ValueError("cannot bootstrap without clusters")
    rng = random.Random(seed)
    values: list[float] = []
    for _ in range(draws):
        sample: list[object] = []
        for _ in range(len(keys)):
            sample.extend(groups[keys[rng.randrange(len(keys))]])
        if sample:
            values.append(statistic(sample))
    if not values:
        raise ValueError("bootstrap produced no samples")
    values.sort()
    lo_index = max(0, int(alpha / 2 * len(values)) - 1)
    hi_index = min(len(values) - 1, int((1 - alpha / 2) * len(values)))
    return values[lo_index], values[hi_index]
