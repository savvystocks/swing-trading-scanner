#!/usr/bin/env bash
# ONE-COMMAND VERIFICATION (learned from the 2026-09-11 workshop: an agent must be able to run the
# real thing). Runs the feature-map lint, the regime drill and the ship gate (compile, harvest
# suites, MOT) and prints one screen: the three healthy lines or the first failure of each.
# Usage on the VPS: bash scripts/verify_engine.sh            (exit 0 only if all three are green)
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
PY=./.venv/bin/python; [ -x "$PY" ] || PY=python3
rc=0
echo "=== 1/3 feature map lint ==="
if $PY scripts/feature_map_lint.py > /tmp/verify_lint.log 2>&1; then tail -1 /tmp/verify_lint.log; else cat /tmp/verify_lint.log | head -12; rc=1; fi
echo "=== 2/3 regime drill ==="
if $PY scripts/regime_drill.py > /tmp/verify_drill.log 2>&1; then tail -2 /tmp/verify_drill.log; else grep -n "FAIL" /tmp/verify_drill.log | head -8; tail -2 /tmp/verify_drill.log; rc=1; fi
echo "=== 3/3 ship gate (compile + suites + MOT) ==="
rm -f /tmp/gate_green /tmp/verify_green
if [ -f "$HOME/vps_ship_grid.sh" ]; then
  bash "$HOME/vps_ship_grid.sh" > /tmp/verify_gate.log 2>&1
  if [ -f /tmp/gate_green ]; then tail -3 /tmp/verify_gate.log; else grep -n "FAIL\|MISSING" /tmp/verify_gate.log | head -8; tail -3 /tmp/verify_gate.log; rc=1; fi
else
  echo "gate script $HOME/vps_ship_grid.sh not found"; rc=1
fi
echo "=== verdict ==="
rm -f /tmp/verify_green
if [ $rc -eq 0 ]; then
  echo "VERIFY: ALL GREEN"
  bash scripts/gate_fresh.sh --stamp        # the sentinel names THIS tree; any edit makes it stale
else
  echo "VERIFY: RED (see /tmp/verify_*.log)"
fi
exit $rc
