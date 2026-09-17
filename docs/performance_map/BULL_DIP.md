# BULL_DIP

## What
Calls on a ticker that has dipped below its 20-day average while SPY sits more than 2% above its
50-day average: buying dips in a bull regime. Fires only on BULL days, so it scores rarely.

## Evidence cell
Archive: calls, SPY 50d distance > +2 (prior close), ticker below its 20d (prior close), the exit
the roster runs, executable basis. Live: PROBE records on bull days only.

## Numbers
- live: [[strategies.BULL_DIP.live.n_closed = 0]] closed, [[strategies.BULL_DIP.live.per_trade = n/a]] per trade,
  day mean [[strategies.BULL_DIP.live.unit_mean = n/a]] over [[strategies.BULL_DIP.live.units = 0]] days,
  shared [[strategies.BULL_DIP.live.shared_units = 0]], t vs control [[strategies.BULL_DIP.live.t_vs_control = n/a]].
- archive: [[strategies.BULL_DIP.archive.per_day = +2.5]] per day (pool [[strategies.BULL_DIP.archive.pool_per_day_same_days = -4.9]]),
  t vs pool [[strategies.BULL_DIP.archive.t_vs_pool = +4.28]], [[strategies.BULL_DIP.archive.trades = 5874]] trades over
  [[strategies.BULL_DIP.archive.days = 220]] days, halves [[strategies.BULL_DIP.archive.h1 = +8.1]] / [[strategies.BULL_DIP.archive.h2 = -3.2]].

## Recompute
`./.venv/bin/python scripts/returns_ledger.py` (row BULL_DIP).

## Healthy
Court standing: [[strategies.BULL_DIP.court.standing = 0/8 live virgin days vs control - HOLD]]. Expect long stretches of zero
scoreable days whenever SPY is not in a bull regime.

## Live
Records with `probe_strategy: BULL_DIP`.

## Checks
- The court; the regime gate in the probe loop; `scripts/bull_decay_probe.py` (episodic, not decay).

## Traps
- The archive halves disagree in sign: the first half carried the cell. The 2026-09-10 decay probe
  read it as episodic rather than a trend; either way the second half is the number to watch.
- A bull-only strategy cannot show all-regime skill by construction; it competes for a regime
  seat, not the universal one.
