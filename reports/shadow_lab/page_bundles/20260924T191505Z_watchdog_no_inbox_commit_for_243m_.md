# PAGE BUNDLE 20260924T191505Z

reason: watchdog: no inbox commit for 243m
utc: 2026-09-24T19:15:05Z   local(BST/GMT): 2026-09-24T20:15:05

## last-good cycle (origin/main:data/last_cycle_ok)
2026-09-24T19:11:55Z
7545902bd798759358b9b2018f2758ce8db601a9

## last commits on main
c41af8bf 2026-09-24 19:11:55 +0000 sandbox lab data [skip ci]
7545902b 2026-09-24 19:02:01 +0000 sandbox lab data [skip ci]
57074a81 2026-09-24 19:00:09 +0000 page bundle: watchdog_no_inbox_commit_for_228m_ [skip ci]
fd2bfa47 2026-09-24 18:51:47 +0000 sandbox lab data [skip ci]
a8eb2d2c 2026-09-24 18:45:07 +0000 page bundle: watchdog_no_inbox_commit_for_213m_ [skip ci]

## last engine runs (GitHub Actions, v10_lab.yml)
(actions api unavailable)

## engine_watch.log (tail)
2026-09-24T16:15:03Z ok: heartbeat 3 min
2026-09-24T16:30:14Z ok: heartbeat 0 min
2026-09-24T16:45:15Z ok: heartbeat 0 min
2026-09-24T17:00:15Z ok: heartbeat 0 min
2026-09-24T17:15:15Z ok: heartbeat 0 min
2026-09-24T17:30:14Z ok: heartbeat 0 min
2026-09-24T17:45:14Z ok: heartbeat 0 min
2026-09-24T18:00:04Z ok: heartbeat 7 min
2026-09-24T18:15:15Z ok: heartbeat 0 min
2026-09-24T18:30:14Z ok: heartbeat 0 min
2026-09-24T18:45:14Z ok: heartbeat 0 min
2026-09-24T19:00:16Z ok: heartbeat 8 min

## watchdog status
{"ts_utc":"2026-09-24T19:00:18Z","market_open":1,"last_inbox_commit_age_min":228,"status":"stalled"}

## sentinel rows (tail)
{"run": "2026-09-23", "book": "SENTINEL_C2", "days": 21, "llr": -2.14, "t": -3.91, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-23", "book": "SENTINEL_C3", "days": 21, "llr": -2.01, "t": -3.55, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-23", "book": "SENTINEL_C4", "days": 21, "llr": -1.95, "t": -3.56, "thr": -3.19, "verdict": "accruing"}

## book
records by status: {'CLOSED': 659, 'CANCELLED': 75, 'FLUSHED': 129, 'SENT': 6, 'CLOSED_RECONCILED_UNTRACKED_EXIT': 9, 'STALE_CANCELLED_RECONCILED': 46, 'LOGGED': 37, 'SHADOW': 19, None: 47, 'MEASUREMENT_PROBE': 2, 'RETIRED': 57, 'VOID': 1, 'OPEN': 12}
open option records: 11 newest entry: 2026-09-21T17:54:24.299Z

## read next (docs/feature_map)
- persist-and-merge.md, market-gate.md, telegram-and-watchdogs.md
