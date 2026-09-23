# PAGE BUNDLE 20260923T141506Z

reason: watchdog: no inbox commit for 33m
utc: 2026-09-23T14:15:06Z   local(BST/GMT): 2026-09-23T15:15:06

## last-good cycle (origin/main:data/last_cycle_ok)
2026-09-23T14:12:04Z
925005100323187d1f5dc50aca29d3865a013420

## last commits on main
cd61880a 2026-09-23 14:12:05 +0000 sandbox lab data [skip ci]
92500510 2026-09-23 14:02:25 +0000 sandbox lab data [skip ci]
cf4c5774 2026-09-23 13:51:50 +0000 sandbox lab data [skip ci]
60c0985b 2026-09-23 13:41:41 +0000 sandbox lab data [skip ci]
43c4ad33 2026-09-23 13:31:47 +0000 sandbox lab data [skip ci]

## last engine runs (GitHub Actions, v10_lab.yml)
(actions api unavailable)

## engine_watch.log (tail)
2026-09-22T17:30:14Z ok: heartbeat 4 min
2026-09-22T17:45:15Z ok: heartbeat 3 min
2026-09-22T18:00:16Z ok: heartbeat 4 min
2026-09-22T18:15:15Z ok: heartbeat 0 min
2026-09-22T18:30:14Z ok: heartbeat 5 min
2026-09-22T18:45:15Z ok: heartbeat 9 min
2026-09-22T19:00:16Z ok: heartbeat 5 min
2026-09-22T19:15:03Z ok: heartbeat 9 min
2026-09-22T19:30:02Z ok: heartbeat 5 min
2026-09-22T19:45:15Z ok: heartbeat 9 min
2026-09-22T20:00:15Z ok: heartbeat 2 min
2026-09-23T14:00:03Z ok: heartbeat 8 min

## watchdog status
{"ts_utc":"2026-09-23T14:00:04Z","market_open":1,"last_inbox_commit_age_min":18,"status":"ok"}

## sentinel rows (tail)
{"run": "2026-09-22", "book": "SENTINEL_C2", "days": 21, "llr": -2.14, "t": -3.91, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-22", "book": "SENTINEL_C3", "days": 21, "llr": -2.01, "t": -3.55, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-22", "book": "SENTINEL_C4", "days": 21, "llr": -1.95, "t": -3.56, "thr": -3.19, "verdict": "accruing"}

## book
records by status: {'CLOSED': 650, 'CANCELLED': 75, 'FLUSHED': 129, 'SENT': 6, 'CLOSED_RECONCILED_UNTRACKED_EXIT': 9, 'STALE_CANCELLED_RECONCILED': 46, 'LOGGED': 37, 'SHADOW': 19, None: 46, 'MEASUREMENT_PROBE': 2, 'RETIRED': 57, 'VOID': 1, 'OPEN': 21}
open option records: 20 newest entry: 2026-09-21T17:54:24.299Z

## read next (docs/feature_map)
- persist-and-merge.md, market-gate.md, telegram-and-watchdogs.md
