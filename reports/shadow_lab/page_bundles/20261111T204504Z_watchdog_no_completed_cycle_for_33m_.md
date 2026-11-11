# PAGE BUNDLE 20261111T204504Z

reason: watchdog: no completed cycle for 33m
utc: 2026-11-11T20:45:04Z   local(BST/GMT): 2026-11-11T20:45:04

## last-good cycle (origin/main:data/last_cycle_ok)
2026-11-11T20:11:45Z
0dff140450211973a32f1fa2963c1d779840b02b

## last commits on main
67d4ab00 2026-11-11 20:11:46 +0000 sandbox lab data [skip ci]
0dff1404 2026-11-11 20:09:07 +0000 sandbox lab data [skip ci]
56c161d9 2026-11-11 20:02:06 +0000 sandbox lab data [skip ci]
65b39a8c 2026-11-11 19:51:34 +0000 sandbox lab data [skip ci]
aa57e1e3 2026-11-11 19:50:04 +0000 xsp quote log [skip ci]

## last engine runs (GitHub Actions, v10_lab.yml)
(actions api unavailable)

## engine_watch.log (tail)
2026-11-11T18:00:03Z ok: heartbeat 8 min
2026-11-11T18:15:03Z ok: heartbeat 3 min
2026-11-11T18:30:04Z ok: heartbeat 8 min
2026-11-11T18:45:03Z ok: heartbeat 3 min
2026-11-11T19:00:04Z ok: heartbeat 8 min
2026-11-11T19:15:03Z ok: heartbeat 3 min
2026-11-11T19:30:04Z ok: heartbeat 8 min
2026-11-11T19:45:03Z ok: heartbeat 3 min
2026-11-11T20:00:03Z ok: heartbeat 8 min
2026-11-11T20:15:04Z ok: heartbeat 3 min
2026-11-11T20:30:03Z ok: heartbeat 18 min
2026-11-11T20:45:04Z ok: heartbeat 33 min

## watchdog status
{"ts_utc":"2026-11-11T20:30:03Z","market_open":1,"last_cycle_ok_age_min":18,"status":"ok"}

## sentinel rows (tail)
{"run": "2026-09-25", "book": "SENTINEL_C2", "days": 21, "llr": -2.14, "t": -3.91, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-25", "book": "SENTINEL_C3", "days": 21, "llr": -2.01, "t": -3.55, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-25", "book": "SENTINEL_C4", "days": 21, "llr": -1.95, "t": -3.56, "thr": -3.19, "verdict": "accruing"}

## book
records by status: {'CLOSED': 674, 'CANCELLED': 76, 'FLUSHED': 129, 'SENT': 6, 'CLOSED_RECONCILED_UNTRACKED_EXIT': 9, 'STALE_CANCELLED_RECONCILED': 46, 'LOGGED': 37, 'SHADOW': 19, None: 81, 'MEASUREMENT_PROBE': 2, 'RETIRED': 57, 'VOID': 1, 'OPEN': 1}
open option records: 1 newest entry: 2026-10-19T15:01:57.433959+00:00

## read next (docs/feature_map)
- telegram-and-watchdogs.md, then the subsystem the reason names
