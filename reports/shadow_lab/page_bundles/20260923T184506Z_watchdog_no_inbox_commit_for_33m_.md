# PAGE BUNDLE 20260923T184506Z

reason: watchdog: no inbox commit for 33m
utc: 2026-09-23T18:45:06Z   local(BST/GMT): 2026-09-23T19:45:06

## last-good cycle (origin/main:data/last_cycle_ok)
2026-09-23T18:41:51Z
169a971e9016239ce5a45e60b77521edc4646696

## last commits on main
59400e51 2026-09-23 18:41:51 +0000 sandbox lab data [skip ci]
169a971e 2026-09-23 18:31:44 +0000 sandbox lab data [skip ci]
f285b047 2026-09-23 18:21:54 +0000 sandbox lab data [skip ci]
d35c4642 2026-09-23 18:11:50 +0000 sandbox lab data [skip ci]
cb15571b 2026-09-23 18:02:10 +0000 sandbox lab data [skip ci]

## last engine runs (GitHub Actions, v10_lab.yml)
(actions api unavailable)

## engine_watch.log (tail)
2026-09-23T16:00:03Z ok: heartbeat 8 min
2026-09-23T16:15:03Z ok: heartbeat 2 min
2026-09-23T16:30:15Z ok: heartbeat 0 min
2026-09-23T16:45:15Z ok: heartbeat 0 min
2026-09-23T17:00:03Z ok: heartbeat 8 min
2026-09-23T17:15:15Z ok: heartbeat 0 min
2026-09-23T17:30:03Z ok: heartbeat 8 min
2026-09-23T17:45:03Z ok: heartbeat 3 min
2026-09-23T18:00:04Z ok: heartbeat 8 min
2026-09-23T18:15:15Z ok: heartbeat 3 min
2026-09-23T18:30:03Z ok: heartbeat 8 min
2026-09-23T18:45:03Z ok: heartbeat 3 min

## watchdog status
{"ts_utc":"2026-09-23T18:30:05Z","market_open":1,"last_inbox_commit_age_min":18,"status":"ok"}

## sentinel rows (tail)
{"run": "2026-09-22", "book": "SENTINEL_C2", "days": 21, "llr": -2.14, "t": -3.91, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-22", "book": "SENTINEL_C3", "days": 21, "llr": -2.01, "t": -3.55, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-22", "book": "SENTINEL_C4", "days": 21, "llr": -1.95, "t": -3.56, "thr": -3.19, "verdict": "accruing"}

## book
records by status: {'CLOSED': 655, 'CANCELLED': 75, 'FLUSHED': 129, 'SENT': 6, 'CLOSED_RECONCILED_UNTRACKED_EXIT': 9, 'STALE_CANCELLED_RECONCILED': 46, 'LOGGED': 37, 'SHADOW': 19, None: 46, 'MEASUREMENT_PROBE': 2, 'RETIRED': 57, 'VOID': 1, 'OPEN': 16}
open option records: 15 newest entry: 2026-09-21T17:54:24.299Z

## read next (docs/feature_map)
- persist-and-merge.md, market-gate.md, telegram-and-watchdogs.md
