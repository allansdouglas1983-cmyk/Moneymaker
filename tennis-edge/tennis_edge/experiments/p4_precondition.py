"""P4 precondition check — is the derivative-market data there at all? (TE-0017 §3 P4)

The registration is explicit: "The tail archive contains the settlement-registry-v2 usable
derivative markets with sufficient pre-off prints. If it does not, the probe is not run and
the layer is not mourned." This harness answers that one question and nothing else. It fits
no parameters, prices nothing, and reads no outcomes beyond what the priced Match Odds table
already carries.

DECLARATIONS, fixed before the extract is examined
--------------------------------------------------

Registry basis: specs/evidence/tennis-derivative-settlement-semantics-v2.yaml. The four
extracted types are all usable there — COMBINED_TOTAL
(VERIFIED_CONTRACTUALLY_DIFFERENT_BUT_USABLE_WITH_EXCLUSIONS), SET_WINNER, SET_BETTING and
NUMBER_OF_SETS (USABLE_WITH_EXCLUSIONS). HANDICAP is also registry-usable but was not
extracted; its absence can only make this check stricter, never looser, and is recorded in
the output rather than silently forgotten. SET_CORRECT_SCORE and TOURNAMENT_WINNER are
prohibited_from_v1 and are not extracted or counted.

Why two constraints: the production solver (sport_tennis.coherence.solver.identify) solves
two latent serve parameters from two targets, and P4's measurement plan requires the fit to
use derivatives ONLY — excluding Match Odds is what makes the estimate independent of the
price it would correct. Two latents from derivatives alone therefore needs at least two
independent derivative-implied constraints per event. An event with one printed derivative
market cannot be fitted without leaning on Match Odds, which the registration forbids.

A derivative market is PRINT-SUFFICIENT when:
  - its LTP series has >= 6 prints strictly before T-600s (600s before scheduled off —
    the probe's decision snapshot; 6 matches MIN_PRINTS used by the Roll estimator), and
  - at least one of those prints falls within the final hour before T-600s (a series
    whose last trade is hours old is exactly the stale-price failure mode the registration
    cites; it constrains nothing about the T-600 state).

An event is PROBE-ELIGIBLE when:
  - it has >= 2 print-sufficient derivative markets of DISTINCT market types, and
  - its event_id links (via the Match Odds tail extract) to a market_id present in the
    priced v4 table — the probe's question (A) is conditional on contemporaneous Match
    Odds, so an event outside the priced corpus can never contribute a scored row.

PRE-REGISTERED FLOOR — the precondition PASSES only if:
  - probe-eligible events >= 2,000, and
  - those events span >= 100 distinct UTC days (the programme's bootstrap is
    day-clustered; a large n on few clusters is a small experiment wearing a big one's
    clothes).

Below the floor the verdict is FAIL: the probe is not run, the layer is not mourned, and
the negative is recorded (TE-0030). No re-slicing, no threshold softened after seeing the
counts. Truncation flags in the extract header are reported verbatim; a truncated extract
can still PASS (the archive contains at least what it contains) but a FAIL on a truncated
extract is recorded as FAIL-ON-AVAILABLE-DATA, since a fuller extract could only add.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

USABLE_TYPES = ("SET_WINNER", "SET_BETTING", "NUMBER_OF_SETS", "COMBINED_TOTAL")
MIN_PRINTS = 6
SNAPSHOT_SECONDS = 600
RECENCY_SECONDS = 3600
FLOOR_EVENTS = 2000
FLOOR_DAYS = 100

DATA = Path("/home/user/tennis_edge_data/betfair_historical")
DERIVATIVES = DATA / "derivatives_tail.jsonl"
MATCH_ODDS_TAIL = DATA / "match_odds_tail.jsonl"
PRICED_TABLE = DATA / "exchange_prices_600s_v4.jsonl"


def _priced_market_ids() -> set[str]:
    ids: set[str] = set()
    with PRICED_TABLE.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if "market_id" in row:
                ids.add(str(row["market_id"]))
    return ids


def _priced_events(priced_ids: set[str]) -> dict[str, str]:
    """event_id -> priced Match Odds market_id, from the Match Odds tail extract."""
    events: dict[str, str] = {}
    with MATCH_ODDS_TAIL.open(encoding="utf-8") as handle:
        header = json.loads(handle.readline())
        if header.get("kind") != "tennis-edge-betfair-extract-v1":
            raise SystemExit("match_odds_tail.jsonl is not a recognised extract")
        for line in handle:
            row = json.loads(line)
            if str(row.get("market_id")) in priced_ids:
                events[str(row.get("event_id"))] = str(row["market_id"])
    return events


def main() -> None:
    priced_ids = _priced_market_ids()
    priced_events = _priced_events(priced_ids)
    print(f"priced v4 rows link to {len(priced_events):,} tail events "
          f"({len(priced_ids):,} priced market ids)")

    sufficient_by_event: dict[str, set[str]] = defaultdict(set)
    event_day: dict[str, str] = {}
    type_counts: Counter[str] = Counter()
    sufficient_counts: Counter[str] = Counter()
    markets_read = 0

    with DERIVATIVES.open(encoding="utf-8") as handle:
        header = json.loads(handle.readline())
        if header.get("kind") != "tennis-edge-betfair-extract-v1":
            raise SystemExit("derivatives_tail.jsonl is not a recognised extract")
        truncated = bool(header.get("truncated"))
        source_truncated = bool(header.get("source_truncated"))
        print(f"extract header: truncated={truncated} source_truncated={source_truncated} "
              f"types={header.get('market_types')}")
        for line in handle:
            row = json.loads(line)
            market_type = str(row.get("market_type"))
            if market_type not in USABLE_TYPES:
                continue
            markets_read += 1
            type_counts[market_type] += 1
            off_ms = row.get("market_time_ms")
            if not isinstance(off_ms, int):
                continue
            t600 = off_ms - SNAPSHOT_SECONDS * 1000
            pre = [obs for obs in row.get("ltp", []) if obs[0] < t600]
            if len(pre) < MIN_PRINTS:
                continue
            last_print = max(obs[0] for obs in pre)
            if last_print < t600 - RECENCY_SECONDS * 1000:
                continue
            sufficient_counts[market_type] += 1
            event = str(row.get("event_id"))
            sufficient_by_event[event].add(market_type)
            event_day.setdefault(
                event,
                datetime.fromtimestamp(off_ms / 1000, tz=timezone.utc).date().isoformat())

    print(f"\nusable-type derivative markets read: {markets_read:,}")
    for market_type in USABLE_TYPES:
        print(f"  {market_type:<16} extracted {type_counts[market_type]:>7,}   "
              f"print-sufficient {sufficient_counts[market_type]:>7,}")

    multi = {e: t for e, t in sufficient_by_event.items() if len(t) >= 2}
    eligible = {e for e in multi if e in priced_events}
    days = {event_day[e] for e in eligible}
    by_year = Counter(event_day[e][:4] for e in eligible)

    print(f"\nevents with >=1 print-sufficient derivative: {len(sufficient_by_event):,}")
    print(f"events with >=2 distinct sufficient types:   {len(multi):,}")
    print(f"PROBE-ELIGIBLE (also linked to priced MO):   {len(eligible):,} "
          f"across {len(days):,} distinct UTC days")
    for year in sorted(by_year):
        print(f"  {year}: {by_year[year]:,}")

    passed = len(eligible) >= FLOOR_EVENTS and len(days) >= FLOOR_DAYS
    print(f"\nPRECONDITION (floor: >={FLOOR_EVENTS:,} events on >={FLOOR_DAYS} days): "
          f"{'PASS — the probe may be built and run' if passed else 'FAIL'}")
    if not passed:
        qualifier = " (FAIL-ON-AVAILABLE-DATA: extract truncated)" if (
            truncated or source_truncated) else ""
        print(f"the probe is not run and the layer is not mourned{qualifier}; "
              f"HANDICAP was not extracted and could only have added")


if __name__ == "__main__":
    main()
