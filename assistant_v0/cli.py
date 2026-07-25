"""PERSONAL_TENNIS_ASSISTANT_V0 — local CLI (STAGE3-0003 §9A; completed for V0 release).

Private, single-user, local, offline. Three subcommands:

  assess  — read one manual Match-Odds snapshot JSON, produce the deterministic V0 JSON,
            optionally render the static HTML report and append an immutable pre-match
            record to the local shadow ledger.
  settle  — append a governed outcome to an existing pre-match record and grade the
            probabilities (log loss + Brier). The pre-match record is never rewritten.
  ledger  — print the deterministic probability-quality summary of a local ledger.

No network, no accounts, no credentials, no server, no order placement, no stake, no EV.
Stdlib only (plus the governed local packages).
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

from assistant_v0 import grading as G
from assistant_v0 import html_report
from assistant_v0.manual_input import ManualMarketSnapshot
from assistant_v0.pipeline import RatingLookup, assemble, to_pre_match_record
from assistant_v0.ratings_store import load_rating_lookup
from assistant_v0.shadow_ledger import ShadowLedger

BANNER = "RESEARCH / SHADOW ONLY — NO BET RECOMMENDATION"


def _snapshot_from_dict(d: dict[str, Any]) -> ManualMarketSnapshot:
    return ManualMarketSnapshot(
        competitor_a=d["competitor_a"], competitor_b=d["competitor_b"],
        competitor_a_id=d.get("competitor_a_id"), competitor_b_id=d.get("competitor_b_id"),
        tour=d["tour"], scheduled_start_ms=int(d["scheduled_start_ms"]),
        input_timestamp_ms=int(d["input_timestamp_ms"]), source=d["source"],
        back_a=Decimal(str(d["back_a"])), back_a_size=Decimal(str(d["back_a_size"])),
        lay_a=Decimal(str(d["lay_a"])), lay_a_size=Decimal(str(d["lay_a_size"])),
        back_b=Decimal(str(d["back_b"])), back_b_size=Decimal(str(d["back_b_size"])),
        lay_b=Decimal(str(d["lay_b"])), lay_b_size=Decimal(str(d["lay_b_size"])),
        market_status=d["market_status"], in_play=bool(d["in_play"]),
        market_id=d.get("market_id"), event_id=d.get("event_id"),
    )


def run_snapshot_file(path: str, *, reference_time_ms: int,
                      rating_lookup: RatingLookup | None = None) -> str:
    """Read a manual-snapshot JSON file and return the deterministic V0 output JSON."""
    data = json.loads(Path(path).read_text())
    snap = _snapshot_from_dict(data)
    out = assemble(snap, reference_time_ms=reference_time_ms, rating_lookup=rating_lookup)
    return out.to_json()


def _cmd_assess(args: argparse.Namespace) -> dict[str, Any]:
    lookup: RatingLookup | None = load_rating_lookup(args.ratings) if args.ratings else None
    data = json.loads(Path(args.snapshot).read_text())
    snap = _snapshot_from_dict(data)
    out = assemble(snap, reference_time_ms=args.reference_time_ms, rating_lookup=lookup)
    payload: dict[str, Any] = out.to_dict()

    if args.out:
        Path(args.out).write_text(out.to_json() + "\n")
    if args.html:
        Path(args.html).write_text(html_report.render_html(payload))
    if args.ledger:
        if not args.record_id:
            raise SystemExit("--record-id is required when --ledger is given")
        created = args.created_at_ms if args.created_at_ms is not None else args.reference_time_ms
        ledger = ShadowLedger(args.ledger)
        ledger.append_pre_match(to_pre_match_record(out, record_id=args.record_id,
                                                    created_at_ms=created))
    return payload


def _cmd_settle(args: argparse.Namespace) -> dict[str, Any]:
    ledger = ShadowLedger(args.ledger)
    app = G.settle_in_ledger(ledger, record_id=args.record_id, winner=args.winner)
    return {
        "record_id": app.record_id, "winner": app.winner, "scored": app.scored,
        "market_log_loss": app.market_log_loss, "market_brier": app.market_brier,
        "model_log_loss": app.model_log_loss, "model_brier": app.model_brier,
        "exclusion_reason": app.exclusion_reason,
    }


def _cmd_ledger(args: argparse.Namespace) -> dict[str, Any]:
    return G.summarise_ledger(ShadowLedger(args.ledger))


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="assistant_v0",
        description=f"PERSONAL_TENNIS_ASSISTANT_V0 — {BANNER}")
    sub = ap.add_subparsers(dest="command", required=True)

    a = sub.add_parser("assess", help="assess one manual Match-Odds snapshot")
    a.add_argument("--snapshot", required=True, help="path to a manual market snapshot JSON")
    a.add_argument("--reference-time-ms", type=int, required=True)
    a.add_argument("--ratings", default=None,
                   help="optional frozen F2-v1 rating snapshot JSON (diagnostic only)")
    a.add_argument("--out", default=None, help="optional path to write the JSON output")
    a.add_argument("--html", default=None, help="optional path to write the static HTML report")
    a.add_argument("--ledger", default=None, help="optional shadow-ledger JSONL path")
    a.add_argument("--record-id", default=None, help="ledger record id (required with --ledger)")
    a.add_argument("--created-at-ms", type=int, default=None)
    a.set_defaults(func=_cmd_assess)

    s = sub.add_parser("settle", help="append a governed outcome and grade the probabilities")
    s.add_argument("--ledger", required=True)
    s.add_argument("--record-id", required=True)
    s.add_argument("--winner", required=True, choices=["A", "B"])
    s.set_defaults(func=_cmd_settle)

    lg = sub.add_parser("ledger", help="print the probability-quality summary of a ledger")
    lg.add_argument("--ledger", required=True)
    lg.set_defaults(func=_cmd_ledger)
    return ap


def main(argv: Sequence[str] | None = None) -> dict[str, Any]:
    args = build_parser().parse_args(argv)
    payload: dict[str, Any] = args.func(args)
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return payload


if __name__ == "__main__":
    main()
