#!/usr/bin/env bash
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 1
mkdir -p "$REPO/data"
LOG="$REPO/data/poller.log"
{
  echo "=== $(date -u +%FT%TZ) poller run ==="
  git pull --ff-only origin main
  set -a
  [ -f "$REPO/.harvest_env" ] && . "$REPO/.harvest_env"
  set +a
  [ -f "$REPO/.venv/bin/activate" ] && . "$REPO/.venv/bin/activate"
  python poller.py --once
} >> "$LOG" 2>&1
if [ "$(stat -c%s "$LOG" 2>/dev/null || echo 0)" -gt 5242880 ]; then
  mv -f "$LOG" "$LOG.1"
fi
