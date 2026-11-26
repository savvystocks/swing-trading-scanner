# Verify and ship a change

## What
How any change reaches `main`. The gate is not optional and the order is not negotiable: the
laptop checkout is stale, so edits are staged in a scratch copy of the VPS files, copied to the VPS,
verified there, then committed and pushed from there.

## Where
- Gate: `bash scripts/verify_engine.sh` on the VPS. Since 2026-11-26 (owner decision) ALL GREEN requires
  exactly one thing, the FX gate `scripts/verify_fx.sh`: it compiles `scripts/fx_s26_alerts.py`,
  `scripts/fx_oanda_orders.py`, `scripts/fx_risk_engine.py`, `research/costs.py` and `research/prop_rules.py`,
  then runs every `tests/fx/test_*.py` (`tests/fx/test_fx_s26_alerts.py`, `tests/fx/test_fx_risk_engine.py`,
  `tests/fx/test_fx_oanda_orders.py`, `tests/fx/test_prop_rules.py`, `tests/fx/test_costs.py`; runner
  `tests/fx/fxtest.py`) with `./.venv/bin/python`, else `python3` (`VERIFY_PY=python` overrides, e.g. on the laptop).
  On ALL GREEN `scripts/verify_engine.sh` stamps `/tmp/verify_green` through `scripts/gate_fresh.sh --stamp`.
- Options engine or harvest path changes also run `bash scripts/verify_options_legacy.sh` (not required for
  ALL GREEN, stamps nothing): the map lint, `scripts/regime_drill.py` (22 scenarios) and `bash ~/vps_ship_grid.sh`
  (compile, spec JSON, the harvest suites `test_harvest_passivity.py`, `test_harvest.py`,
  `test_harvest_harvester.py`, `test_harvest_poller.py`, then `v11_mot_harness.py`; it writes `/tmp/gate_green`
  only on its own ALL GREEN). Entry-path changes get the adversarial six checks or a panel BEFORE code
  (`CLAUDE.md` standing directive).
- Map lint: `python scripts/feature_map_lint.py` (MOT 6.18) - every `file:function` cited in
  `docs/feature_map/` must exist. It needs the VPS data files, so on the laptop it reports `data/*.db` missing.

## Exercise (the routine)
1. Copy the current VPS files to the scratchpad (`scp poller@...:~/swing-trading-scanner/<f> ...`)
   and confirm `md5sum` matches HEAD before editing.
2. Edit the scratch copies; `python -m py_compile` each.
3. `scp` them back; `bash scripts/verify_engine.sh` (the FX gate; on ALL GREEN it stamps
   `/tmp/verify_green` with the HEAD sha and a hash of the working tree). A change to the options engine or
   the harvest path also runs `bash scripts/verify_options_legacy.sh` and needs `LEGACY OPTIONS GATE: GREEN`.
4. Gate the commit on `bash scripts/gate_fresh.sh` (exit 0 only when the sentinel describes the
   tree as it is now), never on the existence of a file: `bash scripts/gate_fresh.sh && git add
   <files> && git commit -F <msg> && git push origin main`; commit messages end
   with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`; data and docs commits carry `[skip ci]`.
5. Every fix adds its BREAKDOWNS.md entry in the same commit and names its regression check;
   `SYSTEM_ARCHITECTURE.md` gets the present-tense reality; `ROADMAP.md` the decision.
6. Verify on `origin/main` after the push (`git show origin/main:<file> | grep ...`); spec writes
   verify after push too.

## Healthy
- `FX GATE: ALL GREEN (96/96 checks)`, `VERIFY: ALL GREEN`, `gate sentinel stamped: <sha> <hash>`, then the push line.
- Legacy (options/harvest changes only): `REGIME DRILL: ALL SCENARIOS ROUTE AS DESIGNED`,
  `MOT CERTIFICATE: ALL CHECKS PASS - V11 CLEARED`, `LEGACY OPTIONS GATE: GREEN`.

## Checks
- The gate itself. Never force-push, never delete branches, never push on a red FX gate, and never push an
  options or harvest change on a red legacy gate.
- Untracked files are outside `scripts/gate_fresh.sh`'s hash (`git status --untracked-files=no`): a new file edited after
  the green stamp is not caught until it is tracked, so stamp after the last edit of a new file.

## Traps
- 2026-09-02 (evening) PUSHED ON A RED MOT (process breakdown).
- 2026-09-13 PUSHED WITHOUT THE GATE ON A STALE GREEN SENTINEL: a lint failed, the chain stopped
  before the gate, and `[ -f /tmp/gate_green ]` found the previous run's file. The sentinel now
  names the tree it certified (`scripts/gate_fresh.sh`); a chain that tests a bare file is wrong.
- 2026-09-11 PUSHES BLOCKED BY A 131 MB CORPUS (never `git add -A`; corpora are gitignored).
- 2026-07-03 CRLF PASS ZEROED A SCRIPT; heredoc quoting through ssh mangles Python - write scratch
  files and `scp` them.
- `pkill -f <pattern>` matches the ssh session that runs it; kill by PID or use `[p]attern`.
- The VPS never holds proof-account keys; keys never appear in chat.
