#!/usr/bin/env bash
# 30-MINUTE WATCHDOG (owner decision 28) - cross-watching, VPS side. During US market hours, if the
# newest inbox commit on origin/main is older than 30 minutes the engine has stalled -> Telegram.
# Every run stamps watchdog_status.json into the local harvest-snapshots checkout; the nightly
# snapshot push carries it off-box, and the Sunday brain report renders the weekly self-test line
# from it. Deploy: */15 13-21 * * 1-5 on the VPS crontab (13:45 gate below avoids open-cycle noise).
# The reverse watch is healthchecks.io: run_poller_vps.sh pings HEALTHCHECK_URL every poller run and
# healthchecks emails on silence - so the VPS watches GitHub and healthchecks watches the VPS.
set -uo pipefail
REPO="$HOME/swing-trading-scanner"
SNAP="$HOME/harvest-snapshots"
cd "$REPO" || exit 0
set -a
[ -f "$REPO/.harvest_env" ] && . "$REPO/.harvest_env"
set +a
git fetch -q origin main || true
NOW=$(date -u +%s)
DOW=$(date -u +%u)
HHMM=$(date -u +%H%M)
MARKET=1
if [ "$DOW" -ge 6 ] || [ "$HHMM" -lt 1345 ] || [ "$HHMM" -gt 2000 ]; then MARKET=0; fi
LAST=$(git log origin/main -1 --format=%ct -- data/harvest_inbox/ 2>/dev/null || echo 0)
AGE=$(( (NOW - LAST) / 60 ))
STATUS=ok
if [ "$MARKET" = "1" ] && [ "$AGE" -gt 30 ]; then
  STATUS=stalled
  if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
    curl -fsS -m 10 "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d chat_id="${TELEGRAM_CHAT_ID}" \
      -d text="WATCHDOG: no inbox commit for ${AGE}m during market hours - the engine may be stalled (check cron-job.org + GHA v10-lab runs)" \
      >/dev/null 2>&1
  fi
fi
printf '{"ts_utc":"%s","market_open":%s,"last_inbox_commit_age_min":%s,"status":"%s"}\n' \
  "$(date -u +%FT%TZ)" "$MARKET" "$AGE" "$STATUS" > "$SNAP/watchdog_status.json" 2>/dev/null || true
