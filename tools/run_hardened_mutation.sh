#!/bin/bash
# Hardened mutation run wrapper (STAGE3-0006 §4/§5).
#
# Fixes both facets of MUTATION_HARNESS_PROCESS_ISOLATION_DEFECT:
#   1. the test-command runs under tools/isolated_exec.py (set in the config), so a hanging mutant's
#      whole descendant tree is reaped on timeout — no ORPHANED_RUNAWAY_PYTEST_PROCESS escapes;
#   2. the TARGET SOURCE is restored and PROVEN byte-identical to HEAD on EXIT — even if cosmic-ray
#      exec dies/is killed mid-mutant (the failure that left solver.py mutated on 2026-07-22). An
#      EXIT/INT/TERM trap runs the restore; a pre-run restore guarantees a clean start; and the run
#      is RESUMABLE (cosmic-ray exec continues an existing session), so an interrupted run is
#      recovered by simply re-invoking this wrapper.
#
# Usage: tools/run_hardened_mutation.sh <config.toml> <session.sqlite> <module_path>
# Exit:  0 restored+verified; 3 SOURCE_RESTORE_FAILED (a gate stop).
set -u
CONFIG="$1"; SESSION="$2"; MODULE="$3"
ROOT="/home/user/Moneymaker"
cd "$ROOT" || exit 2

restore() { git checkout -- "$MODULE" 2>/dev/null; }
trap restore EXIT INT TERM

restore                                   # clean start regardless of prior state
[ -f "$SESSION" ] || uv run cosmic-ray init "$CONFIG" "$SESSION"
uv run cosmic-ray exec "$CONFIG" "$SESSION"
RC=$?
restore

EXPECT="$(git rev-parse "HEAD:$MODULE")"
GOT="$(git hash-object "$MODULE")"
if [ "$EXPECT" != "$GOT" ]; then
  echo "SOURCE_RESTORE_FAILED: $MODULE expected=$EXPECT got=$GOT"
  exit 3
fi
echo "SOURCE_RESTORED_OK: $MODULE=$GOT exec_rc=$RC"
