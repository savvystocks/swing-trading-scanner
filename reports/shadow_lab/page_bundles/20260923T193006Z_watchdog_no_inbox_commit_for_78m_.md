# PAGE BUNDLE 20260923T193006Z

reason: watchdog: no inbox commit for 78m
utc: 2026-09-23T19:30:06Z   local(BST/GMT): 2026-09-23T20:30:06

## last-good cycle (origin/main:data/last_cycle_ok)
2026-09-23T19:21:37Z
6077fb3043ef4f6c6ef161e80a4557df38f654ad

## last commits on main
0d8e36ba 2026-09-23 19:21:38 +0000 sandbox lab data [skip ci]
6077fb30 2026-09-23 19:15:09 +0000 page bundle: watchdog_no_inbox_commit_for_63m_ [skip ci]
d274ead4 2026-09-23 19:11:41 +0000 sandbox lab data [skip ci]
bc72bc4f 2026-09-23 19:02:07 +0000 sandbox lab data [skip ci]
beff30d4 2026-09-23 19:00:08 +0000 page bundle: watchdog_no_inbox_commit_for_48m_ [skip ci]

## last engine runs (GitHub Actions, v10_lab.yml)
(actions api unavailable)

## engine_watch.log (tail)
2026-09-23T16:45:15Z ok: heartbeat 0 min
2026-09-23T17:00:03Z ok: heartbeat 8 min
2026-09-23T17:15:15Z ok: heartbeat 0 min
2026-09-23T17:30:03Z ok: heartbeat 8 min
2026-09-23T17:45:03Z ok: heartbeat 3 min
2026-09-23T18:00:04Z ok: heartbeat 8 min
2026-09-23T18:15:15Z ok: heartbeat 3 min
2026-09-23T18:30:03Z ok: heartbeat 8 min
2026-09-23T18:45:03Z ok: heartbeat 3 min
2026-09-23T19:00:16Z ok: heartbeat 0 min
2026-09-23T19:15:15Z ok: heartbeat 0 min
2026-09-23T19:30:03Z ok: heartbeat 8 min

## watchdog status
{"ts_utc":"2026-09-23T19:15:13Z","market_open":1,"last_inbox_commit_age_min":63,"status":"stalled"}

## sentinel rows (tail)
{"run": "2026-09-22", "book": "SENTINEL_C2", "days": 21, "llr": -2.14, "t": -3.91, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-22", "book": "SENTINEL_C3", "days": 21, "llr": -2.01, "t": -3.55, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-22", "book": "SENTINEL_C4", "days": 21, "llr": -1.95, "t": -3.56, "thr": -3.19, "verdict": "accruing"}

## book
records by status: {'CLOSED': 655, 'CANCELLED': 75, 'FLUSHED': 129, 'SENT': 6, 'CLOSED_RECONCILED_UNTRACKED_EXIT': 9, 'STALE_CANCELLED_RECONCILED': 46, 'LOGGED': 37, 'SHADOW': 19, None: 46, 'MEASUREMENT_PROBE': 2, 'RETIRED': 57, 'VOID': 1, 'OPEN': 16}
open option records: 15 newest entry: 2026-09-21T17:54:24.299Z

## read next (docs/feature_map)
- persist-and-merge.md, market-gate.md, telegram-and-watchdogs.md
