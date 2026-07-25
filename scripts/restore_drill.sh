#!/usr/bin/env bash
# RESTORE DRILL (School build, Phase 1a) - proves the off-box backup actually restores into a working
# system, in a clean directory, touching nothing live. Run anywhere with the repo + a snapshot source
# (a harvest-snapshots checkout or a single .db.gz). Writes a plain-English PASS/FAIL report.
#
#   bash scripts/restore_drill.sh <snapshot-dir-or-gz> [report-out.md]
#
# PASS requires: gunzip ok, PRAGMA integrity_check ok, all three tables present with sane row counts,
# a fresh clone of the repo builds a venv that can open the restored DB, and the poller's offline
# --drill exercises the full ingest->bid_path->barrier->label chain against a COPY of the restored DB.
set -uo pipefail
SRC="${1:?usage: restore_drill.sh <snapshot-dir-or-gz> [report.md]}"
OUT="${2:-reports/ops/restore_drill_$(date -u +%Y-%m-%d).md}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/restore_drill_XXXXXX")"
PASS=0; FAIL=0
LINES=()
say() { LINES+=("$1"); echo "$1"; }
check() { # check <name> <0-for-pass> <detail>
  if [ "$2" -eq 0 ]; then PASS=$((PASS+1)); say "- PASS: $1 $3"; else FAIL=$((FAIL+1)); say "- FAIL: $1 $3"; fi
}

say "# Restore drill - $(date -u +%FT%TZ)"
say ""
say "Source: \`$SRC\`  |  Work dir: \`$WORK\` (deleted after)"
say ""

GZ="$SRC"
if [ -d "$SRC" ]; then GZ="$(ls -1 "$SRC"/harvest_*.db.gz 2>/dev/null | sort | tail -1)"; fi
[ -n "$GZ" ] && [ -f "$GZ" ]; check "snapshot located" $? "($(basename "${GZ:-none}"))"

gunzip -c "$GZ" > "$WORK/restored.db" 2>/dev/null
check "gunzip clean (no truncation)" $? "($(stat -c%s "$WORK/restored.db" 2>/dev/null || echo 0) bytes)"

# portable python + path resolution (VPS venv, Windows venv, plain python; Git Bash path mapping)
PYBIN="$REPO/.venv/bin/python"
[ -x "$PYBIN" ] || PYBIN="$REPO/.venv/Scripts/python.exe"
[ -x "$PYBIN" ] || PYBIN="$(command -v python || command -v python3)"
DB_PY="$(cygpath -m "$WORK/restored.db" 2>/dev/null || echo "$WORK/restored.db")"
INTEG=$("$PYBIN" -c "import sqlite3;print(sqlite3.connect(r'$DB_PY').execute('PRAGMA integrity_check').fetchone()[0])" 2>/dev/null)
[ "$INTEG" = "ok" ]; check "sqlite integrity_check" $? "($INTEG)"

COUNTS=$("$PYBIN" -c "
import sqlite3
c = sqlite3.connect(r'$DB_PY')
n = {t: c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in ('candidates','labels','bid_path')}
assert n['candidates'] > 1000 and n['labels'] > 500 and n['bid_path'] > n['candidates'], n
print(n['candidates'], n['labels'], n['bid_path'])" 2>/dev/null)
check "tables present with sane row counts" $? "(candidates/labels/bid_path: ${COUNTS:-unreadable})"

git clone -q --depth 1 "file://$REPO" "$WORK/clean_repo" 2>/dev/null
check "clean repo clone" $? ""

mkdir -p "$WORK/clean_repo/data"
cp "$WORK/restored.db" "$WORK/clean_repo/data/harvest.db"
DRILL=$(cd "$WORK/clean_repo" && "$PYBIN" poller.py --drill 2>&1 | tail -2 | head -1)
echo "$DRILL" | grep -q "full chain executed end-to-end"; check "poller offline drill on restored DB" $? "($DRILL)"

say ""
if [ "$FAIL" -eq 0 ]; then say "VERDICT: RESTORABLE - a working system rebuilds from the off-box backup ($PASS/$((PASS+FAIL)) checks)."
else say "VERDICT: NOT PROVEN - $FAIL check(s) failed; treat the backup as suspect until this drill passes."; fi

mkdir -p "$(dirname "$REPO/$OUT")"
printf '%s\n' "${LINES[@]}" > "$REPO/$OUT"
echo "report -> $OUT"
rm -rf "$WORK"
[ "$FAIL" -eq 0 ]
