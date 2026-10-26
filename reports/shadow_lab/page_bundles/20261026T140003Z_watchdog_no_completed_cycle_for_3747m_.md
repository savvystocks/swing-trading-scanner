# PAGE BUNDLE 20261026T140003Z

reason: watchdog: no completed cycle for 3747m
utc: 2026-10-26T14:00:03Z   local(BST/GMT): 2026-10-26T14:00:03

## last-good cycle (origin/main:data/last_cycle_ok)
2026-10-23T23:32:37Z
98dab1b6bf99bbaa462ffa0b152169609d665efb

## last commits on main
b26077d2 2026-10-25 19:28:48 +0000 wind-down: the weekly XSP credit spread stops opening trades on both books; open reco
89cf8125 2026-10-24 12:00:09 +0000 cs live fills [skip ci]
9165ea9c 2026-10-23 23:32:38 +0000 sandbox lab data [skip ci]
98dab1b6 2026-10-23 22:40:03 +0000 returns ledger + performance map refresh [skip ci]
42ead9df 2026-10-23 22:18:03 +0000 proof stint state 2026-10-23 [skip ci]

## last engine runs (GitHub Actions, v10_lab.yml)
(actions api unavailable)

## engine_watch.log (tail)
2026-10-23T17:30:03Z ok: heartbeat 8 min
2026-10-23T17:45:04Z ok: heartbeat 3 min
2026-10-23T18:00:03Z ok: heartbeat 7 min
2026-10-23T18:15:03Z ok: heartbeat 3 min
2026-10-23T18:30:04Z ok: heartbeat 8 min
2026-10-23T18:45:03Z ok: heartbeat 3 min
2026-10-23T19:00:04Z ok: heartbeat 8 min
2026-10-23T19:15:03Z ok: heartbeat 3 min
2026-10-23T19:30:04Z ok: heartbeat 8 min
2026-10-23T19:45:04Z ok: heartbeat 3 min
2026-10-23T20:00:03Z ok: heartbeat 8 min
2026-10-26T14:00:03Z ALARM: engine heartbeat is 1111 min old during market hours - cycles are NOT completing (GHA timeout / dispatcher down / platform incident). Running VPS FULL FAILOVER cycle now (entries+exits+harvest).

## watchdog status
{"ts_utc":"2026-10-26T13:45:03Z","market_open":0,"last_cycle_ok_age_min":3732,"status":"ok"}

## sentinel rows (tail)
{"run": "2026-09-25", "book": "SENTINEL_C2", "days": 21, "llr": -2.14, "t": -3.91, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-25", "book": "SENTINEL_C3", "days": 21, "llr": -2.01, "t": -3.55, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-25", "book": "SENTINEL_C4", "days": 21, "llr": -1.95, "t": -3.56, "thr": -3.19, "verdict": "accruing"}

## book
records by status: {'CLOSED': 673, 'CANCELLED': 76, 'FLUSHED': 129, 'SENT': 6, 'CLOSED_RECONCILED_UNTRACKED_EXIT': 9, 'STALE_CANCELLED_RECONCILED': 46, 'LOGGED': 37, 'SHADOW': 19, None: 68, 'MEASUREMENT_PROBE': 2, 'RETIRED': 57, 'VOID': 1, 'OPEN': 2}
open option records: 1 newest entry: 2026-10-19T15:01:57.433959+00:00

## read next (docs/feature_map)
- telegram-and-watchdogs.md, then the subsystem the reason names
