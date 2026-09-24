# PAGE BUNDLE 20260924T143007Z

reason: watchdog: no inbox commit for 48m
utc: 2026-09-24T14:30:07Z   local(BST/GMT): 2026-09-24T15:30:07

## last-good cycle (origin/main:data/last_cycle_ok)
2026-09-24T14:21:45Z
d545a58a3fb41eec1cf800f074a95600111f9f1a

## last commits on main
3731532f 2026-09-24 14:21:46 +0000 sandbox lab data [skip ci]
d545a58a 2026-09-24 14:15:09 +0000 page bundle: watchdog_no_inbox_commit_for_33m_ [skip ci]
57928c92 2026-09-24 14:11:48 +0000 sandbox lab data [skip ci]
8b3e091b 2026-09-24 14:02:14 +0000 sandbox lab data [skip ci]
cc3d42ad 2026-09-24 13:51:48 +0000 sandbox lab data [skip ci]

## last engine runs (GitHub Actions, v10_lab.yml)
(actions api unavailable)

## engine_watch.log (tail)
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
2026-09-24T14:30:13Z ok: heartbeat 8 min

## watchdog status
{"ts_utc":"2026-09-24T14:15:13Z","market_open":1,"last_inbox_commit_age_min":33,"status":"stalled"}

## sentinel rows (tail)
{"run": "2026-09-23", "book": "SENTINEL_C2", "days": 21, "llr": -2.14, "t": -3.91, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-23", "book": "SENTINEL_C3", "days": 21, "llr": -2.01, "t": -3.55, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-23", "book": "SENTINEL_C4", "days": 21, "llr": -1.95, "t": -3.56, "thr": -3.19, "verdict": "accruing"}

## book
records by status: {'CLOSED': 658, 'CANCELLED': 75, 'FLUSHED': 129, 'SENT': 6, 'CLOSED_RECONCILED_UNTRACKED_EXIT': 9, 'STALE_CANCELLED_RECONCILED': 46, 'LOGGED': 37, 'SHADOW': 19, None: 47, 'MEASUREMENT_PROBE': 2, 'RETIRED': 57, 'VOID': 1, 'OPEN': 13}
open option records: 12 newest entry: 2026-09-21T17:54:24.299Z

## read next (docs/feature_map)
- persist-and-merge.md, market-gate.md, telegram-and-watchdogs.md
