# Persist step and merge resolver

## What
The engine runs on an ephemeral GitHub runner; the record books survive only because the last
workflow step commits them to `main` (the harvest inbox rode the same step until 2026-09-26; the
transport is retired and `data/harvest_inbox/` is frozen history). Two runners can race (a stale checkout 34 seconds
after a push happened on 2026-09-11), so the push loop rebases, resolves whole-file JSON at record
level, and finally unions the book with `origin/main` so no record present on either side is lost.

## Where
- `.github/workflows/v10_lab.yml` step "Persist forensic logs to main": `git add -f` of the book,
  the proof book (`proof_logs.json`, `proof_logs_equity.jsonl` - the stint judge's inputs), cool-off, watchlist, `data/last_cycle_ok`, `reports/shadow_lab/student_scores.jsonl`, advisory
  files (the harvest inbox no longer, since 2026-09-26); `validate_log` (never push unparseable JSON); a five-attempt loop:
  push, on rejection `git pull --rebase --autostash`, on conflict `scripts/merge_logs.py`
  (record-level), on resolver failure abort and `-X theirs`; then the UNION GUARD
  `python scripts/merge_logs.py --guard origin/main` and an amend; a final validate and push.
- `scripts/merge_logs.py` - `merge_log` (union by trade_set_id, the more advanced version wins),
  `merge_state` (harvest state), flat-dict unions, the heartbeat file, unknown files taken from the
  run's own side instead of failing; `--selftest`; `--guard <ref>`.
- Concurrency: group `v10-lab`, `cancel-in-progress: false`; job timeout 8 minutes.

## Exercise
- `python scripts/merge_logs.py --selftest` -> `merge_logs selftest: ALL PASS`.
- `gh run view <id> --log | grep -n "rejected\|CONFLICT\|merge_logs\|guard\|HEAD -> main"`.

## Healthy
- `   982fa02..f654da2  HEAD -> main` after `push rejected - rebasing onto sandbox, attempt 1` and
  `merge_logs: resolved data/harvest_state.json (9 ours + 9 theirs -> 9 merged)`.
- A guard line naming restored records is a race that was caught; note it, no action.
- `PERSIST FAILED - trade records NOT on main` fails the run and pages; investigate at once.

## Evidence
- `git log origin/main -- proactive_sandbox_logs.json`; a record's presence per commit is
  `git show <sha>:proactive_sandbox_logs.json | grep <occ>`.

## Checks
- MOT 6.14 pending-intent block (resolver handles the heartbeat file, never aborts on unknown files;
  the workflow runs the guard before every retried push; selftest passes).

## Traps
- 2026-08-12 RECORD VANISHED IN A PUSH RACE (NVDA) -> the record-level resolver.
- 2026-08-24 MASS-ADOPTION / CORRUPT-LOG -> the JSON validation gate.
- 2026-09-11 PUSHES BLOCKED BY A 131 MB CORPUS IN A NIGHTLY COMMIT -> corpora gitignored, MOT 6.10j.
- 2026-09-12 (second entry) A FILLED TRADE'S RECORD WAS LOST TO A PUSH RACE (NBIS) -> the resolver
  no longer aborts on `data/last_cycle_ok`, and the union guard.
- `[skip ci]` in a commit subject keeps a data or docs push from dispatching the engine.
