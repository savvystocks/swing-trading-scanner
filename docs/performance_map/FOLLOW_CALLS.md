# FOLLOW_CALLS

## What
Buy aggressively bought calls, all regimes, from the full band (premium 50k-1M), the standard
exit. The archive's first "winner" (2026-08-23, on the old basis) and the one directional probe
with a scoreable court day.

## Evidence cell
Archive: calls only, every regime, BASE exit, executable basis. Live: PROBE records since the roster.

## Numbers
- live: [[strategies.FOLLOW_CALLS.live.n_closed = 22]] closed, [[strategies.FOLLOW_CALLS.live.per_trade = +8.3]] per trade,
  day mean [[strategies.FOLLOW_CALLS.live.unit_mean = -7.3]] over [[strategies.FOLLOW_CALLS.live.units = 11]] days,
  shared with the control [[strategies.FOLLOW_CALLS.live.shared_units = 11]], t vs control [[strategies.FOLLOW_CALLS.live.t_vs_control = -1.08]].
- archive: [[strategies.FOLLOW_CALLS.archive.per_day = -0.1]] per day (pool on the same days
  [[strategies.FOLLOW_CALLS.archive.pool_per_day_same_days = -5.1]]), t vs pool [[strategies.FOLLOW_CALLS.archive.t_vs_pool = +4.99]],
  [[strategies.FOLLOW_CALLS.archive.trades = 51806]] trades over [[strategies.FOLLOW_CALLS.archive.days = 492]] days,
  halves [[strategies.FOLLOW_CALLS.archive.h1 = +2.3]] / [[strategies.FOLLOW_CALLS.archive.h2 = -2.6]].

## Recompute
`./.venv/bin/python scripts/returns_ledger.py` (row FOLLOW_CALLS).

## Healthy
Court standing: [[strategies.FOLLOW_CALLS.court.standing = 7/8 live virgin days vs control - HOLD]]. Promotion needs eight shared
days, trimmed t of 1.8, own mean above +3%/day, both halves positive.

## Live
Records with `probe_strategy: FOLLOW_CALLS`; NBIS (2026-09-11) is one of them, restored after the
push race.

## Checks
- The court; MOT 6.10e roster focus; the tuner's Friday pass on its anchors.

## Traps
- The 2026-08-23 archive verdict (+32/+12/+14 by regime, t > 3) was on the bar-close basis; on the
  executable basis the cell is flat. Quote only the ledger's number.
- Bull-market beta: positive months coincide with a rising tape; the regime split in the
  ledger's archive halves is the honest read.
