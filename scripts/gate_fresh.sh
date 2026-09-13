#!/usr/bin/env bash
# GATE FRESHNESS (BREAKDOWNS 2026-09-13: a commit went out on a leftover green sentinel after the
# lint had failed and the gate never ran). scripts/verify_engine.sh writes /tmp/verify_green as
# "<HEAD sha> <hash of the working tree's diff and status>" ONLY when everything is green. This
# script exits 0 only if that sentinel describes the tree as it is RIGHT NOW - any edit, any new
# file, any commit since the green run makes it stale. Ship chains gate the commit on this, never
# on the existence of a file.
#   bash scripts/gate_fresh.sh          -> exit 0 fresh / 1 stale or missing (prints why)
#   bash scripts/gate_fresh.sh --stamp  -> write the sentinel for the current tree (verify_engine.sh only)
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
SENT=/tmp/verify_green
state() {
  printf '%s %s\n' "$(git rev-parse HEAD 2>/dev/null)" "$( (git status --porcelain --untracked-files=no; git diff HEAD) 2>/dev/null | md5sum | cut -c1-16)"
}
if [ "${1:-}" = "--stamp" ]; then
  state > "$SENT"; echo "gate sentinel stamped: $(cat "$SENT")"; exit 0
fi
[ -f "$SENT" ] || { echo "gate: no green sentinel - run bash scripts/verify_engine.sh"; exit 1; }
NOW=$(state); WAS=$(cat "$SENT")
if [ "$NOW" = "$WAS" ]; then echo "gate: fresh ($WAS)"; exit 0; fi
echo "gate: STALE - sentinel '$WAS' vs tree '$NOW'; the tree changed since the last green run"; exit 1
