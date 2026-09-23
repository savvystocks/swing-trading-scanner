# PAGE BUNDLE 20260923T170005Z

reason: watchdog: no inbox commit for 108m
utc: 2026-09-23T17:00:05Z   local(BST/GMT): 2026-09-23T18:00:05

## last-good cycle (origin/main:data/last_cycle_ok)
2026-09-23T16:51:41Z
0a9a91a350af2ff95c193231b64c216a09395a13

## last commits on main
4048cb0f 2026-09-23 16:51:42 +0000 sandbox lab data [skip ci]
0a9a91a3 2026-09-23 16:45:08 +0000 page bundle: watchdog_no_inbox_commit_for_93m_ [skip ci]
82dc29b8 2026-09-23 16:41:48 +0000 sandbox lab data [skip ci]
6604740e 2026-09-23 16:31:43 +0000 sandbox lab data [skip ci]
01506792 2026-09-23 16:30:08 +0000 page bundle: watchdog_no_inbox_commit_for_78m_ [skip ci]

## last engine runs (GitHub Actions, v10_lab.yml)
(actions api unavailable)

## engine_watch.log (tail)
2026-09-23T14:15:15Z ok: heartbeat 0 min
2026-09-23T14:30:03Z ok: heartbeat 8 min
2026-09-23T14:45:04Z ok: heartbeat 3 min
2026-09-23T15:00:03Z ok: heartbeat 7 min
2026-09-23T15:15:05Z ok: heartbeat 3 min
2026-09-23T15:30:03Z ok: heartbeat 8 min
2026-09-23T15:45:04Z ok: heartbeat 3 min
2026-09-23T16:00:03Z ok: heartbeat 8 min
2026-09-23T16:15:03Z ok: heartbeat 2 min
2026-09-23T16:30:15Z ok: heartbeat 0 min
2026-09-23T16:45:15Z ok: heartbeat 0 min
2026-09-23T17:00:03Z ok: heartbeat 8 min

## watchdog status
{"ts_utc":"2026-09-23T16:45:11Z","market_open":1,"last_inbox_commit_age_min":93,"status":"stalled"}

## sentinel rows (tail)
{"run": "2026-09-22", "book": "SENTINEL_C2", "days": 21, "llr": -2.14, "t": -3.91, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-22", "book": "SENTINEL_C3", "days": 21, "llr": -2.01, "t": -3.55, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-22", "book": "SENTINEL_C4", "days": 21, "llr": -1.95, "t": -3.56, "thr": -3.19, "verdict": "accruing"}

## book
records by status: {'CLOSED': 654, 'CANCELLED': 75, 'FLUSHED': 129, 'SENT': 6, 'CLOSED_RECONCILED_UNTRACKED_EXIT': 9, 'STALE_CANCELLED_RECONCILED': 46, 'LOGGED': 37, 'SHADOW': 19, None: 46, 'MEASUREMENT_PROBE': 2, 'RETIRED': 57, 'VOID': 1, 'OPEN': 17}
open option records: 16 newest entry: 2026-09-21T17:54:24.299Z

## read next (docs/feature_map)
- persist-and-merge.md, market-gate.md, telegram-and-watchdogs.md
