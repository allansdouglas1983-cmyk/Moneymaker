"""TE-0017 S3 measurement: what the rank_gap serve-path defect was forfeiting.

The fix itself deployed on its own justification — it removes a measured train/serve
mismatch, restoring the model that was actually validated — and nothing here gates it.
These are the three registered arms, on identical rows, day-clustered:

(a)  22 vs 21 features, paired walk-forward refit: the coherent marginal value of
     rank_gap. A lower bound on the forfeiture, because a refit without the feature
     redistributes its work onto correlated features, which the broken serve path could not.
(a') The fixed deployed 22-coefficient artifact scored with rank_gap withheld vs present:
     the exact serve-path estimand, including the coefficient-mismatch term. This is
     literally the site's old arithmetic against its new arithmetic on the same rows.
(b)  The proxy check: rank_gap built from each player's latest-PRIOR-match rank (what the
     snapshot serves) vs from the fixture-time corpus rank (what training used), bucketed
     by rank staleness — the protected-ranking/injury-return cases live in the stale tail.

Registered analysis choices: arms (a) and (a') carry a Bonferroni correction between them
(two confirmatory contrasts -> 97.5% intervals); arm (b) is descriptive validation. A
stale-beats-fresh or sign-anomalous reading is a suspected harness bug per house rules,
not a finding.
"""
from __future__ import annotations

import collections
import datetime as dt
import math
from pathlib import Path

from tennis_edge.experiments.residual_edge import _sigmoid, walk_forward
from tennis_edge.feature_cache import FeatureRow as Row
from tennis_edge.metrics import clustered_bootstrap
from tennis_edge.residual_features import build_residual_features
from tennis_edge.residual_model import load_model

#: Two confirmatory contrasts share the family; each reads at 1 - 0.05/2.
BONFERRONI_ALPHA = 0.025

#: Resolved from the module location, not the cwd — the harness must find the artifact
#: whether it is run from the repo root or from tennis-edge/.
MODEL_PATH = Path(__file__).resolve().parents[3] / "artifacts" / "residual-model-v3.json"


def _log_loss(probability: float, won: int) -> float:
    p = min(max(probability, 1e-12), 1.0 - 1e-12)
    return -math.log(p if won else 1.0 - p)


def _mean(pairs: list[tuple[dt.date, float]]) -> float:
    return sum(d for _, d in pairs) / len(pairs) if pairs else 0.0


def _paired(name: str, diffs: list[tuple[dt.date, float]], *, alpha: float) -> None:
    gain = _mean(diffs)
    lo, hi = clustered_bootstrap(
        diffs, statistic=lambda items: _mean(list(items)),  # type: ignore[arg-type]
        cluster_of=lambda item: item[0],  # type: ignore[union-attr,index]
        alpha=alpha)
    level = 100 * (1 - alpha)
    verdict = "clears zero" if lo > 0 else ("below zero" if hi < 0 else "spans zero")
    print(f"  {name:<52} {gain:+.6f} nats  CI{level:.1f}=[{lo:+.6f},{hi:+.6f}]  {verdict}")


def _score_fixed(rows: list[Row], *, withhold_rank: bool) -> list[float]:
    """The deployed artifact's probability for each row, optionally on the broken path."""
    model = load_model(MODEL_PATH)
    out: list[float] = []
    for row in rows:
        features = dict(row.features)
        if withhold_rank:
            features.pop("rank_gap", None)
        z = row.market_logit + math.fsum(
            model.coefficients.get(name, 0.0) * value
            for name, value in features.items())
        out.append(_sigmoid(z))
    return out


def main() -> None:
    rows = build_residual_features()
    names = sorted({n for r in rows for n in r.features})
    assert "rank_gap" in names

    print("ARM (a) — paired walk-forward refit, 22 vs 21 features")
    with_rank = {(r.date, r.tour, r.player_a, r.player_b): (r, p)
                 for r, p in walk_forward(rows, names)}
    without_names = [n for n in names if n != "rank_gap"]
    without_rank = walk_forward(rows, without_names)
    diffs_a: list[tuple[dt.date, float]] = []
    for row, p_without in without_rank:
        key = (row.date, row.tour, row.player_a, row.player_b)
        matched = with_rank.get(key)
        if matched is None:
            continue
        _, p_with = matched
        diffs_a.append((row.date,
                        _log_loss(p_without, row.won) - _log_loss(p_with, row.won)))
    print(f"  paired rows: {len(diffs_a):,}")
    _paired("with rank_gap over without (refit both ways)", diffs_a,
            alpha=BONFERRONI_ALPHA)

    print("\nARM (a') — fixed deployed artifact, rank_gap withheld vs present")
    print("  The serve-path estimand: the site's old arithmetic against its new one.")
    scored_rows = [r for r, _p in without_rank]
    present = _score_fixed(scored_rows, withhold_rank=False)
    withheld = _score_fixed(scored_rows, withhold_rank=True)
    diffs_ap = [(row.date,
                 _log_loss(p_broken, row.won) - _log_loss(p_fixed, row.won))
                for row, p_fixed, p_broken in zip(scored_rows, present, withheld,
                                                  strict=True)]
    _paired("present over withheld (fixed coefficients)", diffs_ap,
            alpha=BONFERRONI_ALPHA)
    moved = sum(1 for (_, d) in diffs_ap if d != 0.0)
    print(f"  rows where the paths disagree at all: {moved:,} of {len(diffs_ap):,} "
          f"({100 * moved / len(diffs_ap):.1f}%)")

    print("\nARM (b) — latest-prior-match rank as a proxy for fixture-time rank")
    latest: dict[tuple[str, str], tuple[int, dt.date]] = {}
    by_bucket: dict[str, list[float]] = collections.defaultdict(list)
    exact = 0
    compared = 0
    from tennis_edge.corpus import default_vintage_root, load_corpus
    from tennis_edge.refresh import latest_vintage
    vintage = latest_vintage(default_vintage_root())
    assert vintage is not None
    matches, _stats = load_corpus(vintage.root)
    for match in matches:
        for player, true_rank in ((match.player_a, match.rank_a),
                                  (match.player_b, match.rank_b)):
            known = latest.get((match.tour, player))
            if known is not None and true_rank is not None:
                proxy_rank, seen_on = known
                staleness = (match.match_date - seen_on).days
                bucket = ("<=7d" if staleness <= 7 else
                          "<=28d" if staleness <= 28 else
                          "<=90d" if staleness <= 90 else ">90d")
                error = abs(math.log1p(proxy_rank) - math.log1p(true_rank))
                by_bucket[bucket].append(error)
                exact += int(proxy_rank == true_rank)
                compared += 1
            if true_rank is not None:
                latest[(match.tour, player)] = (true_rank, match.match_date)
    print(f"  comparisons: {compared:,}   proxy exactly right: "
          f"{100 * exact / compared:.1f}%")
    for bucket in ("<=7d", "<=28d", "<=90d", ">90d"):
        errors = by_bucket[bucket]
        if not errors:
            continue
        errors.sort()
        median = errors[len(errors) // 2]
        p90 = errors[int(0.9 * len(errors))]
        print(f"  staleness {bucket:<6} n={len(errors):8,}  "
              f"|log1p error| median {median:.4f}  p90 {p90:.4f}")

    print("\nREADING")
    print("  (a) lower-bounds the forfeiture; (a') is the exact serve-path term the site")
    print("  was paying. Both deploy-irrelevant: the fix restores the measured model")
    print("  either way. (b) says how good the served fallback rank is, and where the")
    print("  stale tail lives.")


if __name__ == "__main__":
    main()
