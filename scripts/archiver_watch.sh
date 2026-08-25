#!/usr/bin/env bash
# ARCHIVER LANDING WATCHDOG v2 (restored 2026-08-25; the original died Aug 5 with the manifest
# workflow and its cron entry vanished - the watchdog itself had no watchdog). Modernised for
# what ships NOW: backup_snapshot.sh pushes harvest_YYYYMMDD_2130.db.gz nightly at 21:30 UTC.
# That script alarms if its PUSH fails; this covers the silent class - the cron never firing
# at all. Runs 22:15 UTC on trading days: pull the snapshots repo, demand TODAY's snapshot
# exists remotely. Missing -> loud Telegram. A missed day is permanently unrecoverable.
# Guard: only meaningful AFTER the 21:30 backup slot - exits quietly if run earlier (a manual
# morning run must not false-alarm; learned 2026-08-25 at 00:54).
set -u
REPO="$HOME/swing-trading-scanner"
SNAP="$HOME/harvest-snapshots"
[ -f "$REPO/.harvest_env" ] && . "$REPO/.harvest_env"
HOUR=$(date -u +%H)
if [ "$HOUR" -lt 22 ]; then
  echo "$(date -u +%FT%TZ) skip: before today's 21:30 backup slot - nothing to verify yet"
  exit 0
fi
DAY=$(date -u +%Y%m%d)
alarm() {
  echo "$(date -u +%FT%TZ) ALARM: $1"
  if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
    curl -fsS -m 15 "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d chat_id="${TELEGRAM_CHAT_ID}" -d text="BACKUP LANDING WATCH: $1" >/dev/null || true
  fi
}
git -C "$SNAP" pull --rebase --autostash -q origin main 2>/dev/null
if ls "$SNAP"/harvest_"$DAY"_*.db.gz >/dev/null 2>&1; then
  echo "$(date -u +%FT%TZ) OK: snapshot for $DAY landed off-box"
else
  alarm "no database snapshot landed for $DAY - the 21:30 backup cron did not run or did not push. A missed day is unrecoverable; run backup_snapshot.sh manually NOW."
fi
