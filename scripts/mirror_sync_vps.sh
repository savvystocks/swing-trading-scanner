#!/usr/bin/env bash
# VPS MIRROR SYNC (2026-09-26). The harvest poller is retired, but its FIRST action - mirroring origin/main into this
# checkout every quarter-hour of the session (git fetch + reset --hard FETCH_HEAD, never `git pull`: the 2026-07-10
# ref-lock lesson) - is what lands the engine's files here: the freshness sentinel's mtimes (engine last_cycle_ok,
# engine records log, proof book equity samples), the Monday proof stint runs at :07, and the XSP quote log's held
# legs all read this tree. This keeps that sync, and the poller's LAST action: the healthchecks.io ping (owner
# decision 28, cross-watching; SILENT-GAP AUDIT 2026-08-25). HEALTHCHECK_URL lives in .harvest_env (owner-created
# check; sourced with set -a exactly as the poller did). A clean fetch + reset pings the check; a failed one pings
# its /fail endpoint so healthchecks alerts on the FIRST failure; when HEALTHCHECK_URL is unset nothing is pinged.
# The external dead-man therefore rides this job on the poller's old cadence. SAFE: the databases are gitignored and
# untracked and the checkout carries no local commits, so the reset only refreshes engine-owned tracked files -
# which is also why nothing may be parked uncommitted on the VPS during 13:00-21:45 UTC on a weekday.
# Cron: */15 13-21 * * 1-5 (UTC), the poller's old slot. Log: /home/poller/mirror_sync.log (sentinel row "vps mirror sync").
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 1
LOG="$HOME/mirror_sync.log"
{
  echo "=== $(date -u +%FT%TZ) mirror sync ==="
  RC=0
  git fetch --no-tags origin main || RC=1
  git reset --hard FETCH_HEAD || RC=1
  set -a
  [ -f "$REPO/.harvest_env" ] && . "$REPO/.harvest_env"
  set +a
  if [ -n "${HEALTHCHECK_URL:-}" ]; then
    if [ "$RC" -eq 0 ]; then
      curl -fsS -m 10 --retry 3 "$HEALTHCHECK_URL" >/dev/null 2>&1 || echo "healthcheck ping failed (network?)"
    else
      curl -fsS -m 10 --retry 3 "$HEALTHCHECK_URL/fail" >/dev/null 2>&1 || echo "healthcheck /fail ping failed (network?)"
    fi
  fi
  [ "$RC" -eq 0 ] || echo "MIRROR SYNC FAILED (fetch or reset rc != 0)"
} >> "$LOG" 2>&1
if [ "$(stat -c%s "$LOG" 2>/dev/null || echo 0)" -gt 2097152 ]; then
  mv -f "$LOG" "$LOG.1"
fi
