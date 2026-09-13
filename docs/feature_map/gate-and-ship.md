# Verify and ship a change

## What
How any change reaches `main`. The gate is not optional and the order is not negotiable: the
laptop checkout is stale, so edits are staged in a scratch copy of the VPS files, copied to the VPS,
verified there, then committed and pushed from there.

## Where
- Gate: `bash ~/vps_ship_grid.sh` on the VPS - compile, spec JSON, the harvest suites
  (`test_harvest_passivity.py`, `test_harvest.py`, `test_harvest_harvester.py`,
  `test_harvest_poller.py`; a listed file that is absent prints MISSING and is skipped), then
  `v11_mot_harness.py` (7 dimensions, 180+ checks); writes
  `/tmp/gate_green` only on ALL GREEN. Check ITS exit code, then commit.
- Entry-path changes also run `./.venv/bin/python scripts/regime_drill.py` (15 scenarios) and get
  the adversarial six checks or a panel BEFORE code (`CLAUDE.md` standing directive).
- Map lint: `python scripts/feature_map_lint.py` (MOT 6.18) - every `file:function` cited in
  `docs/feature_map/` must exist.

## Exercise (the routine)
1. Copy the current VPS files to the scratchpad (`scp poller@...:~/swing-trading-scanner/<f> ...`)
   and confirm `md5sum` matches HEAD before editing.
2. Edit the scratch copies; `python -m py_compile` each.
3. `scp` them back; `bash ~/vps_ship_grid.sh 2>&1 | tail -4; [ -f /tmp/gate_green ]`.
4. On green: `git add <files> && git commit -F <msg> && git push origin main`; commit messages end
   with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`; data and docs commits carry `[skip ci]`.
5. Every fix adds its BREAKDOWNS.md entry in the same commit and names its regression check;
   `SYSTEM_ARCHITECTURE.md` gets the present-tense reality; `ROADMAP.md` the decision.
6. Verify on `origin/main` after the push (`git show origin/main:<file> | grep ...`); spec writes
   verify after push too.

## Healthy
- `MOT CERTIFICATE: ALL CHECKS PASS - V11 CLEARED`, `MOT PASS`, `ALL GREEN`, then the push line.
- `REGIME DRILL: ALL SCENARIOS ROUTE AS DESIGNED`.

## Checks
- The gate itself. Never force-push, never delete branches, never push on a red MOT.

## Traps
- 2026-09-02 (evening) PUSHED ON A RED MOT (process breakdown).
- 2026-09-11 PUSHES BLOCKED BY A 131 MB CORPUS (never `git add -A`; corpora are gitignored).
- 2026-07-03 CRLF PASS ZEROED A SCRIPT; heredoc quoting through ssh mangles Python - write scratch
  files and `scp` them.
- `pkill -f <pattern>` matches the ssh session that runs it; kill by PID or use `[p]attern`.
- The VPS never holds proof-account keys; keys never appear in chat.
