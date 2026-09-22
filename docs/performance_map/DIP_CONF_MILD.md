# DIP_CONF_MILD

## What
In a MILD regime (SPY within 2% of its 50-day), a ticker dip confirmed by SPY itself sitting
below its 20-day: buy THE trigger contract from the pricey pool ($4-9 calls). The confirmation is
the strategy; without the SPY gate the same trade loses.

## Evidence cell
Archive: calls, SPY 50d within +-2, ticker below 20d, SPY below 20d, all prior-close, the exit the
roster runs, executable basis. Live: the trigger contract via `_PROBE_CONTRACT`, mild days only.

## Numbers
- live: [[strategies.DIP_CONF_MILD.live.n_closed = 3]] closed, [[strategies.DIP_CONF_MILD.live.per_trade = +47.4]] per trade,
  day mean [[strategies.DIP_CONF_MILD.live.unit_mean = +47.4]] over [[strategies.DIP_CONF_MILD.live.units = 3]] days,
  t vs control [[strategies.DIP_CONF_MILD.live.t_vs_control = +0.92]].
- archive: [[strategies.DIP_CONF_MILD.archive.per_day = +0.5]] per day (pool [[strategies.DIP_CONF_MILD.archive.pool_per_day_same_days = -7.4]]),
  t vs pool [[strategies.DIP_CONF_MILD.archive.t_vs_pool = +2.69]], [[strategies.DIP_CONF_MILD.archive.trades = 4220]] trades over
  [[strategies.DIP_CONF_MILD.archive.days = 86]] days, halves [[strategies.DIP_CONF_MILD.archive.h1 = +3.8]] / [[strategies.DIP_CONF_MILD.archive.h2 = -2.8]].

## Recompute
`./.venv/bin/python scripts/returns_ledger.py` (row DIP_CONF_MILD).

## Healthy
Court standing: [[strategies.DIP_CONF_MILD.court.standing = 1/8 live virgin days vs control - HOLD]]. Mild days are a minority of the
calendar; expect weeks with nothing to score.

## Live
Records with `probe_strategy: DIP_CONF_MILD` (SLV, 2026-09-11, was one).

## Checks
- The court; drill scenario 2 (the trigger-contract path); the pricey pool filters in the feature map.

## Traps
- The +11.3%/day, t 2.43 cell of the 2026-08-31 grand retest was on the bar-close basis; the
  executable cell is a fraction of that. The instrument-identity rule (buy the measured contract)
  came out of this strategy's near-miss on 2026-09-01.
- The pricey pool is $4-9 calls with a 7-day DTE floor; the archive cell had no such floor.
