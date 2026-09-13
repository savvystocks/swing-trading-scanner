# DIP_CONVEXITY

## What
Calls in a BEAR regime (SPY more than 2% below its 50-day), near-the-money, about 50 days to
expiry: buying the bounce with time for it. The strongest honest archive cell in the system,
and the rarest: bear days are a small slice of the calendar.

## Evidence cell
Archive: calls, SPY 50d distance < -2 (prior close), the exit the roster runs (the wide variant
scored higher on the older basis; the ledger snaps to what the spec says), executable basis.
Live: PROBE records on bear days only.

## Numbers
- live: [[strategies.DIP_CONVEXITY.live.n_closed = 0]] closed, [[strategies.DIP_CONVEXITY.live.per_trade = n/a]] per trade,
  day mean [[strategies.DIP_CONVEXITY.live.unit_mean = n/a]] over [[strategies.DIP_CONVEXITY.live.units = 0]] days,
  t vs control [[strategies.DIP_CONVEXITY.live.t_vs_control = n/a]].
- archive: [[strategies.DIP_CONVEXITY.archive.per_day = +8.1]] per day (pool [[strategies.DIP_CONVEXITY.archive.pool_per_day_same_days = +0.1]]),
  t vs pool [[strategies.DIP_CONVEXITY.archive.t_vs_pool = +2.07]], [[strategies.DIP_CONVEXITY.archive.trades = 3581]] trades over
  [[strategies.DIP_CONVEXITY.archive.days = 63]] days, halves [[strategies.DIP_CONVEXITY.archive.h1 = -3.4]] / [[strategies.DIP_CONVEXITY.archive.h2 = +19.1]].

## Recompute
`./.venv/bin/python scripts/returns_ledger.py` (row DIP_CONVEXITY).

## Healthy
Court standing: [[strategies.DIP_CONVEXITY.court.standing = 0/8 live virgin days vs control - HOLD]]. Zero scoreable days is the
normal state outside a bear regime; it has never had a live bear day on current code.

## Live
Records with `probe_strategy: DIP_CONVEXITY`.

## Checks
- The court; the regime gate; drill scenario 3 (bear routing); the tuner's struct keys (`probe.tuning.DIP_CONVEXITY.struct`).

## Traps
- Sixty-odd bear days in two years is a thin cell; the halves disagree (the recent half carries it).
- BEAR has never been traded live on the current code (the drill exists because of that).
- The archive number depends on the exit variant; the ledger states which one it replayed.
