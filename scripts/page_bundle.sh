#!/usr/bin/env bash
# PAGE EVIDENCE BUNDLE (learned from the 2026-09-11 workshop's triage bot, built without an LLM in
# the loop). Whenever a watchdog pages, gather everything a human or an agent would otherwise hunt
# for into ONE file and push it to main, so the next session starts from evidence, not from
# guesses: the reason, the last-good cycle stamp, the last engine runs (public Actions API, no
# token), the tails of the watchdog logs, the sentinel rows, the book's open count, and which map
# files to read. Usage: bash scripts/page_bundle.sh "<reason>"   (fail-open: never blocks a page)
set -uo pipefail
REASON="${1:-unspecified}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO" || exit 0
TS=$(date -u +%Y%m%dT%H%M%SZ)
SLUG=$(echo "$REASON" | tr -cs 'A-Za-z0-9' '_' | cut -c1-40)
DIR="reports/shadow_lab/page_bundles"
OUT="$DIR/${TS}_${SLUG}.md"
mkdir -p "$DIR"
{
  echo "# PAGE BUNDLE $TS"
  echo
  echo "reason: $REASON"
  echo "utc: $(date -u +%FT%TZ)   local(BST/GMT): $(TZ=Europe/London date +%FT%T)"
  echo
  echo "## last-good cycle (origin/main:data/last_cycle_ok)"
  git fetch -q origin main 2>/dev/null || true
  git show origin/main:data/last_cycle_ok 2>/dev/null || echo "(unavailable)"
  echo
  echo "## last commits on main"
  git log origin/main -5 --format="%h %ci %s" 2>/dev/null | cut -c1-120 || true
  echo
  echo "## last engine runs (GitHub Actions, v10_lab.yml)"
  curl -s -m 15 "https://api.github.com/repos/savvystocks/swing-trading-scanner/actions/workflows/v10_lab.yml/runs?per_page=5" \
    | python3 -c 'import json,sys
try:
    d=json.load(sys.stdin)
    for r in d.get("workflow_runs", [])[:5]:
        print(f"- {r[\"created_at\"]} {r[\"status\"]}/{r[\"conclusion\"]} {r[\"html_url\"]}")
    if not d.get("workflow_runs"): print("(no runs returned: " + str(d.get("message")) + ")")
except Exception as e:
    print("(actions api unavailable: " + type(e).__name__ + ")")' 2>/dev/null || echo "(actions api unavailable)"
  echo
  echo "## engine_watch.log (tail)"
  tail -12 "$HOME/engine_watch.log" 2>/dev/null || echo "(no log)"
  echo
  echo "## watchdog status"
  cat "$HOME/harvest-snapshots/watchdog_status.json" 2>/dev/null || echo "(no status file)"
  echo
  echo "## sentinel rows (tail)"
  tail -3 reports/shadow_lab/sentinels.jsonl 2>/dev/null | cut -c1-400 || echo "(none)"
  echo
  echo "## book"
  python3 -c 'import json
L=json.load(open("proactive_sandbox_logs.json"))
st={}
for r in L: st[r.get("status")]=st.get(r.get("status"),0)+1
print("records by status:", st)
op=[r for r in L if r.get("status")=="OPEN" and isinstance(r.get("legs"),dict)]
print("open option records:", len(op), "newest entry:", max((r.get("entry_ts_utc") or "" for r in L), default=""))' 2>/dev/null || echo "(book unreadable - that is itself the finding)"
  echo
  echo "## read next (docs/feature_map)"
  case "$REASON" in
    *inbox*|*stall*|*PERSIST*) echo "- persist-and-merge.md, market-gate.md, telegram-and-watchdogs.md" ;;
    *CRASH*|*crash*|*ROLLBACK*|*DEAD*|*dead*) echo "- gate-and-ship.md, telegram-and-watchdogs.md, exit-engine.md" ;;
    *disk*) echo "- vps-crons.md" ;;
    *) echo "- telegram-and-watchdogs.md, then the subsystem the reason names" ;;
  esac
} > "$OUT" 2>&1
echo "bundle: $OUT"
git add -f "$OUT" >/dev/null 2>&1 \
  && git -c user.name=watchdog -c user.email=watchdog@vps commit -qm "page bundle: ${SLUG} [skip ci]" -- "$OUT" >/dev/null 2>&1 \
  && (git pull -q --rebase --autostash origin main >/dev/null 2>&1 || true) \
  && git push -q origin HEAD:main >/dev/null 2>&1 \
  && echo "bundle pushed" || echo "bundle kept locally (push failed or nothing to commit)"
exit 0
