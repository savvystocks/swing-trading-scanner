#!/usr/bin/env bash
# EVENING PERSIST (silent-gap audit 2026-08-25, confirmed finding #6): the poller's 15-min
# `git reset --hard FETCH_HEAD` destroys any uncommitted tracked-file append. The 22:00+
# writers (sunday_boundary -> trajectory.log + sentinels.jsonl, shadow_breaker -> breaker.jsonl)
# append AFTER the 21:50 shadow-lab commit, so their output silently died at the NEXT MORNING's
# first poller reset. This commits the whole evening chain's output at 22:45 UTC before anything
# can reset it away.
set -u
cd /home/poller/swing-trading-scanner || exit 1
git add reports/shadow_lab 2>/dev/null
if git diff --cached --quiet; then
  echo "$(date -u +%FT%TZ) nothing to persist"
  exit 0
fi
git commit -qm "evening persist: court verdicts + sentinels + breaker $(date -u +%F) [skip ci]"
git pull -q --rebase --autostash 2>/dev/null || true
git push -q && echo "$(date -u +%FT%TZ) persisted" || echo "$(date -u +%FT%TZ) PUSH FAILED"
