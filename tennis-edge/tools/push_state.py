"""Push the fitted model and the walk-forward state into Postgres.

This is the seam between the part that thinks and the part that serves. Everything upstream
of it is Python running weekly on a scheduler; everything downstream is a web page reading
rows. Neither knows the other exists beyond these tables, which is what makes the site keep
working when nothing is running.

**The model table is append-only and this script honours that.** A refit inserts a new row
keyed by its digest and flips ``is_current``; it never updates an existing row. A prediction
recorded eight months ago names its digest, so the coefficients that produced it can always
be recovered even after four refits. ``on conflict do nothing`` on the digest makes a re-run
of the same fit a no-op rather than an error, which is what lets the weekly job be safely
retried.

**Player state is replace-in-place and that is correct.** It is not evidence; it is a
derived cache of "what the ratings are now", rebuilt from the corpus every week. The
evidence is the prediction snapshot, which copies the state date it used. Keeping old
rating rows would imply a history the state file does not actually carry.

Talks to PostgREST over HTTPS with the service-role key, so it needs no database driver and
no connection pooling — the GitHub runner has network and nothing else.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Sequence

#: PostgREST rejects very large bodies and a slow runner can time out on one huge insert.
#: Chunking also means a transient failure loses one batch rather than the whole push.
BATCH = 500

_TABLE_PATH = "/rest/v1/{table}"


def _request(url: str, key: str, payload: bytes, *, prefer: str) -> None:
    request = urllib.request.Request(url, data=payload, method="POST")
    request.add_header("apikey", key)
    request.add_header("Authorization", f"Bearer {key}")
    request.add_header("Content-Type", "application/json")
    request.add_header("Content-Profile", "tennis")
    request.add_header("Prefer", prefer)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            response.read()
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:2000]
        raise SystemExit(f"{url} -> {error.code}: {detail}") from error


def _post(base: str, key: str, table: str, rows: Sequence[dict[str, Any]], *,
          on_conflict: str | None, merge: bool) -> None:
    """Insert ``rows`` in batches. ``merge`` upserts; otherwise conflicts are ignored."""
    if not rows:
        return
    url = base.rstrip("/") + _TABLE_PATH.format(table=table)
    if on_conflict:
        url += f"?on_conflict={on_conflict}"
    prefer = "resolution=merge-duplicates" if merge else "resolution=ignore-duplicates"
    for start in range(0, len(rows), BATCH):
        chunk = rows[start:start + BATCH]
        _request(url, key, json.dumps(chunk).encode("utf-8"), prefer=prefer)
        print(f"  {table}: {min(start + BATCH, len(rows))}/{len(rows)}", flush=True)


def model_row(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "digest": model["digest"],
        "coefficients": model["coefficients"],
        "feature_names": model["feature_names"],
        "feature_set_version": model["feature_set_version"],
        "l2": model["l2"],
        "trained_from": model["trained_from"],
        "trained_through": model["trained_through"],
        "trained_rows": model["trained_rows"],
        "is_current": True,
    }


def state_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    as_of = state["as_of"]
    return [
        {
            "tour": entry["tour"],
            "player": entry["name"],
            "as_of": as_of,
            "elo": entry["elo"],
            "surface_elo": entry["surface_elo"],
            "weighted_elo": entry["weighted_elo"],
            "matches": entry["matches"],
            "last_played": entry["last_played"],
            "serve_rate": entry["serve_rate"],
            "return_rate": entry["return_rate"],
            "serve_points": entry["serve_points"],
            "serve_matches": entry["serve_matches"],
            "pyramid_elo": entry["pyramid_elo"],
            "pyramid_surface_elo": entry["pyramid_surface_elo"],
            "pyramid_matches": entry["pyramid_matches"],
            "pyramid_last_played": entry["pyramid_last_played"],
            "pyramid_recent_14d": entry["pyramid_recent_14d"],
            "pyramid_tour_share": entry["pyramid_tour_share"],
        }
        for entry in state["players"]
    ]


def main(argv: Sequence[str]) -> int:
    base = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not base or not key:
        print("set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY", file=sys.stderr)
        return 2

    root = Path(argv[1]) if len(argv) > 1 else Path("artifacts")
    model = json.loads((root / "residual-model.json").read_text(encoding="utf-8"))
    state = json.loads((root / "live-state.json").read_text(encoding="utf-8"))

    rows = state_rows(state)
    print(f"model {model['digest'][:23]}…  state {state['as_of']}  {len(rows)} players")

    # The new fit goes in first and claims is_current; the partial unique index means the
    # previous current row must be stood down in the same breath, so this is one upsert.
    _post(base, key, "model", [model_row(model)], on_conflict="digest", merge=False)
    _post(base, key, "player_state", rows, on_conflict="tour,player", merge=True)
    print("pushed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
