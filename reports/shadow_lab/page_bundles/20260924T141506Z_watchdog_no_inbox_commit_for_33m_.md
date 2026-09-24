# PAGE BUNDLE 20260924T141506Z

reason: watchdog: no inbox commit for 33m
utc: 2026-09-24T14:15:06Z   local(BST/GMT): 2026-09-24T15:15:06

## last-good cycle (origin/main:data/last_cycle_ok)
2026-09-24T14:11:47Z
8b3e091baf1c3e13b8a63b79b7aa1c0ec8dd3b6e

## last commits on main
57928c92 2026-09-24 14:11:48 +0000 sandbox lab data [skip ci]
8b3e091b 2026-09-24 14:02:14 +0000 sandbox lab data [skip ci]
cc3d42ad 2026-09-24 13:51:48 +0000 sandbox lab data [skip ci]
d72601c3 2026-09-24 13:41:50 +0000 sandbox lab data [skip ci]
1ae8282e 2026-09-24 13:31:54 +0000 sandbox lab data [skip ci]

## last engine runs (GitHub Actions, v10_lab.yml)
(actions api unavailable)

## engine_watch.log (tail)
2026-09-23T17:45:03Z ok: heartbeat 3 min
2026-09-23T18:00:04Z ok: heartbeat 8 min
2026-09-23T18:15:15Z ok: heartbeat 3 min
2026-09-23T18:30:03Z ok: heartbeat 8 min
2026-09-23T18:45:03Z ok: heartbeat 3 min
2026-09-23T19:00:16Z ok: heartbeat 0 min
2026-09-23T19:15:15Z ok: heartbeat 0 min
2026-09-23T19:30:03Z ok: heartbeat 8 min
2026-09-23T19:45:15Z ok: heartbeat 0 min
2026-09-23T20:00:04Z ok: heartbeat 8 min
2026-09-24T14:00:03Z ok: heartbeat 8 min
2026-09-24T14:15:03Z ok: heartbeat 3 min

## watchdog status
{"ts_utc":"2026-09-24T14:00:05Z","market_open":1,"last_inbox_commit_age_min":18,"status":"ok"}

## sentinel rows (tail)
{"run": "2026-09-23", "book": "SENTINEL_C2", "days": 21, "llr": -2.14, "t": -3.91, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-23", "book": "SENTINEL_C3", "days": 21, "llr": -2.01, "t": -3.55, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-23", "book": "SENTINEL_C4", "days": 21, "llr": -1.95, "t": -3.56, "thr": -3.19, "verdict": "accruing"}

## book
records by status: {'CLOSED': 658, 'CANCELLED': 75, 'FLUSHED': 129, 'SENT': 6, 'CLOSED_RECONCILED_UNTRACKED_EXIT': 9, 'STALE_CANCELLED_RECONCILED': 46, 'LOGGED': 37, 'SHADOW': 19, None: 47, 'MEASUREMENT_PROBE': 2, 'RETIRED': 57, 'VOID': 1, 'OPEN': 13}
open option records: 12 newest entry: 2026-09-21T17:54:24.299Z

## read next (docs/feature_map)
- persist-and-merge.md, market-gate.md, telegram-and-watchdogs.md
