#!/usr/bin/env bash
# VPS TREE MIRROR (2026-09-26): fetch origin/main and reset --hard to it every quarter-hour - the retired poller's first
# action, kept because the sentinel's mtime rows, the proof stint judge and the XSP quote log all read the VPS tree.
# It also carries the external dead-man: a run whose OUTCOME is right (HEAD is the fetched main) pings
# the check; a run that is not right pings NOTHING - silence past the check's grace is the alarm. 2026-09-29:
# the first version pinged the check's failure endpoint on the fetch's return code, which the shared origin/main ref lock made
# non-zero on healthy syncs; the first fix moved to a private ref but git still updated origin/main opportunistically
# and still lost the race (15 of 32 runs), and worse, skipped the reset on those runs.
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 1
LOG="$HOME/mirror_sync.log"
{
  echo "=== $(date -u +%FT%TZ) mirror sync ==="
  # --refmap='' : fetch ONLY into the private ref; never touch refs/remotes/origin/main, which the watchdogs also write
  git fetch --no-tags --refmap='' origin +refs/heads/main:refs/mirror/main || echo "fetch returned non-zero (judged on the outcome below)"
  OK=0
  if git rev-parse -q --verify refs/mirror/main >/dev/null; then
    git reset --hard refs/mirror/main && [ "$(git rev-parse HEAD)" = "$(git rev-parse refs/mirror/main)" ] \
      && [ "$(git rev-parse FETCH_HEAD 2>/dev/null)" = "$(git rev-parse refs/mirror/main)" ] && OK=1
  fi
  set -a
  [ -f "$REPO/.harvest_env" ] && . "$REPO/.harvest_env"
  set +a
  if [ "$OK" -eq 1 ]; then
    if [ -n "${HEALTHCHECK_URL:-}" ]; then
      curl -fsS -m 10 --retry 3 "$HEALTHCHECK_URL" >/dev/null 2>&1 || echo "healthcheck ping failed (network?)"
    fi
  else
    echo "MIRROR SYNC FAILED (the tree is not at the fetched main) - no ping sent; silence past the grace is the alarm"
  fi
} >> "$LOG" 2>&1
if [ "$(stat -c%s "$LOG" 2>/dev/null || echo 0)" -gt 2097152 ]; then
  mv -f "$LOG" "$LOG.1"
fi
