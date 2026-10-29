# PAGE BUNDLE 20261029T140003Z

reason: watchdog: no completed cycle for 904m
utc: 2026-10-29T14:00:03Z   local(BST/GMT): 2026-10-29T14:00:03

## last-good cycle (origin/main:data/last_cycle_ok)
2026-10-28T22:55:14Z
9b00b3eb143dde98d946d1edf2d9b6132942e5c3

## last commits on main
4fd2bcb8 2026-10-28 22:55:14 +0000 sandbox lab data [skip ci]
9b00b3eb 2026-10-28 22:45:01 +0000 evening persist: court verdicts + sentinels + breaker 2026-10-28 [skip ci]
b8e6e003 2026-10-28 21:51:47 +0000 sandbox lab data [skip ci]
bbae403f 2026-10-28 21:50:39 +0000 docs: ledger - doubling the S&P by leverage answered NO from recorded rows (research 
c99d0a70 2026-10-28 21:41:54 +0000 sandbox lab data [skip ci]

## last engine runs (GitHub Actions, v10_lab.yml)
(actions api unavailable)

## engine_watch.log (tail)
2026-10-28T17:30:03Z ok: heartbeat 8 min
2026-10-28T17:45:04Z ok: heartbeat 3 min
2026-10-28T18:00:03Z ok: heartbeat 8 min
2026-10-28T18:15:04Z ok: heartbeat 3 min
2026-10-28T18:30:03Z ok: heartbeat 8 min
2026-10-28T18:45:04Z ok: heartbeat 3 min
2026-10-28T19:00:03Z ok: heartbeat 8 min
2026-10-28T19:15:03Z ok: heartbeat 3 min
2026-10-28T19:30:04Z ok: heartbeat 8 min
2026-10-28T19:45:04Z ok: heartbeat 3 min
2026-10-28T20:00:03Z ok: heartbeat 8 min
2026-10-29T14:00:03Z ALARM: engine heartbeat is 904 min old during market hours - cycles are NOT completing (GHA timeout / dispatcher down / platform incident). Running VPS FULL FAILOVER cycle now (entries+exits+harvest).

## watchdog status
{"ts_utc":"2026-10-29T13:45:04Z","market_open":0,"last_cycle_ok_age_min":889,"status":"ok"}

## sentinel rows (tail)
{"run": "2026-09-25", "book": "SENTINEL_C2", "days": 21, "llr": -2.14, "t": -3.91, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-25", "book": "SENTINEL_C3", "days": 21, "llr": -2.01, "t": -3.55, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-25", "book": "SENTINEL_C4", "days": 21, "llr": -1.95, "t": -3.56, "thr": -3.19, "verdict": "accruing"}

## book
records by status: {'CLOSED': 674, 'CANCELLED': 76, 'FLUSHED': 129, 'SENT': 6, 'CLOSED_RECONCILED_UNTRACKED_EXIT': 9, 'STALE_CANCELLED_RECONCILED': 46, 'LOGGED': 37, 'SHADOW': 19, None: 71, 'MEASUREMENT_PROBE': 2, 'RETIRED': 57, 'VOID': 1, 'OPEN': 1}
open option records: 1 newest entry: 2026-10-19T15:01:57.433959+00:00

## read next (docs/feature_map)
- telegram-and-watchdogs.md, then the subsystem the reason names
