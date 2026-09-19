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
- 2026-09-19 THE PRINTS TAPE IS THINNED BY THE VENDOR AND WAS BEING CAPTURED BY LUCK: contract-days pulled
  fresh hold 149-484 prints, the same requests a week later return 2-9, and recent days return nothing at all
  for several days first. `scripts/uw_flow_prints.py:is_final` now keeps every contract-day inside a 12-day
  window open - asked again nightly, fullest tape kept - and the session prints one `window` line per day so the
  vendor's clock can be read off the log. A full tape that was missed cannot be re-pulled at any price.
- 2026-09-19 TRUNCATED DAYS ARE RE-PAGED WITH LEFTOVER BUDGET: `scripts/uw_history_pull.py:needs_repage` picks the
  stored ticker-days that sit exactly at 500 rows with more than UW_MIN_TAIL_VOL (10) lots in their thinnest row;
  the `repaged` table marks a day only when all of them are done. Both pullers end every session by writing
  `scripts/uw_history_pull.py:_session_state` to a file the landing watch reads.
- 2026-04-28 CRON DRIFT; 2026-08-05 WATCHDOG CRON SILENTLY LOST; 2026-09-04 (evening) FRIDAY CHAIN
  TRIPPED ON AN UNCOMMITTED SCRIPT; 2026-09-04 (late) NIGHTLY BOUNDARY SILENT 3 NIGHTS; 2026-09-07
  THE WATCHDOG'S MESSENGER FAILED SILENTLY.
- 2026-09-17 TWO YEARS OF ARCHIVE TRUNCATED AT 500 A DAY: `scripts/uw_history_pull.py` asked for
  `limit=500` and never for page 2, so 80.6% of ticker-days sat at exactly the cap and the
  low-volume far-OTM tail was silently absent (SPY cut at volume 1,262). `limit` is a hard SERVER
  cap; `&page=N` is the only way past it and `offset`/`skip` are ignored. START was also 2024-09-03
  against a ROLLING 730-TRADING-day token floor, so entitled history was expiring unpulled. The
  puller now pages while a page comes back full with volume still in its tail, and prints
  TRUNCATION WARNING when it stops early. Days already stored keep their truncated chains -
  re-paging them is owed.
- 2026-09-18 THE ARCHIVE PULLER DIED ON A LOCKED DATABASE: `scripts/fade_meta.py` (22:10, ~30 minutes) reads
  `data/uw_history.db` while `scripts/uw_history_pull.py` (22:30) writes it; a commit that cannot take its
  exclusive lock inside the timeout raised and ended the night at call 900. `scripts/uw_history_pull.py:commit_retry`
  now waits a lock out (MOT 6.27). The page cap is 12 after 5 tripped the truncation sentinel on night one.
  Any new job that scans the archive in the 22:30-02:00 UTC window shares this lock.
- 2026-09-01 VENV DEPENDENCY DRIFT: jobs that import sklearn or pandas must use `./.venv/bin/python`.
- A dirty working tree on the VPS makes `git pull --ff-only` fail for every job that follows; never
  leave uncommitted edits on the VPS overnight.
