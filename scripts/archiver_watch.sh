#!/usr/bin/env bash
# ARCHIVER LANDING WATCHDOG (VPS side, owner order 2026-07-28). The workflow's own failure alarm
# covers runs that START and fail; this covers the failure mode GitHub email never will - the
# scheduled run silently NOT FIRING (schedule skips, disabled workflows). At 21:15 UTC on trading
# days, pull the snapshots repo and demand today's manifest with ok == total. Missing or short ->
# Telegram. A missed snapshot day is permanently unrecoverable, so this alarm is loud by design.
set -u
REPO="$HOME/swing-trading-scanner"
SNAP="$HOME/harvest-snapshots"
[ -f "$REPO/.harvest_env" ] && . "$REPO/.harvest_env"
DAY=$(date -u +%F)

# weekday guard (cron already 1-5, this protects manual runs on holidays only lightly)
git -C "$SNAP" pull --rebase --autostash -q origin main 2>/dev/null

MANIFEST="$SNAP/archiver/$DAY/manifest.json"
alarm() {
  MSG="$1"
  echo "$(date -u +%FT%TZ) ALARM: $MSG"
  if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
    curl -fsS -m 15 "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d chat_id="${TELEGRAM_CHAT_ID}" -d text="ARCHIVER WATCH: ${MSG}" >/dev/null || true
  fi
}

if [ ! -f "$MANIFEST" ]; then
  alarm "no snapshot landed for $DAY - the 19:50 UTC run did not fire or did not push. A missed day is unrecoverable; dispatch manually NOW (gh workflow run chain-feed-archiver)."
  exit 1
fi
OK=$(python3 -c "import json;m=json.load(open('$MANIFEST'));print('yes' if m.get('ok')==m.get('total') and m.get('total',0)>0 else 'no')" 2>/dev/null)
if [ "$OK" != "yes" ]; then
  alarm "snapshot for $DAY landed INCOMPLETE (manifest ok != total) - check the run log."
  exit 1
fi
echo "$(date -u +%FT%TZ) OK: $DAY manifest complete"
