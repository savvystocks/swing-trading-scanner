# VPS cron slots

All times UTC; `crontab -l` on the VPS is the source. Every job pulls `main` first. Logs live in
`/home/poller/`. The freshness sentinel (08:00 daily) carries a row per job with its expected
cadence; a red row is the first place to look.

Retired 2026-09-21 (owner ended Unusual Whales and switched off every directional strategy): the archive and
prints pullers, the Saturday legs pull, the shadow lab and breaker, the student gate and live exit, the
monthly corpus, the nightly corpus chain and both Friday tuner jobs. The final data pull ran once from
`~/cs_multi/final_pulls.sh`. The crontab backup is `~/cron.pre_uw_exit.bak`.

Retired 2026-09-26 (the harvest froze on 2026-09-25 with its last label and the court's docket held no living
challenger): the harvest poller (its quarter-hour mirror of origin/main survives as `scripts/mirror_sync_vps.sh`
in the same slot), the nightly off-box snapshot (its final push, 2026-09-25 21:30, carries harvest_20260925_2130
and cs_legs_20260925_2130), the integrity gate, the archiver watch and the court's three slots.
`scripts/watchdog_vps.sh` stays: `scripts/engine_watch.sh` covers the stall with a slower fuse but its
session window is a hard-coded summer clock, and the watchdog is the only intraday disk alarm.

| slot | job | log | healthy |
|---|---|---|---|
| */15 13-21 Mon-Fri | `scripts/mirror_sync_vps.sh` (fetch + reset --hard to origin/main; the retired poller's first action, kept because the sentinel's mtimes, the Monday judge runs and the quote log read this tree; then the external dead-man: pings HEALTHCHECK_URL from `.harvest_env`, or its /fail endpoint when the fetch or reset failed) | mirror_sync.log | `HEAD is now at` lines, no `MIRROR SYNC FAILED` |
| */15 13-22 Mon-Fri | `scripts/watchdog_vps.sh` (engine dead-man on the `data/last_cycle_ok` stamp, 30 min) | watchdog log | no page |
| */15 14-21 Mon-Fri | `scripts/engine_watch.sh` (engine heartbeat, `data/last_cycle_ok`, auto-rollback to the last-good SHA) | engine_watch.log | `ok` lines, no rollback |
| */15 always | `scripts/telegram_commands.py` (owner commands) | telegram log | commands acknowledged |
| 15:05 and 19:50 Mon-Fri | `scripts/xsp_quote_log.py` (passive: XSP vs SPY quote width on the legs the credit spread would trade) | xsp_quotes.log | one line per run; `reports/research/xsp_quotes.jsonl` grows by two rows a day |
| Mon 14:07-21:07 hourly | `scripts/proof_stint.py` (the settle's verdict and the week-close telegram; today's equity row is an intraday mark, shown but not judged) | proof_stint.log | PROOF STINT line |
| 22:15 Mon-Fri | `scripts/daily_bars_archive.py` (30 ETF daily bars and the ^XSP/^GSPC closes into `data/daily_bars.db`) | daily_bars.log | one line per run |
| 22:18 Mon-Fri | `scripts/proof_stint.py` (the day's close mark judged against the -30% bound; Friday writes and pushes `reports/performance/proof_stint.json`) | proof_stint.log | PROOF STINT line |
| 22:20 Mon-Fri | `scripts/daily_digest.py` (exits by `closed_at`, settles by `at`, both books) | digest.log | digest telegram sent |
| 22:24 Mon-Fri | `scripts/returns_alarms.py` | returns_alarms.log | - |
| Fri 22:40 | `scripts/returns_ledger.py --update-map`, then commit and push of the ledger and `docs/performance_map` | returns.log | the ledger table |
| 22:45 Mon-Fri | `scripts/evening_persist.sh` | evening_persist.log | - |
| 22:45 Mon-Sat | `scripts/landing_watch.sh` (kill-switch poller state only since 2026-09-26) | landing_watch.log | `OK: all scheduled artifacts landed` |
| 08:00 daily | `scripts/freshness_sentinel.py` | freshness log | all rows green |
| 08:10 Mon-Fri | `scripts/morning_analyst.py` | analyst.log | morning brief telegram |
| Sat 12:00 | `scripts/cs_live_fills.py` (the credit spread's real fills, read-only, Alpaca) | cs_legs.log | `cs live fills: n/n records with both fills` |
| Fri 22:25 | `scripts/trajectory_scoreboard.py` | scoreboard.log | North Star block |

## Exercise
- `crontab -l | grep <script>`; `tail -20 /home/poller/<log>`; `./.venv/bin/python scripts/freshness_sentinel.py`.

## Traps
- 2026-09-19 THE PRINTS TAPE IS THINNED BY THE VENDOR AND WAS BEING CAPTURED BY LUCK: contract-days pulled
  fresh hold 149-484 prints, the same requests a week later return 2-9, and recent days return nothing at all
  for several days first. scripts/uw_flow_prints.py:is_final (deleted 2026-09-21) now keeps every contract-day inside a 12-day
  window open - asked again nightly, fullest tape kept - and the session prints one `window` line per day so the
  vendor's clock can be read off the log. A full tape that was missed cannot be re-pulled at any price.
- 2026-09-19 TRUNCATED DAYS ARE RE-PAGED WITH LEFTOVER BUDGET: scripts/uw_history_pull.py:needs_repage (deleted 2026-09-21) picks the
  stored ticker-days that sit exactly at 500 rows with more than UW_MIN_TAIL_VOL (10) lots in their thinnest row;
  the `repaged` table marks a day only when all of them are done. Both pullers end every session by writing
  scripts/uw_history_pull.py:_session_state (deleted 2026-09-21) to a file the landing watch reads.
- 2026-04-28 CRON DRIFT; 2026-08-05 WATCHDOG CRON SILENTLY LOST; 2026-09-04 (evening) FRIDAY CHAIN
  TRIPPED ON AN UNCOMMITTED SCRIPT; 2026-09-04 (late) NIGHTLY BOUNDARY SILENT 3 NIGHTS; 2026-09-07
  THE WATCHDOG'S MESSENGER FAILED SILENTLY.
- 2026-09-17 TWO YEARS OF ARCHIVE TRUNCATED AT 500 A DAY: scripts/uw_history_pull.py (deleted 2026-09-21) asked for
  `limit=500` and never for page 2, so 80.6% of ticker-days sat at exactly the cap and the
  low-volume far-OTM tail was silently absent (SPY cut at volume 1,262). `limit` is a hard SERVER
  cap; `&page=N` is the only way past it and `offset`/`skip` are ignored. START was also 2024-09-03
  against a ROLLING 730-TRADING-day token floor, so entitled history was expiring unpulled. The
  puller now pages while a page comes back full with volume still in its tail, and prints
  TRUNCATION WARNING when it stops early. Days already stored keep their truncated chains -
  re-paging them is owed.
- 2026-09-18 THE ARCHIVE PULLER DIED ON A LOCKED DATABASE: `scripts/fade_meta.py` (22:10, ~30 minutes) reads
  `data/uw_history.db` while scripts/uw_history_pull.py (deleted 2026-09-21) (22:30) writes it; a commit that cannot take its
  exclusive lock inside the timeout raised and ended the night at call 900. scripts/uw_history_pull.py:commit_retry (deleted 2026-09-21)
  now waits a lock out (MOT 6.27). The page cap is 12 after 5 tripped the truncation sentinel on night one.
  Any new job that scans the archive in the 22:30-02:00 UTC window shares this lock.
- 2026-09-01 VENV DEPENDENCY DRIFT: jobs that import sklearn or pandas must use `./.venv/bin/python`.
- A dirty working tree on the VPS makes `git pull --ff-only` fail for every job that follows; never
  leave uncommitted edits on the VPS overnight.
