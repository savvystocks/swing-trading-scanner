# PAGE BUNDLE 20261028T140004Z

reason: watchdog: no completed cycle for 921m
utc: 2026-10-28T14:00:04Z   local(BST/GMT): 2026-10-28T14:00:04

## last-good cycle (origin/main:data/last_cycle_ok)
2026-10-27T22:38:50Z
7e76080e6172908ee5ebad2cf768ecce07dd035e

## last commits on main
e06be41f 2026-10-27 22:38:51 +0000 sandbox lab data [skip ci]
7e76080e 2026-10-27 21:51:25 +0000 sandbox lab data [skip ci]
a3b74633 2026-10-27 21:41:37 +0000 sandbox lab data [skip ci]
369454fb 2026-10-27 21:31:57 +0000 sandbox lab data [skip ci]
e8900c5e 2026-10-27 21:21:39 +0000 sandbox lab data [skip ci]

## last engine runs (GitHub Actions, v10_lab.yml)
(actions api unavailable)

## engine_watch.log (tail)
2026-10-27T17:30:03Z ok: heartbeat 8 min
2026-10-27T17:45:04Z ok: heartbeat 2 min
2026-10-27T18:00:03Z ok: heartbeat 8 min
2026-10-27T18:15:04Z ok: heartbeat 3 min
2026-10-27T18:30:04Z ok: heartbeat 8 min
2026-10-27T18:45:03Z ok: heartbeat 3 min
2026-10-27T19:00:04Z ok: heartbeat 8 min
2026-10-27T19:15:03Z ok: heartbeat 3 min
2026-10-27T19:30:04Z ok: heartbeat 8 min
2026-10-27T19:45:03Z ok: heartbeat 3 min
2026-10-27T20:00:03Z ok: heartbeat 8 min
2026-10-28T14:00:04Z ALARM: engine heartbeat is 921 min old during market hours - cycles are NOT completing (GHA timeout / dispatcher down / platform incident). Running VPS FULL FAILOVER cycle now (entries+exits+harvest).

## watchdog status
{"ts_utc":"2026-10-28T13:45:03Z","market_open":0,"last_cycle_ok_age_min":906,"status":"ok"}

## sentinel rows (tail)
{"run": "2026-09-25", "book": "SENTINEL_C2", "days": 21, "llr": -2.14, "t": -3.91, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-25", "book": "SENTINEL_C3", "days": 21, "llr": -2.01, "t": -3.55, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-25", "book": "SENTINEL_C4", "days": 21, "llr": -1.95, "t": -3.56, "thr": -3.19, "verdict": "accruing"}

## book
records by status: {'CLOSED': 674, 'CANCELLED': 76, 'FLUSHED': 129, 'SENT': 6, 'CLOSED_RECONCILED_UNTRACKED_EXIT': 9, 'STALE_CANCELLED_RECONCILED': 46, 'LOGGED': 37, 'SHADOW': 19, None: 70, 'MEASUREMENT_PROBE': 2, 'RETIRED': 57, 'VOID': 1, 'OPEN': 1}
open option records: 1 newest entry: 2026-10-19T15:01:57.433959+00:00

## read next (docs/feature_map)
- telegram-and-watchdogs.md, then the subsystem the reason names
