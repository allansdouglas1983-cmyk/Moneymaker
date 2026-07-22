"""Audit a cosmic-ray mutation session DB for outcome integrity (STAGE3-0006 §5/§6).

Reports, for each session, the exact outcome breakdown so that no non-normal job can be mistaken
for a survivor:

  normal_killed    - worker_outcome NORMAL, test_outcome KILLED   (a genuine detected mutant)
  normal_survived  - worker_outcome NORMAL, test_outcome SURVIVED (a GENUINE survivor)
  incompetent      - test_outcome INCOMPETENT (mutant did not compile/run; not a survivor)
  worker_nonnormal - worker_outcome != NORMAL (timeout / exception / abnormal; NOT a survivor)
  untested         - a mutation_spec with NO work_result row (never ran; NOT a survivor)
  other            - anything else

Only ``normal_survived`` jobs may enter a founder survivor packet. A session is CLEAN when
untested == 0 and worker_nonnormal == 0 and incompetent == 0 and other == 0 — i.e. every job
completed NORMALLY. ``--require-clean`` exits non-zero otherwise (a gate stop).
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def audit(session: Path) -> dict[str, object]:
    con = sqlite3.connect(f"file:{session}?mode=ro", uri=True)
    specs = con.execute("SELECT COUNT(*) FROM mutation_specs").fetchone()[0]
    rows = con.execute(
        """SELECT COALESCE(r.worker_outcome, '<UNTESTED>') AS wo,
                  COALESCE(r.test_outcome, '<NONE>') AS to_,
                  COUNT(*)
           FROM mutation_specs s LEFT JOIN work_results r ON s.job_id = r.job_id
           GROUP BY wo, to_""").fetchall()
    counts = {"normal_killed": 0, "normal_survived": 0, "incompetent": 0,
              "worker_nonnormal": 0, "untested": 0, "other": 0}
    breakdown: list[dict[str, object]] = []
    for wo, to_, n in rows:
        breakdown.append({"worker_outcome": wo, "test_outcome": to_, "count": n})
        if wo == "<UNTESTED>":
            counts["untested"] += n
        elif wo == "NORMAL" and to_ == "KILLED":
            counts["normal_killed"] += n
        elif wo == "NORMAL" and to_ == "SURVIVED":
            counts["normal_survived"] += n
        elif to_ == "INCOMPETENT":
            counts["incompetent"] += n
        elif wo != "NORMAL":
            counts["worker_nonnormal"] += n
        else:
            counts["other"] += n
    clean = (counts["untested"] == 0 and counts["worker_nonnormal"] == 0
             and counts["incompetent"] == 0 and counts["other"] == 0)
    return {"session": str(session), "specs": specs, "tested": specs - counts["untested"],
            "counts": counts, "breakdown": breakdown, "clean": clean,
            "survivors_are_all_normal": True}


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Audit cosmic-ray session DBs for outcome integrity.")
    p.add_argument("sessions", nargs="+", type=Path)
    p.add_argument("--require-clean", action="store_true",
                   help="exit non-zero if any session has untested/non-normal/incompetent jobs")
    args = p.parse_args(argv)
    reports = [audit(s) for s in args.sessions]
    print(json.dumps(reports, indent=2))
    if args.require_clean and not all(r["clean"] for r in reports):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
