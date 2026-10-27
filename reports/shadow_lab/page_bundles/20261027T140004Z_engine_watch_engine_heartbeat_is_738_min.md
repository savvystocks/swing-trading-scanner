# PAGE BUNDLE 20261027T140004Z

reason: engine_watch: engine heartbeat is 738 min old during market hours - cycles are NOT completing (GHA timeout / dispatcher down / platform incident). Running VPS FULL FAILOVER cycle now (entries+exits+harvest).
utc: 2026-10-27T14:00:04Z   local(BST/GMT): 2026-10-27T14:00:04

## last-good cycle (origin/main:data/last_cycle_ok)
2026-10-26T23:08:07Z
a63c1ca1de34950a1b585443ede9f7cf4e85fdfd

## last commits on main
70f05d3d 2026-10-27 01:41:51 +0000 feat(research): the research desk - nine agent roles, two team scripts, desk tools wi
7f537f50 2026-10-27 01:02:00 +0000 docs: ledger result for strategy B pre-seat checks (0a fail, 0b pass, 0c no paper div
6e0a4829 2026-10-27 00:49:23 +0000 docs: ledger row for strategy B pre-seat checks, locked before their data is read [sk
49948d4c 2026-10-26 23:43:59 +0000 ops+docs: retire the proof stint judge's sentinel row; ledger, two standing rules, wh
233af88f 2026-10-26 23:08:08 +0000 sandbox lab data [skip ci]

## last engine runs (GitHub Actions, v10_lab.yml)
(actions api unavailable)

## engine_watch.log (tail)
2026-10-26T17:30:04Z ok: heartbeat 8 min
2026-10-26T17:45:03Z ok: heartbeat 3 min
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

## watchdog status
{"ts_utc":"2026-10-27T13:45:03Z","market_open":0,"last_cycle_ok_age_min":876,"status":"ok"}

## sentinel rows (tail)
{"run": "2026-09-25", "book": "SENTINEL_C2", "days": 21, "llr": -2.14, "t": -3.91, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-25", "book": "SENTINEL_C3", "days": 21, "llr": -2.01, "t": -3.55, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-25", "book": "SENTINEL_C4", "days": 21, "llr": -1.95, "t": -3.56, "thr": -3.19, "verdict": "accruing"}

## book
records by status: {'CLOSED': 674, 'CANCELLED': 76, 'FLUSHED': 129, 'SENT': 6, 'CLOSED_RECONCILED_UNTRACKED_EXIT': 9, 'STALE_CANCELLED_RECONCILED': 46, 'LOGGED': 37, 'SHADOW': 19, None: 69, 'MEASUREMENT_PROBE': 2, 'RETIRED': 57, 'VOID': 1, 'OPEN': 1}
open option records: 1 newest entry: 2026-10-19T15:01:57.433959+00:00

## read next (docs/feature_map)
- telegram-and-watchdogs.md, then the subsystem the reason names
