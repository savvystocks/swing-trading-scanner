# VPS cron slots

All times UTC; `crontab -l` on the VPS is the source. Every job pulls `main` first. Logs live in
`/home/poller/`. The freshness sentinel (08:00 daily) carries a row per job with its expected
cadence; a red row is the first place to look.

| slot | job | log | healthy |
|---|---|---|---|
| */15 13-21 Mon-Fri | `scripts/run_poller_vps.sh` (harvest poller) | poller log | `data/harvest.db` max(day) = today |
| */15 13-22 Mon-Fri | `scripts/watchdog_vps.sh` (inbox / heartbeat dead-man) | watchdog log | no page |
| */15 14-21 Mon-Fri | `scripts/engine_watch.sh` (engine heartbeat, `data/last_cycle_ok`, auto-rollback to the last-good SHA) | engine_watch.log | `ok` lines, no rollback |
| */15 always | `scripts/telegram_commands.py` (owner commands) | telegram log | commands acknowledged |
| 21:30 Mon-Fri | `/home/poller/backup_snapshot.sh` | - | snapshot landed (landing_watch) |
| 21:50 Mon-Fri | `scripts/shadow_lab_nightly.sh` | - | ledger rows appended |
| 22:00 Mon-Fri | `scripts/sunday_boundary.py` report-only, sequential apply (trajectory) | trajectory log | nightly line |
| 22:05 Tue-Sat | `scripts/integrity_gate.py` | - | gate green |
| 22:10 Mon-Fri | `scripts/fade_meta.py` (student gate page) | fade_meta.log | ledger appended |
| 22:12 Mon-Fri | `scripts/shadow_breaker.py` | breaker.log | - |
| 22:15 Mon-Fri | `scripts/archiver_watch.sh` | archiver_watch.log | - |
| 22:20 Mon-Fri | `scripts/daily_digest.py` | digest.log | digest telegram sent |
| 22:30 daily | `scripts/uw_history_pull.py` (budget 30000) | - | new archive days, zero-result defer |
| 22:45 Mon-Sat | `scripts/landing_watch.sh`, `scripts/evening_persist.sh` | landing_watch.log, evening_persist.log | - |
| 00:15 daily | `scripts/uw_flow_prints.py` (budget 12000) | - | prints for the new day |
| 01:45 Tue-Sat | corpus chain: hourly_library -> probe_tuner build -> glide_sim build | corpus_nightly.log | `row build complete` |
| 08:00 daily | `scripts/freshness_sentinel.py` | freshness log | all rows green |
| 08:10 Mon-Fri | `scripts/morning_analyst.py` | analyst.log | morning brief telegram |
| Wed 10:00 | `scripts/sunday_boundary.py` report-only | sunday_boundary.log | standings |
| Fri 20:15 | `scripts/probe_tuner.py` (tuner report) | tuner.log | anchors vs incumbents |
| Fri 21:45 | hourly_library -> glide_sim -> `scripts/tuner_apply.py` | tuner.log | HOLD or an applied change with verify-after-push |
| Fri 22:25 | `scripts/trajectory_scoreboard.py` | scoreboard.log | North Star block |
| Fri 22:35 | `scripts/sunday_boundary.py` (the court) | sunday_boundary.log | verdict lines |
| Sat 09:00 | `scripts/student_live_exit.py` | student_live_exit.log | `waiting` until 20 closed fills |
| monthly Sat 08:00 | `scripts/historical_corpus.py` | - | - |

## Exercise
- `crontab -l | grep <script>`; `tail -20 /home/poller/<log>`; `./.venv/bin/python scripts/freshness_sentinel.py`.

## Traps
- 2026-04-28 CRON DRIFT; 2026-08-05 WATCHDOG CRON SILENTLY LOST; 2026-09-04 (evening) FRIDAY CHAIN
  TRIPPED ON AN UNCOMMITTED SCRIPT; 2026-09-04 (late) NIGHTLY BOUNDARY SILENT 3 NIGHTS; 2026-09-07
  THE WATCHDOG'S MESSENGER FAILED SILENTLY.
- 2026-09-01 VENV DEPENDENCY DRIFT: jobs that import sklearn or pandas must use `./.venv/bin/python`.
- A dirty working tree on the VPS makes `git pull --ff-only` fail for every job that follows; never
  leave uncommitted edits on the VPS overnight.
