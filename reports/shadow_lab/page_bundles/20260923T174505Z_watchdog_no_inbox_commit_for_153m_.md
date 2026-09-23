# PAGE BUNDLE 20260923T174505Z

reason: watchdog: no inbox commit for 153m
utc: 2026-09-23T17:45:05Z   local(BST/GMT): 2026-09-23T18:45:05

## last-good cycle (origin/main:data/last_cycle_ok)
2026-09-23T17:41:42Z
1380233b851a8ebed72ea7d4dfeee623434e9bc2

## last commits on main
58d085aa 2026-09-23 17:41:43 +0000 sandbox lab data [skip ci]
1380233b 2026-09-23 17:32:00 +0000 sandbox lab data [skip ci]
8bfdf454 2026-09-23 17:30:09 +0000 page bundle: watchdog_no_inbox_commit_for_138m_ [skip ci]
2efda0e9 2026-09-23 17:21:34 +0000 sandbox lab data [skip ci]
d8577b65 2026-09-23 17:15:08 +0000 page bundle: watchdog_no_inbox_commit_for_123m_ [skip ci]

## last engine runs (GitHub Actions, v10_lab.yml)
(actions api unavailable)

## engine_watch.log (tail)
2026-09-23T15:00:03Z ok: heartbeat 7 min
2026-09-23T15:15:05Z ok: heartbeat 3 min
2026-09-23T15:30:03Z ok: heartbeat 8 min
2026-09-23T15:45:04Z ok: heartbeat 3 min
2026-09-23T16:00:03Z ok: heartbeat 8 min
2026-09-23T16:15:03Z ok: heartbeat 2 min
2026-09-23T16:30:15Z ok: heartbeat 0 min
2026-09-23T16:45:15Z ok: heartbeat 0 min
2026-09-23T17:00:03Z ok: heartbeat 8 min
2026-09-23T17:15:15Z ok: heartbeat 0 min
2026-09-23T17:30:03Z ok: heartbeat 8 min
2026-09-23T17:45:03Z ok: heartbeat 3 min

## watchdog status
{"ts_utc":"2026-09-23T17:30:12Z","market_open":1,"last_inbox_commit_age_min":138,"status":"stalled"}

## sentinel rows (tail)
{"run": "2026-09-22", "book": "SENTINEL_C2", "days": 21, "llr": -2.14, "t": -3.91, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-22", "book": "SENTINEL_C3", "days": 21, "llr": -2.01, "t": -3.55, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-22", "book": "SENTINEL_C4", "days": 21, "llr": -1.95, "t": -3.56, "thr": -3.19, "verdict": "accruing"}

## book
records by status: {'CLOSED': 654, 'CANCELLED': 75, 'FLUSHED': 129, 'SENT': 6, 'CLOSED_RECONCILED_UNTRACKED_EXIT': 9, 'STALE_CANCELLED_RECONCILED': 46, 'LOGGED': 37, 'SHADOW': 19, None: 46, 'MEASUREMENT_PROBE': 2, 'RETIRED': 57, 'VOID': 1, 'OPEN': 17}
open option records: 16 newest entry: 2026-09-21T17:54:24.299Z

## read next (docs/feature_map)
- persist-and-merge.md, market-gate.md, telegram-and-watchdogs.md
