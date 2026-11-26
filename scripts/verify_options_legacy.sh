#!/usr/bin/env bash
# OPTIONS-ERA VERIFICATION: the three steps verify_engine.sh required until 2026-11-26 (feature-map lint, regime drill,
# and the ship grid: compile, harvest suites, MOT). Runnable on its own for any change to the options engine or the
# harvest path; not required for ALL GREEN, and it stamps no sentinel.
# Usage on the VPS: bash scripts/verify_options_legacy.sh     (exit 0 only if all three are green)
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
PY=./.venv/bin/python; [ -x "$PY" ] || PY=python3
rc=0
echo "=== 1/3 feature map lint ==="
if $PY scripts/feature_map_lint.py > /tmp/verify_lint.log 2>&1; then tail -1 /tmp/verify_lint.log; else cat /tmp/verify_lint.log | head -12; rc=1; fi
echo "=== 2/3 regime drill ==="
if $PY scripts/regime_drill.py > /tmp/verify_drill.log 2>&1; then tail -2 /tmp/verify_drill.log; else grep -n "FAIL" /tmp/verify_drill.log | head -8; tail -2 /tmp/verify_drill.log; rc=1; fi
echo "=== 3/3 ship gate (compile + suites + MOT) ==="
rm -f /tmp/gate_green
if [ -f "$HOME/vps_ship_grid.sh" ]; then
  bash "$HOME/vps_ship_grid.sh" > /tmp/verify_gate.log 2>&1
  if [ -f /tmp/gate_green ]; then tail -3 /tmp/verify_gate.log; else grep -n "FAIL\|MISSING" /tmp/verify_gate.log | head -8; tail -3 /tmp/verify_gate.log; rc=1; fi
else
  echo "gate script $HOME/vps_ship_grid.sh not found"; rc=1
fi
echo "=== verdict ==="
if [ $rc -eq 0 ]; then echo "LEGACY OPTIONS GATE: GREEN"; else echo "LEGACY OPTIONS GATE: RED (see /tmp/verify_*.log)"; fi
exit $rc
