#!/usr/bin/env bash
# UNIVERSAL LANDING WATCH (owner order 2026-07-29): every scheduled job that only alarms on FAILURE
# is blind to ABSENCE - this pages the moment any expected DAILY ARTIFACT is missing by deadline.
# Runs 22:45 UTC Mon-Sat. One Telegram lists every missing artifact. The archiver has its own
# dedicated watch at 21:15; it is re-checked here as the single pane of glass.
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
  # weekday market jobs
  if [ "$DOW" -le 5 ]; then
    grep -q "=== ${TODAY_ISO}" "$REPO/data/poller.log" 2>/dev/null || MISS+=("poller: no run logged today")
    ls "$SNAP"/harvest_${TODAY_C}_*.db.gz >/dev/null 2>&1 || MISS+=("nightly DB backup: no snapshot file for today (21:30 job)")
    git -C "$SNAP" pull --rebase --autostash -q origin main 2>/dev/null
    # 2026-09-01: the manifest workflow died Aug 5 and was replaced by the 21:30 snapshot
    # push (checked above and by archiver_watch.sh) - the manifest check alarmed nightly on a
    # retired artifact. The snapshot IS the archive now; no second file to demand.
  fi
  # integrity gate runs 22:05 Tue-Sat
  if [ "$DOW" -ge 2 ] && [ "$DOW" -le 6 ]; then
    grep -q "INTEGRITY GATE" "$HOME/integrity_gate.log" 2>/dev/null &&       grep -q "$(date -u +%Y-%m-%d)" <(tail -5 "$HOME/integrity_gate.log") || MISS+=("integrity gate: no run logged today (22:05 job)")
  fi
  # kill-switch poller: state file must be fresh (runs every 15 min)
  AGE=$(( $(date +%s) - $(stat -c %Y "$HOME/telegram_commands_state.json" 2>/dev/null || echo 0) ))
  [ "$AGE" -lt 2700 ] || MISS+=("telegram command poller: state stale ${AGE}s - the /halt channel may be dead")
  # Monday: the Sunday brain chain must have landed
  if [ "$DOW" -eq 1 ]; then
    git -C "$REPO" log --since="36 hours ago" --oneline 2>/dev/null | grep -qi "weekly report"       || MISS+=("Sunday brain chain: no student weekly commit within 36h - the week has no verdict")
  fi
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
