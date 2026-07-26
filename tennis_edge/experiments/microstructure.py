"""Every microstructure question the June corpus can answer, run off the snapshot cache.

Six architectures have now failed to beat the closing price, and the fitted combination gave
the model a weight indistinguishable from zero across seventeen years. That closes the
*tennis modelling* line. It says nothing about the line this file tests, which needs no
tennis knowledge at all:

**the price two days out is not the price at the off — is that movement predictable?**

The tests run in the order things would have to be true, and each one can kill the next:

1. **Does the price sharpen?** Log loss at each horizon. If the late price is no better than
   the early one, no information is arriving and there is nothing to anticipate.
2. **Does the market move systematically?** Signed drift by price band, with an
   always-back-A control so any drift in the data itself is visible before any strategy is
   read.
3. **Is drift predictable from the early book?** Correlation of realised drift with size
   imbalance, volume share and spread — all readable at the early horizon, none a
   restatement of the price.
4. **Does the favourite-longshot bias pay?** The oldest and most replicated bias in betting
   markets. Bet it directly at the early best-back price.
5. **Does any of it survive costs?** Settled at the actual early back price with commission
   on net winnings, out-of-sample by date.

Run ``scratchpad/build_cache.py`` first; this reads only the cache.
"""
import collections
import math
from decimal import Decimal

from tennis_edge.combine import logit
from tennis_edge.exchange import COMMISSION, expected_value
from tennis_edge.snapshots import HORIZONS, MarketSnapshot, load_snapshots

CACHE = ("/tmp/claude-0/-home-user-Moneymaker/"
         "b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/june_snapshots.jsonl")
EARLY, LATE = 21_600, 600


def _stats(values: list[float]) -> tuple[float, float]:
    """Mean and its standard error."""
    n = len(values)
    mean = math.fsum(values) / n
    if n < 2:
        return mean, float("inf")
    var = math.fsum((v - mean) ** 2 for v in values) / (n - 1)
    return mean, math.sqrt(var / n)


def sharpening(snapshots: list[MarketSnapshot]) -> None:
    print("1. DOES THE PRICE SHARPEN AS THE OFF APPROACHES?")
    print(f"   {'horizon':>9}{'markets':>9}{'log loss':>11}{'brier':>9}{'mean spread':>13}")
    for horizon in HORIZONS:
        block = [(st, s.won_a) for s in snapshots
                 if (st := s.at(horizon)) is not None]
        if len(block) < 50:
            print(f"   {horizon:>9}{len(block):>9}   (too few)")
            continue
        ll = -math.fsum(math.log(st.midpoint_a if y else 1 - st.midpoint_a)
                        for st, y in block) / len(block)
        br = math.fsum((st.midpoint_a - y) ** 2 for st, y in block) / len(block)
        spread = math.fsum(st.spread_ticks_a for st, _y in block) / len(block)
        print(f"   {horizon:>9}{len(block):>9,}{ll:>11.5f}{br:>9.5f}{spread:>13.2f}")


def drift(snapshots: list[MarketSnapshot]) -> list[MarketSnapshot]:
    rows = [s for s in snapshots if s.at(EARLY) and s.at(LATE)]
    print(f"\n2. HOW DOES THE MARKET MOVE, T-6h -> T-10m?  ({len(rows):,} markets)")
    if len(rows) < 100:
        print("   too few markets with both horizons")
        return rows
    print(f"   {'early band':<20}{'n':>7}{'mean drift':>12}{'t':>8}{'won':>9}")
    bands = ((0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0))
    for lo, hi in bands:
        block = [s for s in rows if lo <= s.at(EARLY).midpoint_a < hi]  # type: ignore[union-attr]
        if len(block) < 30:
            continue
        moves = [logit(s.at(LATE).midpoint_a) - logit(s.at(EARLY).midpoint_a)  # type: ignore[union-attr]
                 for s in block]
        mean, se = _stats(moves)
        strike = math.fsum(float(s.won_a) for s in block) / len(block)
        print(f"   p_early {lo:.1f}-{hi:.1f}{'':<8}{len(block):>7,}{mean:>+12.4f}"
              f"{mean / se:>8.2f}{strike:>9.1%}")
    allmoves = [logit(s.at(LATE).midpoint_a) - logit(s.at(EARLY).midpoint_a)  # type: ignore[union-attr]
                for s in rows]
    mean, se = _stats(allmoves)
    print(f"   {'ALL (control)':<20}{len(rows):>7,}{mean:>+12.4f}{mean / se:>8.2f}")
    return rows


def predictability(rows: list[MarketSnapshot]) -> None:
    print(f"\n3. IS THE DRIFT PREDICTABLE FROM THE EARLY BOOK?  ({len(rows):,} markets)")
    if len(rows) < 100:
        return
    drifts = [logit(s.at(LATE).midpoint_a) - logit(s.at(EARLY).midpoint_a)  # type: ignore[union-attr]
              for s in rows]
    signals = {
        "size_imbalance": [s.at(EARLY).size_imbalance_a - 0.5 for s in rows],  # type: ignore[union-attr]
        "volume_share": [s.at(EARLY).volume_share_a - 0.5 for s in rows],  # type: ignore[union-attr]
        "spread_ticks": [float(s.at(EARLY).spread_ticks_a) for s in rows],  # type: ignore[union-attr]
        "early_logit": [logit(s.at(EARLY).midpoint_a) for s in rows],  # type: ignore[union-attr]
    }
    print(f"   {'signal':<20}{'corr':>10}{'t':>8}")
    my = math.fsum(drifts) / len(drifts)
    vy = math.fsum((d - my) ** 2 for d in drifts) / len(drifts)
    for name, xs in signals.items():
        mx = math.fsum(xs) / len(xs)
        vx = math.fsum((x - mx) ** 2 for x in xs) / len(xs)
        if vx <= 0 or vy <= 0:
            continue
        cov = math.fsum((x - mx) * (d - my) for x, d in zip(xs, drifts)) / len(xs)
        corr = cov / math.sqrt(vx * vy)
        t = corr * math.sqrt(max(len(xs) - 2, 1) / max(1 - corr * corr, 1e-12))
        print(f"   {name:<20}{corr:>10.4f}{t:>8.2f}")


def _settle(snapshot: MarketSnapshot, back_a: bool) -> tuple[float, float]:
    """Return (profit, price) for backing one side at the early best-back price."""
    state = snapshot.at(EARLY)
    assert state is not None
    price = state.back_a if back_a else state.back_b
    won = snapshot.won_a if back_a else 1 - snapshot.won_a
    net = 1.0 + (price - 1.0) * (1.0 - float(COMMISSION))
    return ((net - 1.0) if won else -1.0), price


def bias_strategies(rows: list[MarketSnapshot]) -> None:
    """Bet the favourite-longshot bias directly — the oldest, most replicated bias there is.

    Each plan returns which side to back, or None to sit out. Expressing it that way rather
    than as nested conditions keeps "which side" and "whether to bet" separate, which is
    where the first version of this got itself confused.
    """
    print(f"\n4. FAVOURITE-LONGSHOT BIAS AT THE EARLY PRICE  ({len(rows):,} markets)")
    print(f"   {'strategy':<26}{'bets':>7}{'ROI':>10}{'SE':>9}{'t':>7}")

    def favourite(p: float) -> bool | None:
        return p >= 0.5

    def outsider(p: float) -> bool | None:
        return p < 0.5

    def heavy_favourite(p: float) -> bool | None:
        if p >= 0.8:
            return True
        if p <= 0.2:
            return False
        return None

    def longshot(p: float) -> bool | None:
        if p <= 0.2:
            return True
        if p >= 0.8:
            return False
        return None

    plans = {
        "back the favourite": favourite,
        "back the outsider": outsider,
        "back heavy fav (>=0.8)": heavy_favourite,
        "back longshot (<=0.2)": longshot,
    }
    for name, plan in plans.items():
        results = []
        for snapshot in rows:
            state = snapshot.at(EARLY)
            if state is None:
                continue
            side = plan(state.midpoint_a)
            if side is None:
                continue
            results.append(_settle(snapshot, side)[0])
        if len(results) < 30:
            print(f"   {name:<26}{len(results):>7}   (too few)")
            continue
        mean, se = _stats(results)
        print(f"   {name:<26}{len(results):>7,}{100 * mean:>+9.2f}%"
              f"{100 * se:>8.2f}%{mean / se:>7.2f}")


def drift_strategy(rows: list[MarketSnapshot]) -> None:
    """Out-of-sample by date: fit the sign of the drift on the first half, trade the second."""
    print(f"\n5. TRADING THE DRIFT, OUT-OF-SAMPLE BY DATE  ({len(rows):,} markets)")
    dated = sorted(rows, key=lambda s: s.market_time_ms)
    split = len(dated) // 2
    train, test = dated[:split], dated[split:]
    if len(train) < 100 or len(test) < 100:
        print("   too few markets to split")
        return

    # Simplest honest rule: does size imbalance predict the drift sign in training?
    def imbalance(s: MarketSnapshot) -> float:
        return s.at(EARLY).size_imbalance_a - 0.5  # type: ignore[union-attr]

    def realised(s: MarketSnapshot) -> float:
        return logit(s.at(LATE).midpoint_a) - logit(s.at(EARLY).midpoint_a)  # type: ignore[union-attr]

    agree = sum(1 for s in train if imbalance(s) * realised(s) > 0)
    rate = agree / len(train)
    print(f"   training: imbalance sign matches drift sign {rate:.1%} of the time "
          f"({'informative' if abs(rate - 0.5) > 0.03 else 'coin flip'})")

    direction = 1.0 if rate > 0.5 else -1.0
    results = []
    for snapshot in test:
        signal = direction * imbalance(snapshot)
        if abs(signal) < 0.05:
            continue
        back_a = signal > 0
        state = snapshot.at(EARLY)
        assert state is not None
        price = state.back_a if back_a else state.back_b
        implied = 1.0 / price
        # Only take it when the predicted move covers the cost of crossing.
        if expected_value(probability=implied * 1.02, price=Decimal(str(price)),
                          commission=COMMISSION) <= 0:
            continue
        results.append(_settle(snapshot, back_a)[0])
    if len(results) < 30:
        print(f"   test bets {len(results)} — too few to score")
        return
    mean, se = _stats(results)
    print(f"   test bets {len(results):,}  ROI {100 * mean:+.2f}%  SE {100 * se:.2f}%  "
          f"t {mean / se:+.2f}")


def main() -> None:
    snapshots = load_snapshots(CACHE)
    print(f"snapshot cache: {len(snapshots):,} markets\n")
    sharpening(snapshots)
    rows = drift(snapshots)
    predictability(rows)
    bias_strategies(rows)
    drift_strategy(rows)
    by_band: collections.Counter[str] = collections.Counter()
    for snapshot in rows:
        state = snapshot.at(EARLY)
        assert state is not None
        by_band[f"{int(state.midpoint_a * 5) / 5:.1f}"] += 1
    print("\nearly-price distribution:", dict(sorted(by_band.items())))


if __name__ == "__main__":
    main()
