# Telegram and watchdogs

## What
The owner's phone gets actionable or felt events only: buys, sells, autopsies, safety stops,
tidy-ups, the daily digest, the morning brief, the Friday court and scoreboard, milestones, alarms.
Research verdicts go to reports and briefs, never their own pings. Three dead-man watchdogs page
when the engine, the snapshot landing, or the data freshness goes quiet.

## Where
- `sandbox_proactive_lab.py:_notify` (engine telegrams; `_buy_msg`, `_sell_msg`, `_autopsy_msg`);
  the buy alert's delivery flag is stored on the record (`buy_alert_delivered`) and reconciled in
  the digest (`sandbox_proactive_lab.py:daily_digest`).
- Owner commands: `scripts/telegram_commands.py` (every 15 minutes); `/flatten` is the one exit
  exempt from the no-same-day-sell rule. Read its header for the command list.
- Engine watchdog: `scripts/engine_watch.sh` - reads `origin/main:data/last_cycle_ok`; a stale
  stamp during session hours pages "engine dead"; a crash loop rolls the workflow back to the
  last-good SHA recorded in that file.
- Inbox / heartbeat watchdog: `scripts/watchdog_vps.sh`; snapshot landing: `scripts/landing_watch.sh`.
- Freshness: `scripts/freshness_sentinel.py` (08:00 UTC): one row per evidence store and job with
  lag limits (session holes, day density, jsonl density, schedule rows, student model age).
- Failover exits: `scripts/engine_failover_exits.py` (the VPS can run exits if GHA is down).
- Page bundle: `scripts/page_bundle.sh` runs from both watchdogs' page paths and writes
  `reports/shadow_lab/page_bundles/<utc>_<reason>.md` (last-good stamp, last commits, last engine
  runs from the public Actions API, watchdog log tails, sentinel rows, book counts, which map files
  to read), pushed to main with `[skip ci]`. Start every page investigation from the bundle.

## Exercise
- `tail -20 /home/poller/engine_watch.log`; `./.venv/bin/python scripts/freshness_sentinel.py`.
- `git show origin/main:data/last_cycle_ok` (stamp + SHA).

## Healthy
- A digest each weekday evening; a morning brief each weekday; a court and scoreboard each Friday.
- `/home/poller/engine_watch.log` lines without DEAD or ROLLBACK during the session.

## Evidence
- `reports/shadow_lab/sentinels.jsonl`; the telegram bot's own history.

## Checks
- MOT dimension 5 observability (6 checks); the digest renders the scoreboard and reconciliation lines.

## Traps
- 2026-07-08 SILENT-DEATH ALARM OFF; 2026-08-07 8 FALSE "ENGINE DEAD" PAGES; 2026-08-18/20 auto-
  rollback with collateral and a false rollback (twin schedulers).
- 2026-09-07 THE WATCHDOG'S MESSENGER FAILED SILENTLY (sentinel ran, telegram did not send).
- 2026-09-11 the inbox watchdog was the one that caught the 55-minute blind window: it watches the
  DATA, not exit codes. Keep it that way.
- Never put n8n or LLM judgment in the trade path; the morning brief is the one adopted agent pattern.
