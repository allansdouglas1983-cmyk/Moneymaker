"""Append the week's automatic forecasts to ``artifacts/forecasts.json``.

MUST run BEFORE the state rebuild in the weekly Action: it scores with the PREVIOUS
run's committed ``live-state.json``, whose pre-match existence is enforced by git
history. Running it after the rebuild would grade a state that has already absorbed the
week's results, and every number it produced would be quietly wrong.

Append-only: rows already present are never rewritten or re-emitted; the file is the
predictor's accumulating public record. Run from tennis-edge/:
``python tools/export_forecasts.py``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tennis_edge.corpus import default_vintage_root, load_corpus  # noqa: E402
from tennis_edge.forecast_ledger import (  # noqa: E402
    FORECASTS_KIND,
    row_key,
    weekly_forecasts,
)
from tennis_edge.live_state import load_state  # noqa: E402
from tennis_edge.refresh import latest_vintage  # noqa: E402
from tennis_edge.residual_model import load_model  # noqa: E402

ARTIFACTS = Path(__file__).resolve().parents[2] / "artifacts"
LEDGER = ARTIFACTS / "forecasts.json"


def main() -> int:
    vintage = latest_vintage(default_vintage_root())
    if vintage is None:
        raise SystemExit("no corpus vintage on disk — run the refresh first")
    matches, _stats = load_corpus(vintage.root, completed_only=False)
    snapshot = load_state(ARTIFACTS / "live-state.json")
    model = load_model(ARTIFACTS / "residual-model.json")

    existing_rows: list[dict[str, object]] = []
    if LEDGER.exists():
        payload = json.loads(LEDGER.read_text())
        if payload.get("kind") != FORECASTS_KIND:
            raise SystemExit(f"{LEDGER} is not a {FORECASTS_KIND} file; refusing")
        existing_rows = payload["rows"]

    new_rows, exclusions = weekly_forecasts(
        snapshot, model, matches, {row_key(r) for r in existing_rows})

    all_rows = existing_rows + new_rows
    LEDGER.write_text(json.dumps({
        "kind": FORECASTS_KIND,
        "rows": all_rows,
    }, indent=None, separators=(",", ":")) + "\n")
    print(f"forecasts: {len(new_rows)} new rows from state {snapshot.as_of} "
          f"({len(all_rows)} total); exclusions {dict(sorted(exclusions.items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
