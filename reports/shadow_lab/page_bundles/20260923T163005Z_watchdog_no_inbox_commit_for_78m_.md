# PAGE BUNDLE 20260923T163005Z

reason: watchdog: no inbox commit for 78m
utc: 2026-09-23T16:30:05Z   local(BST/GMT): 2026-09-23T17:30:05

## last-good cycle (origin/main:data/last_cycle_ok)
2026-09-23T16:21:57Z
3eaf8850ad054f7bd6e793b3683a97f0125ef356

## last commits on main
d6282ffe 2026-09-23 16:21:58 +0000 sandbox lab data [skip ci]
3eaf8850 2026-09-23 16:15:08 +0000 page bundle: watchdog_no_inbox_commit_for_63m_ [skip ci]
82e20f4d 2026-09-23 16:12:12 +0000 sandbox lab data [skip ci]
59eba19f 2026-09-23 16:02:14 +0000 sandbox lab data [skip ci]
71bb444e 2026-09-23 16:00:08 +0000 page bundle: watchdog_no_inbox_commit_for_48m_ [skip ci]

## last engine runs (GitHub Actions, v10_lab.yml)
(actions api unavailable)

## engine_watch.log (tail)
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
2026-09-23T16:00:03Z ok: heartbeat 8 min
2026-09-23T16:15:03Z ok: heartbeat 2 min

## watchdog status
{"ts_utc":"2026-09-23T16:15:11Z","market_open":1,"last_inbox_commit_age_min":63,"status":"stalled"}

## sentinel rows (tail)
{"run": "2026-09-22", "book": "SENTINEL_C2", "days": 21, "llr": -2.14, "t": -3.91, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-22", "book": "SENTINEL_C3", "days": 21, "llr": -2.01, "t": -3.55, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-22", "book": "SENTINEL_C4", "days": 21, "llr": -1.95, "t": -3.56, "thr": -3.19, "verdict": "accruing"}

## book
records by status: {'CLOSED': 654, 'CANCELLED': 75, 'FLUSHED': 129, 'SENT': 6, 'CLOSED_RECONCILED_UNTRACKED_EXIT': 9, 'STALE_CANCELLED_RECONCILED': 46, 'LOGGED': 37, 'SHADOW': 19, None: 46, 'MEASUREMENT_PROBE': 2, 'RETIRED': 57, 'VOID': 1, 'OPEN': 17}
open option records: 16 newest entry: 2026-09-21T17:54:24.299Z

## read next (docs/feature_map)
- persist-and-merge.md, market-gate.md, telegram-and-watchdogs.md
