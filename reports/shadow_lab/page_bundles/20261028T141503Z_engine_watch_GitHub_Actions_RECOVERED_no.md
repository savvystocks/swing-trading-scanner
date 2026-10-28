# PAGE BUNDLE 20261028T141503Z

reason: engine_watch: GitHub Actions RECOVERED - normal engine cycles resumed; VPS failover standing down. No action needed.
utc: 2026-10-28T14:15:03Z   local(BST/GMT): 2026-10-28T14:15:03

## last-good cycle (origin/main:data/last_cycle_ok)
2026-10-28T14:11:57Z
76b861aaa79409544baeed740997caed2aa04dae

## last commits on main
3ba2a1aa 2026-10-28 14:11:57 +0000 sandbox lab data [skip ci]
76b861aa 2026-10-28 14:02:13 +0000 sandbox lab data [skip ci]
19e4c806 2026-10-28 14:00:19 +0000 vps failover exit pass [skip ci]
21fe1d13 2026-10-28 14:00:06 +0000 page bundle: engine_watch_engine_heartbeat_is_921_min [skip ci]
e06be41f 2026-10-27 22:38:51 +0000 sandbox lab data [skip ci]

## last engine runs (GitHub Actions, v10_lab.yml)
(actions api unavailable)

## engine_watch.log (tail)
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
2026-10-28T14:15:03Z ok: heartbeat 3 min
2026-10-28T14:15:03Z ALARM: GitHub Actions RECOVERED - normal engine cycles resumed; VPS failover standing down. No action needed.

## watchdog status
{"ts_utc":"2026-10-28T14:15:03Z","market_open":1,"last_cycle_ok_age_min":3,"status":"ok"}

## sentinel rows (tail)
{"run": "2026-09-25", "book": "SENTINEL_C2", "days": 21, "llr": -2.14, "t": -3.91, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-25", "book": "SENTINEL_C3", "days": 21, "llr": -2.01, "t": -3.55, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-25", "book": "SENTINEL_C4", "days": 21, "llr": -1.95, "t": -3.56, "thr": -3.19, "verdict": "accruing"}

## book
records by status: {'CLOSED': 674, 'CANCELLED': 76, 'FLUSHED': 129, 'SENT': 6, 'CLOSED_RECONCILED_UNTRACKED_EXIT': 9, 'STALE_CANCELLED_RECONCILED': 46, 'LOGGED': 37, 'SHADOW': 19, None: 71, 'MEASUREMENT_PROBE': 2, 'RETIRED': 57, 'VOID': 1, 'OPEN': 1}
open option records: 1 newest entry: 2026-10-19T15:01:57.433959+00:00

## read next (docs/feature_map)
- telegram-and-watchdogs.md, then the subsystem the reason names
