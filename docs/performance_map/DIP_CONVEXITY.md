# DIP_CONVEXITY

## What
Calls when SPY is below its 50-day and its 20-day (since 2026-09-15; the BEAR label, more than 2%
below the 50-day, until then), near-the-money, about 50 days to expiry: buying the bounce with time
for it. The strongest honest archive cell in the system,
and the rarest: bear days are a small slice of the calendar.

## Evidence cell
Archive: calls, SPY 50d distance < 0 and SPY 20d distance < 0 (prior close), the engine's wide exit
(-70 / +80 / 0.30, `PROBE_EXITS`; a `probe.tuning` override wins), executable basis.
Live: PROBE records on days whose prior close had SPY below its 50-day and 20-day.

## Numbers
- live: [[strategies.DIP_CONVEXITY.live.n_closed = 2]] closed, [[strategies.DIP_CONVEXITY.live.per_trade = +419.6]] per trade,
  day mean [[strategies.DIP_CONVEXITY.live.unit_mean = +419.6]] over [[strategies.DIP_CONVEXITY.live.units = 2]] days,
  t vs control [[strategies.DIP_CONVEXITY.live.t_vs_control = n/a]].
- archive: [[strategies.DIP_CONVEXITY.archive.per_day = +8.3]] per day (pool [[strategies.DIP_CONVEXITY.archive.pool_per_day_same_days = -4.8]]),
  t vs pool [[strategies.DIP_CONVEXITY.archive.t_vs_pool = +3.83]], [[strategies.DIP_CONVEXITY.archive.trades = 7249]] trades over
  [[strategies.DIP_CONVEXITY.archive.days = 104]] days, halves [[strategies.DIP_CONVEXITY.archive.h1 = +5.7]] / [[strategies.DIP_CONVEXITY.archive.h2 = +10.9]].

## Recompute
`./.venv/bin/python scripts/returns_ledger.py` (row DIP_CONVEXITY).

## Healthy
Court standing: [[strategies.DIP_CONVEXITY.court.standing = 2/8 live virgin days vs control - HOLD]]. Zero scoreable days is the
normal state while SPY holds above its 50-day (1 of the 60 sessions to 2026-09-14); it has never had a
live day on current code.

## Live
Records with `probe_strategy: DIP_CONVEXITY`.

## Checks
- The court; the regime gate (MOT 6.23, drill scenario 8); drill scenario 3 (bear routing); the tuner's struct keys (`probe.tuning.DIP_CONVEXITY.struct`).

## Traps
- Sixty-odd bear days in two years is a thin cell; the halves disagree (the recent half carries it).
- BEAR has never been traded live on the current code (the drill exists because of that).
- The archive number depends on the exit variant; the ledger states which one it replayed.
- 2026-09-15: the cell had omitted the 20d confirmation and run the BASE exit; the numbers above are on
  the live cell and the wide exit from this date.
- The $1,000 slot trades the $4-9.90 band, where this cell's own return is negative in the archive:
  -2.33/day (t 0.36) at SPY-below-50d on the wide exit, +1.88 (t -0.03) at the old BEAR band
  (reports/research/probe_funnel_2026-09-15.md); the edge is above $16 per contract. Expect flat live
  days, not the whole-cell +8.75; the archive tokens above are whole-cell numbers.
