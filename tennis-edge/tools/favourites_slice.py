"""EXPLORATORY diagnostic: the frozen bet rule sliced by favourites vs outsiders.

Founder question (2026-07-29): "ones the model thinks will likely win, but more than
the market does" — i.e. bets where the model's side has probability > 0.5. This slices
the EXACT frozen TE-0019 machinery's bets by that definition; nothing is refit and no
rule changes. LABELLED EXPLORATORY: a founder-requested subgroup reading, reported
beside the pooled number, never in place of it (no cherry-picked subgroup may be
labelled overall performance).

Run from tennis-edge/: python tools/favourites_slice.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tennis_edge.experiments.exchange_settlement import (  # noqa: E402
    DEFAULT_PRICES,
    report,
    settle,
)
from tennis_edge.experiments.residual_edge import walk_forward  # noqa: E402
from tennis_edge.exchange_prices import read_prices  # noqa: E402
from tennis_edge.fill_evidence import FillSupport  # noqa: E402
from tennis_edge.residual_features import build_residual_features  # noqa: E402


def main() -> None:
    rows = build_residual_features()
    names = sorted({n for r in rows for n in r.features})
    prices = {(p.date, p.tour, p.player_a, p.player_b): p
              for p in read_prices(Path(DEFAULT_PRICES))}
    scored = walk_forward(rows, names)
    covered = [(r, p) for r, p in scored
               if (r.date, r.tour, r.player_a, r.player_b) in prices]
    bets = settle(covered, prices, use_model=True)

    # The bet's implied model probability of its own side exceeds 1/2 exactly when the
    # side's break-even-plus-edge does; odds <= 2.0 marks the market's own favourite.
    # Two definitions, both reported: the model's favourite, and the market's.
    supported = [b for b in bets if b.support is FillSupport.SUPPORTED]
    print(f"total bets {len(bets):,}; supported {len(supported):,}\n")
    for label, subset in (
        ("ALL bets, supported (the frozen headline)", supported),
        ("model-favourite: model side p > 0.5", [
            b for b in supported
            if (1.0 / (1.0 + (b.odds - 1.0) * 0.98)) + b.edge > 0.5]),
        ("market-favourite: odds <= 2.0", [b for b in supported if b.odds <= 2.0]),
        ("outsiders: odds > 2.0", [b for b in supported if b.odds > 2.0]),
    ):
        report(label, subset)
    print("\nEXPLORATORY subgroup diagnostic (founder-requested slice, 2026-07-29).")
    print("The pooled supported number remains the only headline.")


if __name__ == "__main__":
    main()
