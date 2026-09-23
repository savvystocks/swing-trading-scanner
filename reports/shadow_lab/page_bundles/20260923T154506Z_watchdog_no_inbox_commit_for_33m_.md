# PAGE BUNDLE 20260923T154506Z

reason: watchdog: no inbox commit for 33m
utc: 2026-09-23T15:45:06Z   local(BST/GMT): 2026-09-23T16:45:06

## last-good cycle (origin/main:data/last_cycle_ok)
2026-09-23T15:41:38Z
2553599d42848d75cc5eb4f508eb05f38254ce3f

## last commits on main
1147b446 2026-09-23 15:41:39 +0000 sandbox lab data [skip ci]
2553599d 2026-09-23 15:32:02 +0000 sandbox lab data [skip ci]
fb51cf5b 2026-09-23 15:21:38 +0000 sandbox lab data [skip ci]
b645b442 2026-09-23 15:11:56 +0000 sandbox lab data [skip ci]
706f1441 2026-09-23 15:05:07 +0000 xsp quote log [skip ci]

## last engine runs (GitHub Actions, v10_lab.yml)
(actions api unavailable)

## engine_watch.log (tail)
2026-09-22T19:15:03Z ok: heartbeat 9 min
2026-09-22T19:30:02Z ok: heartbeat 5 min
2026-09-22T19:45:15Z ok: heartbeat 9 min
2026-09-22T20:00:15Z ok: heartbeat 2 min
2026-09-23T14:00:03Z ok: heartbeat 8 min
2026-09-23T14:15:15Z ok: heartbeat 0 min
2026-09-23T14:30:03Z ok: heartbeat 8 min
2026-09-23T14:45:04Z ok: heartbeat 3 min
2026-09-23T15:00:03Z ok: heartbeat 7 min
2026-09-23T15:15:05Z ok: heartbeat 3 min
2026-09-23T15:30:03Z ok: heartbeat 8 min
2026-09-23T15:45:04Z ok: heartbeat 3 min

## watchdog status
{"ts_utc":"2026-09-23T15:30:05Z","market_open":1,"last_inbox_commit_age_min":18,"status":"ok"}

## sentinel rows (tail)
{"run": "2026-09-22", "book": "SENTINEL_C2", "days": 21, "llr": -2.14, "t": -3.91, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-22", "book": "SENTINEL_C3", "days": 21, "llr": -2.01, "t": -3.55, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-22", "book": "SENTINEL_C4", "days": 21, "llr": -1.95, "t": -3.56, "thr": -3.19, "verdict": "accruing"}

## book
records by status: {'CLOSED': 654, 'CANCELLED': 75, 'FLUSHED': 129, 'SENT': 6, 'CLOSED_RECONCILED_UNTRACKED_EXIT': 9, 'STALE_CANCELLED_RECONCILED': 46, 'LOGGED': 37, 'SHADOW': 19, None: 46, 'MEASUREMENT_PROBE': 2, 'RETIRED': 57, 'VOID': 1, 'OPEN': 17}
open option records: 16 newest entry: 2026-09-21T17:54:24.299Z

## read next (docs/feature_map)
- persist-and-merge.md, market-gate.md, telegram-and-watchdogs.md
