# PAGE BUNDLE 20261029T141504Z

reason: engine_watch: GitHub Actions RECOVERED - normal engine cycles resumed; VPS failover standing down. No action needed.
utc: 2026-10-29T14:15:04Z   local(BST/GMT): 2026-10-29T14:15:04

## last-good cycle (origin/main:data/last_cycle_ok)
2026-10-29T14:11:52Z
44909d1bb3afcfd01db69c917f1bd2b40965b0c2

## last commits on main
0af58373 2026-10-29 14:11:53 +0000 sandbox lab data [skip ci]
44909d1b 2026-10-29 14:02:12 +0000 sandbox lab data [skip ci]
7cbc47e3 2026-10-29 14:00:15 +0000 vps failover exit pass [skip ci]
c02dd7f1 2026-10-29 14:00:05 +0000 page bundle: watchdog_no_completed_cycle_for_904m_ [skip ci]
4fd2bcb8 2026-10-28 22:55:14 +0000 sandbox lab data [skip ci]

## last engine runs (GitHub Actions, v10_lab.yml)
(actions api unavailable)

## engine_watch.log (tail)
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
2026-10-29T14:15:04Z ok: heartbeat 3 min
2026-10-29T14:15:04Z ALARM: GitHub Actions RECOVERED - normal engine cycles resumed; VPS failover standing down. No action needed.

## watchdog status
{"ts_utc":"2026-10-29T14:15:04Z","market_open":1,"last_cycle_ok_age_min":3,"status":"ok"}

## sentinel rows (tail)
{"run": "2026-09-25", "book": "SENTINEL_C2", "days": 21, "llr": -2.14, "t": -3.91, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-25", "book": "SENTINEL_C3", "days": 21, "llr": -2.01, "t": -3.55, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-25", "book": "SENTINEL_C4", "days": 21, "llr": -1.95, "t": -3.56, "thr": -3.19, "verdict": "accruing"}

## book
records by status: {'CLOSED': 674, 'CANCELLED': 76, 'FLUSHED': 129, 'SENT': 6, 'CLOSED_RECONCILED_UNTRACKED_EXIT': 9, 'STALE_CANCELLED_RECONCILED': 46, 'LOGGED': 37, 'SHADOW': 19, None: 72, 'MEASUREMENT_PROBE': 2, 'RETIRED': 57, 'VOID': 1, 'OPEN': 1}
open option records: 1 newest entry: 2026-10-19T15:01:57.433959+00:00

## read next (docs/feature_map)
- telegram-and-watchdogs.md, then the subsystem the reason names
