# PAGE BUNDLE 20260924T194506Z

reason: watchdog: no inbox commit for 273m
utc: 2026-09-24T19:45:06Z   local(BST/GMT): 2026-09-24T20:45:06

## last-good cycle (origin/main:data/last_cycle_ok)
2026-09-24T19:41:59Z
33400c472482b6ed196af3ee60aeb20c57877dbb

## last commits on main
d468fb5c 2026-09-24 19:42:01 +0000 sandbox lab data [skip ci]
33400c47 2026-09-24 19:31:44 +0000 sandbox lab data [skip ci]
43ef1f0c 2026-09-24 19:30:07 +0000 page bundle: watchdog_no_inbox_commit_for_258m_ [skip ci]
a167ec17 2026-09-24 19:21:45 +0000 sandbox lab data [skip ci]
a06ca840 2026-09-24 19:15:08 +0000 page bundle: watchdog_no_inbox_commit_for_243m_ [skip ci]

## last engine runs (GitHub Actions, v10_lab.yml)
(actions api unavailable)

## engine_watch.log (tail)
2026-09-24T17:00:15Z ok: heartbeat 0 min
2026-09-24T17:15:15Z ok: heartbeat 0 min
2026-09-24T17:30:14Z ok: heartbeat 0 min
2026-09-24T17:45:14Z ok: heartbeat 0 min
2026-09-24T18:00:04Z ok: heartbeat 7 min
2026-09-24T18:15:15Z ok: heartbeat 0 min
2026-09-24T18:30:14Z ok: heartbeat 0 min
2026-09-24T18:45:14Z ok: heartbeat 0 min
2026-09-24T19:00:16Z ok: heartbeat 8 min
2026-09-24T19:15:15Z ok: heartbeat 0 min
2026-09-24T19:30:02Z ok: heartbeat 8 min
2026-09-24T19:45:04Z ok: heartbeat 3 min

## watchdog status
{"ts_utc":"2026-09-24T19:30:10Z","market_open":1,"last_inbox_commit_age_min":258,"status":"stalled"}

## sentinel rows (tail)
{"run": "2026-09-23", "book": "SENTINEL_C2", "days": 21, "llr": -2.14, "t": -3.91, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-23", "book": "SENTINEL_C3", "days": 21, "llr": -2.01, "t": -3.55, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-23", "book": "SENTINEL_C4", "days": 21, "llr": -1.95, "t": -3.56, "thr": -3.19, "verdict": "accruing"}

## book
records by status: {'CLOSED': 659, 'CANCELLED': 75, 'FLUSHED': 129, 'SENT': 6, 'CLOSED_RECONCILED_UNTRACKED_EXIT': 9, 'STALE_CANCELLED_RECONCILED': 46, 'LOGGED': 37, 'SHADOW': 19, None: 47, 'MEASUREMENT_PROBE': 2, 'RETIRED': 57, 'VOID': 1, 'OPEN': 12}
open option records: 11 newest entry: 2026-09-21T17:54:24.299Z

## read next (docs/feature_map)
- persist-and-merge.md, market-gate.md, telegram-and-watchdogs.md
