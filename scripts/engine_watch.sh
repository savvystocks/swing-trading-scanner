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
  # CRASH-NOT-DEAD (2026-08-17 KeyError day): crashed runs still push data, so the heartbeat
  # stays fresh while every cycle dies mid-engine. The workflow stamps data/last_cycle_ok ONLY
  # when Execute succeeds; fresh heartbeat + stale stamp = CRASHING. Page at 2 consecutive
  # ticks (30 min), once per episode. NO failover - it would run the same crashing code.
  CRASHF=/home/poller/.engine_watch_crash
  OK_TS=$(git show origin/main:data/last_cycle_ok 2>/dev/null | head -1 || echo "")
  GOOD_SHA=$(git show origin/main:data/last_cycle_ok 2>/dev/null | sed -n 2p || echo "")
  if [ -n "$OK_TS" ]; then
    OK_EPOCH=$(date -u -d "$OK_TS" +%s 2>/dev/null || echo 0)
    OK_AGE=$(( (NOW - OK_EPOCH) / 60 ))
    if [ "$OK_EPOCH" -gt 0 ] && [ "$OK_AGE" -gt 35 ]; then
      C=$(cat "$CRASHF" 2>/dev/null || echo 0); C=$((C+1)); echo "$C" > "$CRASHF"
      echo "$(date -u +%FT%TZ) crash tick $C (last good cycle ${OK_AGE}m ago, heartbeat ${AGE}m)"
      if [ "$C" -eq 2 ]; then
        # AUTO-ROLLBACK (owner order 2026-08-17: days must never be wasted while he works).
        # Revert engine CODE (root *.py + scripts/*.py) to the last SHA that completed a green
        # cycle, commit forward, push. Once per episode; spec/data untouched; never force.
        RB=/home/poller/.engine_watch_rolledback
        if [ -n "$GOOD_SHA" ] && [ ! -f "$RB" ]; then
          git pull -q --rebase -X theirs 2>/dev/null || true
          # 2026-08-18 mass-adoption fix: pin DATA files to origin before the rollback
          # commit - a stale VPS working tree must never overwrite live trade records
          git checkout -q origin/main -- proactive_sandbox_logs.json data/harvest_state.json sandbox_ticker_cooloff.json sandbox_watchlist.json 2>/dev/null || true
          if git checkout -q "$GOOD_SHA" -- "*.py" "scripts/" 2>/dev/null && ! git diff --cached --quiet -- "*.py" "scripts/" 2>/dev/null              && git -c user.name=watchdog -c user.email=watchdog@vps commit -qm "AUTO-ROLLBACK: engine code to last-good $GOOD_SHA (crash watchdog) [skip ci]" -- "*.py" scripts/              && git push -q origin HEAD:main; then
            echo rolled > "$RB"
            alarm "engine was CRASHING (last good cycle ${OK_AGE}m ago) - AUTO-ROLLBACK executed: code reverted to last-good ${GOOD_SHA}. Cycles resume on proven code within 10 min. The bad change stays in git history for a code session."
          else
            git rebase --abort 2>/dev/null; git checkout -q -- . 2>/dev/null
            if git diff --cached --quiet -- "*.py" "scripts/" 2>/dev/null; then
              git reset -q HEAD 2>/dev/null; git checkout -q -- . 2>/dev/null
              echo rolled > "$RB"
              alarm "cycle completions are GAPPY (last good ${OK_AGE}m ago) but the CODE is unchanged since last-good - no rollback possible or needed. Likely run-queue churn; trades that filled are safe; watching."
            else
              git rebase --abort 2>/dev/null; git checkout -q -- . 2>/dev/null
              alarm "engine is CRASHING and AUTO-ROLLBACK FAILED - manual session needed NOW. Last good cycle ${OK_AGE}m ago."
            fi
          fi
        elif [ -f "$RB" ]; then
          alarm "engine STILL crashing after auto-rollback - the fault predates the last-good stamp or is environmental. Manual session needed NOW."
        else
          alarm "engine is CRASHING mid-cycle (last good ${OK_AGE}m ago) and no last-good SHA is stamped yet - manual session needed."
        fi
      fi
    else
      rm -f "$CRASHF" /home/poller/.engine_watch_rolledback 2>/dev/null
    fi
  fi
fi
