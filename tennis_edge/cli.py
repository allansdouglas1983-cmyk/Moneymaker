"""Command line: fit a model, freeze it, and price fixtures with it.

Three subcommands, which are the three things a person does with this.

``fit`` builds the feature matrix (from cache when it can), fits the residual model on
everything up to a cutoff, and writes it to disk with its training window and a digest.
Freezing matters: a prediction recorded today is only evidence if the coefficients that
produced it can be named months later, and a model refitted on every run cannot be held to
anything it said.

``show`` prints a frozen model — coefficients, training window, digest — because a file
whose contents nobody has looked at is not really frozen, it is just old.

``price`` reads fixtures with their quoted prices and prints the model's probability, fair
odds, commission-aware break-even and edge for each. It never prints a recommendation.
``recommendation`` is pinned to ``NOT_EVALUATED``; TE-0007 measured the model's exchange
performance as *undecided at the available power*, and turning an undecided statistical
result into a financial instruction is precisely the failure this programme exists to avoid.

The fixture file is JSON: a list of objects with ``date``, ``tour``, ``player_a``,
``player_b``, ``surface``, ``best_of``, ``odds_a``, ``odds_b``. Prices are strings so they
survive as exact decimals rather than arriving pre-damaged by a float literal.

``state`` walks the corpus and archive once and freezes what pricing needs about each
player — a few scalars each — so that ``price`` computes its own features in milliseconds
instead of ten minutes. That is what makes this a tool rather than a demonstration.

A fixture may still carry an explicit ``features`` map, which overrides the snapshot. That
exists for reproducing a specific historical prediction, not for ordinary use.

Optional per-fixture ``rank_a``/``rank_b`` add the ranking feature. Rankings belong to the
fixture rather than the rating state — they move weekly and the value that matters is the
one current at the match — so they are supplied rather than snapshotted, and omitting them
drops one feature rather than zeroing it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Sequence

from tennis_edge.live_state import build_state, live_features, load_state, save_state
from tennis_edge.residual_features import build_residual_features
from tennis_edge.residual_model import fit_model, load_model, save_model
from tennis_edge.upcoming import Fixture, price_fixture

__all__ = ["main"]

#: Everything strictly before this trains the frozen model. Defaults to today, so a fit run
#: unattended uses every settled match available and nothing that is not.
DEFAULT_MODEL_PATH = Path("artifacts/residual-model.json")
DEFAULT_STATE_PATH = Path("artifacts/live-state.json")

#: A snapshot older than this is reported loudly. Ratings go stale: a player's form, rest
#: and workload all move within a fortnight, and pricing today's match off a month-old state
#: is a quiet accuracy loss rather than an error.
STALE_AFTER_DAYS = 14


def _fit(args: argparse.Namespace) -> int:
    rows = build_residual_features(refresh=args.refresh)
    cutoff = (dt.date.fromisoformat(args.through) if args.through
              else dt.date.today())
    training = [r for r in rows if r.date < cutoff]
    if not training:
        print(f"no rows before {cutoff} — nothing to fit", file=sys.stderr)
        return 1
    names = sorted({n for r in training for n in r.features})
    model = fit_model(training, names)
    save_model(args.out, model)
    print(f"fitted on {model.trained_rows:,} matches "
          f"({model.trained_from} .. {model.trained_through})")
    print(f"digest {model.digest}")
    print(f"written to {args.out}")
    return 0


def _state(args: argparse.Namespace) -> int:
    snapshot = build_state(dt.date.fromisoformat(args.as_of) if args.as_of else None)
    save_state(args.out, snapshot)
    print(f"state as of {snapshot.as_of} from {snapshot.corpus_vintage}")
    print(f"{len(snapshot.players):,} players")
    print(f"written to {args.out}")
    return 0


def _show(args: argparse.Namespace) -> int:
    model = load_model(args.model)
    print(f"model    {args.model}")
    print(f"digest   {model.digest}")
    print(f"trained  {model.trained_rows:,} matches, "
          f"{model.trained_from} .. {model.trained_through}")
    print(f"features {model.feature_set_version}, L2={model.l2}")
    print("\ncoefficients (sign is the market's error, not the feature's):")
    for name, value in sorted(model.coefficients.items(), key=lambda kv: -abs(kv[1])):
        direction = "market under-weights" if value > 0 else "market over-weights"
        print(f"  {name:<26}{value:>+10.4f}   {direction}")
    return 0


def _price(args: argparse.Namespace) -> int:
    model = load_model(args.model)
    snapshot = None
    if Path(args.state).exists():
        snapshot = load_state(args.state)
        age = snapshot.days_old(dt.date.today())
        note = "  STALE — rebuild with `state`" if age > STALE_AFTER_DAYS else ""
        print(f"state as of {snapshot.as_of} ({age}d old){note}")
    else:
        print(f"no state at {args.state} — fixtures will price at the market unless they "
              f"carry their own features. Build one with `state`.")

    payload = json.loads(Path(args.fixtures).read_text(encoding="utf-8"))
    predictions = []
    unpriced = 0
    for entry in payload:
        fixture = Fixture(
            date=dt.date.fromisoformat(entry["date"]),
            tour=entry["tour"],
            player_a=entry["player_a"],
            player_b=entry["player_b"],
            surface=entry.get("surface", "Hard"),
            best_of=int(entry.get("best_of", 3)),
            odds_a=Decimal(str(entry["odds_a"])),
            odds_b=Decimal(str(entry["odds_b"])),
        )
        features = {k: float(v) for k, v in (entry.get("features") or {}).items()}
        if not features and snapshot is not None:
            market = 1.0 / float(fixture.odds_a)
            market = market / (market + 1.0 / float(fixture.odds_b))
            features = live_features(
                snapshot, fixture.tour, fixture.player_a, fixture.player_b,
                surface=fixture.surface, best_of=fixture.best_of,
                market_probability=market, match_date=fixture.date,
                rank_a=entry.get("rank_a"), rank_b=entry.get("rank_b"),
            )
        if not features:
            unpriced += 1
        predictions.append(price_fixture(fixture, features, model))

    if args.json:
        print(json.dumps([p.as_dict() for p in predictions], indent=2, sort_keys=True))
        return 0
    print(f"model {model.digest[:23]}...  trained through {model.trained_through}")
    if unpriced:
        print(f"{unpriced} fixture(s) had no usable state and priced at the market — "
              f"unknown players or too thin a record")
    print()
    for prediction in predictions:
        print(prediction.render())
        print()
    print("This output states probabilities. It authorises no stake, and the model's")
    print("performance at the exchange is undecided at the power available (TE-0007).")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tennis-edge", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    fit = sub.add_parser("fit", help="fit and freeze the residual model")
    fit.add_argument("--out", type=Path, default=DEFAULT_MODEL_PATH)
    fit.add_argument("--through", help="train on matches strictly before this ISO date")
    fit.add_argument("--refresh", action="store_true",
                     help="rebuild the feature cache even if it looks current")
    fit.set_defaults(handler=_fit)

    state = sub.add_parser("state", help="freeze per-player state for live pricing")
    state.add_argument("--out", type=Path, default=DEFAULT_STATE_PATH)
    state.add_argument("--as-of", help="ISO date to snapshot at (default today)")
    state.set_defaults(handler=_state)

    show = sub.add_parser("show", help="print a frozen model")
    show.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    show.set_defaults(handler=_show)

    price = sub.add_parser("price", help="price fixtures from a frozen model")
    price.add_argument("fixtures", type=Path, help="JSON list of fixtures with quotes")
    price.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    price.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)
    price.add_argument("--json", action="store_true", help="machine-readable output")
    price.set_defaults(handler=_price)

    args = parser.parse_args(argv)
    result: int = args.handler(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
