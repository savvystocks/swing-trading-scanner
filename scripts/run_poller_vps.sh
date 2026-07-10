#!/usr/bin/env bash
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 1
mkdir -p "$REPO/data"
LOG="$REPO/data/poller.log"
{
  echo "=== $(date -u +%FT%TZ) poller run ==="
  # sync = mirror origin/main via fetch + hard-reset (NOT `git pull`). `git pull origin main` duplicated
  # `main` in FETCH_HEAD (explicit arg + configured refspec) -> "Cannot fast-forward to multiple branches",
  # and its ref update raced the engine's frequent pushes -> "cannot lock ref". reset --hard has NO merge
  # step (both errors impossible) and targets FETCH_HEAD (written even if the origin/main ref update warns),
  # so ingestion proceeds through the race. SAFE: harvest.db is gitignored + untracked and the checkout has
  # no local commits, so this only refreshes engine-owned tracked files - the pile is never touched.
  git fetch --no-tags origin main || true
  git reset --hard FETCH_HEAD || true
  set -a
  [ -f "$REPO/.harvest_env" ] && . "$REPO/.harvest_env"
  set +a
  [ -f "$REPO/.venv/bin/activate" ] && . "$REPO/.venv/bin/activate"
  python poller.py --once
  # cross-watching (owner decision 28): every poller run pings healthchecks.io; silence -> email.
  # HEALTHCHECK_URL lives in .harvest_env (owner-created check). No-op when unset.
  [ -n "${HEALTHCHECK_URL:-}" ] && curl -fsS -m 10 --retry 3 "$HEALTHCHECK_URL" >/dev/null 2>&1
} >> "$LOG" 2>&1
if [ "$(stat -c%s "$LOG" 2>/dev/null || echo 0)" -gt 5242880 ]; then
  mv -f "$LOG" "$LOG.1"
fi
