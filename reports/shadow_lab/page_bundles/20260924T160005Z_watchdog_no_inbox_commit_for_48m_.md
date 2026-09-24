# PAGE BUNDLE 20260924T160005Z

reason: watchdog: no inbox commit for 48m
utc: 2026-09-24T16:00:05Z   local(BST/GMT): 2026-09-24T17:00:05

## last-good cycle (origin/main:data/last_cycle_ok)
2026-09-24T15:51:41Z
a81e7fc7c7aa6ada224a74355202677a67f44f7a

## last commits on main
3a0049a7 2026-09-24 15:51:42 +0000 sandbox lab data [skip ci]
a81e7fc7 2026-09-24 15:45:08 +0000 page bundle: watchdog_no_inbox_commit_for_33m_ [skip ci]
e8cb5f3c 2026-09-24 15:41:52 +0000 sandbox lab data [skip ci]
7dddfbf8 2026-09-24 15:31:56 +0000 sandbox lab data [skip ci]
de218c6f 2026-09-24 15:22:03 +0000 sandbox lab data [skip ci]

## last engine runs (GitHub Actions, v10_lab.yml)
(actions api unavailable)

## engine_watch.log (tail)
2026-09-23T19:30:03Z ok: heartbeat 8 min
2026-09-23T19:45:15Z ok: heartbeat 0 min
2026-09-23T20:00:04Z ok: heartbeat 8 min
2026-09-24T14:00:03Z ok: heartbeat 8 min
2026-09-24T14:15:03Z ok: heartbeat 3 min
2026-09-24T14:30:13Z ok: heartbeat 8 min
2026-09-24T14:45:06Z ok: heartbeat 3 min
2026-09-24T15:00:04Z ok: heartbeat 8 min
2026-09-24T15:15:17Z ok: heartbeat 3 min
2026-09-24T15:30:02Z ok: heartbeat 7 min
2026-09-24T15:45:14Z ok: heartbeat 0 min
2026-09-24T16:00:02Z ok: heartbeat 8 min

## watchdog status
{"ts_utc":"2026-09-24T15:45:12Z","market_open":1,"last_inbox_commit_age_min":33,"status":"stalled"}

## sentinel rows (tail)
{"run": "2026-09-23", "book": "SENTINEL_C2", "days": 21, "llr": -2.14, "t": -3.91, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-23", "book": "SENTINEL_C3", "days": 21, "llr": -2.01, "t": -3.55, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-23", "book": "SENTINEL_C4", "days": 21, "llr": -1.95, "t": -3.56, "thr": -3.19, "verdict": "accruing"}

## book
records by status: {'CLOSED': 659, 'CANCELLED': 75, 'FLUSHED': 129, 'SENT': 6, 'CLOSED_RECONCILED_UNTRACKED_EXIT': 9, 'STALE_CANCELLED_RECONCILED': 46, 'LOGGED': 37, 'SHADOW': 19, None: 47, 'MEASUREMENT_PROBE': 2, 'RETIRED': 57, 'VOID': 1, 'OPEN': 12}
open option records: 11 newest entry: 2026-09-21T17:54:24.299Z

## read next (docs/feature_map)
- persist-and-merge.md, market-gate.md, telegram-and-watchdogs.md
