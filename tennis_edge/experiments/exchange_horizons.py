"""Does the edge live in the *early* exchange price rather than the closing one?

Every measurement in this programme so far has been against a **closing** price, and beating
a closing price is the hardest version of the problem — it is the price after every informed
participant has finished acting. It is also not the price anyone bets at. A personal bettor
places at some point before the off, and the question that actually decides whether a system
is worth running is narrower and easier:

**is the model better than the price *at the moment the bet would go on*?**

The June ADVANCED corpus is the only data here that can answer it. It carries the full
one-second two-sided ladder for each market from formation to the off, so the same model can
be scored against the price at T-24h, T-6h, T-1h and T-10m and the answer read off as a
curve rather than a single number.

Three things are being separated, and the design keeps them apart deliberately:

1. **Does the exchange price sharpen?** If the T-24h price is already as good as the T-10m
   price, no information arrives and there is nothing to be early to.
2. **Is the model's advantage larger early?** Scored as log-score gain over the exchange
   midpoint at that same horizon — so both sides of the comparison use identical information
   timing, and a gain cannot come from the model quietly knowing something later.
3. **Does it survive the actual cost of transacting?** Settled at the horizon's real
   **best-back** price — not the midpoint — with Betfair commission on net winnings. The
   midpoint is a probability estimator; nobody transacts at it. Conflating the two is what
   made an earlier version of this look profitable.

**An extrapolation worth stating plainly.** The residual coefficients are fitted with a
*bookmaker closing logit* as the offset, because that is the only price the long corpus
carries. Applying them to an *exchange* logit at an *early* horizon assumes the market's
error has the same shape at both, which is an assumption and not a result. It is the honest
thing to do with the data available; it is not the same as having fitted them there, and any
gain seen here should be treated as provisional until a long exchange history exists.
"""
import datetime as dt
import math

from tennis_edge.corpus import default_vintage_root, load_corpus
from tennis_edge.exchange import COMMISSION
from tennis_edge.experiments.residual_edge import (
    BOOTSTRAP_DRAWS,
    Row,
    _day_of,
    _mean_gain,
    _sigmoid,
    build,
    fit,
)
from tennis_edge.metrics import BetResult, clustered_bootstrap, summarise_bets
from tennis_edge.refresh import latest_vintage
from tennis_edge.snapshots import HORIZONS, MarketSnapshot, load_snapshots

CACHE = ("/tmp/claude-0/-home-user-Moneymaker/"
         "b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/june_snapshots.jsonl")

#: Everything strictly before this trains; the exchange corpus is scored. The exchange data
#: begins here, so this is a data boundary rather than a chosen split.
EXCHANGE_FROM = dt.date(2026, 6, 1)


def _key(date: str, tour: str, player_a: str, player_b: str) -> tuple[str, str, str, str]:
    """Join key: date, tour, and the unordered pair.

    Unordered because the corpus and the exchange snapshot may name the same match with the
    players the other way round; the orientation is then restored from the snapshot's own
    ``player_a``, so a swap cannot silently invert a probability.
    """
    first, second = sorted((player_a, player_b))
    return (date, tour, first, second)


def _anchor(midpoint_a: float, row: Row, beta: dict[str, float], aligned: bool) -> float:
    """Apply the residual correction to the exchange midpoint, in the snapshot's orientation.

    The features were built with the corpus row's player A as the subject. When the snapshot
    names the pair the other way round, the correction changes sign — that is the whole of
    the transposition risk, handled once, here.
    """
    correction = math.fsum(b * row.features[n] for n, b in beta.items()
                           if n in row.features)
    if not aligned:
        correction = -correction
    return _sigmoid(math.log(midpoint_a / (1 - midpoint_a)) + correction)


def main() -> None:
    vintage = latest_vintage(default_vintage_root())
    assert vintage is not None
    matches, _stats = load_corpus(vintage.root)
    rows = build(matches)
    names = sorted({n for r in rows for n in r.features})

    train = [r for r in rows if r.date < EXCHANGE_FROM]
    beta = fit(train, names)
    print(f"trained on {len(train):,} matches before {EXCHANGE_FROM}")

    # Index the model's view by the join key. The snapshot carries the corpus names the
    # identity bridge resolved it to, so this is a real join and not a guess from the date.
    by_key: dict[tuple[str, str, str, str], list[Row]] = {}
    for row in rows:
        by_key.setdefault(
            _key(row.date.isoformat(), row.tour, row.player_a, row.player_b), []
        ).append(row)

    snapshots = load_snapshots(CACHE)
    print(f"snapshot cache: {len(snapshots):,} markets")

    paired: list[tuple[MarketSnapshot, Row, bool]] = []
    ambiguous = unmatched = 0
    for snapshot in snapshots:
        candidates = by_key.get(
            _key(snapshot.match_date, snapshot.tour,
                 snapshot.player_a, snapshot.player_b), [])
        candidates = [r for r in candidates if r.features]
        if not candidates:
            unmatched += 1
            continue
        if len(candidates) > 1:
            # Two corpus matches for the same pair on the same day. Dropped rather than
            # guessed: a wrong pairing is indistinguishable from a wrong model.
            ambiguous += 1
            continue
        row = candidates[0]
        # The snapshot's A and the corpus row's A may be different players. Recording which
        # is which here means every probability below can be stated in the snapshot's
        # orientation without a second chance to transpose it.
        paired.append((snapshot, row, row.player_a == snapshot.player_a))
    print(f"paired to a model view: {len(paired):,}  "
          f"(unmatched {unmatched:,}, ambiguous {ambiguous:,})\n")
    if len(paired) < 30:
        print("too few paired markets to score — the exchange corpus and the priced corpus")
        print("do not overlap enough at this vintage.")
        return

    print(f"{'horizon':>9}{'markets':>9}{'mkt log loss':>14}{'model gain':>13}"
          f"{'95% CI (day-clustered)':>30}")
    for horizon in HORIZONS:
        block = [(s, r, aligned, st) for s, r, aligned in paired
                 if (st := s.at(horizon)) is not None]
        if len(block) < 30:
            print(f"{horizon:>9}{len(block):>9}   (too few)")
            continue
        market_loss = -math.fsum(
            math.log(st.midpoint_a if s.won_a else 1 - st.midpoint_a)
            for s, _r, _al, st in block) / len(block)
        gains: list[tuple[dt.date, float]] = []
        for snapshot, row, aligned, state in block:
            anchored = _anchor(state.midpoint_a, row, beta, aligned)
            base = state.midpoint_a
            gains.append((
                dt.date.fromisoformat(snapshot.match_date),
                math.log(anchored if snapshot.won_a else 1 - anchored)
                - math.log(base if snapshot.won_a else 1 - base),
            ))
        mean = math.fsum(g for _d, g in gains) / len(gains)
        lo, hi = clustered_bootstrap(gains, statistic=_mean_gain, cluster_of=_day_of,
                                     draws=BOOTSTRAP_DRAWS)
        print(f"{horizon:>9}{len(block):>9,}{market_loss:>14.5f}{mean:>+13.6f}"
              f"   [{lo:+.6f}, {hi:+.6f}]{'  *' if lo > 0 or hi < 0 else ''}")

    print("\nMONEY at the horizon's actual best-back price, Betfair commission on winnings")
    for horizon in HORIZONS:
        block = [(s, r, aligned, st) for s, r, aligned in paired
                 if (st := s.at(horizon)) is not None]
        if len(block) < 30:
            continue
        results: list[BetResult] = []
        for snapshot, row, aligned, state in block:
            anchored = _anchor(state.midpoint_a, row, beta, aligned)
            for probability, price, won in (
                (anchored, state.back_a, bool(snapshot.won_a)),
                (1 - anchored, state.back_b, not snapshot.won_a),
            ):
                if price <= 1.0:
                    continue
                # Commission applies to winnings, so the break-even price is higher than
                # 1/p. Using 1/p here would credit the strategy with money Betfair keeps.
                if probability * (1.0 + (price - 1.0) * (1.0 - float(COMMISSION))) <= 1.0:
                    continue
                results.append(BetResult(
                    cluster=dt.date.fromisoformat(snapshot.match_date),
                    odds=price, stake=1.0, won=won, commission=float(COMMISSION)))
        if len(results) < 30:
            print(f"  T-{horizon:>6}s  {len(results)} bets — too few to score")
            continue
        print("  " + summarise_bets(results, bootstrap=BOOTSTRAP_DRAWS)
              .report(f"T-{horizon}s"))

    print(f"\nCommission {float(COMMISSION):.1%} on net winnings; break-even price is "
          f"1/p adjusted for it,\nnot 1/p. Prices are best-back, never the midpoint — "
          f"the midpoint is an estimator\nand nobody transacts at it.")


if __name__ == "__main__":
    main()
