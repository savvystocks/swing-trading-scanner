#!/usr/bin/env bash
# ONE-COMMAND VERIFICATION (learned from the 2026-09-11 workshop: an agent must be able to run the
# real thing). Since 2026-11-26 (owner decision) ALL GREEN requires the FX gate, scripts/verify_fx.sh:
# the live OANDA-practice book, the risk engine, the prop-firm rules and the cost model. The options-era
# steps (feature-map lint, regime drill, harvest suites, MOT) run separately as
# scripts/verify_options_legacy.sh and are not required here.
# Usage on the VPS: bash scripts/verify_engine.sh            (exit 0 only if the FX gate is green)
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
rc=0
rm -f /tmp/gate_green /tmp/verify_green
echo "=== FX gate (scripts/verify_fx.sh) ==="
bash scripts/verify_fx.sh > /tmp/verify_fx.log 2>&1 || rc=1
cat /tmp/verify_fx.log
echo "=== verdict ==="
if [ $rc -eq 0 ]; then
  echo "VERIFY: ALL GREEN"
  bash scripts/gate_fresh.sh --stamp        # the sentinel names THIS tree; any edit makes it stale
else
  echo "VERIFY: RED (see /tmp/verify_fx.log)"
fi
exit $rc
