"""The candidate model: fit the market's *residual*, letting each correction take its own sign.

Six architectures failed and the fitted combination gave the model a weight indistinguishable
from zero. The single-feature diagnostic (``serve_features.py``) then said something those
six builds could not have discovered, because every one of them combined a model probability
with the market in one direction:

**the market's errors do not all point the same way.** Ranking and rating gaps came back with
*negative* coefficients — the closing price over-extrapolates them — while the serve-based
point model came back positive. Bundled into one composite probability those cancel, which is
exactly the ``alpha ~ 0`` that TE-0004 reported.

So this fits them as what they are: separate corrections to the price, each free to take its
own sign, with the market logit as an unpenalised offset.

The features come from :mod:`tennis_edge.residual_features` and the fit from
:mod:`tennis_edge.residual_model` — this file is the *evidence harness* around them, not a
second copy of either. That separation exists because the same model now has to be
deployable, and a model whose definition lives inside an experiment cannot be.

Three things it reports, in the order that decides whether any of it counts:

1. **Forecast quality** — log-score gain over the market, day-clustered.
2. **Money, with a control, at venues that exist.** Settlement is split: first the places a
   UK resident can actually bet into — Betfair Exchange, Bet365, Ladbrokes, Unibet — and
   then, clearly separated, the columns that are not places. Pinnacle has not accepted UK
   customers since 2014 and the panel maximum is arithmetic over twenty books rather than a
   counter anyone stands at; both are kept as diagnostics and neither is a return. Each
   venue reports the model's rule and then the identical rule driven by the market's own
   probability, because betting whenever a probability clears the break-even at the best
   available quote is partly price selection no matter what supplies the probability. The
   control's return is that selection; only the difference can be credited to the model.
3. **A placebo** on the whole procedure, which asks whether it can manufacture a gain from
   nothing at all.

Everything is out-of-sample by year, the staking rule is parameter-free — bet whenever the
probability clears the quoted break-even, flat stakes, no required-edge buffer — and every
interval is day-clustered. A required-edge threshold is the classic place to launder an
overfit, since every threshold is a parameter and the best one is always found afterwards.
"""
import collections
import datetime as dt
import math
from dataclasses import replace
from typing import Sequence, cast

from tennis_edge.feature_cache import FeatureRow as Row
from tennis_edge.metrics import BetResult, clustered_bootstrap, summarise_bets
from tennis_edge.residual_features import build_residual_features
from tennis_edge.residual_model import L2, fit_coefficients
from tennis_edge.venues import (VENUES, Kind, Venue, benchmark_keys, by_key,
                                uk_settlement_keys)

FIRST_SCORED_YEAR = 2012
BOOTSTRAP_DRAWS = 2000

#: Commission charged on net winnings. A traditional bookmaker charges none because its
#: margin is already inside the quote; the exchange charges 2% because its quote has no
#: margin in it. Derived from the venue registry rather than listed by hand so that adding a
#: venue cannot leave it silently free to bet at.
COMMISSIONS = {v.key: (0.02 if v.kind is Kind.EXCHANGE else 0.0) for v in VENUES}


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(min(z, 30.0), -30.0)))


def fit(rows: list[Row], names: list[str]) -> dict[str, float]:
    """The shared fit. Kept as a one-liner so the experiment reads the same as before."""
    return fit_coefficients(rows, names, l2=L2)


def predict(row: Row, beta: dict[str, float]) -> float:
    return _sigmoid(row.market_logit + math.fsum(
        b * row.features[n] for n, b in beta.items() if n in row.features))


def _mean_gain(rows: Sequence[object]) -> float:
    """Mean per-match log-score gain over a bootstrap resample of whole days."""
    return math.fsum(cast(tuple[dt.date, float], r)[1] for r in rows) / len(rows)


def _day_of(row: object) -> dt.date:
    return cast(tuple[dt.date, float], row)[0]


def report_forecast(scored: list[tuple[Row, float]]) -> None:
    print(f"\nFORECAST QUALITY, out-of-sample ({len(scored):,} matches)")
    gains = [(row.date,
              math.log(p if row.won else 1 - p)
              - math.log(_sigmoid(row.market_logit) if row.won
                         else 1 - _sigmoid(row.market_logit)))
             for row, p in scored]
    mean = math.fsum(g for _d, g in gains) / len(gains)
    lo, hi = clustered_bootstrap(gains, statistic=_mean_gain, cluster_of=_day_of,
                                 draws=BOOTSTRAP_DRAWS)
    verdict = "beats the price" if lo > 0 else (
        "worse than the price" if hi < 0 else "indistinguishable from the price")
    print(f"  log-score gain over the market  {mean:+.6f} nats  "
          f"95% CI [{lo:+.6f}, {hi:+.6f}]  -> {verdict}")


def _settle_at(scored: list[tuple[Row, float]], book: str,
               use_model: bool) -> list[BetResult]:
    results: list[BetResult] = []
    for row, p in scored:
        probability = p if use_model else _sigmoid(row.market_logit)
        # (probability of this side, its price, whether it won). Carried together so the
        # side a bet is on can never drift apart from the outcome it settles by.
        for side, odds, won in (
            (probability, row.odds_a.get(book), bool(row.won)),
            (1.0 - probability, row.odds_b.get(book), not row.won),
        ):
            # Commission applies to winnings, so the break-even price is above 1/p. Using
            # 1/p on the exchange would credit the strategy with money Betfair keeps.
            net = 1.0 + (odds - 1.0) * (1.0 - COMMISSIONS[book]) if odds else 0.0
            if odds is None or odds <= 1.0 or side * net <= 1.0:
                continue
            results.append(BetResult(cluster=row.date, odds=odds, stake=1.0,
                                     won=won, commission=COMMISSIONS[book]))
    return results


def _report_one(scored: list[tuple[Row, float]], venue: Venue) -> None:
    model = _settle_at(scored, venue.key, use_model=True)
    control = _settle_at(scored, venue.key, use_model=False)
    if len(model) < 100:
        print(f"\n  {venue.name:<18} {len(model)} bets — too few to score")
        return
    print()
    print("  " + summarise_bets(model, bootstrap=BOOTSTRAP_DRAWS).report(venue.name))
    if len(control) < 100:
        print(f"  {'control':<28}{len(control)} bets — the market's own rule fires "
              f"too rarely to compare")
        return
    print("  " + summarise_bets(control, bootstrap=BOOTSTRAP_DRAWS)
          .report(f"{venue.name} CONTROL"))


def report_money(scored: list[tuple[Row, float]]) -> None:
    """Flat stakes, no buffer: bet whenever the model clears the quoted break-even.

    A required-edge threshold is the classic place to launder an overfit — every threshold
    is a parameter, and the best one is always found after the fact. There is none here.

    **A return is only money if there is an account to place it from.** The venues are split
    in two and never mixed. The first block is the places a UK resident can bet into today:
    Betfair Exchange, Bet365, Ladbrokes, Unibet. The second block is not — Pinnacle stopped
    taking UK customers in 2014, and the panel maximum and average are arithmetic over the
    table rather than counters anyone stands at. Numbers in the second block are diagnostics
    about how sharp the forecast is. They are not returns and must never be headlined as
    though a person could have collected them.

    **The control is the point of this function, not an ornament on it.** A rule that bets
    whenever a probability clears the break-even at the *best* quote is partly a
    price-selection strategy no matter what supplies the probability — it fires wherever
    some book is out of line with the one used for pricing. The control runs the identical
    rule driven by the **market's own** de-vigged probability, with no model correction at
    all. Whatever it earns is attributable to shopping between books; only the difference
    between the two rows can be credited to the model, and if the control earns as much then
    none of it can.

    Within the UK block the ordering still matters. Bet365 and Ladbrokes will restrict an
    account that keeps winning, so a return there is real for as long as the account is
    allowed to exist. Betfair Exchange will not, which is why it is the venue every
    conclusion is finally judged at — and why its two seasons of coverage are the binding
    constraint on this whole project rather than an inconvenience.
    """
    print("\nMONEY, settled at the actual quoted price (flat 1u, no required-edge buffer)")
    print("  Each venue: the model's rule, then the identical rule driven by the market's")
    print("  own probability. The control's return is price selection, not skill.")

    print("\n--- BETTABLE FROM THE UK ---------------------------------------------------")
    for key in uk_settlement_keys():
        venue = by_key(key)
        flag = "restricts winners" if venue.restricts_winners else "does not limit winners"
        print(f"\n  [{venue.name}] {venue.kind.value.lower()}, UK-licensed, {flag}")
        _report_one(scored, venue)

    print("\n--- NOT BETTABLE FROM HERE: diagnostics, not returns ------------------------")
    for key in benchmark_keys():
        venue = by_key(key)
        print(f"\n  [{venue.name}] {venue.access.value} — {venue.note.split('.')[0]}.")
        _report_one(scored, venue)


def placebo(rows: list[Row], names: list[str]) -> None:
    """Re-run the entire procedure with the features detached from their matches.

    The control in :func:`report_money` asks whether the *money* could come from shopping
    between books. This asks the prior question: whether the **procedure** can manufacture a
    forecast gain out of nothing.

    Each row keeps its market price, its odds and its result, and is given another row's
    feature vector from the same season. Every genuine link between a feature and the match
    it describes is destroyed; everything else — sample size, feature correlations, the
    penalty, the walk-forward, the day-clustered interval — is identical. A procedure that
    reports a gain here is reporting one it can also report from noise, and the real number
    means nothing.

    Shuffling *features* rather than *outcomes* is deliberate. TE-0001 recorded that
    shuffling outcomes is invalid: it breaks the price-outcome coupling, and with asymmetric
    payoffs that inflates returns mechanically. That test was run once, proved nothing, and
    is not repeated here.

    The permutation is a fixed rotation within each season rather than a random draw — it
    needs no seed, it is exactly reproducible, and it cannot accidentally leave a row
    holding its own features.
    """
    print("\nPLACEBO: the same procedure, features detached from their matches")
    by_year: dict[int, list[Row]] = collections.defaultdict(list)
    for row in rows:
        by_year[row.date.year].append(row)
    scrambled: list[Row] = []
    for _year, block in sorted(by_year.items()):
        if len(block) < 2:
            continue
        for index, row in enumerate(block):
            donor = block[(index + 1) % len(block)]
            scrambled.append(replace(row, features=donor.features))
    scrambled.sort(key=lambda r: r.date)
    scored = walk_forward(scrambled, names)
    if not scored:
        print("  no out-of-sample years")
        return
    report_forecast(scored)


def walk_forward(rows: list[Row], names: list[str]) -> list[tuple[Row, float]]:
    """Fit on every prior year, predict the next. Never on data the fit has seen."""
    by_year: dict[int, list[Row]] = collections.defaultdict(list)
    for row in rows:
        by_year[row.date.year].append(row)
    ordered = sorted(by_year)
    years = [y for y in ordered if y >= FIRST_SCORED_YEAR]
    out: list[tuple[Row, float]] = []
    # The training set only ever grows, so it is extended year by year rather than rebuilt.
    train: list[Row] = [r for y in ordered if y < years[0] for r in by_year[y]]
    for year in years:
        if len(train) >= 5000:
            beta = fit(train, names)
            for row in by_year[year]:
                out.append((row, predict(row, beta)))
            print(f"  {year}: trained on {len(train):,}, scored {len(by_year[year]):,}",
                  flush=True)
        train.extend(by_year[year])
    return out


def main() -> None:
    rows = build_residual_features()
    names = sorted({n for r in rows for n in r.features})
    coverage = {n: sum(1 for r in rows if n in r.features) for n in names}
    print(f"priceable matches: {len(rows):,}")
    print("feature coverage: " + ", ".join(f"{n} {coverage[n]:,}" for n in names))

    print("\nwalk-forward:")
    scored = walk_forward(rows, names)
    if not scored:
        print("no out-of-sample years")
        return
    # `max` hoisted out of the comprehension deliberately: leaving it inside re-scans every
    # row for every row, which on 96,162 rows is nine billion comparisons and looks exactly
    # like a hung process.
    last_year = max(r.date.year for r in rows)
    final = fit([r for r in rows if r.date.year < last_year], names)
    print("\nCOEFFICIENTS on the final fit (sign is the market's error, not the feature's)")
    for name, value in sorted(final.items(), key=lambda kv: -abs(kv[1])):
        direction = "market under-weights" if value > 0 else "market over-weights"
        print(f"  {name:<24}{value:>+10.4f}   {direction}")

    report_forecast(scored)
    report_money(scored)
    placebo(rows, names)


if __name__ == "__main__":
    main()
