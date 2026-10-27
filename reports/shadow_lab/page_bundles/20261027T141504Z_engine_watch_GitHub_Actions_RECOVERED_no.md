# PAGE BUNDLE 20261027T141504Z

reason: engine_watch: GitHub Actions RECOVERED - normal engine cycles resumed; VPS failover standing down. No action needed.
utc: 2026-10-27T14:15:04Z   local(BST/GMT): 2026-10-27T14:15:04

## last-good cycle (origin/main:data/last_cycle_ok)
2026-10-27T14:11:47Z
81468c208508c1c1b53e4d146fae0e5910e9f214

## last commits on main
67be1f0e 2026-10-27 14:11:48 +0000 sandbox lab data [skip ci]
81468c20 2026-10-27 14:02:24 +0000 sandbox lab data [skip ci]
be14aa40 2026-10-27 14:00:18 +0000 vps failover exit pass [skip ci]
89950911 2026-10-27 14:00:06 +0000 page bundle: engine_watch_engine_heartbeat_is_738_min [skip ci]
70f05d3d 2026-10-27 01:41:51 +0000 feat(research): the research desk - nine agent roles, two team scripts, desk tools wi

## last engine runs (GitHub Actions, v10_lab.yml)
(actions api unavailable)

## engine_watch.log (tail)
2026-10-26T18:00:04Z ok: heartbeat 8 min
2026-10-26T18:15:03Z ok: heartbeat 3 min
2026-10-26T18:30:03Z ok: heartbeat 8 min
2026-10-26T18:45:03Z ok: heartbeat 3 min
2026-10-26T19:00:03Z ok: heartbeat 8 min
2026-10-26T19:15:03Z ok: heartbeat 2 min
2026-10-26T19:30:04Z ok: heartbeat 8 min
2026-10-26T19:45:03Z ok: heartbeat 3 min
2026-10-26T20:00:04Z ok: heartbeat 8 min
2026-10-27T14:00:04Z ALARM: engine heartbeat is 738 min old during market hours - cycles are NOT completing (GHA timeout / dispatcher down / platform incident). Running VPS FULL FAILOVER cycle now (entries+exits+harvest).
2026-10-27T14:15:04Z ok: heartbeat 3 min
2026-10-27T14:15:04Z ALARM: GitHub Actions RECOVERED - normal engine cycles resumed; VPS failover standing down. No action needed.

## watchdog status
{"ts_utc":"2026-10-27T14:15:04Z","market_open":1,"last_cycle_ok_age_min":3,"status":"ok"}

## sentinel rows (tail)
{"run": "2026-09-25", "book": "SENTINEL_C2", "days": 21, "llr": -2.14, "t": -3.91, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-25", "book": "SENTINEL_C3", "days": 21, "llr": -2.01, "t": -3.55, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-25", "book": "SENTINEL_C4", "days": 21, "llr": -1.95, "t": -3.56, "thr": -3.19, "verdict": "accruing"}

## book
records by status: {'CLOSED': 674, 'CANCELLED': 76, 'FLUSHED': 129, 'SENT': 6, 'CLOSED_RECONCILED_UNTRACKED_EXIT': 9, 'STALE_CANCELLED_RECONCILED': 46, 'LOGGED': 37, 'SHADOW': 19, None: 70, 'MEASUREMENT_PROBE': 2, 'RETIRED': 57, 'VOID': 1, 'OPEN': 1}
open option records: 1 newest entry: 2026-10-19T15:01:57.433959+00:00

## read next (docs/feature_map)
- telegram-and-watchdogs.md, then the subsystem the reason names
