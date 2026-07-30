"""Export the full betting OPPORTUNITY SET, so staking rules can be traded head-to-head.

WHY THIS EXISTS. The question "which staking rule is best" cannot be answered from theory,
because every rule is optimal for some objective and the objectives conflict. It has to be
measured: run each rule over the same real sequence of settled bets and compare what
actually happened. That needs a frozen, reproducible bet sequence — this file produces it.

WHAT IT EXPORTS, AND WHY IT IS THE OPPORTUNITY SET RATHER THAN THE FIRED BETS. Both sides
of every out-of-sample match that carries an exchange price, with the model's probability,
the market's own de-vigged probability, the price, the outcome and the fill evidence. The
*firing* decision is deliberately NOT applied here, because firing depends on the
commission rate through the break-even probability `1/(1+(O-1)(1-c))`, and commission is a
parameter of the study (2% on the Basic package, 5% on Rewards). Baking one rate in would
silently fix a variable the study is supposed to vary — the exact error TE-0042 documents.

WHAT IT DOES NOT DO. It does not size a stake, choose a rule, or assume a fill. Fill
evidence travels with each row (`support`), so a downstream reading that wants to credit
only supported fills can, and one that credits everything has to say so. None of these
rows is a realised return: Betfair Historical BASIC is a last-trade trace, so `SUPPORTED`
means the market later traded there or better, not that we would have been matched.

Determinism: the walk-forward fit is a ridge solve on a frozen feature cache, so the same
cache and the same code produce byte-identical output. The output records the corpus
vintage, the price table and the feature-set version so a later run can prove it.

Run from tennis-edge/:  python tools/export_bet_sequence.py [--out PATH]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tennis_edge.exchange_prices import ExchangePrice, read_prices  # noqa: E402
from tennis_edge.experiments.residual_edge import walk_forward  # noqa: E402
from tennis_edge.feature_cache import FeatureRow  # noqa: E402
from tennis_edge.fill_evidence import stratify  # noqa: E402
from tennis_edge.residual_features import build_residual_features  # noqa: E402

#: The 600-second horizon table, v4 — v3's exact join plus the S5 per-side LTP ages, and
#: the widest link the project has built. Named explicitly rather than discovered, so two
#: runs cannot silently use different horizons or different links and then be compared as
#: though they were the same measurement. The output filename carries the table name for
#: the same reason.
DEFAULT_PRICES = Path("/home/user/tennis_edge_data/betfair_historical/"
                      "exchange_prices_600s_v4.jsonl")

OUT_DIR = Path("/home/user/tennis_edge_data")

SEQUENCE_KIND = "tennis-edge-bet-sequence-v1"


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


def rows_for(scored: list[tuple[FeatureRow, float]],
             prices: dict[tuple[dt.date, str, str, str], ExchangePrice]) -> list[dict]:
    """One record per (match, side). Probabilities for BOTH the model and the market."""
    out: list[dict] = []
    for row, model_p in scored:
        price = prices.get((row.date, row.tour, row.player_a, row.player_b))
        if price is None:
            continue
        market_p = _sigmoid(row.market_logit)
        sides = (
            ("a", price.odds_a, price.won_a, price.support_a, price.prints_a,
             price.ltp_age_a, model_p, market_p),
            ("b", price.odds_b, not price.won_a, price.support_b, price.prints_b,
             price.ltp_age_b, 1.0 - model_p, 1.0 - market_p),
        )
        for side, odds, won, support, prints, ltp_age, p_model, p_market in sides:
            if odds <= 1:
                # No transactable price on this side. Excluded explicitly rather than
                # dropped silently — the count is reported at the end.
                continue
            out.append({
                "date": row.date.isoformat(),
                "tour": row.tour,
                "player_a": row.player_a,
                "player_b": row.player_b,
                "market_id": price.market_id,
                "side": side,
                # Odds as a string: Decimal in, Decimal out, never a float round-trip.
                "odds": str(odds),
                "p_model": repr(p_model),
                "p_market": repr(p_market),
                "won": bool(won),
                "support": support.value,
                "stratum": stratify(prints).value,
                "prints": int(prints),
                "ltp_age": None if ltp_age is None else int(ltp_age),
            })
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prices", type=Path, default=DEFAULT_PRICES)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    if args.out is None:
        args.out = OUT_DIR / f"bet_sequence__{args.prices.stem}.jsonl"

    if not args.prices.exists():
        raise SystemExit(f"price table not found: {args.prices}")

    print("building residual features ...", flush=True)
    feature_rows = build_residual_features()
    names = sorted({n for r in feature_rows for n in r.features})
    print(f"  {len(feature_rows):,} feature rows, {len(names)} features", flush=True)

    prices = {(p.date, p.tour, p.player_a, p.player_b): p
              for p in read_prices(args.prices)}
    days = {d for d, _t, _a, _b in prices}
    print(f"exchange prices: {len(prices):,} matches, {len(days):,} days, "
          f"{min(days)} .. {max(days)}", flush=True)

    print("walk-forward ...", flush=True)
    scored = walk_forward(feature_rows, names)
    print(f"  {len(scored):,} out-of-sample scored matches", flush=True)

    records = rows_for(scored, prices)
    covered = len({(r["date"], r["tour"], r["player_a"], r["player_b"]) for r in records})
    print(f"opportunity set: {len(records):,} side-prices over {covered:,} matches",
          flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        header = {
            "kind": SEQUENCE_KIND,
            "price_table": args.prices.name,
            "feature_rows": len(feature_rows),
            "feature_names": names,
            "scored_matches": len(scored),
            "priced_matches": covered,
            "side_prices": len(records),
            "note": ("Opportunity set, NOT fired bets. The firing rule depends on the "
                     "commission rate through break-even, so it is applied downstream."),
        }
        handle.write(json.dumps(header, sort_keys=True) + "\n")
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    print(f"wrote {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
