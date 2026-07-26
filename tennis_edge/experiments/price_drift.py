"""Line movement: does the exchange price drift predictably, and can it be bet early?

Every previous test in this package pitted a tennis model against the **closing** price —
the sharpest number the market ever produces, and the hardest possible benchmark. This asks
a different question, one no tennis model is needed for:

**The price two days out is not the price at the off. Is that movement predictable?**

If it is, the strategy is not "know more about tennis than the market" but "know which way
this market is going to move, and take the early price before it does". That is a market
microstructure question, and it is the one genuinely untried direction with data in hand:
the June ADVANCED corpus carries ~45 hours of trace per market at one-second resolution,
with book depth and cumulative matched volume.

Three things get measured, in order of what would have to be true:

1. **Does the price sharpen?** Log loss of the midpoint at each horizon. If the T-10m price
   is no better than the T-24h price, there is no information arriving and nothing to front-
   run. If it *is* better, information is arriving and the question becomes whether it is
   visible in advance.
2. **Is the drift predictable?** Regress the realised logit drift on the book state at the
   early horizon — size imbalance, volume imbalance, spread. These are the classic
   microstructure signals and none of them is a restatement of the price itself.
3. **Does it pay?** The only test that matters. Back at the **early best-back price** — the
   one actually available then, not the midpoint, not the later price — whenever the drift
   model says the price is about to shorten, and settle against the real outcome with
   commission on net winnings.

Every number is out-of-sample: the drift model is fitted on the first half of the month by
date and applied to the second. A drift model fitted on the days it then trades would be
measuring its own memory.
"""
import math
from dataclasses import dataclass
from decimal import Decimal

from tennis_edge.betfair import MarketHistory, read_markets
from tennis_edge.combine import fit_combination, logit
from tennis_edge.corpus import default_vintage_root, load_corpus
from tennis_edge.exchange import COMMISSION, expected_value
from tennis_edge.exchange_link import link_markets
from tennis_edge.refresh import latest_vintage

#: Seconds before the scheduled off. 24h out most markets are formed but thin.
HORIZONS = (86_400, 43_200, 21_600, 10_800, 3_600, 1_800, 600, 120)

CORPUS = ("/tmp/claude-0/-home-user-Moneymaker/"
          "b09554bc-9729-5d86-bb7c-43d4f555802d/scratchpad/pilot-data/extracted")


@dataclass(frozen=True)
class Snapshot:
    """The market's state for one selection at one horizon."""

    probability: float
    back_price: Decimal
    back_size: Decimal
    lay_size: Decimal
    spread_ticks: float
    volume: float


def _midpoint(history: MarketHistory, a: int, b: int, horizon: int) -> float | None:
    back_a = history.best_back_at(a, seconds_before_off=horizon)
    back_b = history.best_back_at(b, seconds_before_off=horizon)
    lay_a = history.best_lay_at(a, seconds_before_off=horizon)
    lay_b = history.best_lay_at(b, seconds_before_off=horizon)
    if None in (back_a, back_b, lay_a, lay_b):
        return None
    assert back_a and back_b and lay_a and lay_b
    imp_a = (1.0 / float(back_a.price) + 1.0 / float(lay_a.price)) / 2.0
    imp_b = (1.0 / float(back_b.price) + 1.0 / float(lay_b.price)) / 2.0
    total = imp_a + imp_b
    return imp_a / total if total > 0 else None


def _snapshot(history: MarketHistory, a: int, b: int, horizon: int) -> Snapshot | None:
    probability = _midpoint(history, a, b, horizon)
    back_a = history.best_back_at(a, seconds_before_off=horizon)
    lay_a = history.best_lay_at(a, seconds_before_off=horizon)
    back_b = history.best_back_at(b, seconds_before_off=horizon)
    if probability is None or back_a is None or lay_a is None or back_b is None:
        return None
    from price_contracts.ladder import index_of

    volume_a = history.traded_volume_at(a, seconds_before_off=horizon) or Decimal(0)
    volume_b = history.traded_volume_at(b, seconds_before_off=horizon) or Decimal(0)
    total_volume = float(volume_a + volume_b)
    return Snapshot(
        probability=probability,
        back_price=back_a.price,
        back_size=back_a.size,
        lay_size=lay_a.size,
        spread_ticks=float(index_of(lay_a.price) - index_of(back_a.price)),
        volume=(float(volume_a) / total_volume) if total_volume > 0 else 0.5,
    )


def main() -> None:
    markets = read_markets(CORPUS)
    vintage = latest_vintage(default_vintage_root())
    assert vintage is not None
    matches, _stats = load_corpus(vintage.root)
    linked = link_markets(markets, matches).linked
    print(f"linked markets: {len(linked):,}\n")

    # ---------------------------------------------------------- 1. does it sharpen?
    print("1. DOES THE PRICE SHARPEN AS THE OFF APPROACHES?")
    print(f"{'horizon':>10}{'markets':>10}{'log loss':>11}{'brier':>9}")
    traces: list[tuple[dict[int, Snapshot], int, MarketHistory, int, int]] = []
    for row in linked:
        a = row.selection_for_player_a
        b = (row.quote.selection_b if a == row.quote.selection_a
             else row.quote.selection_a)
        snaps = {}
        for horizon in HORIZONS:
            snap = _snapshot(row.market, a, b, horizon)
            if snap is not None:
                snaps[horizon] = snap
        if snaps:
            traces.append((snaps, 1 if row.match.winner_is_a else 0, row.market, a, b))

    for horizon in HORIZONS:
        block = [(s[horizon].probability, y) for s, y, _m, _a, _b in traces if horizon in s]
        if len(block) < 50:
            print(f"{horizon:>10}{len(block):>10}   (too few)")
            continue
        ll = -math.fsum(math.log(p if y else 1 - p) for p, y in block) / len(block)
        br = math.fsum((p - y) ** 2 for p, y in block) / len(block)
        print(f"{horizon:>10}{len(block):>10,}{ll:>11.5f}{br:>9.5f}")

    # ---------------------------------------------------------- 2. is drift predictable?
    early, late = 21_600, 600          # T-6h -> T-10m
    rows = [(s, y, m, a, b) for s, y, m, a, b in traces if early in s and late in s]
    print(f"\n2. IS THE DRIFT T-6h -> T-10m PREDICTABLE?  ({len(rows):,} markets)")
    if len(rows) < 200:
        print("   too few markets with both horizons; stopping here")
        return

    drifts = [logit(s[late].probability) - logit(s[early].probability)
              for s, _y, _m, _a, _b in rows]
    mean_drift = math.fsum(drifts) / len(drifts)
    abs_drift = math.fsum(abs(d) for d in drifts) / len(drifts)
    print(f"   mean signed drift {mean_drift:+.4f} logits, mean |drift| {abs_drift:.4f}")

    # Signals available at the EARLY horizon only.
    def signals(s: dict[int, Snapshot]) -> tuple[float, ...]:
        e = s[early]
        size_total = float(e.back_size + e.lay_size)
        return (
            (float(e.back_size) / size_total - 0.5) if size_total > 0 else 0.0,
            e.volume - 0.5,
            min(e.spread_ticks, 20.0) / 20.0,
        )

    names = ("size_imbalance", "volume_imbalance", "spread")
    print(f"   {'signal':<20}{'corr with drift':>18}{'t':>8}")
    for i, name in enumerate(names):
        xs = [signals(s)[i] for s, _y, _m, _a, _b in rows]
        mx = math.fsum(xs) / len(xs)
        my = mean_drift
        cov = math.fsum((x - mx) * (d - my) for x, d in zip(xs, drifts)) / len(xs)
        vx = math.fsum((x - mx) ** 2 for x in xs) / len(xs)
        vy = math.fsum((d - my) ** 2 for d in drifts) / len(drifts)
        corr = cov / math.sqrt(vx * vy) if vx > 0 and vy > 0 else 0.0
        t = corr * math.sqrt(max(len(xs) - 2, 1) / max(1 - corr * corr, 1e-12))
        print(f"   {name:<20}{corr:>18.4f}{t:>8.2f}")

    # ---------------------------------------------------------- 3. does it pay?
    print("\n3. DOES BETTING THE EARLY PRICE PAY?  (out-of-sample by date)")
    dated = sorted(rows, key=lambda r: r[2].market_time_ms)
    split = len(dated) // 2
    train, test = dated[:split], dated[split:]

    # Fit the drift model on the FIRST half only: predict the late probability from the
    # early probability and the early book state. A model fitted on the days it then trades
    # would be measuring its own memory.
    train_rows = [(max(min(0.5 + 4.0 * signals(s)[0], 0.999), 0.001),
                   s[early].probability, y) for s, y, _m, _a, _b in train]
    try:
        fit = fit_combination(train_rows)
    except ValueError as error:
        print(f"   drift model refused to fit: {error}")
        return
    print(f"   fitted on {len(train):,} markets: signal weight {fit.alpha:+.4f} "
          f"(t {fit.alpha_t:+.2f}), price weight {fit.beta:.4f}")

    bets = 0
    profit = 0.0
    for s, y, _m, _a, _b in test:
        signal = max(min(0.5 + 4.0 * signals(s)[0], 0.999), 0.001)
        predicted = 1.0 / (1.0 + math.exp(
            -(fit.alpha * logit(signal) + fit.beta * logit(s[early].probability))))
        price = s[early].back_price
        edge = expected_value(probability=predicted, price=price, commission=COMMISSION)
        if edge > 0.02:
            bets += 1
            net = 1.0 + (float(price) - 1.0) * (1.0 - float(COMMISSION))
            profit += (net - 1.0) if y else -1.0
    print(f"   test markets {len(test):,}  bets {bets:,}  "
          + (f"unit return {profit:+.2f}  ROI {100 * profit / bets:+.2f}%"
             if bets else "no bets"))
    if bets >= 30:
        se = math.sqrt(max(bets, 1)) / bets
        print(f"   per-bet SE roughly {100 * se:.2f}%  -> "
              f"{'inside' if abs(profit / bets) < 2 * se else 'outside'} two standard errors")


if __name__ == "__main__":
    main()
