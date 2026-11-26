#!/usr/bin/env bash
# FX GATE (owner decision 2026-11-26): the code that trades now. Compiles the live OANDA-practice book, the risk engine
# and the research modules it is judged by, then runs every suite under tests/fx/ and prints one line per suite.
# Usage: bash scripts/verify_fx.sh      (exit 0 and "FX GATE: ALL GREEN" only if every suite passes)
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
PY="${VERIFY_PY:-./.venv/bin/python}"; [ -x "$PY" ] || command -v "$PY" >/dev/null 2>&1 || PY=python3
rc=0; pass=0; total=0
if $PY -m py_compile scripts/fx_s26_alerts.py scripts/fx_oanda_orders.py scripts/fx_risk_engine.py scripts/fx_veto_dossier.py scripts/fx_veto_run.py scripts/fx_veto_scoreboard.py research/costs.py research/prop_rules.py; then
  echo "compile: ok"
else
  echo "compile: FAIL"; rc=1
fi
for t in tests/fx/test_*.py; do
  out=$($PY "$t" 2>&1); code=$?
  last=$(printf '%s\n' "$out" | tail -1)
  if [ $code -ne 0 ]; then printf '%s\n' "$out" | grep "^FAIL\|Error" | head -8; rc=1; fi
  echo "$last"
  if [[ "$last" =~ ([0-9]+)/([0-9]+)\ passed$ ]]; then
    pass=$((pass + BASH_REMATCH[1])); total=$((total + BASH_REMATCH[2]))
  else
    rc=1
  fi
done
if [ $rc -eq 0 ] && [ $total -gt 0 ]; then echo "FX GATE: ALL GREEN ($pass/$total checks)"; exit 0; fi
echo "FX GATE: RED ($pass/$total checks)"; exit 1
