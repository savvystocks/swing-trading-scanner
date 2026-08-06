#!/bin/sh
# ENGINE HEARTBEAT WATCHDOG (VPS side, owner escalation 2026-08-06). Lives OUTSIDE GitHub
# Actions on purpose: on 08-06 the engine lost most of a trading day to cycle timeouts and a
# dead dispatcher, and every alarm that lived inside GHA died with it. This watches the
# engine's own commit heartbeat ("sandbox lab data" after every successful cycle) from the
# outside. Absence pages: heartbeat older than 35 min during market hours -> Telegram, loud.
# Cron: */15 14-20 * * 1-5 (UTC). sh-compatible (dash) - the 07-22 lesson.
set -u
REPO="/home/poller/swing-trading-scanner"
cd "$REPO" || exit 0
. ./.harvest_env 2>/dev/null || true

alarm() {
  MSG="$1"
  echo "$(date -u +%FT%TZ) ALARM: ${MSG}"
  if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
    curl -fsS -m 15 "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d chat_id="${TELEGRAM_CHAT_ID}" -d text="ENGINE WATCH: ${MSG}" >/dev/null || true
  fi
}

# market-hours guard (UTC): 13:40-20:05 Mon-Fri, skip outside
HHMM=$(date -u +%H%M)
DOW=$(date -u +%u)
[ "$DOW" -gt 5 ] && exit 0
[ "$HHMM" -lt 1340 ] && exit 0
[ "$HHMM" -gt 2005 ] && exit 0

git fetch -q origin main 2>/dev/null || { alarm "git fetch failed - cannot see the heartbeat"; exit 0; }
LAST=$(git log -1 --format=%ct origin/main 2>/dev/null || echo 0)
NOW=$(date -u +%s)
AGE=$(( (NOW - LAST) / 60 ))
if [ "$AGE" -gt 35 ]; then
  alarm "engine heartbeat is ${AGE} min old during market hours - cycles are NOT completing (GHA timeout / dispatcher down / platform incident). Running VPS FAILOVER exit pass now."
  # FAILOVER (2026-08-06): exits-only engine pass on this box - manages open positions while
  # GHA is dead; its push refreshes the heartbeat, which quiets this alarm until stale again.
  git pull -q --rebase -X theirs 2>/dev/null || true
  . ./.venv/bin/activate 2>/dev/null || true
  python scripts/engine_failover_exits.py >> /home/poller/engine_failover.log 2>&1 || \
    alarm "FAILOVER ITSELF FAILED - open positions are UNMANAGED. Manual intervention needed."
else
  echo "$(date -u +%FT%TZ) ok: heartbeat ${AGE} min"
fi
