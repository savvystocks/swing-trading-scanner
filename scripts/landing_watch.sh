#!/usr/bin/env bash
# UNIVERSAL LANDING WATCH (owner order 2026-07-29): every scheduled job that only alarms on FAILURE
# is blind to ABSENCE - this pages the moment any expected DAILY ARTIFACT is missing by deadline.
# Runs 22:45 UTC Mon-Sat. One Telegram lists every missing artifact.
set -u
REPO="$HOME/swing-trading-scanner"
SNAP="$HOME/harvest-snapshots"
. "$REPO/.harvest_env" 2>/dev/null || true
TODAY_ISO=$(date -u +%F)
TODAY_C=$(date -u +%Y%m%d)
DOW=$(date -u +%u)   # 1=Mon .. 7=Sun
MISS=()

if [ "${DRILL:-0}" = "1" ]; then
  MISS+=("DRILL: simulated missing artifact (test, no action needed)")
else
  # 2026-09-26: the harvest poller, the nightly DB snapshot and the integrity gate are retired (the harvest froze
  # on 2026-09-25 with its last label; data/harvest.db is a record). Their artefacts are no longer demanded here -
  # a watch that greps a retired job's log pages every night (the 2026-09-19 class, in reverse).
  # archive pullers: retired 2026-09-21 - the Unusual Whales subscription ended and nothing pulls from it.
  # kill-switch poller: state file must be fresh (runs every 15 min)
  AGE=$(( $(date +%s) - $(stat -c %Y "$HOME/telegram_commands_state.json" 2>/dev/null || echo 0) ))
  [ "$AGE" -lt 2700 ] || MISS+=("telegram command poller: state stale ${AGE}s - the /halt channel may be dead")
  # Monday brain-chain check retired 2026-09-21 with the student and brain (directional research).
fi

if [ ${#MISS[@]} -gt 0 ]; then
  TEXT="LANDING WATCH: ${#MISS[@]} scheduled artifact(s) MISSING today:"
  for m in "${MISS[@]}"; do TEXT="$TEXT
- $m"; done
  echo "$(date -u +%FT%TZ) ALARM: ${MISS[*]}"
  if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
    curl -fsS -m 15 "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage"       -d chat_id="${TELEGRAM_CHAT_ID}" -d text="$TEXT" >/dev/null || true
  fi
  exit 1
fi
echo "$(date -u +%FT%TZ) OK: all scheduled artifacts landed"
