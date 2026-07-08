#!/usr/bin/env bash
# 30-MINUTE WATCHDOG (owner decision 28) - cross-watching, VPS side. During US market hours, if the
# newest inbox commit on origin/main is older than 30 minutes the engine has stalled -> Telegram.
# Every run stamps watchdog_status.json into the local harvest-snapshots checkout; the nightly
# snapshot push carries it off-box, and the Sunday brain report renders the weekly self-test line
# from it. Deploy: */15 13-22 * * 1-5 on the VPS crontab (the market gate below is DST-correct, so a
# slightly wider cron window is harmless - it self-silences outside RTH).
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
# DST-correct market gate: reuse poller._market_open_now (XNYS calendar, DST + early-close aware) instead
# of a hardcoded UTC window that would false-alarm every winter morning (Nov-Mar RTH is 14:30-21:00 UTC,
# not 13:30-20:00). Any python hiccup -> treat as closed (fail-safe: silence, never a false stall alert).
PY="$REPO/.venv/bin/python"; [ -x "$PY" ] || PY=python3
MARKET=$("$PY" -c "import sys; sys.path.insert(0,'$REPO'); from poller import _market_open_now; print(1 if _market_open_now(buffer_min=0) else 0)" 2>/dev/null || echo 0)
case "$MARKET" in 0|1) ;; *) MARKET=0 ;; esac
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
