#!/usr/bin/env bash
# VPS cron (UTC): 12 21,22 * * 1-5 and 3 22,23 * * 0-4, the four fx-s26-alerts schedule minutes.
# Pushes one tick file to main; the push starts .github/workflows/fx_s26_alerts.yml at once, because GitHub ran the
# schedule about 6 hours late and the book missed its first signal (BREAKDOWNS 2026-11-27). Uses its own sparse clone
# so the engine checkout is never touched. Never force-pushes. Pages Telegram if no tick could be pushed.
set -u
D="$HOME/fx_tick"
# The default github.com key on the VPS is read-only; push with the key the engine checkout pushes with.
SSHC=$(git -C "$HOME/swing-trading-scanner" config --get core.sshCommand)
[ -n "$SSHC" ] && export GIT_SSH_COMMAND="$SSHC"
if [ ! -d "$D/.git" ]; then
  git clone -q --depth 1 --filter=blob:none --sparse git@github.com:savvystocks/swing-trading-scanner.git "$D" || exit 1
  git -C "$D" sparse-checkout set reports/fx_alerts/tick || exit 1
fi
cd "$D" || exit 1
git config user.name "fx-tick-vps"
git config user.email "fx-tick-vps@users.noreply.github.com"
for i in 1 2 3 4 5; do
  if git fetch -q --depth 1 origin main && git reset -q --hard origin/main; then
    mkdir -p reports/fx_alerts/tick
    date -u +%Y-%m-%dT%H:%M:%SZ > reports/fx_alerts/tick/last_tick.txt
    git add reports/fx_alerts/tick/last_tick.txt
    if git commit -q -m "fx alerts: tick $(date -u +%H:%M) UTC" && git push -q origin HEAD:main; then
      echo "$(date -u +%FT%TZ) tick pushed"
      exit 0
    fi
  fi
  sleep 15
done
echo "$(date -u +%FT%TZ) tick FAILED"
ENVF="$HOME/swing-trading-scanner/.harvest_env"
[ -f "$ENVF" ] && . "$ENVF"
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
  curl -s -o /dev/null --max-time 20 "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
    --data-urlencode "text=FX paper book: the VPS could not push its on-time tick ($(date -u +%H:%M) UTC). The job falls back to GitHub's late schedule and may miss tonight's entry window."
fi
exit 1
