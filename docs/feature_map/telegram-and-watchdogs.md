# Telegram and watchdogs

## What
The owner's phone gets actionable or felt events only: buys, sells, autopsies, safety stops,
tidy-ups, the daily digest, the morning brief, the Friday scoreboard, the proof stint's week closes and
verdicts, milestones, alarms. Research verdicts go to reports and briefs, never their own pings. Two
dead-man watchdogs page when the engine or the data freshness goes quiet; the external dead-man
(healthchecks.io, owner-created, emails on silence) rides the quarter-hour mirror
`scripts/mirror_sync_vps.sh` since 2026-09-26: a clean fetch + reset pings the check, a failed one pings
its /fail endpoint, the URL comes from `.harvest_env` and an unset URL pings nothing.

## Where
- `sandbox_proactive_lab.py:_notify` (engine telegrams; `_buy_msg`, `_sell_msg`, `_autopsy_msg`);
  the buy alert's delivery flag is stored on the record (`buy_alert_delivered`) and reconciled in
  the digest (`sandbox_proactive_lab.py:daily_digest`).
- Owner commands: `scripts/telegram_commands.py` (every 15 minutes); `/flatten` is the one exit
  exempt from the no-same-day-sell rule. Read its header for the command list.
- Engine watchdog: `scripts/engine_watch.sh` - reads `origin/main:data/last_cycle_ok`; a stale
  stamp during session hours pages "engine dead"; a crash loop rolls the workflow back to the
  last-good SHA recorded in that file.
- Second dead-man, independent of the first: `scripts/watchdog_vps.sh` reads the stamp in
  `origin/main:data/last_cycle_ok` and pages when it is older than 30 minutes during the session (until
  2026-09-24 it read the harvest inbox's newest commit); kill-switch poller state: `scripts/landing_watch.sh`.
- Proof-week close, streak met, pass, fail and drawdown breach: `scripts/proof_stint.py:announce`, once per event,
  marked only after a confirmed send (`scripts/proof_stint.py:send_telegram` returns True on a 200).
- Evening digest: `scripts/daily_digest.py:trade_lines` (22:20 UTC) reads exits by `closed_at` and settles
  by `at` from both books; `scripts/daily_digest.py:main` takes a day for a replay.
- Freshness: `scripts/freshness_sentinel.py` (08:00 UTC): one row per in-use store and job (schedule rows on
  the logs, push-sync on both checkouts, a daily `git pull --rebase --autostash` of the kill-switch repository
  that pages on rc != 0 or a leftover rebase, spec parse, expired/ghost scans of both books, disk, failover
  flag); a schedule row younger than its first firing (`FIRST_RUN`) is not yet due, never CHECK FAILED.
- Failover exits: `scripts/engine_failover_exits.py` (the VPS can run exits if GHA is down).
- Page bundle: `scripts/page_bundle.sh` runs from both watchdogs' page paths and writes
  `reports/shadow_lab/page_bundles/<utc>_<reason>.md` (last-good stamp, last commits, last engine
  runs from the public Actions API, watchdog log tails, sentinel rows, book counts, which map files
  to read), pushed to main with `[skip ci]`. Start every page investigation from the bundle.

## Exercise
- `tail -20 /home/poller/engine_watch.log`; `./.venv/bin/python scripts/freshness_sentinel.py`.
- `git show origin/main:data/last_cycle_ok` (stamp + SHA).

## Healthy
- A digest each weekday evening; a morning brief each weekday; a scoreboard each Friday (the court retired 2026-09-26).
- A `PROOF WEEK n CLOSED` telegram every Monday a proof spread settles.
- `/home/poller/engine_watch.log` lines without DEAD or ROLLBACK during the session.

## Evidence
- `reports/shadow_lab/sentinels.jsonl`; the telegram bot's own history.

## Checks
- MOT dimension 5 observability (6 checks); the digest renders the scoreboard and reconciliation lines.
- MOT 6.39 (the evening digest lists a `closed_at` exit and an `at` settle on their day, nothing on another) and
  6.40 (the VPS watchdog reads the cycle stamp, never the harvest inbox).

## Traps
- 2026-09-26 (second entry) THE KILL SWITCH COULD NOT PUBLISH WHILE THE WATCHDOG'S STAMP WAS DIRTY:
  `scripts/watchdog_vps.sh` rewrites `/home/poller/harvest-snapshots/watchdog_status.json` every quarter-hour and only the
  nightly snapshot committed it, so `scripts/telegram_commands.py:_write_flag`'s plain `git pull --rebase` refused
  the dirty tree and /halt answered COMMAND FAILED TO PUBLISH outside one quarter-hour a day. The pull now carries
  `--autostash` (MOT 6.45); the sentinel row "kill-switch repo push sync" pages on an unpushed commit there and the
  row "kill-switch repo pull" runs the same pull every morning and pages when it is refused or a rebase is left
  unfinished (a refused pull returns False in `_write_flag` before any commit exists, so push-sync alone cannot
  see it). A control channel is tested by sending a command through it.
- 2026-09-26: the proof stint judge's telegrams are marked sent only after a confirmed 200; a failed send is retried
  on the next run and logged `TELEGRAM SEND FAILED` (the 2026-09-07 messenger class).
- 2026-09-22: the kill switch publishes through ~/harvest-snapshots, and for twelve days every push to that
  repo was rejected on GitHub's 100 MB file limit (the nightly database snapshots), so `/halt` would have failed.
  Control flags never share a transport with bulk data; the nightly gz is now split into 90 MB parts.
- 2026-09-19 THE LANDING WATCH PAGED A FALSE ALARM EVERY NIGHT: `scripts/landing_watch.sh` looked for today's date
  in the last 5 lines of the integrity gate's log, and the gate had grown to 7 lines below its dated header. A
  watch that greps a fixed tail of another job's log breaks the day that job prints one more line; the window is
  40 now and MOT 6.28 holds it above 20. The same watch now reads both archive pullers' session-state files.
- 2026-07-08 SILENT-DEATH ALARM OFF; 2026-08-07 8 FALSE "ENGINE DEAD" PAGES; 2026-08-18/20 auto-
  rollback with collateral and a false rollback (twin schedulers).
- 2026-09-07 THE WATCHDOG'S MESSENGER FAILED SILENTLY (sentinel ran, telegram did not send).
- 2026-09-11 the inbox watchdog was the one that caught the 55-minute blind window: it watched the
  DATA, not exit codes - and on 2026-09-24 that data had stopped: the harvest inbox went quiet when Unusual
  Whales ended and the watchdog paged 28 times in two days. It now reads the engine's completion stamp; when a
  feed is switched off, grep every watchdog and sentinel for the artefacts the feed produced (MOT 6.40).
- 2026-09-24 THE EVENING DIGEST NEVER REPORTED A SALE OR A SETTLE: `scripts/daily_digest.py` read
  `exit_ts_utc` and `ts` from records that carry `closed_at` and `at`, so every evening since 2026-08-25 said
  "Sold today: nothing". A report that prints a reassuring sentence must be proven on a day when something
  happened (MOT 6.39).
- Never put n8n or LLM judgment in the trade path; the morning brief is the one adopted agent pattern.
- 2026-09-14 (third entry) THE EIGHT-MINUTE WALL: a GitHub run cancelled at its timeout is not a failure;
  the cycle sentinel is stamped only on success, but one successful run inside the heartbeat window keeps
  `scripts/engine_watch.sh` green, so a quarter of cycles died for a week unseen. Count cancelled runs; the
  heartbeat only proves the last one finished.
