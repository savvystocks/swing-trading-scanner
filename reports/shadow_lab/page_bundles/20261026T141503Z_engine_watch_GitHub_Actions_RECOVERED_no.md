# PAGE BUNDLE 20261026T141503Z

reason: engine_watch: GitHub Actions RECOVERED - normal engine cycles resumed; VPS failover standing down. No action needed.
utc: 2026-10-26T14:15:03Z   local(BST/GMT): 2026-10-26T14:15:03

## last-good cycle (origin/main:data/last_cycle_ok)
2026-10-26T14:11:54Z
5504c94fb2dfdd6e23cd497c4235c414ab9d22c7

## last commits on main
c8e0108b 2026-10-26 14:11:55 +0000 sandbox lab data [skip ci]
5504c94f 2026-10-26 14:02:13 +0000 sandbox lab data [skip ci]
deddc620 2026-10-26 14:00:18 +0000 vps failover exit pass [skip ci]
0aece0a7 2026-10-26 14:00:05 +0000 page bundle: watchdog_no_completed_cycle_for_3747m_ [skip ci]
b26077d2 2026-10-25 19:28:48 +0000 wind-down: the weekly XSP credit spread stops opening trades on both books; open reco

## last engine runs (GitHub Actions, v10_lab.yml)
(actions api unavailable)

## engine_watch.log (tail)
2026-10-23T18:00:03Z ok: heartbeat 7 min
2026-10-23T18:15:03Z ok: heartbeat 3 min
2026-10-23T18:30:04Z ok: heartbeat 8 min
2026-10-23T18:45:03Z ok: heartbeat 3 min
2026-10-23T19:00:04Z ok: heartbeat 8 min
2026-10-23T19:15:03Z ok: heartbeat 3 min
2026-10-23T19:30:04Z ok: heartbeat 8 min
2026-10-23T19:45:04Z ok: heartbeat 3 min
2026-10-23T20:00:03Z ok: heartbeat 8 min
2026-10-26T14:00:03Z ALARM: engine heartbeat is 1111 min old during market hours - cycles are NOT completing (GHA timeout / dispatcher down / platform incident). Running VPS FULL FAILOVER cycle now (entries+exits+harvest).
2026-10-26T14:15:03Z ok: heartbeat 3 min
2026-10-26T14:15:03Z ALARM: GitHub Actions RECOVERED - normal engine cycles resumed; VPS failover standing down. No action needed.

## watchdog status
{"ts_utc":"2026-10-26T14:15:03Z","market_open":1,"last_cycle_ok_age_min":3,"status":"ok"}

## sentinel rows (tail)
{"run": "2026-09-25", "book": "SENTINEL_C2", "days": 21, "llr": -2.14, "t": -3.91, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-25", "book": "SENTINEL_C3", "days": 21, "llr": -2.01, "t": -3.55, "thr": -3.19, "verdict": "accruing"}
{"run": "2026-09-25", "book": "SENTINEL_C4", "days": 21, "llr": -1.95, "t": -3.56, "thr": -3.19, "verdict": "accruing"}

## book
records by status: {'CLOSED': 674, 'CANCELLED': 76, 'FLUSHED': 129, 'SENT': 6, 'CLOSED_RECONCILED_UNTRACKED_EXIT': 9, 'STALE_CANCELLED_RECONCILED': 46, 'LOGGED': 37, 'SHADOW': 19, None: 69, 'MEASUREMENT_PROBE': 2, 'RETIRED': 57, 'VOID': 1, 'OPEN': 1}
open option records: 1 newest entry: 2026-10-19T15:01:57.433959+00:00

## read next (docs/feature_map)
- telegram-and-watchdogs.md, then the subsystem the reason names
