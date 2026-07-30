"""DR-TENNIS-STAKING-007: re-derive the DR-004/005 staking arithmetic at 2% commission.

The completed deep research (DR-003/004/005) computed its entire chain — Kelly fractions
by price, expressibility thresholds, and the "edge interval spans zero" condition — at 5%
commission, the TE-0042 error the founder attested was wrong from the start (TE-0044
correction). This script re-runs the SAME chain at the corrected 2% rate. It changes no
premise and invents no number: the KL displacement is DR-004's (+0.001 nats), the chain
is DR-004's (KL -> delta -> commission -> EV/b), and the validation gate is that the 5%
column must reproduce DR-005's published table BEFORE the 2% column is trusted.

Deterministic, no inputs, prints the tables the findings document quotes.
"""
from __future__ import annotations

from decimal import Decimal, getcontext

getcontext().prec = 40

NATS = Decimal("0.001")          # DR-004's measured displacement input
MIN_STAKE = Decimal("1")         # GBP, DR-005 verified (7 Feb 2022)

# DR-005's published @5% table, the validation gate for the chain implementation.
DR005_AT_5PCT = {
    "1.30": ("+1.24%", "4.36%"),
    "1.50": ("+1.43%", "3.00%"),
    "2.00": ("+1.86%", "1.96%"),
    "3.00": ("+2.81%", "1.48%"),
    "5.00": ("+4.68%", "1.23%"),
}


def _ln(x: Decimal) -> Decimal:
    return x.ln()


def kl(p: Decimal, q: Decimal) -> Decimal:
    return p * _ln(p / q) + (1 - p) * _ln((1 - p) / (1 - q))


def delta_for(q: Decimal, nats: Decimal) -> Decimal:
    """Solve KL(q+delta || q) = nats for delta > 0 by bisection. Exact to 1e-30."""
    lo, hi = Decimal(0), Decimal(1) - q - Decimal("1e-30")
    for _ in range(200):
        mid = (lo + hi) / 2
        if kl(q + mid, q) < nats:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def chain(odds: Decimal, commission: Decimal) -> tuple[Decimal, Decimal]:
    """DR-004's chain at one price: (ROI per unit stake, full-Kelly fraction)."""
    q = 1 / odds
    p = q + delta_for(q, NATS)
    b = (odds - 1) * (1 - commission)
    ev = p * b - (1 - p)
    return ev, ev / b


def main() -> None:
    prices = [Decimal(s) for s in ("1.30", "1.50", "2.00", "3.00", "5.00")]

    print("VALIDATION — the chain must reproduce DR-005's @5% table:")
    ok = True
    for odds in prices:
        ev, f = chain(odds, Decimal("0.05"))
        roi_s = f"{ev * 100:+.2f}%"
        f_s = f"{f * 100:.2f}%"
        want_roi, want_f = DR005_AT_5PCT[str(odds)]
        match = "OK" if (roi_s == want_roi and f_s == want_f) else "MISMATCH"
        ok &= match == "OK"
        print(f"  O={odds}: ROI {roi_s} (want {want_roi})  fullKelly {f_s} "
              f"(want {want_f})  {match}")
    if not ok:
        raise SystemExit("chain does not reproduce DR-005 — 2% column not emitted")

    print("\nTHE SAME CHAIN AT 2% (TE-0044 founder-attested rate):")
    print("  odds | ROI @2% | full Kelly | on GBP 100 | full expressible from | "
          "half from | quarter from")
    for odds in prices:
        ev, f = chain(odds, Decimal("0.02"))
        full_from = MIN_STAKE / f
        print(f"  {odds} | {ev * 100:+.2f}% | {f * 100:.2f}% | "
              f"GBP {f * 100:.2f} | GBP {full_from:.2f} | GBP {2 * full_from:.2f} | "
              f"GBP {4 * full_from:.2f}")

    print("\nDR-003 CONDITION CHECK (measured, TE-0043 raw sweep, supported fills, "
          "day-clustered CI95):")
    rows = [("0.00", "+2.32", "+0.62", "+4.06", 25_174),
            ("0.01", "+3.22", "+1.31", "+5.20", 16_563),
            ("0.02", "+3.86", "+1.37", "+6.29", 9_793),
            ("0.03", "+4.10", "+0.89", "+7.38", 5_474),
            ("0.04", "+5.03", "+0.72", "+9.44", 2_862)]
    for threshold, central, lower, upper, bets in rows:
        print(f"  min_edge {threshold}: {central}% [{lower}%, {upper}%]  "
              f"({bets:,} bets)  lower bound {'>0 CLEARS' if Decimal(lower) > 0 else 'spans'}")

    central = Decimal("3.86")
    lower = Decimal("1.37")
    print(f"\nOPERATIVE THRESHOLD (min_edge 0.02): central {central}%, lower {lower}%, "
          f"conservative displacement Delta_e = {central - lower}pp = "
          f"{(central - lower) / 100} per unit stake")


if __name__ == "__main__":
    main()
