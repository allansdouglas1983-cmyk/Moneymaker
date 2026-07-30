"""TE-0040: score the configuration the site actually serves.

The residual model's coefficients were fitted with the Bet365 power-de-vigged price as the
unpenalised offset, and two of its features — ``elo_residual`` and ``point_model_residual``
— are defined as ``logit(estimate) - market_logit``, so they carry that same anchor inside
them. The site serves neither: ``scoring.ts`` anchors to the Betfair back/back pair.

That configuration had never been scored. This harness scores it.

Re-anchoring needs no feature rebuild. Both anchored features are of the form
``logit(estimate) - market_logit``, so replacing the anchor is an exact addition::

    feature_exchange = feature_b365 + (market_logit_b365 - market_logit_exchange)

Both configurations are scored against the SAME exchange baseline, so the comparison is
about the model's anchor and nothing else.

CONTAMINATION, stated up front: the v3 coefficients were fitted on these rows, so neither
level below is out-of-fold. Both configurations carry that contamination equally, which is
why the DIFFERENCE is the reportable quantity and the levels are context only.

Run from tennis-edge/: python tools/served_anchor_check.py
"""
from __future__ import annotations

import collections
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tennis_edge.corpus import default_vintage_root, load_corpus  # noqa: E402
from tennis_edge.devig import power  # noqa: E402
from tennis_edge.exchange_prices import read_prices  # noqa: E402
from tennis_edge.experiments.exchange_settlement import DEFAULT_PRICES  # noqa: E402
from tennis_edge.refresh import latest_vintage  # noqa: E402
from tennis_edge.residual_features import build_residual_features  # noqa: E402

SEED = 20260730
DRAWS = 2000
MODEL = Path(__file__).resolve().parents[2] / "artifacts" / "residual-model-v3.json"

#: The only two features that carry the market anchor inside their definition.
ANCHORED = ("elo_residual", "point_model_residual")


def _logit(p: float) -> float:
    return math.log(p / (1.0 - p))


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(min(z, 30.0), -30.0)))


def _log_score(p: float, won: bool) -> float:
    q = min(max(p if won else 1.0 - p, 1e-12), 1.0 - 1e-12)
    return math.log(q)


def main() -> None:
    coefficients = json.load(open(MODEL))["coefficients"]

    vintage = latest_vintage(default_vintage_root())
    assert vintage is not None
    matches, _stats = load_corpus(vintage.root)
    known = {(m.match_date, m.tour, m.player_a, m.player_b) for m in matches}
    prices = {(p.date, p.tour, p.player_a, p.player_b): p
              for p in read_prices(Path(DEFAULT_PRICES))}

    by_day: dict[object, list[tuple[float, float, float]]] = collections.defaultdict(list)
    shifts: list[float] = []

    for row in build_residual_features():
        key = (row.date, row.tour, row.player_a, row.player_b)
        price = prices.get(key)
        if price is None or key not in known:
            continue
        odds_a, odds_b = float(price.odds_a), float(price.odds_b)
        if not (odds_a > 1.0 and odds_b > 1.0):
            continue

        market_exchange = power([odds_a, odds_b]).probabilities[0]
        anchor_exchange = _logit(market_exchange)
        shift = row.market_logit - anchor_exchange
        shifts.append(abs(shift))

        measured = row.features
        served = dict(measured)
        for name in ANCHORED:
            if name in served:
                served[name] = served[name] + shift

        z_measured = row.market_logit + math.fsum(
            coefficients.get(k, 0.0) * v for k, v in measured.items())
        z_served = anchor_exchange + math.fsum(
            coefficients.get(k, 0.0) * v for k, v in served.items())

        won = bool(row.won)
        baseline = _log_score(market_exchange, won)
        by_day[row.date].append((
            _log_score(_sigmoid(z_measured), won) - baseline,
            _log_score(_sigmoid(z_served), won) - baseline,
            _sigmoid(z_measured) - _sigmoid(z_served),
        ))

    flat = [x for day in by_day.values() for x in day]
    if not flat:
        print("no joined rows")
        return

    shifts.sort()

    def q(values: list[float], p: float) -> float:
        return values[int(p * (len(values) - 1))]

    print(f"joined {len(flat):,} rows across {len(by_day):,} days\n")
    print("  ANCHOR SHIFT |b365 logit - exchange logit|")
    print(f"    median {q(shifts, 0.5):.4f}  p75 {q(shifts, 0.75):.4f}  "
          f"p90 {q(shifts, 0.90):.4f}  p99 {q(shifts, 0.99):.4f} logits")

    print("\n  LOG-SCORE GAIN over the same exchange baseline (NOT out-of-fold):")
    print(f"    as MEASURED (b365 offset, b365-anchored features) "
          f"{sum(x[0] for x in flat) / len(flat):+.6f} nats")
    print(f"    as SERVED   (exchange offset, re-anchored features) "
          f"{sum(x[1] for x in flat) / len(flat):+.6f} nats")

    moves = sorted(abs(x[2]) for x in flat)
    print(f"\n  |p_measured - p_served|  median {q(moves, 0.5):.4f}  "
          f"p90 {q(moves, 0.90):.4f}  p99 {q(moves, 0.99):.4f}")

    days = list(by_day.values())
    rng = random.Random(SEED)
    draws = []
    for _ in range(DRAWS):
        sample: list[tuple[float, float, float]] = []
        for _ in range(len(days)):
            sample.extend(days[rng.randrange(len(days))])
        draws.append(sum(x[1] - x[0] for x in sample) / len(sample))
    draws.sort()
    point = sum(x[1] - x[0] for x in flat) / len(flat)
    lo, hi = draws[int(0.025 * DRAWS)], draws[int(0.975 * DRAWS)]
    verdict = "clears zero" if lo > 0 else ("below zero" if hi < 0 else "spans zero")
    print(f"\n  SERVED minus MEASURED, day-clustered: {point:+.6f} nats  "
          f"CI95=[{lo:+.6f},{hi:+.6f}]  {verdict}")
    print("\nDiagnostic. Licenses no rule change: the levels are not out-of-fold and the "
          "difference is a restatement of one frozen model under two anchors.")


if __name__ == "__main__":
    main()
