# PAGE BUNDLE 20261030T140003Z

reason: watchdog: no completed cycle for 893m
utc: 2026-10-30T14:00:03Z   local(BST/GMT): 2026-10-30T14:00:03

## last-good cycle (origin/main:data/last_cycle_ok)
2026-10-29T23:06:31Z
2adfbff3a71d25748eabe43aebe95312be283e8e

## last commits on main
c2831d03 2026-10-29 23:06:32 +0000 sandbox lab data [skip ci]
2adfbff3 2026-10-29 22:45:01 +0000 evening persist: court verdicts + sentinels + breaker 2026-10-29 [skip ci]
5b003364 2026-10-29 21:51:36 +0000 sandbox lab data [skip ci]
e1736d4e 2026-10-29 21:41:40 +0000 sandbox lab data [skip ci]
c8c717e5 2026-10-29 21:31:53 +0000 sandbox lab data [skip ci]

## last engine runs (GitHub Actions, v10_lab.yml)
(actions api unavailable)

## engine_watch.log (tail)
2026-10-29T17:30:03Z ok: heartbeat 8 min
2026-10-29T17:45:03Z ok: heartbeat 3 min
2026-10-29T18:00:03Z ok: heartbeat 8 min
2026-10-29T18:15:03Z ok: heartbeat 3 min
2026-10-29T18:30:04Z ok: heartbeat 8 min
2026-10-29T18:45:03Z ok: heartbeat 3 min
2026-10-29T19:00:03Z ok: heartbeat 3 min
2026-10-29T19:15:03Z ok: heartbeat 3 min
2026-10-29T19:30:03Z ok: heartbeat 8 min
2026-10-29T19:45:04Z ok: heartbeat 3 min
2026-10-29T20:00:03Z ok: heartbeat 8 min
2026-10-30T14:00:03Z ALARM: engine heartbeat is 893 min old during market hours - cycles are NOT completing (GHA timeout / dispatcher down / platform incident). Running VPS FULL FAILOVER cycle now (entries+exits+harvest).

## watchdog status
{"ts_utc":"2026-10-30T13:45:03Z","market_open":0,"last_cycle_ok_age_min":878,"status":"ok"}

## sentinel rows (tail)
{"run": "2026-09-25", "book": "SENTINEL_C2", "days": 21, "llr": -2.14, "t": -3.91, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-25", "book": "SENTINEL_C3", "days": 21, "llr": -2.01, "t": -3.55, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-25", "book": "SENTINEL_C4", "days": 21, "llr": -1.95, "t": -3.56, "thr": -3.19, "verdict": "accruing"}

## book
records by status: {'CLOSED': 674, 'CANCELLED': 76, 'FLUSHED': 129, 'SENT': 6, 'CLOSED_RECONCILED_UNTRACKED_EXIT': 9, 'STALE_CANCELLED_RECONCILED': 46, 'LOGGED': 37, 'SHADOW': 19, None: 72, 'MEASUREMENT_PROBE': 2, 'RETIRED': 57, 'VOID': 1, 'OPEN': 1}
open option records: 1 newest entry: 2026-10-19T15:01:57.433959+00:00

## read next (docs/feature_map)
- telegram-and-watchdogs.md, then the subsystem the reason names
