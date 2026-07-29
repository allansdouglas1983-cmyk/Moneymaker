"""Export recent corpus results for the scorecard (TE-0017 S6).

Runs in the weekly Action after the corpus refresh and writes
``artifacts/results.json`` — the file the database pulls on its own schedule, exactly the
credential-free pattern the live state uses. Every row carries the grade keys
precomputed by :func:`tennis_edge.scorecard.grade_key`, so no name logic ever lives in
SQL: the database joins strings the reference implementation produced.

Walkovers and abandonments are exported WITH a null winner rather than dropped — the
grading side needs to see them to mark the prediction NOT_GRADEABLE instead of leaving it
pending forever.

Run from tennis-edge/: ``python tools/export_results.py``.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tennis_edge.corpus import Completion, default_vintage_root, load_corpus  # noqa: E402
from tennis_edge.refresh import latest_vintage  # noqa: E402
from tennis_edge.sackmann import load_matches  # noqa: E402
from tennis_edge.scorecard import grade_key  # noqa: E402

RESULTS_KIND = "tennis-edge-results-v1"

#: Wide enough that a prediction can wait out a rain-delayed tournament and still grade;
#: bounded so the artifact stays small and the pull stays fast.
WINDOW_DAYS = 120

#: Completions where Tennis-Data declares a winner the forecast can be graded against.
#: WALKOVER and ABANDONED export with a null winner and grade as NOT_GRADEABLE.
_WINNER_DEFINED = {Completion.COMPLETED, Completion.RETIRED, Completion.AWARDED,
                   Completion.DISQUALIFIED}


def main() -> int:
    vintage = latest_vintage(default_vintage_root())
    if vintage is None:
        raise SystemExit("no corpus vintage on disk — run the refresh first")
    matches, _stats = load_corpus(vintage.root)
    cutoff = dt.date.today() - dt.timedelta(days=WINDOW_DAYS)

    rows = []
    unkeyed = 0
    for match in matches:
        if match.match_date < cutoff:
            continue
        key_a = grade_key(match.player_a)
        key_b = grade_key(match.player_b)
        if key_a is None or key_b is None or key_a == key_b:
            unkeyed += 1
            continue
        winner_defined = match.completion in _WINNER_DEFINED
        rows.append({
            "match_date": match.match_date.isoformat(),
            "tour": match.tour,
            "key_a": key_a,
            "key_b": key_b,
            "winner_key": (key_a if match.winner_is_a else key_b)
            if winner_defined else None,
            "completion": match.completion.value,
        })

    # The alias table: every name form that reduces to a key in this window, so the
    # database matches prediction names by EXACT string lookup and no name logic ever
    # exists in SQL. Both the raw lowercase form and an ASCII-folded form are exported —
    # a user may type "Muller" or "Müller" and both must land.
    window_keys = {key for row in rows for key in (row["key_a"], row["key_b"])}
    aliases: dict[str, str] = {}

    def alias(name: str, key: str | None) -> None:
        if key is None or key not in window_keys:
            return
        import unicodedata
        raw = name.strip().lower()
        folded = unicodedata.normalize("NFKD", raw).encode(
            "ascii", "ignore").decode("ascii")
        for form in {raw, folded}:
            if form and aliases.get(form, key) == key:
                aliases[form] = key
            elif form in aliases and aliases[form] != key:
                # An ambiguous alias points at two players; it must match neither.
                aliases[form] = ""

    for match in matches:
        if match.match_date >= cutoff:
            alias(match.player_a, grade_key(match.player_a))
            alias(match.player_b, grade_key(match.player_b))
    for row_s in load_matches(families=("main", "qual_chall"),
                              since=cutoff - dt.timedelta(days=365)):
        alias(row_s.winner_name, grade_key(row_s.winner_name))
        alias(row_s.loser_name, grade_key(row_s.loser_name))
    alias_rows = [{"alias": form, "key": key}
                  for form, key in sorted(aliases.items()) if key]

    target = Path(__file__).resolve().parents[2] / "artifacts" / "results.json"
    target.write_text(json.dumps({
        "kind": RESULTS_KIND,
        "corpus_vintage": vintage.vintage_id,
        "window_days": WINDOW_DAYS,
        "rows": rows,
        "aliases": alias_rows,
    }, indent=1) + "\n", encoding="utf-8")
    print(f"{len(rows)} results, {len(alias_rows)} aliases "
          f"({unkeyed} unkeyed results excluded) -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
