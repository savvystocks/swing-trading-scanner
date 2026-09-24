# PAGE BUNDLE 20260924T180006Z

reason: watchdog: no inbox commit for 168m
utc: 2026-09-24T18:00:06Z   local(BST/GMT): 2026-09-24T19:00:06

## last-good cycle (origin/main:data/last_cycle_ok)
2026-09-24T17:52:14Z
195073547ee01f6c47237a3d8c41a2881082e13d

## last commits on main
872cb932 2026-09-24 17:52:16 +0000 sandbox lab data [skip ci]
aa44d847 2026-09-24 17:50:50 +0000 sandbox lab data [skip ci]
19507354 2026-09-24 17:45:07 +0000 page bundle: watchdog_no_inbox_commit_for_153m_ [skip ci]
a00b8071 2026-09-24 17:41:55 +0000 sandbox lab data [skip ci]
12ad0ca1 2026-09-24 17:31:54 +0000 sandbox lab data [skip ci]

## last engine runs (GitHub Actions, v10_lab.yml)
(actions api unavailable)

## engine_watch.log (tail)
2026-09-24T15:15:17Z ok: heartbeat 3 min
2026-09-24T15:30:02Z ok: heartbeat 7 min
2026-09-24T15:45:14Z ok: heartbeat 0 min
2026-09-24T16:00:02Z ok: heartbeat 8 min
2026-09-24T16:15:03Z ok: heartbeat 3 min
2026-09-24T16:30:14Z ok: heartbeat 0 min
2026-09-24T16:45:15Z ok: heartbeat 0 min
2026-09-24T17:00:15Z ok: heartbeat 0 min
2026-09-24T17:15:15Z ok: heartbeat 0 min
2026-09-24T17:30:14Z ok: heartbeat 0 min
2026-09-24T17:45:14Z ok: heartbeat 0 min
2026-09-24T18:00:04Z ok: heartbeat 7 min

## watchdog status
{"ts_utc":"2026-09-24T17:45:10Z","market_open":1,"last_inbox_commit_age_min":153,"status":"stalled"}

## sentinel rows (tail)
{"run": "2026-09-23", "book": "SENTINEL_C2", "days": 21, "llr": -2.14, "t": -3.91, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-23", "book": "SENTINEL_C3", "days": 21, "llr": -2.01, "t": -3.55, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-23", "book": "SENTINEL_C4", "days": 21, "llr": -1.95, "t": -3.56, "thr": -3.19, "verdict": "accruing"}

## book
records by status: {'CLOSED': 659, 'CANCELLED': 75, 'FLUSHED': 129, 'SENT': 6, 'CLOSED_RECONCILED_UNTRACKED_EXIT': 9, 'STALE_CANCELLED_RECONCILED': 46, 'LOGGED': 37, 'SHADOW': 19, None: 47, 'MEASUREMENT_PROBE': 2, 'RETIRED': 57, 'VOID': 1, 'OPEN': 12}
open option records: 11 newest entry: 2026-09-21T17:54:24.299Z

## read next (docs/feature_map)
- persist-and-merge.md, market-gate.md, telegram-and-watchdogs.md
