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

BLINDF=/home/poller/.engine_watch_blind
if ! git fetch -q origin main 2>/dev/null; then
  sleep 10
  if ! git fetch -q origin main 2>/dev/null; then
    # BLIND is not DEAD (2026-08-07 lesson: 8 false pages on a 50/50-green day). Count
    # consecutive blind ticks; speak only at 3 (45 min), once per episode, honestly.
    N=$(cat "$BLINDF" 2>/dev/null || echo 0); N=$((N+1)); echo "$N" > "$BLINDF"
    echo "$(date -u +%FT%TZ) blind tick $N (github fetch failing)"
    # QUIET MODE (owner order 2026-08-08: Telegram = trades + critical only). Blindness is
    # logged, never paged - if the engine is also dead, the AGE>35 branch pages when vision
    # returns, and the failover handles positions meanwhile.
    echo "$(date -u +%FT%TZ) blind tick $N logged (no page - quiet mode)"
    exit 0
  fi
fi
rm -f "$BLINDF" 2>/dev/null
LAST=$(git log -1 --format=%ct origin/main 2>/dev/null || echo 0)
NOW=$(date -u +%s)
AGE=$(( (NOW - LAST) / 60 ))
if [ "$AGE" -gt 35 ]; then
  alarm "engine heartbeat is ${AGE} min old during market hours - cycles are NOT completing (GHA timeout / dispatcher down / platform incident). Running VPS FULL FAILOVER cycle now (entries+exits+harvest)."
  # FAILOVER (2026-08-06): exits-only engine pass on this box - manages open positions while
  # GHA is dead; its push refreshes the heartbeat, which quiets this alarm until stale again.
  git pull -q --rebase -X theirs 2>/dev/null || true
  . ./.venv/bin/activate 2>/dev/null || true
  python scripts/engine_failover_exits.py >> /home/poller/engine_failover.log 2>&1 || \
    alarm "FAILOVER ITSELF FAILED - open positions are UNMANAGED. Manual intervention needed."
else
  echo "$(date -u +%FT%TZ) ok: heartbeat ${AGE} min"
fi
