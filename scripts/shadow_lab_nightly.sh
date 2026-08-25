#!/bin/bash
# nightly rolling 5-day shadow lab (2026-08-25: replaces the fragile nested-quote crontab
# one-liner whose date arg got mangled - shadow_lab then ran dateless on an empty "today")
cd /home/poller/swing-trading-scanner || exit 1
. ./.harvest_env
for i in 4 3 2 1 0; do
  D=$(date -u -d "-$i day" +%F)
  python3 scripts/shadow_lab.py data/harvest.db "$D" >> /home/poller/shadow_lab.log 2>&1
done
git add reports/shadow_lab
git commit -qm "shadow lab $(date -u +%F) [skip ci]" || exit 0
git pull -q --rebase -X ours 2>/dev/null
git push -q
